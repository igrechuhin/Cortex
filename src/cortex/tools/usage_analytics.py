"""
Usage Analytics Tools (Phase 29)

MCP tools for querying MCP tool usage statistics and optimization recommendations.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.initialization import get_managers
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.usage_tracker import UsageTracker
from cortex.server import mcp


def _parse_date_range(
    start_date: str | None, end_date: str | None, default_days: int = 365
) -> tuple[datetime, datetime]:
    """Parse start/end date strings; default to default_days ago to now."""
    end = datetime.now(UTC)
    start = end - timedelta(days=default_days)
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    return start, end


def parse_date_range(
    start_date: str | None, end_date: str | None, default_days: int = 365
) -> tuple[datetime, datetime]:
    """Public wrapper around _parse_date_range for testing and callers."""
    return _parse_date_range(start_date, end_date, default_days)


async def _get_tracker(project_root: Path) -> UsageTracker | None:
    """Resolve UsageTracker for project root."""
    managers = await get_managers(project_root)
    raw: object = getattr(managers, "usage_tracker", None)
    if raw is None:
        return None
    if isinstance(raw, LazyManager):
        resolved: object = cast(object, await raw.get())
        return resolved if isinstance(resolved, UsageTracker) else None
    return raw if isinstance(raw, UsageTracker) else None


async def _get_usage_observation_impl(
    id: str,
    root: Path,
    tracker: UsageTracker | None,
) -> str:
    """Implementation helper for get_usage_observation."""
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"},
            indent=2,
        )
    event = await tracker.get_event_by_id(event_id=id)
    if event is None:
        return json.dumps(
            {
                "status": "error",
                "error": f"Usage event not found for id {id}",
                "error_type": "UsageEventNotFound",
                "id": id,
            },
            indent=2,
        )
    return json.dumps(
        {
            "status": "success",
            "project_root": str(root),
            "event": event.model_dump(),
        },
        indent=2,
    )


@mcp.tool(annotations=read_only_annotations("Get Usage Observation"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_observation(
    id: str,
    ctx: MCPContext | None = None,
) -> str:
    """Get a single usage observation by ID."""
    if ctx is not None:
        await log_client(ctx, "debug", f"get_usage_observation: starting id={id}")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    return await _get_usage_observation_impl(id=id, root=root, tracker=tracker)


@mcp.tool(annotations=read_only_annotations("Get Tool Usage Stats"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_stats(
    start_date: str | None = None,
    end_date: str | None = None,
    tool_name: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Get usage statistics for MCP tools.

    USE WHEN: User asks about tool usage, user needs usage analytics,
    user wants to see which tools are used most.

    EXAMPLES: 'get tool usage stats', 'show usage statistics',
    'which tools are used most'.

    RETURNS: JSON with tools list (total_calls, success rates, durations)
    and total_events.

    Args:
        start_date: Start of range (YYYY-MM-DD). Default: 365 days ago.
        end_date: End of range (YYYY-MM-DD). Default: today.
        tool_name: If set, filter to this tool only.

    Returns:
        JSON string with tools array and total_events.
    """
    if ctx is not None:
        await log_client(ctx, "debug", "get_tool_usage_stats: starting")
    root = await resolve_project_root_async(None, ctx)
    tracker: UsageTracker | None = await _get_tracker(root)
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"}
        )
    start, end = _parse_date_range(start_date, end_date, 365)
    result = await tracker.get_usage_stats(
        start_date=start, end_date=end, tool_name=tool_name
    )
    return json.dumps(
        {"status": "success", "project_root": str(root), **result},
        indent=2,
    )


@mcp.tool(annotations=read_only_annotations("Get Unused Tools"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_unused_tools(
    days: int = 90,
    min_usage_count: int = 0,
    ctx: MCPContext | None = None,
) -> str:
    """Identify unused or rarely-used MCP tools.

    USE WHEN: User wants to find unused tools, user asks which tools
    to deprecate, user needs optimization recommendations.

    EXAMPLES: 'get unused tools', 'which tools are rarely used',
    'tools to deprecate'.

    RETURNS: JSON with unused_tools list and parameters used.

    Args:
        days: Look back this many days (default: 90).
        min_usage_count: Tools with total_calls <= this are unused (default: 0).

    Returns:
        JSON string with unused_tools array.
    """
    if ctx is not None:
        await log_client(ctx, "debug", "get_unused_tools: starting")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"}
        )
    unused = await tracker.get_unused_tools(days=days, min_usage_count=min_usage_count)
    return json.dumps(
        {
            "status": "success",
            "project_root": str(root),
            "days": days,
            "min_usage_count": min_usage_count,
            "unused_tools": unused,
        },
        indent=2,
    )


def _calls_key(t: dict[str, object]) -> int:
    """Sort key for tools by total_calls descending."""
    v = t.get("total_calls", 0)
    return -(int(v) if isinstance(v, (int, float)) else 0)


def calls_key(t: dict[str, object]) -> int:
    """Public wrapper around _calls_key for testing and callers."""
    return _calls_key(t)


def _build_usage_report_text(
    tools: list[dict[str, object]], start: datetime, end: datetime, total: int
) -> str:
    """Build markdown report body from tools and date range."""
    lines = [
        "# MCP Tool Usage Report",
        "",
        f"Period: {start.date()} to {end.date()}",
        f"Total events: {total}",
        "",
        "## By tool",
        "",
    ]
    for t in sorted(tools, key=_calls_key):
        name = str(t.get("tool_name", "?"))
        calls_val = t.get("total_calls", 0)
        calls = int(calls_val) if isinstance(calls_val, (int, float)) else 0
        avg_val = t.get("avg_duration_ms", 0)
        avg_ms = float(avg_val) if isinstance(avg_val, (int, float)) else 0.0
        lines.append(f"- **{name}**: {calls} calls, avg {avg_ms:.1f} ms")
    return "\n".join(lines)


def build_usage_report_text(
    tools: list[dict[str, object]], start: datetime, end: datetime, total: int
) -> str:
    """Public wrapper around _build_usage_report_text for testing and callers."""
    return _build_usage_report_text(tools, start, end, total)


async def _fetch_report_data(
    tracker: UsageTracker,
    root: Path,
    start: datetime,
    end: datetime,
    include_recommendations: bool,
) -> dict[str, str | dict[str, object]]:
    """Fetch usage stats and build report dict; add recommendations if requested."""
    result = await tracker.get_usage_stats(start_date=start, end_date=end)
    _raw_list = cast(list[object], result.get("tools", []) or [])
    tools = [cast(dict[str, object], x) for x in _raw_list if isinstance(x, dict)]
    tot_val: object = result.get("total_events", 0)
    total = int(tot_val) if isinstance(tot_val, (int, float)) else 0
    report = _build_usage_report_text(tools, start, end, total)
    out: dict[str, str | dict[str, object]] = {
        "status": "success",
        "project_root": str(root),
        "report": report,
    }
    if include_recommendations:
        unused = await tracker.get_unused_tools(days=90, min_usage_count=5)
        out["recommendations"] = {
            "low_usage_tools": unused,
            "message": "Consider deprecating or consolidating low-usage tools.",
        }
    return out


@mcp.tool(annotations=read_only_annotations("Get Tool Usage Report"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_report(
    format: str = "markdown",
    include_recommendations: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Generate comprehensive usage report.

    USE WHEN: User wants a usage report, user needs summary of tool usage,
    user asks for optimization report.

    EXAMPLES: 'get tool usage report', 'usage report', 'tool usage summary'.

    RETURNS: JSON with report (markdown or raw) and optional recommendations.

    Args:
        format: 'markdown' or 'json' (default: markdown).
        include_recommendations: Include optimization recommendations (default: True).

    Returns:
        JSON string with report and optionally recommendations.
    """
    if ctx is not None:
        await log_client(ctx, "debug", "get_tool_usage_report: starting")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"}
        )
    start, end = _parse_date_range(None, None, 90)
    out = await _fetch_report_data(tracker, root, start, end, include_recommendations)
    return json.dumps(out, indent=2)


@mcp.tool(annotations=read_only_annotations("Get Optimization Recommendations"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_optimization_recommendations(
    min_usage_threshold: int = 5,
    days: int = 90,
    ctx: MCPContext | None = None,
) -> str:
    """Get recommendations for tool optimization.

    USE WHEN: User wants optimization recommendations, user asks which
    tools to consolidate or remove.

    EXAMPLES: 'get optimization recommendations', 'tool optimization',
    'which tools to deprecate'.

    RETURNS: JSON with low_usage_tools and reasoning.

    Args:
        min_usage_threshold: Tools with <= this many uses are candidates (default: 5).
        days: Look back this many days (default: 90).

    Returns:
        JSON string with low_usage_tools and message.
    """
    if ctx is not None:
        await log_client(ctx, "debug", "get_optimization_recommendations: starting")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"}
        )
    low_usage = await tracker.get_unused_tools(
        days=days, min_usage_count=min_usage_threshold
    )
    return json.dumps(
        {
            "status": "success",
            "project_root": str(root),
            "min_usage_threshold": min_usage_threshold,
            "days": days,
            "low_usage_tools": low_usage,
            "message": (
                "Tools with usage at or below threshold may be candidates "
                "for deprecation or consolidation."
            ),
        },
        indent=2,
    )


# Phase 43: Usage analytics resources (read-only, default params)


@mcp.resource(uri="cortex://usage/stats")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_stats_resource() -> str:
    """Resource: Tool usage statistics (default date range). Read via cortex://usage/stats."""
    return await get_tool_usage_stats(start_date=None, end_date=None, tool_name=None)


@mcp.resource(uri="cortex://usage/unused")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_unused_tools_resource() -> str:
    """Resource: Unused tools report (default days/min_usage). Read via cortex://usage/unused."""
    return await get_unused_tools(days=90, min_usage_count=0)


@mcp.resource(uri="cortex://usage/report")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_report_resource() -> str:
    """Resource: Usage report (default format and recommendations). Read via cortex://usage/report."""
    return await get_tool_usage_report(format="markdown", include_recommendations=True)


@mcp.resource(uri="cortex://usage/optimization-recommendations")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_optimization_recommendations_resource() -> str:
    """Resource: Optimization recommendations (default threshold/days). Read via cortex://usage/optimization-recommendations."""
    return await get_optimization_recommendations(min_usage_threshold=5, days=90)


@mcp.resource(uri="cortex://usage/observation/{id}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_observation_resource(id: str) -> str:
    """Resource: Usage observation by ID. Read via cortex://usage/observation/{id}."""
    return await get_usage_observation(id=id, ctx=None)
