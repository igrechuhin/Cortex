"""MCP connection stability and resource management.

This module provides connection stability features for MCP tool handlers:
- Timeout protection for long-running operations
- Resource limit enforcement (concurrent operations)
- Connection error handling and recovery
- Connection health monitoring
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from inspect import Signature
from pathlib import Path
from types import TracebackType
from typing import Literal, Protocol, cast

import anyio

from cortex.core.constants import (
    MCP_CONNECTION_RETRY_ATTEMPTS,
    MCP_CONNECTION_RETRY_DELAY_SECONDS,
    MCP_MAX_CONCURRENT_TOOLS,
    MCP_TOOL_TIMEOUT_SECONDS,
)
from cortex.core.mcp_failure_handler import MCPToolFailureHandler
from cortex.core.models import ConnectionHealth, JsonValue, MCPToolArguments
from cortex.core.usage_context import get_current_managers, set_current_managers

logger = logging.getLogger(__name__)


def _project_root_from_tool_args(
    args: tuple[JsonValue, ...], kwargs: dict[str, JsonValue]
) -> Path:
    """Resolve project root from tool (args, kwargs) for usage context."""
    from cortex.managers.initialization import get_project_root

    raw = kwargs.get("project_root") if kwargs else None
    if raw is None and args:
        raw = args[0]
    if isinstance(raw, str):
        return get_project_root(raw)
    return get_project_root(None)


def ensure_usage_context[T](
    func: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """Decorator that sets usage context (for recording) when not already set.

    Wraps an async MCP tool handler so that get_current_managers() is set
    before the handler runs, enabling usage recording for tools that do not
    call get_managers() themselves.
    """
    import functools
    import inspect

    @functools.wraps(func)
    async def wrapper(
        *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
        **kwargs: JsonValue,  # pyright: ignore[reportUnknownParameterType]
    ) -> T:
        if get_current_managers() is None:
            from cortex.managers.initialization import get_managers

            root = _project_root_from_tool_args(args, kwargs)
            mgrs = await get_managers(root)
            mgrs_dict = mgrs if isinstance(mgrs, dict) else mgrs.model_dump()
            set_current_managers(mgrs_dict)
        return await func(*args, **kwargs)

    original_sig = inspect.signature(func)
    cast(_SignatureAware, wrapper).__signature__ = original_sig
    return wrapper


class _SignatureAware(Protocol):
    __signature__: Signature


class TrackedSemaphore:
    """Semaphore wrapper that tracks available count without accessing
    private attributes."""

    def __init__(self, value: int) -> None:
        """Initialize semaphore with initial value.

        Args:
            value: Initial semaphore value
        """
        self._semaphore = asyncio.Semaphore(value)
        self._max_value = value
        self._current_count = value

    async def acquire(self) -> None:
        """Acquire semaphore, decrementing available count."""
        _ = await self._semaphore.acquire()
        self._current_count -= 1

    def release(self) -> None:
        """Release semaphore, incrementing available count."""
        self._semaphore.release()
        self._current_count += 1

    async def __aenter__(self) -> "TrackedSemaphore":
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        self.release()

    @property
    def available(self) -> int:
        """Get available semaphore slots."""
        return max(0, self._current_count)

    @property
    def current(self) -> int:
        """Get current concurrent operations."""
        return self._max_value - self.available


# Global semaphore for limiting concurrent tool executions
_concurrent_tools_semaphore: TrackedSemaphore | None = None

# Connection state for diagnostics (Phase 32)
_connection_closure_count: int = 0
_connection_recovery_count: int = 0


def _get_semaphore() -> TrackedSemaphore:
    """Get or create the global semaphore for concurrent tool limits."""
    global _concurrent_tools_semaphore
    if _concurrent_tools_semaphore is None:
        _concurrent_tools_semaphore = TrackedSemaphore(MCP_MAX_CONCURRENT_TOOLS)
    return _concurrent_tools_semaphore


async def _handle_timeout_error(
    func_name: str, timeout: float, attempt: int, e: asyncio.TimeoutError
) -> tuple[TimeoutError | None, Exception | None]:
    """Handle timeout error during retry.

    Args:
        func_name: Name of the function that timed out
        timeout: Timeout value in seconds
        attempt: Current attempt number
        e: The timeout exception

    Returns:
        Tuple of (error to raise if final attempt, exception to store)
    """
    logger.warning(
        f"MCP tool {func_name} timed out after {timeout}s "
        + f"(attempt {attempt}/{MCP_CONNECTION_RETRY_ATTEMPTS})"
    )
    if attempt == MCP_CONNECTION_RETRY_ATTEMPTS:
        error = TimeoutError(f"MCP tool {func_name} exceeded timeout of {timeout}s")
        error.__cause__ = e
        return error, None
    return None, e


def _record_connection_closure() -> None:
    """Record connection closure for diagnostics (Phase 32)."""
    global _connection_closure_count
    _connection_closure_count += 1


def _record_connection_recovery() -> None:
    """Record connection recovery for diagnostics (Phase 32)."""
    global _connection_recovery_count
    _connection_recovery_count += 1


async def _handle_connection_error(
    func_name: str, attempt: int, e: Exception
) -> tuple[ConnectionError | RuntimeError | None, Exception | None]:
    """Handle connection error during retry.

    Args:
        func_name: Name of the function that failed
        attempt: Current attempt number
        e: The connection exception

    Returns:
        Tuple of (error to raise if final attempt, exception to store)
    """
    _record_connection_closure()
    logger.warning(
        f"MCP connection error in {func_name} "
        + f"(attempt {attempt}/{MCP_CONNECTION_RETRY_ATTEMPTS}): {e}"
    )
    if attempt == MCP_CONNECTION_RETRY_ATTEMPTS:
        error: RuntimeError | ConnectionError = (
            ConnectionError(
                f"MCP tool {func_name} failed after {attempt} attempts (connection)"
            )
            if _is_connection_error(e)
            else RuntimeError(
                f"MCP connection failed for {func_name} after {attempt} attempts"
            )
        )
        error.__cause__ = e
        return error, None
    await asyncio.sleep(MCP_CONNECTION_RETRY_DELAY_SECONDS * attempt)
    return None, e


async def _execute_single_attempt[T](
    func: Callable[..., Awaitable[T]],
    semaphore: TrackedSemaphore,
    timeout: float,
    args: tuple[JsonValue, ...],
    kwargs: MCPToolArguments,
) -> T:
    """Execute function once with timeout and resource limits."""
    async with semaphore:
        async with asyncio.timeout(timeout):
            return await func(*args, **kwargs.model_dump(exclude_none=True))


def _is_connection_error(e: Exception) -> bool:
    """Check if exception is connection-related.

    Args:
        e: Exception to check

    Returns:
        True if exception is connection-related
    """
    connection_error_types = (
        ConnectionError,
        BrokenPipeError,
        OSError,
        RuntimeError,  # FastMCP may raise RuntimeError for connection issues
        anyio.BrokenResourceError,  # anyio resource errors (e.g., stdio closed)
        anyio.ClosedResourceError,  # send on closed stream after client disconnect
    )

    if isinstance(e, connection_error_types):
        return True

    error_message = str(e).lower()
    connection_keywords = [
        "connection",
        "broken pipe",
        "connection reset",
        "tool not found",
        "resource",
        "stdio",
    ]

    return any(keyword in error_message for keyword in connection_keywords)


async def _retry_path_health_and_recovery(
    func_name: str, attempt: int, last_exception: Exception | None
) -> None:
    """Check connection health before retry and record recovery (Phase 32)."""
    health = await check_connection_health()
    if not health.healthy:
        raise ConnectionError(
            f"Connection not healthy before retry {attempt} for {func_name}"
        ) from last_exception
    if last_exception and _is_connection_error(last_exception):
        _record_connection_recovery()


def _raise_final_error(func_name: str, last_exception: Exception | None) -> None:
    """Raise ConnectionError or RuntimeError after retries exhausted."""
    if last_exception and _is_connection_error(last_exception):
        raise ConnectionError(
            f"MCP tool {func_name} failed after "
            + f"{MCP_CONNECTION_RETRY_ATTEMPTS} attempts (connection)"
        ) from last_exception
    raise RuntimeError(
        f"MCP tool {func_name} failed after "
        + f"{MCP_CONNECTION_RETRY_ATTEMPTS} attempts"
    ) from last_exception


async def _handle_retry_exception(
    func_name: str,
    timeout: float,
    attempt: int,
    e: Exception,
    last_exception: Exception | None,
) -> tuple[bool, Exception | None]:
    """Handle exception during retry attempt.

    Returns:
        Tuple of (should_raise, new_last_exception)
    """
    if isinstance(e, asyncio.TimeoutError):
        error, stored_exception = await _handle_timeout_error(
            func_name, timeout, attempt, e
        )
        if error:
            raise error
        return False, stored_exception

    if _is_connection_error(e):
        error, stored_exception = await _handle_connection_error(func_name, attempt, e)
        if error:
            raise error
        return False, stored_exception

    logger.error(f"MCP tool {func_name} failed: {e}")
    raise


async def _execute_with_retry[T](
    func: Callable[..., Awaitable[T]],
    semaphore: TrackedSemaphore,
    timeout: float,
    args: tuple[JsonValue, ...],
    kwargs: MCPToolArguments,
) -> T:
    """Execute function with retry logic for transient failures."""
    last_exception: Exception | None = None
    func_name = func.__name__

    for attempt in range(1, MCP_CONNECTION_RETRY_ATTEMPTS + 1):
        try:
            return await _execute_single_attempt(func, semaphore, timeout, args, kwargs)
        except Exception as e:
            _, last_exception = await _handle_retry_exception(
                func_name, timeout, attempt, e, last_exception
            )
        await _retry_path_health_and_recovery(func_name, attempt, last_exception)

    if last_exception:
        _raise_final_error(func_name, last_exception)
    raise RuntimeError(f"MCP tool {func_name} failed unexpectedly")


def _to_timeout_value(value: JsonValue | None) -> float | None:
    """Convert JsonValue to a valid timeout value.

    Ensures we only accept float-compatible values and ignore invalid ones.
    """
    if value is None:
        return None
    # Recursive JsonValue narrows incorrectly in pyright/basedpyright
    if isinstance(value, (int, float)):  # pyright: ignore[reportUnnecessaryIsInstance]
        return float(value)
    if isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        try:
            return float(value)
        except ValueError:
            logger.warning("Invalid timeout value %r, falling back to defaults", value)
            return None
    logger.warning("Unsupported timeout type %s, falling back to defaults", type(value))
    return None


async def _record_usage_if_available(
    tool_name: str,
    duration_ms: float,
    success: bool,
    error_type: str | None,
    kind: Literal["tool", "resource"] = "tool",
) -> None:
    """Record tool or resource usage if UsageTracker is available (Phase 29/43)."""
    try:
        from cortex.managers.lazy_manager import LazyManager
        from cortex.managers.usage_tracker import UsageTracker

        managers = get_current_managers()
        raw = managers.get("usage_tracker") if managers else None
        if raw is None:
            return
        tracker = cast(
            object,
            await raw.get() if isinstance(raw, LazyManager) else raw,
        )
        if isinstance(tracker, UsageTracker):
            await tracker.record_tool_usage(
                tool_name=tool_name,
                duration_ms=duration_ms,
                success=success,
                error_type=error_type,
                handler_kind=kind,
            )
    except Exception as e:
        logger.debug("Usage recording skipped or failed: %s (%s)", type(e).__name__, e)


def _stability_params(
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
) -> tuple[float, MCPToolArguments]:
    """Compute effective timeout and validated kwargs for with_mcp_stability."""
    st = _to_timeout_value(stability_timeout)
    tv = _to_timeout_value(timeout)
    effective = st or tv or float(MCP_TOOL_TIMEOUT_SECONDS)
    func_kwargs = {
        k: v
        for k, v in kwargs.items()
        if k not in {"timeout", "stability_timeout", "kind"}
    }
    return effective, MCPToolArguments.model_validate(func_kwargs)


async def _run_with_retry_and_record[T](
    func: Callable[..., Awaitable[T]],
    args: tuple[JsonValue, ...],
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
    kind: Literal["tool", "resource"] = "tool",
) -> T:
    """Run func with retry and record usage (used by with_mcp_stability)."""
    semaphore = _get_semaphore()
    effective_timeout, kwargs_model = _stability_params(
        timeout, stability_timeout, kwargs
    )
    start_ns = time.perf_counter_ns()
    success = True
    error_type: str | None = None
    try:
        return await _execute_with_retry(
            func, semaphore, effective_timeout, args, kwargs_model
        )
    except Exception as e:
        success = False
        error_type = type(e).__name__
        raise
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
        await _record_usage_if_available(
            func.__name__, duration_ms, success, error_type, kind=kind
        )


async def with_mcp_stability[T](
    func: Callable[..., Awaitable[T]],
    *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
    timeout: JsonValue | None = None,
    stability_timeout: JsonValue | None = None,
    kind: Literal["tool", "resource"] = "tool",
    **kwargs: JsonValue,  # pyright: ignore[reportUnknownParameterType]
) -> T:
    """Execute MCP tool or resource handler with stability protections.

    Provides:
    - Timeout protection (prevents hanging operations)
    - Resource limit enforcement (concurrent operations)
    - Connection error handling
    - Automatic retry for transient failures
    - Usage recording with handler_kind (Phase 43)

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        timeout: Maximum execution time in seconds (public API)
        stability_timeout: Internal timeout override (used by wrappers)
        kind: "tool" or "resource" for usage recording (default "tool")
        **kwargs: Keyword arguments for func

    Returns:
        Result from func execution

    Raises:
        TimeoutError: If operation exceeds timeout
        RuntimeError: If resource limits exceeded or connection fails
    """
    health = await check_connection_health()
    if not health.healthy:
        raise ConnectionError("Connection not healthy before tool execution")
    return await _run_with_retry_and_record(
        func, args, timeout, stability_timeout, kwargs, kind=kind
    )


def _handle_tool_exception_if_failure(error: Exception, tool_name: str) -> None:
    """If error is an MCP tool failure, run protocol and raise; otherwise no-op."""
    handler = MCPToolFailureHandler(project_root=None)
    if handler.detect_failure(error, tool_name, "MCP tool execution"):
        handler.handle_failure(tool_name, error, "MCP tool execution")


def mcp_tool_wrapper[T](
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for MCP tools to add stability protections.

    Usage:
        @mcp.tool()
        @ensure_usage_context
        @mcp_tool_wrapper(timeout=60.0)
        async def my_tool(...):
            ...

    Args:
        timeout: Maximum execution time in seconds

    Returns:
        Decorator function
    """
    import functools
    import inspect

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        """Apply stability wrapper to function."""

        @functools.wraps(func)
        async def wrapper(
            *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
            **kwargs: JsonValue,  # pyright: ignore[reportUnknownParameterType]
        ) -> T:
            try:
                return await with_mcp_stability(
                    func, *args, stability_timeout=timeout, kind="tool", **kwargs
                )
            except Exception as e:
                _handle_tool_exception_if_failure(e, func.__name__)
                raise

        original_sig = inspect.signature(func)
        cast(_SignatureAware, wrapper).__signature__ = original_sig
        return wrapper

    return decorator


def mcp_resource_wrapper[T](
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for MCP resources to add stability protections (Phase 43).

    Same stability as mcp_tool_wrapper (timeout, semaphore, retry, connection
    health) and usage recording with handler_kind="resource". Does not run
    MCP tool failure protocol on exceptions (resource read failures raised
    as normal exceptions).

    Usage:
        @mcp.resource(uri="cortex://memory-bank/stats")
        @ensure_usage_context
        @mcp_resource_wrapper(timeout=30.0)
        async def get_memory_bank_stats(...):
            ...

    Args:
        timeout: Maximum execution time in seconds

    Returns:
        Decorator function
    """
    import functools
    import inspect

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        """Apply stability wrapper to resource handler."""

        @functools.wraps(func)
        async def wrapper(
            *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
            **kwargs: JsonValue,  # pyright: ignore[reportUnknownParameterType]
        ) -> T:
            return await with_mcp_stability(
                func, *args, stability_timeout=timeout, kind="resource", **kwargs
            )

        original_sig = inspect.signature(func)
        cast(_SignatureAware, wrapper).__signature__ = original_sig
        return wrapper

    return decorator


async def execute_tool_with_stability[T](
    func: Callable[..., Awaitable[T]],
    *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
    **kwargs: JsonValue,  # pyright: ignore[reportUnknownParameterType]
) -> T:
    """Execute MCP tool function with stability protections.

    This is a convenience wrapper for tool execution that provides:
    - Timeout protection (prevents hanging operations)
    - Resource limit enforcement (concurrent operations)
    - Connection error handling
    - Automatic retry for transient failures

    Args:
        func: Async function to execute (the tool's business logic)
        *args: Positional arguments for func
        timeout: Maximum execution time in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Result from func execution

    Raises:
        TimeoutError: If operation exceeds timeout
        RuntimeError: If resource limits exceeded or connection fails
    """
    kwargs_no_kind = {k: v for k, v in kwargs.items() if k != "kind"}
    return await with_mcp_stability(
        func, *args, stability_timeout=timeout, kind="tool", **kwargs_no_kind
    )


async def check_connection_health() -> ConnectionHealth:
    """Check MCP connection health status.

    Returns:
        Connection health metrics
    """
    semaphore = _get_semaphore()
    available = semaphore.available
    current = semaphore.current

    return ConnectionHealth(
        healthy=True,  # Connection is healthy if we can check
        concurrent_operations=current,
        max_concurrent=MCP_MAX_CONCURRENT_TOOLS,
        semaphore_available=available,
        utilization_percent=(
            (current / MCP_MAX_CONCURRENT_TOOLS) * 100
            if MCP_MAX_CONCURRENT_TOOLS > 0
            else 0.0
        ),
    )
