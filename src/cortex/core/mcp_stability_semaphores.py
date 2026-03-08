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
# commit-pipeline calls succeed when the first run includes tests.
LONG_RUNNING_SEMAPHORE_WAIT_SECONDS = 330.0
# Max seconds a long-running tool may hold the semaphore before auto-release. Must allow
# one full execute_pre_commit_checks (including tests, test_timeout up to 300s default);
# use >= LONG_RUNNING_SEMAPHORE_WAIT_SECONDS so a single Step 12 run is not cut off mid-run.
LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS = 330.0
_LONG_RUNNING_BUSY_MSG = (
    "Another long-running tool is in progress (e.g. execute_pre_commit_checks or "
    "fix_markdown_lint). Please wait for it to finish (up to 5–6 minutes) and retry."
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
_long_running_tools_semaphore: TrackedSemaphore | None = None
_long_running_semaphore_holder: str | None = None
_long_running_start_time: float | None = None
_long_running_released_by_timeout: bool = False
_long_running_auto_release_task: asyncio.Task[None] | None = None


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


def set_long_running_semaphore_holder(tool_name: str | None) -> None:
    """Set or clear the name of the tool currently holding the long-running semaphore."""
    global _long_running_semaphore_holder, _long_running_start_time
    _long_running_semaphore_holder = tool_name
    _long_running_start_time = time.monotonic() if tool_name else None


def get_long_running_semaphore_holder() -> str | None:
    """Return the name of the tool holding the long-running semaphore, or None."""
    return _long_running_semaphore_holder


def get_long_running_elapsed_seconds() -> float | None:
    """Return seconds since the long-running tool acquired the semaphore, or None."""
    if _long_running_semaphore_holder is None or _long_running_start_time is None:
        return None
    return time.monotonic() - _long_running_start_time


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
    elapsed = (
        time.monotonic() - _long_running_start_time
        if _long_running_start_time is not None
        else None
    )
    global _long_running_released_by_timeout
    try:
        get_long_running_semaphore().release()
        set_long_running_semaphore_holder(None)
        _long_running_released_by_timeout = True
        _logger.info(
            "long_running_semaphore: auto-released after %.0fs (holder=%s elapsed_sec=%s)",
            LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS,
            tool_name,
            f"{elapsed:.1f}" if elapsed is not None else "n/a",
        )
    except Exception as e:
        _logger.error(
            "long_running_semaphore: auto-release failed for %s: %s",
            tool_name,
            e,
        )


def schedule_long_running_auto_release(tool_name: str) -> None:
    """Schedule force-release of the long-running semaphore after max hold time (330s)."""
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
