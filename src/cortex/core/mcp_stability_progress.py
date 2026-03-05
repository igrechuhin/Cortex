"""Progress reporting for long-running MCP tool execution.

Extracted from mcp_stability for file size compliance.
"""

import asyncio
import logging
import time
from typing import cast

from cortex.core.constants import (
    PROGRESS_REPORT_INTERVAL_LONG_RUNNING_SECONDS,
    PROGRESS_REPORT_INTERVAL_SECONDS,
    PROGRESS_REPORT_INTERVAL_VERY_FREQUENT_SECONDS,
    PROGRESS_THRESHOLD_TIMEOUT_SECONDS,
)
from cortex.core.context_logging import MCPContext, report_progress_safe
from cortex.core.mcp_async_utils import cancel_and_drain_progress_task
from cortex.core.mcp_stability_config import (
    is_connection_error,
    tools_needing_frequent_progress,
    tools_with_own_progress,
)
from cortex.core.models import JsonValue

logger = logging.getLogger(__name__)


async def progress_report_loop(
    ctx: JsonValue,
    timeout_sec: float,
    tool_name: str,
) -> None:
    """Background task: report progress every N seconds (Phase 46)."""
    if tool_name in tools_needing_frequent_progress:
        interval = PROGRESS_REPORT_INTERVAL_VERY_FREQUENT_SECONDS
    elif timeout_sec >= 300:
        interval = PROGRESS_REPORT_INTERVAL_LONG_RUNNING_SECONDS
    else:
        interval = PROGRESS_REPORT_INTERVAL_SECONDS

    start = time.perf_counter()
    try:
        _ = await progress_report_step(ctx, timeout_sec, start, tool_name)
    except Exception as e:
        logger.debug(
            "Initial progress report for %s failed with unexpected error: %s",
            tool_name,
            e,
        )

    try:
        while True:
            await asyncio.sleep(interval)
            if not await progress_report_step(ctx, timeout_sec, start, tool_name):
                break
    except asyncio.CancelledError:
        logger.debug("Progress loop for %s cancelled", tool_name)
        raise


async def progress_report_step(
    ctx: JsonValue,
    timeout_sec: float,
    start: float,
    tool_name: str,
) -> bool:
    """Run a single progress-report step; return False when loop should stop."""
    elapsed = time.perf_counter() - start
    if elapsed >= timeout_sec:
        return False

    pct = min(95, int((elapsed / timeout_sec) * 100))
    mcp_ctx = cast(MCPContext | None, ctx)
    try:
        await report_progress_safe(mcp_ctx, float(pct), 100.0)
        return True
    except Exception as e:  # pragma: no cover
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


def create_progress_task_if_needed(
    enable_progress: bool,
    ctx: JsonValue | None,
    effective_timeout: float,
    tool_name: str,
) -> asyncio.Task[None] | None:
    """Create background progress task when enabled and ctx present (Phase 46)."""
    if tool_name in tools_with_own_progress:
        return None

    if (
        enable_progress
        and ctx is not None
        and effective_timeout >= PROGRESS_THRESHOLD_TIMEOUT_SECONDS
    ):
        return asyncio.create_task(
            progress_report_loop(ctx, effective_timeout, tool_name)
        )
    return None


async def cancel_progress_and_report_done(
    progress_task: asyncio.Task[None] | None,
    ctx: JsonValue | None,
    tool_name: str | None = None,
) -> None:
    """Cancel progress task and report 100% (Phase 46)."""
    if progress_task is None:
        return
    await cancel_and_drain_progress_task(progress_task)
    if tool_name is not None and tool_name in tools_with_own_progress:
        return
    mcp_ctx = cast(MCPContext | None, ctx)
    try:
        await report_progress_safe(mcp_ctx, 100.0, 100.0)
    except Exception as e:  # pragma: no cover
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
