"""Semaphores and long-running serialization for MCP stability.

Extracted from mcp_stability_config for file size compliance.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from types import TracebackType

from cortex.core.constants import (
    MCP_MAX_CONCURRENT_RESOURCES,
    MCP_MAX_CONCURRENT_TOOLS,
)

_logger = logging.getLogger(__name__)

# Max seconds a second long-running tool call will wait for the first to finish
# before failing with RuntimeError (reduces commit-blocking when calls are sequential).
# Must be >= default test_timeout for execute_pre_commit_checks (300s) so sequential
# commit-pipeline calls succeed when the first run includes tests. 600s allows Phase A
# (tests up to 300s + format/quality overhead) to complete before a waiting second call times out.
LONG_RUNNING_SEMAPHORE_WAIT_SECONDS = 600.0
# Max seconds a long-running tool may hold the semaphore before auto-release. Must allow
# one full execute_pre_commit_checks (including tests, test_timeout up to 300s default);
# use >= LONG_RUNNING_SEMAPHORE_WAIT_SECONDS so a single Step 12 run is not cut off mid-run.
LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS = 600.0
# After the main wait times out, retry once for this many seconds to absorb the race when
# the first call or auto-release releases at the same moment (reduces commit-blocking).
LONG_RUNNING_SEMAPHORE_RETRY_AFTER_TIMEOUT_SECONDS = 5.0
_LONG_RUNNING_BUSY_MSG = (
    "Another long-running tool is in progress (e.g. execute_pre_commit_checks or "
    "fix_markdown_lint). Please wait for it to finish (up to 10 minutes) and retry. "
    "If running the commit pipeline, ensure Phase A has completed before Step 12; "
    "close other tabs or agents that may be running long-running Cortex tools."
)


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
_long_running_tools_semaphore_map: dict[str, TrackedSemaphore] = {}
_long_running_semaphore_holder_map: dict[str, str] = {}
_long_running_start_time_map: dict[str, float] = {}
_long_running_released_by_timeout_map: dict[str, bool] = {}
_long_running_auto_release_task_map: dict[str, asyncio.Task[None]] = {}


def _normalize_lock_scope(lock_scope: str | None) -> str:
    """Normalize lock scope identifier."""
    return lock_scope or "__global__"


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


def get_long_running_semaphore(lock_scope: str | None = None) -> TrackedSemaphore:
    """Return per-scope semaphore for long-running tool serialization."""
    scope = _normalize_lock_scope(lock_scope)
    sem = _long_running_tools_semaphore_map.get(scope)
    if sem is None:
        sem = TrackedSemaphore(1)
        _long_running_tools_semaphore_map[scope] = sem
    return sem


def reset_long_running_tools_semaphore_for_testing() -> None:
    """Reset cached long-running semaphore state (tests only)."""
    _long_running_tools_semaphore_map.clear()
    _long_running_semaphore_holder_map.clear()
    _long_running_start_time_map.clear()
    _long_running_released_by_timeout_map.clear()
    for task in _long_running_auto_release_task_map.values():
        _ = task.cancel()
    _long_running_auto_release_task_map.clear()


def set_long_running_semaphore_holder(
    tool_name: str | None, lock_scope: str | None = None
) -> None:
    """Set or clear the name of the tool currently holding the scoped semaphore."""
    scope = _normalize_lock_scope(lock_scope)
    if tool_name is None:
        _ = _long_running_semaphore_holder_map.pop(scope, None)
        _ = _long_running_start_time_map.pop(scope, None)
        return
    _long_running_semaphore_holder_map[scope] = tool_name
    _long_running_start_time_map[scope] = time.monotonic()


def get_long_running_semaphore_holder(lock_scope: str | None = None) -> str | None:
    """Return the name of the tool holding the scoped long-running semaphore."""
    scope = _normalize_lock_scope(lock_scope)
    return _long_running_semaphore_holder_map.get(scope)


def get_long_running_elapsed_seconds(lock_scope: str | None = None) -> float | None:
    """Return seconds since scoped long-running semaphore was acquired."""
    scope = _normalize_lock_scope(lock_scope)
    if scope not in _long_running_semaphore_holder_map:
        return None
    start_time = _long_running_start_time_map.get(scope)
    if start_time is None:
        return None
    return time.monotonic() - start_time


def was_long_running_released_by_timeout(lock_scope: str | None = None) -> bool:
    """Return True if scoped semaphore was force-released by timeout."""
    scope = _normalize_lock_scope(lock_scope)
    return _long_running_released_by_timeout_map.get(scope, False)


def clear_long_running_released_by_timeout(lock_scope: str | None = None) -> None:
    """Clear scoped timeout-release marker."""
    scope = _normalize_lock_scope(lock_scope)
    _ = _long_running_released_by_timeout_map.pop(scope, None)


async def _run_auto_release_after_timeout(tool_name: str, lock_scope: str) -> None:
    """After max hold timeout, force-release semaphore if same scoped holder remains."""
    try:
        await asyncio.sleep(LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS)
    except asyncio.CancelledError:
        return
    if get_long_running_semaphore_holder(lock_scope) != tool_name:
        return
    elapsed = get_long_running_elapsed_seconds(lock_scope)
    try:
        get_long_running_semaphore(lock_scope).release()
        set_long_running_semaphore_holder(None, lock_scope)
        _long_running_released_by_timeout_map[lock_scope] = True
        _logger.info(
            "long_running_semaphore: auto-released after %.0fs (scope=%s holder=%s elapsed_sec=%s)",
            LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS,
            lock_scope,
            tool_name,
            f"{elapsed:.1f}" if elapsed is not None else "n/a",
        )
    except Exception as e:
        _logger.error(
            "long_running_semaphore: auto-release failed for %s: %s",
            tool_name,
            e,
        )


def schedule_long_running_auto_release(
    tool_name: str, lock_scope: str | None = None
) -> None:
    """Schedule force-release of scoped long-running semaphore after max hold time."""
    scope = _normalize_lock_scope(lock_scope)
    existing = _long_running_auto_release_task_map.get(scope)
    if existing is not None and not existing.done():
        _ = existing.cancel()
    _long_running_auto_release_task_map[scope] = asyncio.create_task(
        _run_auto_release_after_timeout(tool_name, scope)
    )


def cancel_long_running_auto_release(lock_scope: str | None = None) -> None:
    """Cancel scheduled scoped auto-release task."""
    scope = _normalize_lock_scope(lock_scope)
    task = _long_running_auto_release_task_map.pop(scope, None)
    if task is not None:
        _ = task.cancel()


async def _attempt_long_running_acquire(
    sem: TrackedSemaphore,
    func_name: str,
    holder: str | None,
) -> bool:
    _logger.info(
        "long_running_semaphore: %s waiting for semaphore (holder=%s, timeout=%.0fs)",
        func_name,
        holder or "none",
        LONG_RUNNING_SEMAPHORE_WAIT_SECONDS,
    )
    acquired = await sem.try_acquire(timeout=LONG_RUNNING_SEMAPHORE_WAIT_SECONDS)
    if acquired:
        return True
    _logger.info(
        "long_running_semaphore: %s main wait timed out; retrying up to %.0fs",
        func_name,
        LONG_RUNNING_SEMAPHORE_RETRY_AFTER_TIMEOUT_SECONDS,
    )
    return await sem.try_acquire(
        timeout=LONG_RUNNING_SEMAPHORE_RETRY_AFTER_TIMEOUT_SECONDS
    )


async def acquire_long_running_semaphore(
    func_name: str, lock_scope: str | None = None
) -> bool:
    """Acquire long-running semaphore with timeout. Returns True if acquired.

    If the main wait times out, one short retry is attempted to absorb the race
    when the holder releases or auto-release runs at the same moment.
    """
    scope = _normalize_lock_scope(lock_scope)
    sem = get_long_running_semaphore(scope)
    holder = get_long_running_semaphore_holder(scope)
    acquired = await _attempt_long_running_acquire(sem, func_name, holder)
    if not acquired:
        _logger.warning(
            "long_running_semaphore: %s wait timed out after %.0fs+%.0fs retry (holder=%s)",
            func_name,
            LONG_RUNNING_SEMAPHORE_WAIT_SECONDS,
            LONG_RUNNING_SEMAPHORE_RETRY_AFTER_TIMEOUT_SECONDS,
            get_long_running_semaphore_holder(scope) or "unknown",
        )
        raise RuntimeError(_LONG_RUNNING_BUSY_MSG)
    set_long_running_semaphore_holder(func_name, scope)
    schedule_long_running_auto_release(func_name, scope)
    _logger.info(
        "long_running_semaphore: %s acquired (scope=%s was holder=%s)",
        func_name,
        scope,
        holder or "none",
    )
    return True


def release_long_running_semaphore(
    func_name: str, was_exception: bool = False, lock_scope: str | None = None
) -> None:
    """Release scoped long-running semaphore if still held by func_name."""
    scope = _normalize_lock_scope(lock_scope)
    cancel_long_running_auto_release(scope)
    current_holder = get_long_running_semaphore_holder(scope)
    if current_holder != func_name:
        if was_long_running_released_by_timeout(scope):
            clear_long_running_released_by_timeout(scope)
        _logger.info(
            "long_running_semaphore: %s skip release (%s, scope=%s holder=%s, was auto-released or changed)",
            func_name,
            "exception path" if was_exception else "normal path",
            scope,
            current_holder or "none",
        )
    else:
        set_long_running_semaphore_holder(None, scope)
        get_long_running_semaphore(scope).release()
        _logger.info(
            "long_running_semaphore: %s released%s (scope=%s)",
            func_name,
            " (exception path)" if was_exception else "",
            scope,
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


__all__ = [
    "LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS",
    "LONG_RUNNING_SEMAPHORE_RETRY_AFTER_TIMEOUT_SECONDS",
    "LONG_RUNNING_SEMAPHORE_WAIT_SECONDS",
    "TrackedSemaphore",
    "acquire_long_running_semaphore",
    "cancel_long_running_auto_release",
    "clear_long_running_released_by_timeout",
    "get_long_running_elapsed_seconds",
    "get_long_running_semaphore",
    "get_long_running_semaphore_holder",
    "get_resource_semaphore",
    "get_semaphore",
    "release_long_running_semaphore",
    "release_semaphore_and_cancel_progress_if_needed",
    "schedule_long_running_auto_release",
    "set_long_running_semaphore_holder",
    "was_long_running_released_by_timeout",
]
