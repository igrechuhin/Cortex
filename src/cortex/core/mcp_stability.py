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
from typing import Any, Literal, Protocol, cast

import anyio

from cortex.core.constants import (
    MCP_CONNECTION_RETRY_ATTEMPTS,
    MCP_CONNECTION_RETRY_DELAY_SECONDS,
    MCP_MAX_CONCURRENT_TOOLS,
    MCP_TOOL_TIMEOUT_SECONDS,
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
    connection_error_fallback,
    get_long_running_semaphore,
    get_resource_semaphore,
    get_semaphore,
    get_usage_context_init_lock,
    long_running_tools_serialized,
    record_usage_finish,
    to_timeout_value,
    tools_needing_frequent_progress,
    tools_with_own_progress,
)
from cortex.core.models import ConnectionHealth, JsonValue, MCPToolArguments
from cortex.core.usage_context import get_current_managers, set_current_managers

logger = logging.getLogger(__name__)


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
        lock = get_usage_context_init_lock()
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
        fallback = connection_error_fallback.get(func_name, "")
        base_msg = f"MCP tool {func_name} failed after {attempt} attempts (connection)."
        error: RuntimeError | ConnectionError = (
            ConnectionError(base_msg + fallback)
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
    )

    if isinstance(e, connection_error_types):
        return True

    # RuntimeError only when MCP/client reports connection closed (e.g. -32000)
    if isinstance(e, RuntimeError):
        msg = str(e).lower()
        if "-32000" in str(e) or "connection closed" in msg or "connection" in msg:
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
    """Raise ConnectionError or RuntimeError after retries exhausted.

    Connection errors include fallback steps so the user can resolve without the tool.
    """
    if last_exception and _is_connection_error(last_exception):
        fallback = connection_error_fallback.get(func_name, "")
        raise ConnectionError(
            f"MCP tool {func_name} failed after "
            + f"{MCP_CONNECTION_RETRY_ATTEMPTS} attempts (connection)."
            + fallback
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
    """Execute function with retry logic for transient failures.

    Handles cancellation gracefully: if the client cancels the request,
    we re-raise CancelledError immediately without retrying or sending
    responses, preventing "duplicate response suppressed" errors.
    """
    last_exception: Exception | None = None
    func_name = func.__name__

    for attempt in range(1, MCP_CONNECTION_RETRY_ATTEMPTS + 1):
        try:
            return await _execute_single_attempt(
                func, semaphore, timeout, args, kwargs, ctx
            )
        except asyncio.CancelledError:
            # Client cancelled the request - re-raise immediately without retrying
            # This prevents the MCP SDK from trying to send a response for a cancelled
            # request, which causes "duplicate response suppressed" errors and connection
            # issues. Cancellation is not retryable.
            logger.debug(
                "Request for %s was cancelled by client (attempt %d/%d)",
                func_name,
                attempt,
                MCP_CONNECTION_RETRY_ATTEMPTS,
            )
            raise
        except Exception as e:
            _, last_exception = await _handle_retry_exception(
                func_name, timeout, attempt, e, last_exception
            )
        await _retry_path_health_and_recovery(func_name, attempt, last_exception)

    if last_exception:
        _raise_final_error(func_name, last_exception)
    raise RuntimeError(f"MCP tool {func_name} failed unexpectedly")


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
        if _is_connection_error(e):
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
        if _is_connection_error(e):
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
    kind: Literal["tool", "resource"],
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
    semaphore = get_resource_semaphore() if kind == "resource" else get_semaphore()
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
    kind: Literal["tool", "resource"],
) -> None:  # Finalize execution: cancel progress and record usage.
    if not was_cancelled:
        await _cancel_progress_and_report_done(progress_task, ctx, func_name)
    await record_usage_finish(func_name, start_ns, success, error_type, kind=kind)


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
) -> tuple[T, bool, str | None, bool]:
    """Execute function with retry and handle exceptions.

    Returns:
        Tuple of (result, success, error_type, was_cancelled)
    """
    success, error_type, was_cancelled = True, None, False
    try:
        result = await _execute_with_retry(
            func, semaphore, effective_timeout, args, kwargs_model, ctx
        )
        return result, success, error_type, was_cancelled
    except asyncio.CancelledError:
        success, error_type, was_cancelled = await _handle_cancellation(progress_task)
        raise
    except Exception as e:
        success, error_type = False, type(e).__name__
        raise


async def _run_and_finalize[T](
    execute_fn: Callable[[], Awaitable[tuple[T, bool, str | None, bool]]],
    progress_task: asyncio.Task[None] | None,
    ctx: JsonValue | None,
    func_name: str,
    start_ns: int,
    kind: Literal["tool", "resource"],
    use_serial_semaphore: bool = False,
) -> T:
    """Run execute_fn and finalize (cancel progress, record usage)."""

    async def _do() -> T:
        result, s, et, wc = await execute_fn()
        await _finalize_execution(
            progress_task, ctx, func_name, start_ns, wc, s, et, kind
        )
        return result

    if use_serial_semaphore:
        async with get_long_running_semaphore():
            return await _do()
    return await _do()


async def _run_with_retry_and_record[T](
    func: Callable[..., Awaitable[T]],
    args: tuple[JsonValue, ...],
    timeout: JsonValue | None,
    stability_timeout: JsonValue | None,
    kwargs: dict[str, JsonValue],
    kind: Literal["tool", "resource"] = "tool",
    enable_progress: bool = False,
) -> T:
    """Run func with retry and record usage. Long-running tools are serialized."""
    semaphore, effective_timeout, kwargs_model, ctx, progress_task, start_ns = (
        _prepare_execution_context(
            timeout, stability_timeout, kwargs, kind, enable_progress, func.__name__
        )
    )

    async def _execute_and_finalize() -> tuple[T, bool, str | None, bool]:
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
            kind == "tool" and func.__name__ in long_running_tools_serialized
        ),
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
    )
