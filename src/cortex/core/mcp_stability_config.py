"""Configuration and shared state for MCP connection stability.

Holds tool sets, fallback messages, semaphores, and usage recording helpers
used by mcp_stability to avoid exceeding the main module file size limit.
"""

import asyncio
import logging
import time
from types import TracebackType
from typing import Literal, cast

from cortex.core.constants import (
    MCP_MAX_CONCURRENT_RESOURCES,
    MCP_MAX_CONCURRENT_TOOLS,
)
from cortex.core.models import JsonValue


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

    async def __aenter__(self) -> "TrackedSemaphore":
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
# Fallback steps in connection-error messages so the user can resolve without the tool.
_CONNECTION_ERROR_FALLBACK: dict[str, str] = {
    "execute_pre_commit_checks": (
        " Retry once. If still failing: run pre-commit locally (e.g. uv run pytest, ruff check, black .). "
        "See commit prompt Step 12 and docs/guides/troubleshooting.md."
    ),
    "fix_markdown_lint": (
        " Retry once. If still failing: run markdown lint locally (npx markdownlint-cli2 ... or npm script). "
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


# Public aliases for use by mcp_stability (avoid reportPrivateUsage).
connection_error_fallback = _CONNECTION_ERROR_FALLBACK
long_running_tools_serialized = _LONG_RUNNING_TOOLS_SERIALIZED
tools_needing_frequent_progress = _TOOLS_NEEDING_FREQUENT_PROGRESS
tools_with_own_progress = _TOOLS_WITH_OWN_PROGRESS


def get_usage_context_init_lock() -> asyncio.Lock:
    """Return the shared lock for usage context init (lazy-create for tests)."""
    return _get_usage_context_init_lock()


_logger = logging.getLogger(__name__)


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


async def record_usage_if_available(
    tool_name: str,
    duration_ms: float,
    success: bool,
    error_type: str | None,
    kind: Literal["tool", "resource"] = "tool",
) -> None:
    """Record tool or resource usage if UsageTracker is available."""
    from cortex.core.usage_context import get_current_managers
    from cortex.managers.lazy_manager import LazyManager
    from cortex.managers.usage_tracker import UsageTracker

    try:
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
        _logger.debug("Usage recording skipped or failed: %s (%s)", type(e).__name__, e)


async def record_usage_finish(
    tool_name: str,
    start_ns: int,
    success: bool,
    error_type: str | None,
    kind: Literal["tool", "resource"],
) -> None:
    """Record usage after tool run (duration and outcome)."""
    duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0
    await record_usage_if_available(
        tool_name, duration_ms, success, error_type, kind=kind
    )


__all__ = [
    "TrackedSemaphore",
    "connection_error_fallback",
    "get_long_running_semaphore",
    "LONG_RUNNING_SEMAPHORE_WAIT_SECONDS",
    "get_resource_semaphore",
    "get_semaphore",
    "get_usage_context_init_lock",
    "long_running_tools_serialized",
    "record_usage_finish",
    "record_usage_if_available",
    "to_timeout_value",
    "tools_needing_frequent_progress",
    "tools_with_own_progress",
]
