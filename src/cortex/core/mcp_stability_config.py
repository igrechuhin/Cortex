"""Configuration and shared state for MCP connection stability.

Holds tool sets, fallback messages, and connection retry helpers.
Re-exports from mcp_stability_semaphores and mcp_stability_finalize for backward compatibility.
"""

from __future__ import annotations

import asyncio
import logging
from builtins import BaseExceptionGroup
from typing import NoReturn, cast

import anyio

# Re-exports from submodules
from cortex.core.mcp_stability_finalize import (
    attach_attempt_to_exception,
    record_usage_finish,
    record_usage_if_available,
    run_and_finalize_impl,
    run_execute_and_finalize,
)
from cortex.core.mcp_stability_semaphores import (
    LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS,
    LONG_RUNNING_SEMAPHORE_WAIT_SECONDS,
    TrackedSemaphore,
    acquire_long_running_semaphore,
    cancel_long_running_auto_release,
    clear_long_running_released_by_timeout,
    get_long_running_semaphore,
    get_long_running_semaphore_holder,
    get_resource_semaphore,
    get_semaphore,
    release_long_running_semaphore,
    release_semaphore_and_cancel_progress_if_needed,
    schedule_long_running_auto_release,
    set_long_running_semaphore_holder,
    was_long_running_released_by_timeout,
)
from cortex.core.models import JsonValue

_logger = logging.getLogger(__name__)

# Tools that report their own progress; skip wrapper time-based progress.
# Tools that manage their own progress reporting (test counts, etc.).
# Wrapper time-based progress is disabled for these tools to avoid
# conflicting or backwards progress updates on the client.
# Note: execute_pre_commit_checks was removed after switching to detached mode
# (run_checks_detached returns immediately; no in-process progress needed).
tools_with_own_progress: frozenset[str] = frozenset(
    {
        # run_quality_gate calls poll_for_result which sends tick/500 heartbeats.
        # The stability background loop sends pct/100 on the same ctx,
        # causing the client progress bar to jump between incompatible scales.
        # Registering here suppresses the stability loop so only one stream runs.
        "run_quality_gate",
    }
)
# Tools that need more frequent progress to prevent client idle timeout (-32000).
tools_needing_frequent_progress = frozenset({"fix_markdown_lint"})
# Long-running tools serialized (one at a time) so the connection does not break.
# Detached pipelines like execute_pre_commit_checks manage their own concurrency
# and progress; serializing them at the MCP wrapper layer can cause redundant
# waits when a detached worker is already running.
long_running_tools_serialized = frozenset({"fix_markdown_lint"})
# Default fallback when tool has no specific recovery steps.
_CONNECTION_ERROR_FALLBACK_DEFAULT = (
    " Reconnect Cortex MCP and retry. See docs/guides/troubleshooting.md"
    "#issue-mcp-error-32000-connection-closed for recovery steps."
)
# Tool-specific fallback steps in connection-error messages.
connection_error_fallback: dict[str, str] = {
    "execute_pre_commit_checks": (
        " Retry once. If still failing: run pre-commit locally (e.g. uv run pytest, ruff check, black .). "
        "See commit prompt Step 12 and docs/guides/troubleshooting.md."
    ),
    "fix_markdown_lint": (
        " Retry once. If still failing: run markdown lint locally with rumdl "
        "(for example: uv run rumdl check --fix .). "
        "See commit prompt Step 12.5 fallback and docs/guides/troubleshooting.md."
    ),
}

_usage_context_init_lock: asyncio.Lock | None = None


def _get_usage_context_init_lock() -> asyncio.Lock:
    """Return the shared lock for usage context init (lazy-create for tests)."""
    global _usage_context_init_lock
    _usage_context_init_lock = _usage_context_init_lock or asyncio.Lock()
    return _usage_context_init_lock


def get_usage_context_init_lock() -> asyncio.Lock:
    """Return the shared lock for usage context init (lazy-create for tests)."""
    return _get_usage_context_init_lock()


# Connection retry overrides per tool (Blocker: MCP disconnects). Defaults use
# MCP_CONNECTION_RETRY_ATTEMPTS and MCP_CONNECTION_RETRY_DELAY_SECONDS from constants.
# - fix_markdown_lint: 4 attempts (1 initial + 3 retries), exponential backoff 1s, 2s, 4s.
# Note: execute_pre_commit_checks was removed — it now returns immediately (detached mode)
# so retrying would spawn duplicate workers and is no longer needed.
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


_CONNECTION_MESSAGE_KEYWORDS: tuple[str, ...] = (
    "-32000",
    "connection closed",
    "connection reset",
    "connection refused",
    "broken pipe",
)


def _matches_connection_message(message: str) -> bool:
    msg = message.lower()
    return any(keyword in msg for keyword in _CONNECTION_MESSAGE_KEYWORDS)


def is_connection_error(exc: BaseException) -> bool:
    """Return True if exception is connection-related (e.g. -32000, ClosedResourceError)."""
    if isinstance(exc, BaseExceptionGroup):
        exc_group = cast(BaseExceptionGroup[BaseException], exc)
        return any(is_connection_error(nested) for nested in exc_group.exceptions)

    if isinstance(
        exc,
        (
            anyio.BrokenResourceError,
            anyio.ClosedResourceError,
            BrokenPipeError,
            ConnectionResetError,
            ConnectionError,
        ),
    ):
        return True

    if isinstance(exc, asyncio.CancelledError):
        return True

    if _matches_connection_message(str(exc)):
        return True

    return False


def raise_final_error(func_name: str, last_exception: Exception | None) -> NoReturn:
    """Raise ConnectionError or RuntimeError after retries exhausted; never returns."""
    max_attempts = get_connection_retry_attempts(func_name)
    if last_exception and is_connection_error(last_exception):
        fallback = connection_error_fallback.get(
            func_name, _CONNECTION_ERROR_FALLBACK_DEFAULT
        )
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
