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
from typing import Any, Literal, Protocol, cast

import anyio

from cortex.core.constants import (
    MCP_CONNECTION_RETRY_ATTEMPTS,
    MCP_CONNECTION_RETRY_DELAY_SECONDS,
    MCP_MAX_CONCURRENT_RESOURCES,
    MCP_MAX_CONCURRENT_TOOLS,
    MCP_TOOL_TIMEOUT_SECONDS,
    PROGRESS_REPORT_INTERVAL_LONG_RUNNING_SECONDS,
    PROGRESS_REPORT_INTERVAL_SECONDS,
    PROGRESS_THRESHOLD_TIMEOUT_SECONDS,
)
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_failure_handler import MCPToolFailureHandler
from cortex.core.models import ConnectionHealth, JsonValue, MCPToolArguments
from cortex.core.usage_context import get_current_managers, set_current_managers

logger = logging.getLogger(__name__)

# Tools that report their own progress (file/step-based); skip wrapper time-based progress.
_TOOLS_WITH_OWN_PROGRESS = frozenset({"fix_markdown_lint", "fix_quality_issues"})

# Serialize first-tool context setup so concurrent tool calls do not each run full init.
_usage_context_init_lock: asyncio.Lock | None = None


def _get_usage_context_init_lock() -> asyncio.Lock:
    """Return the shared lock for usage context init (lazy-create for tests)."""
    global _usage_context_init_lock
    if _usage_context_init_lock is None:
        _usage_context_init_lock = asyncio.Lock()
    return _usage_context_init_lock


async def _resolve_root_and_managers(
    mcp_ctx: MCPContext | None,
) -> tuple[Path, dict[str, Any]]:
    """Resolve project root and get managers; log timings. Returns (root, mgrs_dict)."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.managers.initialization import get_managers

    t0 = time.monotonic()
    root = await resolve_project_root_async(None, mcp_ctx)
    resolve_elapsed = time.monotonic() - t0
    logger.debug(
        "ensure_usage_context: resolve_project_root_async took %.3fs -> %s",
        resolve_elapsed,
        root,
    )
    t1 = time.monotonic()
    mgrs = await get_managers(root)
    managers_elapsed = time.monotonic() - t1
    logger.debug(
        "ensure_usage_context: get_managers(%s) took %.3fs",
        root,
        managers_elapsed,
    )
    total = resolve_elapsed + managers_elapsed
    if total > 2.0:
        logger.info(
            "ensure_usage_context: first-tool init took %.2fs (resolve=%.2fs, get_managers=%.2fs)",
            total,
            resolve_elapsed,
            managers_elapsed,
        )
    mgrs_dict = mgrs if isinstance(mgrs, dict) else mgrs.model_dump()
    return (root, mgrs_dict)


async def _init_usage_context_under_lock(
    mcp_ctx: MCPContext | None, func_name: str
) -> None:
    """Resolve root, get managers, set usage context; raise after reporting."""
    from cortex.core.usage_context import set_current_project_root

    try:
        root, mgrs_dict = await _resolve_root_and_managers(mcp_ctx)
        set_current_managers(mgrs_dict)
        set_current_project_root(root)
    except Exception as e:  # pragma: no cover - exercised via tool tests
        await _handle_tool_exception_if_failure(e, func_name, mcp_ctx)
        raise


def ensure_usage_context[T](
    func: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """Decorator that sets usage context (for recording) when not already set.

    Wraps an async MCP tool handler so that get_current_managers() is set
    before the handler runs, enabling usage recording for tools that do not
    call get_managers() themselves.

    Resolves project root internally (via resolve_project_root_async) using
    MCP context when available, consistent with how tools resolve root.
    """
    import functools
    import inspect

    @functools.wraps(func)
    async def wrapper(
        *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
        **kwargs: JsonValue,  # pyright: ignore[reportUnknownParameterType]
    ) -> T:
        if get_current_managers() is not None:
            return await func(*args, **kwargs)
        lock = _get_usage_context_init_lock()
        async with lock:
            if get_current_managers() is not None:
                return await func(*args, **kwargs)
            ctx_raw = kwargs.get("ctx")
            mcp_ctx = cast(MCPContext | None, ctx_raw)
            await _init_usage_context_under_lock(mcp_ctx, func.__name__)
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
# Semaphore for resource reads (Phase 69: separate from tools to avoid -32001 queueing)
_concurrent_resources_semaphore: TrackedSemaphore | None = None

# Connection state for diagnostics (Phase 32)
_connection_closure_count: int = 0
_connection_recovery_count: int = 0


def _get_semaphore() -> TrackedSemaphore:
    """Get or create the global semaphore for concurrent tool limits."""
    global _concurrent_tools_semaphore
    if _concurrent_tools_semaphore is None:
        _concurrent_tools_semaphore = TrackedSemaphore(MCP_MAX_CONCURRENT_TOOLS)
    return _concurrent_tools_semaphore


def _get_resource_semaphore() -> TrackedSemaphore:
    """Get or create the semaphore for concurrent resource read limits (Phase 69)."""
    global _concurrent_resources_semaphore
    if _concurrent_resources_semaphore is None:
        _concurrent_resources_semaphore = TrackedSemaphore(MCP_MAX_CONCURRENT_RESOURCES)
    return _concurrent_resources_semaphore


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
    ctx: JsonValue | None = None,
) -> T:
    """Execute function once with timeout and resource limits."""
    async with semaphore:
        async with asyncio.timeout(timeout):
            call_kwargs = kwargs.model_dump(exclude_none=True)
            # Re-inject ctx if it was provided (MCPContext cannot go through Pydantic)
            if ctx is not None:
                call_kwargs["ctx"] = ctx
            return await func(*args, **call_kwargs)


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
        anyio.BrokenResourceError,  # anyio resource errors (e.g., stdio closed)
        anyio.ClosedResourceError,  # send on closed stream after client disconnect
        RuntimeError,  # Main wraps connection closure in RuntimeError for MCP
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
    ctx: JsonValue | None = None,
) -> T:
    """Execute function with retry logic for transient failures."""
    last_exception: Exception | None = None
    func_name = func.__name__

    for attempt in range(1, MCP_CONNECTION_RETRY_ATTEMPTS + 1):
        try:
            return await _execute_single_attempt(
                func, semaphore, timeout, args, kwargs, ctx
            )
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


async def _progress_report_loop(
    ctx: JsonValue,
    timeout_sec: float,
    _tool_name: str,
) -> None:
    """Background task: report progress every N seconds (Phase 46).

    Uses a shorter interval for long-running tools (timeout >= 300s) to reduce
    client idle timeout risk (Connection closed -32000).
    """
    from cortex.core.context_logging import MCPContext, report_progress_safe

    interval = (
        PROGRESS_REPORT_INTERVAL_LONG_RUNNING_SECONDS
        if timeout_sec >= 300
        else PROGRESS_REPORT_INTERVAL_SECONDS
    )
    start = time.perf_counter()
    while True:
        await asyncio.sleep(interval)
        elapsed = time.perf_counter() - start
        if elapsed >= timeout_sec:
            break
        pct = min(95, int((elapsed / timeout_sec) * 100))
        mcp_ctx = cast(MCPContext | None, ctx)
        await report_progress_safe(mcp_ctx, float(pct), 100.0)


async def _record_usage_if_available(
    tool_name: str,
    duration_ms: float,
    success: bool,
    error_type: str | None,
    kind: Literal["tool", "resource"] = "tool",
) -> None:
    """Record tool or resource usage if UsageTracker is available (Phase 29/43).

    All tool and resource requests are tracked automatically to
    .cortex/.cache/usage/events/{date}.json via UsageTracker, which uses
    cache_json_access (read_modify_write_cache_json) for concurrent-safe writes.
    """
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
) -> tuple[float, MCPToolArguments, JsonValue | None]:
    """Compute effective timeout, validated kwargs, and ctx for with_mcp_stability.

    Returns:
        Tuple of (effective_timeout, kwargs_model, ctx).
        ctx is extracted separately because it's an MCPContext object that
        cannot be serialized through Pydantic's model_dump().
    """
    st = _to_timeout_value(stability_timeout)
    tv = _to_timeout_value(timeout)
    effective = st or tv or float(MCP_TOOL_TIMEOUT_SECONDS)
    # Extract ctx separately - it's an MCPContext object, not JSON-serializable
    ctx = kwargs.get("ctx")
    # project_root is never passed to tools; they resolve it internally
    func_kwargs = {
        k: v
        for k, v in kwargs.items()
        if k not in {"timeout", "stability_timeout", "kind", "ctx", "project_root"}
    }
    return effective, MCPToolArguments.model_validate(func_kwargs), ctx


def _create_progress_task_if_needed(
    enable_progress: bool,
    ctx: JsonValue | None,
    effective_timeout: float,
    tool_name: str,
) -> asyncio.Task[None] | None:
    """Create background progress task when enabled and ctx present (Phase 46).

    Skips time-based progress for tools that report their own progress
    (e.g. fix_markdown_lint, fix_quality_issues) to avoid mixing
    two progress scales (0-100 vs n/total).
    """
    if (
        enable_progress
        and ctx is not None
        and effective_timeout >= PROGRESS_THRESHOLD_TIMEOUT_SECONDS
        and tool_name not in _TOOLS_WITH_OWN_PROGRESS
    ):
        return asyncio.create_task(
            _progress_report_loop(ctx, effective_timeout, tool_name)
        )
    return None


async def _cancel_progress_and_report_done(
    progress_task: asyncio.Task[None] | None, ctx: JsonValue | None
) -> None:
    """Cancel progress task and report 100% (Phase 46)."""
    from cortex.core.context_logging import MCPContext, report_progress_safe

    if progress_task is None:
        return
    _ = progress_task.cancel()
    try:
        await progress_task
    except asyncio.CancelledError:
        pass
    mcp_ctx = cast(MCPContext | None, ctx)
    await report_progress_safe(mcp_ctx, 100.0, 100.0)


async def _record_usage_finish(
    tool_name: str,
    start_ns: int,
    success: bool,
    error_type: str | None,
    kind: Literal["tool", "resource"],
) -> None:
    """Record usage after tool run (duration and outcome)."""
    duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
    await _record_usage_if_available(
        tool_name, duration_ms, success, error_type, kind=kind
    )


async def _run_with_retry_and_record[T](
    func: Callable[..., Awaitable[T]],
    args: tuple[JsonValue, ...],
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
    kind: Literal["tool", "resource"] = "tool",
    enable_progress: bool = False,
) -> T:
    """Run func with retry and record usage (used by with_mcp_stability)."""
    semaphore = _get_resource_semaphore() if kind == "resource" else _get_semaphore()
    effective_timeout, kwargs_model, ctx = _stability_params(
        timeout, stability_timeout, kwargs
    )
    progress_task = _create_progress_task_if_needed(
        enable_progress, ctx, effective_timeout, func.__name__
    )
    start_ns = time.perf_counter_ns()
    success, error_type = True, None
    try:
        return await _execute_with_retry(
            func, semaphore, effective_timeout, args, kwargs_model, ctx
        )
    except Exception as e:
        success, error_type = False, type(e).__name__
        raise
    finally:
        await _cancel_progress_and_report_done(progress_task, ctx)
        await _record_usage_finish(
            func.__name__, start_ns, success, error_type, kind=kind
        )


async def with_mcp_stability[T](
    func: Callable[..., Awaitable[T]],
    *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
    timeout: JsonValue | None = None,
    stability_timeout: JsonValue | None = None,
    kind: Literal["tool", "resource"] = "tool",
    enable_progress: bool = False,
    **kwargs: JsonValue,  # pyright: ignore[reportUnknownParameterType]
) -> T:
    """Execute MCP tool or resource handler with stability protections.

    Provides:
    - Timeout protection (prevents hanging operations)
    - Resource limit enforcement (concurrent operations)
    - Connection error handling
    - Automatic retry for transient failures
    - Usage recording with handler_kind (Phase 43)
    - Optional progress reporting for long-running tools (Phase 46)

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        timeout: Maximum execution time in seconds (public API)
        stability_timeout: Internal timeout override (used by wrappers)
        kind: "tool" or "resource" for usage recording (default "tool")
        enable_progress: If True, report progress every N seconds when ctx present
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
        func,
        args,
        timeout,
        stability_timeout,
        kwargs,
        kind=kind,
        enable_progress=enable_progress,
    )


async def _handle_tool_exception_if_failure(
    error: Exception, tool_name: str, ctx: MCPContext | None = None
) -> None:
    """If error is an MCP tool failure, run protocol and raise; otherwise no-op."""
    handler = MCPToolFailureHandler(project_root=None)
    if await handler.detect_failure(error, tool_name, "MCP tool execution", ctx):
        await handler.handle_failure(tool_name, error, "MCP tool execution", ctx)


def _make_tool_wrapper_func[T](
    func: Callable[..., Awaitable[T]],
    timeout: float,
    progress_enabled: bool,
) -> Callable[..., Awaitable[T]]:
    """Build wrapped async tool with stability and optional progress (Phase 46)."""
    import functools

    @functools.wraps(func)
    async def wrapper(
        *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
        **kwargs: JsonValue,  # pyright: ignore[reportUnknownParameterType]
    ) -> T:
        kwargs_no_progress = {k: v for k, v in kwargs.items() if k != "enable_progress"}
        try:
            return await with_mcp_stability(
                func,
                *args,
                stability_timeout=timeout,
                kind="tool",
                enable_progress=progress_enabled,
                **kwargs_no_progress,
            )
        except Exception as e:
            from cortex.core.context_logging import MCPContext

            ctx_raw = kwargs.get("ctx")
            mcp_ctx = cast(MCPContext | None, ctx_raw)
            await _handle_tool_exception_if_failure(e, func.__name__, mcp_ctx)
            raise

    return wrapper


def mcp_tool_wrapper[T](
    timeout: float = MCP_TOOL_TIMEOUT_SECONDS,
    enable_progress: bool | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for MCP tools to add stability protections.

    When enable_progress is None, progress is auto-enabled for tools with
    timeout >= PROGRESS_THRESHOLD_TIMEOUT_SECONDS (120s).

    Usage:
        @mcp.tool()
        @ensure_usage_context
        @mcp_tool_wrapper(timeout=60.0)
        async def my_tool(...):
            ...

    Args:
        timeout: Maximum execution time in seconds
        enable_progress: If True, report progress every N seconds when ctx
            present. If None, auto-enable for timeout >= 120s.

    Returns:
        Decorator function
    """
    import inspect

    progress_enabled = (
        enable_progress
        if enable_progress is not None
        else timeout >= PROGRESS_THRESHOLD_TIMEOUT_SECONDS
    )

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        wrapper = _make_tool_wrapper_func(func, timeout, progress_enabled)
        cast(_SignatureAware, wrapper).__signature__ = inspect.signature(func)
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
            kwargs_no_progress = {
                k: v for k, v in kwargs.items() if k != "enable_progress"
            }
            return await with_mcp_stability(
                func,
                *args,
                stability_timeout=timeout,
                kind="resource",
                enable_progress=False,
                **kwargs_no_progress,
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
    kwargs_clean = {
        k: v for k, v in kwargs.items() if k not in ("kind", "enable_progress")
    }
    return await with_mcp_stability(
        func,
        *args,
        stability_timeout=timeout,
        kind="tool",
        enable_progress=False,
        **kwargs_clean,
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
