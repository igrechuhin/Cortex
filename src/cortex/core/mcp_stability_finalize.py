"""Run-and-finalize and usage recording for MCP stability.

Extracted from mcp_stability_config for file size compliance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import NoReturn, cast

from cortex.core.mcp_async_utils import cancel_and_drain_progress_task
from cortex.core.mcp_stability_semaphores import (
    acquire_long_running_semaphore,
    release_long_running_semaphore,
    release_semaphore_and_cancel_progress_if_needed,
)
from cortex.core.models import HandlerKind
from cortex.managers.usage_tracker import UsageTracker

_logger = logging.getLogger(__name__)


def _release_lr_for_cancel(fn: str, we: bool) -> None:
    """Release long-running semaphore (used by release_semaphore_and_cancel_progress_if_needed)."""
    release_long_running_semaphore(fn, was_exception=we)


def attach_attempt_to_exception(exc: Exception | None, attempt: int) -> None:
    """Attach attempt number for Phase 57 usage recording."""
    if exc is not None:
        object.__setattr__(exc, "attempt", attempt)


def param_validation_failure_from_exception(e: BaseException) -> str | None:
    """Extract short validation message for usage recording (Phase 57)."""
    if "Validation" not in type(e).__name__:
        return None
    return str(e)[:500]


async def _resolve_usage_tracker(
    managers: dict[str, object] | None,
) -> UsageTracker | None:
    """Resolve usage_tracker from managers; None if missing or not ready."""
    from cortex.managers.lazy_manager import LazyManager

    raw = managers.get("usage_tracker") if managers else None
    if raw is None:
        return None
    tracker = cast(object, await raw.get() if isinstance(raw, LazyManager) else raw)
    return tracker if isinstance(tracker, UsageTracker) else None


def _result_to_countable_string(result: object) -> str:
    """Convert tool result to string for token counting (Phase 62)."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, default=str)
    except (TypeError, ValueError):
        return str(result)


async def _count_response_tokens(result: object) -> int | None:
    """Count tokens in tool response; returns None on failure or missing counter."""
    from cortex.core.token_counter import TokenCounter
    from cortex.core.usage_context import get_current_managers
    from cortex.managers.lazy_manager import LazyManager

    managers = get_current_managers()
    if not managers:
        return None
    raw = managers.get("tokens")
    if raw is None:
        return None
    token_counter: TokenCounter | None = None
    if isinstance(raw, LazyManager):
        try:
            resolved = cast(object, await raw.get())
            token_counter = resolved if isinstance(resolved, TokenCounter) else None
        except Exception:
            return None
    elif isinstance(raw, TokenCounter):
        token_counter = raw
    else:
        return None
    if token_counter is None:
        return None
    try:
        text = _result_to_countable_string(result)
        return token_counter.count_tokens(text) if text else 0
    except Exception:
        return None


async def record_usage_if_available(
    tool_name: str,
    duration_ms: float,
    success: bool,
    error_type: str | None,
    kind: HandlerKind = HandlerKind.TOOL,
    retry_count: int | None = None,
    param_validation_failure: str | None = None,
    response_tokens: int | None = None,
) -> None:
    """Record tool or resource usage if UsageTracker is available."""
    from cortex.core.usage_context import get_current_managers

    try:
        tracker: UsageTracker | None = await _resolve_usage_tracker(
            get_current_managers()
        )
        if isinstance(tracker, UsageTracker):
            await tracker.record_tool_usage(
                tool_name=tool_name,
                duration_ms=duration_ms,
                success=success,
                error_type=error_type,
                handler_kind=kind,
                retry_count=retry_count,
                param_validation_failure=param_validation_failure,
                response_tokens=response_tokens,
            )
    except Exception as e:
        _logger.debug("Usage recording skipped or failed: %s (%s)", type(e).__name__, e)


async def record_usage_finish(
    tool_name: str,
    start_ns: int,
    success: bool,
    error_type: str | None,
    kind: HandlerKind,
    retry_count: int | None = None,
    param_validation_failure: str | None = None,
    response_tokens: int | None = None,
) -> None:
    """Record usage after tool run (duration and outcome)."""
    duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
    await record_usage_if_available(
        tool_name,
        duration_ms,
        success,
        error_type,
        kind=kind,
        retry_count=retry_count,
        param_validation_failure=param_validation_failure,
        response_tokens=response_tokens,
    )


async def finalize_on_exception(
    progress_task: asyncio.Task[None] | None,
    ctx: object,
    func_name: str,
    start_ns: int,
    kind: HandlerKind,
    e: Exception,
    finalize_fn: Callable[..., Awaitable[None]],
) -> None:
    """Record usage on exception path (Phase 57)."""
    rc = getattr(e, "attempt", 1) - 1
    pvf = param_validation_failure_from_exception(e)
    await finalize_fn(
        progress_task,
        ctx,
        func_name,
        start_ns,
        False,
        False,
        type(e).__name__,
        kind,
        retry_count=rc,
        param_validation_failure=pvf,
    )


async def _do_with_serial_semaphore[T](
    _do: Callable[[], Awaitable[T]], func_name: str
) -> T:
    """Run _do() with long-running semaphore acquired; release on exit."""
    _ = await acquire_long_running_semaphore(func_name)
    try:
        return await _do()
    finally:
        release_long_running_semaphore(func_name)


async def _release_serial_and_reraise(
    use_serial: bool,
    semaphore_acquired: bool,
    func_name: str,
    progress_task: asyncio.Task[None] | None,
    exc: BaseException,
) -> NoReturn:
    """Release semaphore and cancel progress if needed, then re-raise."""
    await release_semaphore_and_cancel_progress_if_needed(
        use_serial,
        semaphore_acquired,
        func_name,
        progress_task,
        _release_lr_for_cancel,
        cancel_and_drain_progress_task,
    )
    raise exc


async def _run_do_with_optional_serial[T](
    use_serial: bool,
    _do: Callable[[], Awaitable[T]],
    func_name: str,
) -> tuple[T, bool]:
    """Run _do with optional serial semaphore; return (result, semaphore_acquired)."""
    if use_serial:
        return (await _do_with_serial_semaphore(_do, func_name), True)
    return (await _do(), False)


async def _finalize_with_response_tokens(
    finalize_fn: Callable[..., Awaitable[None]],
    result: object,
    success: bool,
    progress_task: asyncio.Task[None] | None,
    ctx: object,
    func_name: str,
    start_ns: int,
    was_cancelled: bool,
    error_type: str | None,
    kind: HandlerKind,
    retry_count: int | None,
    param_validation_failure: str | None,
) -> None:
    """Compute response_tokens when success, then call finalize_fn."""
    response_tokens: int | None = (
        await _count_response_tokens(result) if success else None
    )
    await finalize_fn(
        progress_task,
        ctx,
        func_name,
        start_ns,
        was_cancelled,
        success,
        error_type,
        kind,
        retry_count=retry_count,
        param_validation_failure=param_validation_failure,
        response_tokens=response_tokens,
    )


async def _execute_then_finalize[T_run](
    finalize_fn: Callable[..., Awaitable[None]],
    execute_fn: Callable[
        [], Awaitable[tuple[T_run, bool, str | None, bool, int | None, str | None]]
    ],
    progress_task: asyncio.Task[None] | None,
    ctx: object,
    func_name: str,
    start_ns: int,
    kind: HandlerKind,
) -> T_run:
    """Execute and finalize on success; caller handles exceptions."""
    result, s, et, wc, retry_count, pvf = await execute_fn()
    await _finalize_with_response_tokens(
        finalize_fn,
        result,
        s,
        progress_task,
        ctx,
        func_name,
        start_ns,
        wc,
        et,
        kind,
        retry_count,
        pvf,
    )
    return result


async def run_execute_and_finalize[T_run](
    finalize_fn: Callable[..., Awaitable[None]],
    execute_fn: Callable[
        [], Awaitable[tuple[T_run, bool, str | None, bool, int | None, str | None]]
    ],
    progress_task: asyncio.Task[None] | None,
    ctx: object,
    func_name: str,
    start_ns: int,
    kind: HandlerKind,
) -> T_run:
    """Run execute_fn, then call finalize_fn (cancel progress, record usage)."""
    try:
        return await _execute_then_finalize(
            finalize_fn, execute_fn, progress_task, ctx, func_name, start_ns, kind
        )
    except Exception as e:
        await finalize_on_exception(
            progress_task, ctx, func_name, start_ns, kind, e, finalize_fn
        )
        raise


async def run_and_finalize_impl[T](
    finalize_fn: Callable[..., Awaitable[None]],
    execute_fn: Callable[
        [], Awaitable[tuple[T, bool, str | None, bool, int | None, str | None]]
    ],
    progress_task: asyncio.Task[None] | None,
    ctx: object,
    func_name: str,
    start_ns: int,
    kind: HandlerKind,
    use_serial_semaphore: bool,
) -> T:
    """Run execute_fn with optional serial semaphore; finalize and release on exception."""

    async def _do() -> T:
        return await run_execute_and_finalize(
            finalize_fn, execute_fn, progress_task, ctx, func_name, start_ns, kind
        )

    semaphore_acquired = False
    try:
        result, semaphore_acquired = await _run_do_with_optional_serial(
            use_serial_semaphore, _do, func_name
        )
        return result
    except BaseException as e:
        await _release_serial_and_reraise(
            use_serial_semaphore, semaphore_acquired, func_name, progress_task, e
        )


__all__ = [
    "attach_attempt_to_exception",
    "param_validation_failure_from_exception",
    "record_usage_finish",
    "record_usage_if_available",
    "run_and_finalize_impl",
    "run_execute_and_finalize",
]
