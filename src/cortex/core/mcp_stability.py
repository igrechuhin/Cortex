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
from typing import Protocol, cast

from cortex.core.constants import (
    MCP_MAX_CONCURRENT_TOOLS,
    MCP_TOOL_TIMEOUT_SECONDS,
    MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS,
    PROGRESS_REPORT_INTERVAL_LONG_RUNNING_SECONDS,
    PROGRESS_REPORT_INTERVAL_SECONDS,
    PROGRESS_REPORT_INTERVAL_VERY_FREQUENT_SECONDS,
    PROGRESS_THRESHOLD_TIMEOUT_SECONDS,
)
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_async_utils import cancel_and_drain_progress_task
from cortex.core.mcp_failure_handler import MCPToolFailureHandler
from cortex.core.mcp_stability_config import (
    TrackedSemaphore,
    attach_attempt_to_exception,
    connection_error_fallback,
    get_connection_retry_attempts,
    get_connection_retry_delay,
    get_long_running_semaphore_holder,
    get_resource_semaphore,
    get_semaphore,
    get_usage_context_init_lock,
    is_connection_error,
    long_running_tools_serialized,
    raise_if_retries_exhausted,
    record_usage_finish,
    run_and_finalize_impl,
    to_timeout_value,
    tools_needing_frequent_progress,
    tools_with_own_progress,
)
from cortex.core.models import (
    ConnectionHealth,
    HandlerKind,
    JsonValue,
    MCPToolArguments,
)
from cortex.core.usage_context import get_current_managers, set_current_managers

# Returned to the client when the request was cancelled (e.g. client timeout).
# Returning this instead of re-raising CancelledError keeps the connection open.
CANCELLED_RESPONSE_JSON = '{"status":"error","error":"CancelledError","message":"Tool call was cancelled by client"}'

logger = logging.getLogger(__name__)


async def _resolve_root_and_managers(
    mcp_ctx: MCPContext | None,
) -> tuple[Path, dict[str, object]]:
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


async def _acquire_usage_context_lock_with_timeout(
    lock: asyncio.Lock, func_name: str
) -> None:
    """Acquire usage context init lock with timeout; raise RuntimeError on timeout."""
    try:
        async with asyncio.timeout(MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS):
            async with lock:
                return
    except TimeoutError:
        logger.error(
            f"Usage context init lock timeout after {MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS}s "
            + f"for {func_name}. Another tool call may be stuck in initialization."
        )
        raise RuntimeError(
            f"Failed to acquire usage context init lock after {MCP_USAGE_CONTEXT_INIT_LOCK_TIMEOUT_SECONDS}s. "
            + "Another tool call may be stuck in initialization."
        ) from None


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
        lock = get_usage_context_init_lock()
        await _acquire_usage_context_lock_with_timeout(lock, func.__name__)
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


# Connection state for diagnostics (Phase 32)
_connection_closure_count: int = 0
_connection_recovery_count: int = 0


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
    max_attempts = get_connection_retry_attempts(func_name)
    logger.warning(
        f"MCP connection error in {func_name} (attempt {attempt}/{max_attempts}): {e}"
    )
    if attempt == max_attempts:
        fallback = connection_error_fallback.get(func_name, "")
        base_msg = f"MCP tool {func_name} failed after {attempt} attempts (connection)."
        error: RuntimeError | ConnectionError = (
            ConnectionError(base_msg + fallback)
            if is_connection_error(e)
            else RuntimeError(
                f"MCP connection failed for {func_name} after {attempt} attempts"
            )
        )
        error.__cause__ = e
        return error, None
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
            # Re-inject ctx if it was provided (MCPContext cannot go through Pydantic)
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


async def _execute_with_retry[T](
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


async def _progress_report_loop(
    ctx: JsonValue,
    timeout_sec: float,
    _tool_name: str,
) -> None:
    """Background task: report progress every N seconds (Phase 46). Uses a shorter
    interval for long-running tools (timeout >= 300s) to reduce client idle
    timeout risk (Connection closed -32000). Uses very frequent interval for
    tools prone to connection closed errors (e.g. execute_pre_commit_checks).

    Handles cancellation gracefully: if the request is cancelled, the loop
    stops immediately without trying to send more progress updates.
    """
    if _tool_name in tools_needing_frequent_progress:
        interval = PROGRESS_REPORT_INTERVAL_VERY_FREQUENT_SECONDS
    elif timeout_sec >= 300:
        interval = PROGRESS_REPORT_INTERVAL_LONG_RUNNING_SECONDS
    else:
        interval = PROGRESS_REPORT_INTERVAL_SECONDS

    start = time.perf_counter()
    try:
        _ = await _progress_report_step(
            ctx, timeout_sec, start, _tool_name
        )  # Send immediate progress report at start (0%) to establish connection activity
    except Exception:
        pass  # If initial progress fails, continue anyway - the loop will retry

    try:
        while True:
            await asyncio.sleep(interval)
            if not await _progress_report_step(ctx, timeout_sec, start, _tool_name):
                break
    except asyncio.CancelledError:
        logger.debug(
            "Progress loop for %s cancelled", _tool_name
        )  # Request was cancelled - stop progress reporting immediately
        raise


async def _progress_report_step(
    ctx: JsonValue,
    timeout_sec: float,
    start: float,
    tool_name: str,
) -> bool:
    """Run a single progress-report step; return False when loop should stop."""
    from cortex.core.context_logging import MCPContext, report_progress_safe

    elapsed = time.perf_counter() - start
    if elapsed >= timeout_sec:
        return False

    pct = min(95, int((elapsed / timeout_sec) * 100))
    mcp_ctx = cast(MCPContext | None, ctx)
    try:
        await report_progress_safe(mcp_ctx, float(pct), 100.0)
        return True
    except Exception as e:  # pragma: no cover - exercised via live MCP connection
        # If the client has disconnected (e.g. stdio closed), stop the
        # progress loop quietly instead of surfacing an unhandled
        # ExceptionGroup during TaskGroup cleanup.
        if is_connection_error(e):
            logger.info(
                "Progress loop for %s stopped due to connection error: %s",
                tool_name,
                e,
            )
            return False
        logger.debug(
            "Progress loop for %s stopped due to unexpected error: %s",
            tool_name,
            e,
        )
        return False


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
    st = to_timeout_value(stability_timeout)
    tv = to_timeout_value(timeout)
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
    (e.g. fix_quality_issues) to avoid mixing two progress scales (0-100 vs n/total).
    fix_markdown_lint gets both wrapper progress (2s keep-alive) and its own file progress.
    """
    # Never create time-based progress for tools that report their own progress
    if tool_name in tools_with_own_progress:
        return None

    if (
        enable_progress
        and ctx is not None
        and effective_timeout >= PROGRESS_THRESHOLD_TIMEOUT_SECONDS
    ):
        return asyncio.create_task(
            _progress_report_loop(ctx, effective_timeout, tool_name)
        )
    return None


async def _cancel_progress_and_report_done(
    progress_task: asyncio.Task[None] | None,
    ctx: JsonValue | None,
    tool_name: str | None = None,
) -> None:
    """Cancel progress task and report 100% (Phase 46).

    For tools that report their own progress (e.g., fix_quality_issues),
    skip the wrapper's 100% report to avoid mixing progress scales.
    """
    from cortex.core.context_logging import MCPContext, report_progress_safe

    if progress_task is None:
        return
    await cancel_and_drain_progress_task(progress_task)
    if tool_name is not None and tool_name in tools_with_own_progress:
        return
    mcp_ctx = cast(MCPContext | None, ctx)
    try:
        await report_progress_safe(mcp_ctx, 100.0, 100.0)
    except Exception as e:  # pragma: no cover - depends on live MCP connection
        # If the connection is already closed, suppress the error so we don't
        # turn a normal client disconnect into a tool failure.
        if is_connection_error(e):
            logger.info(
                "Suppressing final progress report error for %s due to connection issue: %s",
                tool_name or "<unknown>",
                e,
            )
            return
        logger.debug(
            "Final progress report for %s failed with unexpected error: %s",
            tool_name or "<unknown>",
            e,
        )


def _prepare_execution_context(
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
    kind: HandlerKind,
    enable_progress: bool,
    func_name: str,
) -> tuple[
    TrackedSemaphore,
    float,
    MCPToolArguments,
    JsonValue | None,
    asyncio.Task[None] | None,
    int,
]:
    """Prepare execution context for retry and record.

    Returns:
        Tuple of (semaphore, effective_timeout, kwargs_model, ctx, progress_task, start_ns)
    """
    semaphore = (
        get_resource_semaphore() if kind == HandlerKind.RESOURCE else get_semaphore()
    )
    effective_timeout, kwargs_model, ctx = _stability_params(
        timeout, stability_timeout, kwargs
    )
    progress_task = _create_progress_task_if_needed(
        enable_progress, ctx, effective_timeout, func_name
    )
    start_ns = time.perf_counter_ns()
    return semaphore, effective_timeout, kwargs_model, ctx, progress_task, start_ns


async def _finalize_execution(
    progress_task: asyncio.Task[None] | None,
    ctx: JsonValue | None,
    func_name: str,
    start_ns: int,
    was_cancelled: bool,
    success: bool,
    error_type: str | None,
    kind: HandlerKind,
    retry_count: int | None = None,
    param_validation_failure: str | None = None,
) -> None:  # Finalize execution: cancel progress and record usage.
    if not was_cancelled:
        await _cancel_progress_and_report_done(progress_task, ctx, func_name)
    await record_usage_finish(
        func_name,
        start_ns,
        success,
        error_type,
        kind=kind,
        retry_count=retry_count,
        param_validation_failure=param_validation_failure,
    )


async def _handle_cancellation(
    progress_task: asyncio.Task[None] | None,
) -> tuple[bool, str, bool]:
    """Handle cancellation exception.

    Args:
        progress_task: Progress task to cancel

    Returns:
        Tuple of (success=False, error_type="CancelledError", was_cancelled=True)
    """
    if progress_task is not None:
        await cancel_and_drain_progress_task(progress_task)
    return False, "CancelledError", True


async def _execute_with_error_handling[T](
    func: Callable[..., Awaitable[T]],
    semaphore: TrackedSemaphore,
    effective_timeout: float,
    args: tuple[JsonValue, ...],
    kwargs_model: MCPToolArguments,
    ctx: JsonValue | None,
    progress_task: asyncio.Task[None] | None,
) -> tuple[T, bool, str | None, bool, int | None, str | None]:
    """Execute function with retry and handle exceptions.

    Returns:
        Tuple of (result, success, error_type, was_cancelled, retry_count, param_validation_failure)
    """
    success, error_type, was_cancelled = True, None, False
    try:
        result, attempt = await _execute_with_retry(
            func, semaphore, effective_timeout, args, kwargs_model, ctx
        )
        retry_count = attempt - 1 if attempt else 0
        return result, success, error_type, was_cancelled, retry_count, None
    except asyncio.CancelledError:
        success, error_type, was_cancelled = await _handle_cancellation(progress_task)
        return (
            cast(T, CANCELLED_RESPONSE_JSON),
            success,
            error_type,
            was_cancelled,
            None,
            None,
        )
    except Exception as e:
        success, error_type = False, type(e).__name__
        raise


async def _run_and_finalize[T](
    execute_fn: Callable[
        [], Awaitable[tuple[T, bool, str | None, bool, int | None, str | None]]
    ],
    progress_task: asyncio.Task[None] | None,
    ctx: JsonValue | None,
    func_name: str,
    start_ns: int,
    kind: HandlerKind,
    use_serial_semaphore: bool = False,
) -> T:
    """Run execute_fn and finalize (cancel progress, record usage)."""
    return await run_and_finalize_impl(
        _finalize_execution,
        execute_fn,
        progress_task,
        ctx,
        func_name,
        start_ns,
        kind,
        use_serial_semaphore,
    )


async def _run_with_retry_and_record[T](
    func: Callable[..., Awaitable[T]],
    args: tuple[JsonValue, ...],
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
    kind: HandlerKind = HandlerKind.TOOL,
    enable_progress: bool = False,
) -> T:
    """Run func with retry and record usage. Long-running tools are serialized."""
    semaphore, effective_timeout, kwargs_model, ctx, progress_task, start_ns = (
        _prepare_execution_context(
            timeout, stability_timeout, kwargs, kind, enable_progress, func.__name__
        )
    )

    async def _execute_and_finalize() -> tuple[
        T, bool, str | None, bool, int | None, str | None
    ]:
        return await _execute_with_error_handling(
            func, semaphore, effective_timeout, args, kwargs_model, ctx, progress_task
        )

    return await _run_and_finalize(
        _execute_and_finalize,
        progress_task,
        ctx,
        func.__name__,
        start_ns,
        kind,
        use_serial_semaphore=(
            kind == HandlerKind.TOOL and func.__name__ in long_running_tools_serialized
        ),
    )


async def with_mcp_stability[T](
    func: Callable[..., Awaitable[T]],
    *args: JsonValue,  # pyright: ignore[reportUnknownParameterType]
    timeout: JsonValue | None = None,
    stability_timeout: JsonValue | None = None,
    kind: HandlerKind = HandlerKind.TOOL,
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
        kind: HandlerKind for usage recording (default HandlerKind.TOOL)
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
                kind=HandlerKind.TOOL,
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
    health) and usage recording with HandlerKind.RESOURCE. Does not run
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
                kind=HandlerKind.RESOURCE,
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
        kind=HandlerKind.TOOL,
        enable_progress=False,
        **kwargs_clean,
    )


async def check_connection_health() -> ConnectionHealth:
    """Check MCP connection health status.

    Returns:
        Connection health metrics (includes long_running_holder for diagnostics).
    """
    semaphore = get_semaphore()
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
        long_running_holder=get_long_running_semaphore_holder(),
    )
