"""Retry and connection handling for MCP tool execution.

Extracted from mcp_stability for file size compliance.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from cortex.core.constants import MCP_MAX_CONCURRENT_TOOLS
from cortex.core.mcp_stability_config import (
    TrackedSemaphore,
    attach_attempt_to_exception,
    connection_error_fallback,
    get_connection_retry_attempts,
    get_connection_retry_delay,
    get_long_running_semaphore_holder,
    get_semaphore,
    is_connection_error,
    raise_if_retries_exhausted,
)
from cortex.core.mcp_stability_semaphores import get_long_running_elapsed_seconds
from cortex.core.models import ConnectionHealth, JsonValue, MCPToolArguments

logger = logging.getLogger(__name__)

# Connection state for diagnostics (Phase 32)
_connection_closure_count: int = 0
_connection_recovery_count: int = 0


def _record_connection_closure() -> None:
    """Record connection closure for diagnostics (Phase 32)."""
    global _connection_closure_count
    _connection_closure_count += 1


def _record_connection_recovery() -> None:
    """Record connection recovery for diagnostics (Phase 32)."""
    global _connection_recovery_count
    _connection_recovery_count += 1


async def _handle_timeout_error(
    func_name: str, timeout: float, attempt: int, e: asyncio.TimeoutError
) -> tuple[TimeoutError | None, Exception | None]:
    """Handle timeout error during retry."""
    max_attempts = get_connection_retry_attempts(func_name)
    logger.warning(
        f"MCP tool {func_name} timed out after {timeout}s "
        + f"(attempt {attempt}/{max_attempts})"
    )
    if attempt == max_attempts:
        error = TimeoutError(f"MCP tool {func_name} exceeded timeout of {timeout}s")
        error.__cause__ = e
        return error, None
    return None, e


def _connection_error_diag() -> tuple[str, str]:
    """Return (holder_str, elapsed_str) for connection error logging."""
    holder = get_long_running_semaphore_holder()
    elapsed = get_long_running_elapsed_seconds()
    es = f"{elapsed:.1f}" if elapsed is not None else "n/a"
    return (holder or "none", es)


def _build_connection_error_final(
    func_name: str, attempt: int, e: Exception
) -> ConnectionError | RuntimeError:
    """Build final error when retries exhausted for connection error."""
    fallback = connection_error_fallback.get(func_name, "")
    base_msg = f"MCP tool {func_name} failed after {attempt} attempts (connection)."
    err: ConnectionError | RuntimeError = (
        ConnectionError(base_msg + fallback)
        if is_connection_error(e)
        else RuntimeError(
            f"MCP connection failed for {func_name} after {attempt} attempts"
        )
    )
    err.__cause__ = e
    return err


async def _handle_connection_error(
    func_name: str, attempt: int, e: Exception
) -> tuple[ConnectionError | RuntimeError | None, Exception | None]:
    """Handle connection error during retry."""
    _record_connection_closure()
    max_attempts = get_connection_retry_attempts(func_name)
    holder_str, elapsed_str = _connection_error_diag()
    logger.warning(
        "MCP connection error in %s (attempt %d/%d) holder=%s elapsed_sec=%s: %s",
        func_name,
        attempt,
        max_attempts,
        holder_str,
        elapsed_str,
        e,
    )
    if attempt == max_attempts:
        return _build_connection_error_final(func_name, attempt, e), None
    delay = get_connection_retry_delay(func_name, attempt)
    logger.info(
        "MCP connection error in %s (attempt %d/%d): retrying in %.1fs",
        func_name,
        attempt,
        max_attempts,
        delay,
    )
    await asyncio.sleep(delay)
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
            if ctx is not None:
                call_kwargs["ctx"] = ctx
            return await func(*args, **call_kwargs)


async def _retry_path_health_and_recovery(
    func_name: str, attempt: int, last_exception: Exception | None
) -> None:
    """Check connection health before retry and record recovery (Phase 32)."""
    health = await check_connection_health()
    if not health.healthy:
        raise ConnectionError(
            f"Connection not healthy before retry {attempt} for {func_name}"
        ) from last_exception
    if last_exception and is_connection_error(last_exception):
        _record_connection_recovery()


async def _handle_retry_exception(
    func_name: str,
    timeout: float,
    attempt: int,
    e: Exception,
    last_exception: Exception | None,
) -> tuple[bool, Exception | None]:
    """Handle exception during retry attempt. Returns (should_raise, new_last_exception)."""
    if isinstance(e, asyncio.TimeoutError):
        error, stored_exception = await _handle_timeout_error(
            func_name, timeout, attempt, e
        )
        if error:
            raise error
        return False, stored_exception

    if is_connection_error(e):
        error, stored_exception = await _handle_connection_error(func_name, attempt, e)
        if error:
            raise error
        return False, stored_exception

    logger.error(f"MCP tool {func_name} failed: {e}")
    raise


async def _after_failed_attempt(
    func_name: str, attempt: int, last_exception: Exception | None
) -> None:
    """Attach attempt to exception and run retry-path health and recovery."""
    if last_exception is not None:
        attach_attempt_to_exception(last_exception, attempt)
    await _retry_path_health_and_recovery(func_name, attempt, last_exception)


async def _try_one_attempt[T](
    func: Callable[..., Awaitable[T]],
    semaphore: TrackedSemaphore,
    timeout: float,
    args: tuple[JsonValue, ...],
    kwargs: MCPToolArguments,
    ctx: JsonValue | None,
    attempt: int,
    last_exception_ref: list[Exception | None],
) -> tuple[T, int] | None:
    """Run one attempt; return (result, attempt) or None and set last_exception_ref[0]."""
    try:
        result = await _execute_single_attempt(
            func, semaphore, timeout, args, kwargs, ctx
        )
        return (result, attempt)
    except asyncio.CancelledError:
        logger.debug(
            "Request for %s was cancelled (attempt %d/%d)",
            func.__name__,
            attempt,
            get_connection_retry_attempts(func.__name__),
        )
        raise
    except Exception as e:
        _, stored = await _handle_retry_exception(
            func.__name__, timeout, attempt, e, last_exception_ref[0]
        )
        last_exception_ref[0] = stored
        await _after_failed_attempt(func.__name__, attempt, stored)
        return None


async def execute_with_retry[T](
    func: Callable[..., Awaitable[T]],
    semaphore: TrackedSemaphore,
    timeout: float,
    args: tuple[JsonValue, ...],
    kwargs: MCPToolArguments,
    ctx: JsonValue | None = None,
) -> tuple[T, int]:
    """Execute with retry for transient failures; returns (result, attempt_that_succeeded)."""
    last_exception_ref: list[Exception | None] = [None]
    func_name = func.__name__
    max_attempts = get_connection_retry_attempts(func_name)
    for attempt in range(1, max_attempts + 1):
        out = await _try_one_attempt(
            func, semaphore, timeout, args, kwargs, ctx, attempt, last_exception_ref
        )
        if out is not None:
            return out
    raise_if_retries_exhausted(func_name, last_exception_ref[0])


async def check_connection_health() -> ConnectionHealth:
    """Check MCP connection health status."""
    semaphore = get_semaphore()
    available = semaphore.available
    current = semaphore.current

    return ConnectionHealth(
        healthy=True,
        concurrent_operations=current,
        max_concurrent=MCP_MAX_CONCURRENT_TOOLS,
        semaphore_available=available,
        utilization_percent=(
            (current / MCP_MAX_CONCURRENT_TOOLS) * 100
            if MCP_MAX_CONCURRENT_TOOLS > 0
            else 0.0
        ),
        long_running_holder=get_long_running_semaphore_holder(),
    )
