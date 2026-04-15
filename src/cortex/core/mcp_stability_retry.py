"""Retry and connection handling for MCP tool execution.

Extracted from mcp_stability for file size compliance.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import NoReturn

from pydantic import BaseModel, ConfigDict, Field

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
from cortex.core.pydantic_extra import EXTRA_FORBID

logger = logging.getLogger(__name__)

# Connection state for diagnostics (Phase 32) and Phase 86 circuit breaker
_connection_closure_count: int = 0
_connection_recovery_count: int = 0

_RECONNECT_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0)
_MAX_RECONNECT_ATTEMPTS = len(_RECONNECT_BACKOFF_SECONDS)
_MAX_RECONNECT_DELAY_SECONDS = 30.0
_HEALTH_CHECK_INTERVAL_SECONDS = 60.0


class MCPConnectionState(BaseModel):
    """In-process connection state and circuit-breaker flags (Phase 86)."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    connected: bool = Field(
        default=True,
        description="Whether the MCP transport is considered connected.",
    )
    reconnecting: bool = Field(
        default=False,
        description="True while a reconnection attempt is in progress.",
    )
    consecutive_failures: int = Field(
        default=0,
        ge=0,
        description="Number of consecutive connection failures.",
    )
    circuit_open: bool = Field(
        default=False,
        description="Whether the circuit breaker is open (degraded mode).",
    )
    last_error: str | None = Field(
        default=None,
        description="Last connection error message, for diagnostics.",
    )


_connection_state: MCPConnectionState | None = None
_health_monitor_task: asyncio.Task[None] | None = None
_connection_state_lock: asyncio.Lock | None = None


def _get_connection_state_lock() -> asyncio.Lock:
    """Return global asyncio.Lock for connection state mutations (lazy init)."""
    global _connection_state_lock
    if _connection_state_lock is None:
        _connection_state_lock = asyncio.Lock()
    return _connection_state_lock


def get_connection_state() -> MCPConnectionState:
    """Return global MCP connection state (lazy init)."""
    global _connection_state
    if _connection_state is None:
        _connection_state = MCPConnectionState()
    return _connection_state


def reset_connection_state_for_testing() -> None:
    """Clear process-global MCP connection state for test isolation.

    Tests that open the circuit breaker (e.g. reconnect exhaustion) must not
    leave degraded mode for unrelated tests on the same pytest-xdist worker.
    """
    global _connection_state, _connection_state_lock
    _connection_state = None
    _connection_state_lock = None


def ensure_clean_connection_state_for_testing() -> None:
    """Reset connection state and re-init defaults (pytest autouse hook)."""
    reset_connection_state_for_testing()
    _ = get_connection_state()


async def record_connection_closure() -> None:
    """Record connection closure for diagnostics (Phase 32).

    Protected by asyncio.Lock to prevent inconsistent state when multiple
    concurrent tool calls encounter connection errors simultaneously.
    """
    global _connection_closure_count
    async with _get_connection_state_lock():
        _connection_closure_count += 1
        state = get_connection_state()
        state.connected = False


async def record_connection_recovery() -> None:
    """Record connection recovery for diagnostics (Phase 32).

    Protected by asyncio.Lock to prevent inconsistent state when multiple
    concurrent reconnect attempts complete near-simultaneously.
    """
    global _connection_recovery_count
    async with _get_connection_state_lock():
        _connection_recovery_count += 1
        state = get_connection_state()
        state.connected = True
        state.reconnecting = False
        state.circuit_open = False
        state.consecutive_failures = 0
        state.last_error = None


async def _ping_transport() -> None:
    """Lightweight transport ping hook for reconnection.

    Phase 86: this is a placeholder that can be patched in tests or extended
    to perform a real health check at the transport layer. By default it
    completes immediately so reconnection logic is effectively a no-op until
    wired to a concrete transport.
    """
    # Yield control to the event loop; no real network I/O by default.
    await asyncio.sleep(0)


async def _handle_reconnect_attempt_error(
    state: MCPConnectionState,
    exc: Exception,
    attempt: int,
    base_delay: float,
    reason: str | None,
) -> bool:
    """Handle a single reconnect attempt failure. Returns True if we should stop."""
    state.connected = False
    state.consecutive_failures += 1
    state.last_error = str(exc)
    if state.consecutive_failures >= _MAX_RECONNECT_ATTEMPTS:
        return True
    delay = min(base_delay, _MAX_RECONNECT_DELAY_SECONDS)
    logger.info(
        "MCP reconnect attempt %d/%d failed (%s); retrying in %.1fs (reason=%s)",
        attempt,
        _MAX_RECONNECT_ATTEMPTS,
        exc,
        delay,
        reason or "unspecified",
    )
    await asyncio.sleep(delay)
    return False


async def _handle_reconnect_failure(
    state: MCPConnectionState,
    last_error: Exception | None,
    reason: str | None,
) -> NoReturn:
    """Mark circuit as open and raise a final ConnectionError."""
    state.reconnecting = False
    state.circuit_open = True
    msg = (
        "MCP reconnection failed after "
        f"{state.consecutive_failures} attempts; circuit breaker open (reason={reason or 'unspecified'})"
    )
    raise ConnectionError(msg) from last_error


async def reconnect(reason: str | None = None) -> ConnectionHealth:
    """Attempt to reconnect MCP transport with exponential backoff.

    Updates connection state and returns current ConnectionHealth. On repeated
    failure, opens the circuit breaker (degraded mode) and raises
    ConnectionError.
    """
    state = get_connection_state()
    if state.circuit_open:
        # Already in degraded mode; report current health without retry loop.
        return await check_connection_health()

    state.reconnecting = True
    last_error: Exception | None = None
    for attempt, base_delay in enumerate(_RECONNECT_BACKOFF_SECONDS, start=1):
        try:
            await _ping_transport()
            await record_connection_recovery()
            state.reconnecting = False
            return await check_connection_health()
        except Exception as exc:  # pragma: no cover - exercised via tests
            last_error = exc
            should_stop = await _handle_reconnect_attempt_error(
                state, exc, attempt, base_delay, reason
            )
            if should_stop:
                break

    await _handle_reconnect_failure(state, last_error, reason)


async def _health_monitor_loop(interval_seconds: float) -> None:
    """Periodically check connection health and trigger reconnection."""
    while True:
        try:
            health = await check_connection_health()
            if not health.healthy and not get_connection_state().circuit_open:
                try:
                    _ = await reconnect("health_monitor")
                except ConnectionError:
                    logger.warning(
                        "MCP health monitor: circuit breaker open; leaving connection in degraded mode",
                    )
        except Exception as exc:  # pragma: no cover
            logger.debug("MCP health monitor iteration failed: %s", exc)
        await asyncio.sleep(interval_seconds)


def start_connection_health_monitor() -> None:
    """Start background connection health monitor loop if not already running."""
    global _health_monitor_task
    if _health_monitor_task is not None and not _health_monitor_task.done():
        return
    _health_monitor_task = asyncio.create_task(
        _health_monitor_loop(_HEALTH_CHECK_INTERVAL_SECONDS)
    )


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
    await record_connection_closure()
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
        await record_connection_recovery()


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
    utilization = (
        (current / MCP_MAX_CONCURRENT_TOOLS) * 100
        if MCP_MAX_CONCURRENT_TOOLS > 0
        else 0.0
    )
    state = get_connection_state()
    healthy = not state.circuit_open

    return ConnectionHealth(
        healthy=healthy,
        concurrent_operations=current,
        max_concurrent=MCP_MAX_CONCURRENT_TOOLS,
        semaphore_available=available,
        utilization_percent=utilization,
        long_running_holder=get_long_running_semaphore_holder(),
        degraded=state.circuit_open,
        reconnecting=state.reconnecting,
        reconnect_attempts=state.consecutive_failures,
    )
