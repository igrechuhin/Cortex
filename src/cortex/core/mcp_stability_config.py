"""Configuration and shared state for MCP connection stability.

Holds tool sets, fallback messages, semaphores, and usage recording helpers
used by mcp_stability to avoid exceeding the main module file size limit.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import TYPE_CHECKING, NoReturn, cast

if TYPE_CHECKING:
    from cortex.managers.usage_tracker import UsageTracker

import anyio

from cortex.core.constants import (
    MCP_MAX_CONCURRENT_RESOURCES,
    MCP_MAX_CONCURRENT_TOOLS,
)
from cortex.core.mcp_async_utils import cancel_and_drain_progress_task
from cortex.core.models import HandlerKind, JsonValue


class TrackedSemaphore:
    """Semaphore wrapper that tracks available count."""

    def __init__(self, value: int) -> None:
        self._semaphore = asyncio.Semaphore(value)
        self._max_value = value
        self._current_count = value

    async def acquire(self) -> None:
        _ = await self._semaphore.acquire()
        self._current_count -= 1

    async def try_acquire(self, timeout: float = 0.0) -> bool:
        """Acquire if available within timeout (seconds). Return True if acquired."""
        try:
            _ = await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
            self._current_count -= 1
            return True
        except TimeoutError:
            return False

    def release(self) -> None:
        self._semaphore.release()
        self._current_count += 1

    async def __aenter__(self) -> TrackedSemaphore:
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()

    @property
    def available(self) -> int:
        return max(0, self._current_count)

    @property
    def current(self) -> int:
        return self._max_value - self.available


_concurrent_tools_semaphore: TrackedSemaphore | None = None
_concurrent_resources_semaphore: TrackedSemaphore | None = None
_long_running_tools_semaphore: TrackedSemaphore | None = None


def get_semaphore() -> TrackedSemaphore:
    """Get or create the global semaphore for concurrent tool limits."""
    global _concurrent_tools_semaphore
    if _concurrent_tools_semaphore is None:
        _concurrent_tools_semaphore = TrackedSemaphore(MCP_MAX_CONCURRENT_TOOLS)
    return _concurrent_tools_semaphore


def get_resource_semaphore() -> TrackedSemaphore:
    """Get or create the semaphore for concurrent resource read limits."""
    global _concurrent_resources_semaphore
    if _concurrent_resources_semaphore is None:
        _concurrent_resources_semaphore = TrackedSemaphore(MCP_MAX_CONCURRENT_RESOURCES)
    return _concurrent_resources_semaphore


def get_long_running_semaphore() -> TrackedSemaphore:
    """Return semaphore that allows only one long-running tool at a time."""
    global _long_running_tools_semaphore
    if _long_running_tools_semaphore is None:
        _long_running_tools_semaphore = TrackedSemaphore(1)
    return _long_running_tools_semaphore


# Track which tool holds the long-running semaphore (for diagnostics and health checks).
_long_running_semaphore_holder: str | None = None
# True if the semaphore was force-released by the 1-minute auto-release (so normal
# release path must not call sem.release() again).
_long_running_released_by_timeout: bool = False
# Scheduled task that force-releases the semaphore after LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS.
_long_running_auto_release_task: asyncio.Task[None] | None = None


def set_long_running_semaphore_holder(tool_name: str | None) -> None:
    """Set or clear the name of the tool currently holding the long-running semaphore."""
    global _long_running_semaphore_holder
    _long_running_semaphore_holder = tool_name


def get_long_running_semaphore_holder() -> str | None:
    """Return the name of the tool holding the long-running semaphore, or None."""
    return _long_running_semaphore_holder


def was_long_running_released_by_timeout() -> bool:
    """Return True if the long-running semaphore was force-released by the 1-minute auto-release."""
    return _long_running_released_by_timeout


def clear_long_running_released_by_timeout() -> None:
    """Clear the flag set when the long-running semaphore was force-released by timeout."""
    global _long_running_released_by_timeout
    _long_running_released_by_timeout = False


async def _run_auto_release_after_timeout(tool_name: str) -> None:
    """After LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS, force-release if still held by tool_name."""
    try:
        await asyncio.sleep(LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS)
    except asyncio.CancelledError:
        return
    global _long_running_semaphore_holder, _long_running_released_by_timeout
    if _long_running_semaphore_holder != tool_name:
        return
    try:
        get_long_running_semaphore().release()
        _long_running_semaphore_holder = None
        _long_running_released_by_timeout = True
        _logger.info(
            "long_running_semaphore: auto-released after %.0fs (holder was %s)",
            LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS,
            tool_name,
        )
    except Exception as e:
        _logger.error(
            "long_running_semaphore: auto-release failed for %s: %s",
            tool_name,
            e,
        )


def schedule_long_running_auto_release(tool_name: str) -> None:
    """Schedule force-release of the long-running semaphore after max hold time (1 minute)."""
    global _long_running_auto_release_task
    if (
        _long_running_auto_release_task is not None
        and not _long_running_auto_release_task.done()
    ):
        _ = _long_running_auto_release_task.cancel()
    _long_running_auto_release_task = asyncio.create_task(
        _run_auto_release_after_timeout(tool_name)
    )


def cancel_long_running_auto_release() -> None:
    """Cancel the scheduled auto-release task (call when releasing the semaphore normally)."""
    global _long_running_auto_release_task
    if _long_running_auto_release_task is not None:
        _ = _long_running_auto_release_task.cancel()
        _long_running_auto_release_task = None


# Tools that report their own progress; skip wrapper time-based progress.
_TOOLS_WITH_OWN_PROGRESS = frozenset({"fix_quality_issues"})
# Tools that need more frequent progress to prevent client idle timeout (-32000).
_TOOLS_NEEDING_FREQUENT_PROGRESS = frozenset(
    {"execute_pre_commit_checks", "fix_markdown_lint"}
)
# Long-running tools serialized (one at a time) so the connection does not break.
_LONG_RUNNING_TOOLS_SERIALIZED = frozenset(
    {"execute_pre_commit_checks", "fix_markdown_lint", "fix_quality_issues"}
)
# Max seconds a second long-running tool call will wait for the first to finish
# before failing with RuntimeError (reduces commit-blocking when calls are sequential).
# Must be >= default test_timeout for execute_pre_commit_checks (300s) so sequential
# commit-pipeline calls succeed when the first run includes tests.
LONG_RUNNING_SEMAPHORE_WAIT_SECONDS = 330.0
# Max seconds a long-running tool may hold the semaphore before auto-release (aligns with
# task_locking _DEFAULT_LOCK_TIMEOUT_HOURS = 1/60 = 1 minute) to prevent stuck holders.
LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS = 60.0
_LONG_RUNNING_BUSY_MSG = (
    "Another long-running tool is in progress (e.g. execute_pre_commit_checks or "
    "fix_markdown_lint). Please wait for it to finish (up to 5–6 minutes) and retry."
)
# Fallback steps in connection-error messages so the user can resolve without the tool.
_CONNECTION_ERROR_FALLBACK: dict[str, str] = {
    "execute_pre_commit_checks": (
        " Retry once. If still failing: run pre-commit locally (e.g. uv run pytest, ruff check, black .). "
        "See commit prompt Step 12 and docs/guides/troubleshooting.md."
    ),
    "fix_markdown_lint": (
        " Retry once. If still failing: run markdown lint locally "
        "(node_modules/.bin/markdownlint-cli2 --fix '**/*.md' '**/*.mdc'). "
        "See commit prompt Step 12.5 fallback and docs/guides/troubleshooting.md."
    ),
    "fix_quality_issues": (
        " Retry once. If still failing: run format/lint locally (black ., ruff check --fix). "
        "See docs/guides/troubleshooting.md."
    ),
}

_usage_context_init_lock: asyncio.Lock | None = None


def _get_usage_context_init_lock() -> asyncio.Lock:
    """Return the shared lock for usage context init (lazy-create for tests)."""
    global _usage_context_init_lock
    _usage_context_init_lock = _usage_context_init_lock or asyncio.Lock()
    return _usage_context_init_lock


# Connection retry overrides per tool (Blocker: MCP disconnects). Defaults use
# MCP_CONNECTION_RETRY_ATTEMPTS and MCP_CONNECTION_RETRY_DELAY_SECONDS from constants.
# fix_markdown_lint: 4 attempts (1 initial + 3 retries), exponential backoff 1s, 2s, 4s.
_CONNECTION_RETRY_OVERRIDES: dict[str, tuple[int, tuple[float, ...]]] = {
    "fix_markdown_lint": (4, (1.0, 2.0, 4.0)),
}


def get_connection_retry_attempts(tool_name: str) -> int:
    """Return max attempts (initial + retries) for connection retries for a tool."""
    from cortex.core.constants import MCP_CONNECTION_RETRY_ATTEMPTS

    if tool_name in _CONNECTION_RETRY_OVERRIDES:
        return _CONNECTION_RETRY_OVERRIDES[tool_name][0]
    return MCP_CONNECTION_RETRY_ATTEMPTS


def get_connection_retry_delay(tool_name: str, attempt: int) -> float:
    """Return delay in seconds before retry N (attempt is 1-based; delay before attempt 2, 3, ...)."""
    from cortex.core.constants import MCP_CONNECTION_RETRY_DELAY_SECONDS

    if tool_name in _CONNECTION_RETRY_OVERRIDES:
        _, delays = _CONNECTION_RETRY_OVERRIDES[tool_name]
        if 1 <= attempt <= len(delays):
            return delays[attempt - 1]
        return delays[-1] if delays else MCP_CONNECTION_RETRY_DELAY_SECONDS * attempt
    return MCP_CONNECTION_RETRY_DELAY_SECONDS * attempt


def is_connection_error(e: Exception) -> bool:
    """Return True if exception is connection-related (e.g. -32000, ClosedResourceError)."""
    connection_error_types = (
        ConnectionError,
        BrokenPipeError,
        OSError,
        anyio.BrokenResourceError,
        anyio.ClosedResourceError,
    )
    if isinstance(e, connection_error_types):
        return True
    if isinstance(e, RuntimeError):
        msg = str(e).lower()
        if "-32000" in str(e) or "connection closed" in msg or "connection" in msg:
            return True
    keywords = [
        "connection",
        "broken pipe",
        "connection reset",
        "tool not found",
        "resource",
        "stdio",
    ]
    return any(k in str(e).lower() for k in keywords)


def raise_final_error(func_name: str, last_exception: Exception | None) -> NoReturn:
    """Raise ConnectionError or RuntimeError after retries exhausted; never returns."""
    max_attempts = get_connection_retry_attempts(func_name)
    if last_exception and is_connection_error(last_exception):
        fallback = _CONNECTION_ERROR_FALLBACK.get(func_name, "")
        raise ConnectionError(
            f"MCP tool {func_name} failed after {max_attempts} attempts (connection)."
            + fallback
        ) from last_exception
    raise RuntimeError(
        f"MCP tool {func_name} failed after {max_attempts} attempts"
    ) from last_exception


def raise_if_retries_exhausted(
    func_name: str, last_exception: Exception | None
) -> NoReturn:
    """Raise final error after retries exhausted; never returns."""
    if last_exception:
        raise_final_error(func_name, last_exception)
    raise RuntimeError(f"MCP tool {func_name} failed unexpectedly")


# Public aliases for use by mcp_stability (avoid reportPrivateUsage).
connection_error_fallback = _CONNECTION_ERROR_FALLBACK
long_running_tools_serialized = _LONG_RUNNING_TOOLS_SERIALIZED
tools_needing_frequent_progress = _TOOLS_NEEDING_FREQUENT_PROGRESS
tools_with_own_progress = _TOOLS_WITH_OWN_PROGRESS


def get_usage_context_init_lock() -> asyncio.Lock:
    """Return the shared lock for usage context init (lazy-create for tests)."""
    return _get_usage_context_init_lock()


_logger = logging.getLogger(__name__)


async def acquire_long_running_semaphore(func_name: str) -> bool:
    """Acquire long-running semaphore with timeout. Returns True if acquired."""
    sem = get_long_running_semaphore()
    holder = get_long_running_semaphore_holder()
    _logger.info(
        "long_running_semaphore: %s waiting for semaphore (holder=%s, timeout=%.0fs)",
        func_name,
        holder or "none",
        LONG_RUNNING_SEMAPHORE_WAIT_SECONDS,
    )
    if not await sem.try_acquire(timeout=LONG_RUNNING_SEMAPHORE_WAIT_SECONDS):
        _logger.warning(
            "long_running_semaphore: %s wait timed out after %.0fs (holder=%s)",
            func_name,
            LONG_RUNNING_SEMAPHORE_WAIT_SECONDS,
            get_long_running_semaphore_holder() or "unknown",
        )
        raise RuntimeError(_LONG_RUNNING_BUSY_MSG)
    set_long_running_semaphore_holder(func_name)
    schedule_long_running_auto_release(func_name)
    _logger.info(
        "long_running_semaphore: %s acquired (was holder=%s)",
        func_name,
        holder or "none",
    )
    return True


def release_long_running_semaphore(func_name: str, was_exception: bool = False) -> None:
    """Release long-running semaphore if still held by func_name."""
    cancel_long_running_auto_release()
    current_holder = get_long_running_semaphore_holder()
    if current_holder != func_name:
        if was_long_running_released_by_timeout():
            clear_long_running_released_by_timeout()
        _logger.info(
            "long_running_semaphore: %s skip release (%s, holder=%s, was auto-released or changed)",
            func_name,
            "exception path" if was_exception else "normal path",
            current_holder or "none",
        )
    else:
        set_long_running_semaphore_holder(None)
        get_long_running_semaphore().release()
        _logger.info(
            "long_running_semaphore: %s released%s",
            func_name,
            " (exception path)" if was_exception else "",
        )


def to_timeout_value(value: JsonValue | None) -> float | None:
    """Convert JsonValue to float timeout in seconds; None if invalid."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            _logger.warning("Invalid timeout value %r, falling back to defaults", value)
            return None
    _logger.warning(
        "Unsupported timeout type %s, falling back to defaults", type(value)
    )
    return None


async def _resolve_usage_tracker(
    managers: dict[str, object] | None,
) -> UsageTracker | None:
    """Resolve usage_tracker from managers; None if missing or not ready."""
    from cortex.managers.lazy_manager import LazyManager
    from cortex.managers.usage_tracker import UsageTracker

    raw = managers.get("usage_tracker") if managers else None
    if raw is None:
        return None
    tracker = cast(object, await raw.get() if isinstance(raw, LazyManager) else raw)
    return tracker if isinstance(tracker, UsageTracker) else None


async def record_usage_if_available(
    tool_name: str,
    duration_ms: float,
    success: bool,
    error_type: str | None,
    kind: HandlerKind = HandlerKind.TOOL,
    retry_count: int | None = None,
    param_validation_failure: str | None = None,
) -> None:
    """Record tool or resource usage if UsageTracker is available."""
    from cortex.core.usage_context import get_current_managers
    from cortex.managers.usage_tracker import UsageTracker

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
    )


async def release_semaphore_and_cancel_progress_if_needed(
    use_serial_semaphore: bool,
    semaphore_acquired: bool,
    func_name: str,
    progress_task: asyncio.Task[None] | None,
    release_fn: Callable[[str, bool], None],
    cancel_fn: Callable[[asyncio.Task[None]], Awaitable[None]],
) -> None:
    """Release long-running semaphore and cancel progress task on exception path."""
    if use_serial_semaphore and semaphore_acquired:
        try:
            release_fn(func_name, True)
        except Exception as release_err:  # pragma: no cover
            _logger.error(
                "long_running_semaphore: failed to release after %s: %s",
                func_name,
                release_err,
            )
    if progress_task is not None and not progress_task.done():
        await cancel_fn(progress_task)


def attach_attempt_to_exception(exc: Exception | None, attempt: int) -> None:
    """Attach attempt number for Phase 57 usage recording."""
    if exc is not None:
        exc.attempt = attempt  # pyright: ignore[reportAttributeAccessIssue]


def param_validation_failure_from_exception(e: BaseException) -> str | None:
    """Extract short validation message for usage recording (Phase 57)."""
    if "Validation" not in type(e).__name__:
        return None
    return str(e)[:500]


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


def _release_lr_for_cancel(fn: str, we: bool) -> None:
    """Release long-running semaphore (used by release_semaphore_and_cancel_progress_if_needed)."""
    release_long_running_semaphore(fn, was_exception=we)


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
        result, s, et, wc, retry_count, pvf = await execute_fn()
        await finalize_fn(
            progress_task,
            ctx,
            func_name,
            start_ns,
            wc,
            s,
            et,
            kind,
            retry_count=retry_count,
            param_validation_failure=pvf,
        )
        return result
    except Exception as e:
        await finalize_on_exception(
            progress_task, ctx, func_name, start_ns, kind, e, finalize_fn
        )
        raise


__all__ = [
    "attach_attempt_to_exception",
    "run_and_finalize_impl",
    "TrackedSemaphore",
    "acquire_long_running_semaphore",
    "cancel_long_running_auto_release",
    "clear_long_running_released_by_timeout",
    "connection_error_fallback",
    "get_long_running_semaphore",
    "get_long_running_semaphore_holder",
    "LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS",
    "LONG_RUNNING_SEMAPHORE_WAIT_SECONDS",
    "schedule_long_running_auto_release",
    "set_long_running_semaphore_holder",
    "was_long_running_released_by_timeout",
    "get_resource_semaphore",
    "get_semaphore",
    "get_usage_context_init_lock",
    "long_running_tools_serialized",
    "record_usage_finish",
    "record_usage_if_available",
    "release_long_running_semaphore",
    "run_execute_and_finalize",
    "release_semaphore_and_cancel_progress_if_needed",
    "to_timeout_value",
    "tools_needing_frequent_progress",
    "tools_with_own_progress",
]
