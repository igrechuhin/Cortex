"""
Usage Analytics Tools (Phase 29)

MCP tools for querying MCP tool usage statistics and optimization recommendations.

Phase 9.1.14: Extracted models, formatters, and impl to analytics_models,
analytics_formatters, analytics_impl for file size compliance.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.initialization import get_managers
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.usage_tracker import UsageTracker, get_tool_optimization_config
from cortex.server import mcp
from cortex.tools.usage.analytics_formatters import (
    format_search_usage_response,
    format_tool_usage_stats_response,
)
from cortex.tools.usage.analytics_impl import (
    fetch_report_data,
    get_usage_events_impl,
    get_usage_observation_impl,
    get_usage_timeline_impl,
    search_usage_impl,
)


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


def _normalize_ids(ids: list[str]) -> list[str]:
    """Normalize requested IDs while preserving order."""
    return [i for i in ids if i]


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


# Tool consolidated into query_usage (Phase 50); kept as callable for dispatch.
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
    return await get_usage_observation_impl(id=id, root=root, tracker=tracker)


# Tool consolidated into query_usage (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_events(
    ids: list[str],
    ctx: MCPContext | None = None,
) -> str:
    """Get full usage events for a list of observation IDs."""
    if ctx is not None:
        await log_client(ctx, "debug", f"get_usage_events: starting ids={len(ids)}")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    normalized = _normalize_ids(ids)
    return await get_usage_events_impl(
        root=root, tracker=tracker, normalized_ids=normalized
    )


# Tool consolidated into query_usage (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_stats(
    start_date: str | None = None,
    end_date: str | None = None,
    tool_name: str | None = None,
    response_format: ResponseFormat = ResponseFormat.CONCISE,
    ctx: MCPContext | None = None,
) -> str:
    """Get usage statistics for MCP tools."""
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
    return format_tool_usage_stats_response(root, result, response_format)


# Tool consolidated into query_usage (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_unused_tools(
    days: int = 90,
    min_usage_count: int = 0,
    ctx: MCPContext | None = None,
) -> str:
    """Identify unused or rarely-used MCP tools."""
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


# Tool consolidated into query_usage (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def search_usage(
    start_date: str | None = None,
    end_date: str | None = None,
    tool_name: str | None = None,
    success: bool | None = None,
    limit: int = 50,
    query: str | None = None,
    response_format: ResponseFormat = ResponseFormat.CONCISE,
    ctx: MCPContext | None = None,
) -> str:
    """Search usage events and return a compact index."""
    if ctx is not None:
        await log_client(ctx, "debug", "search_usage: starting")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"}
        )
    start, end = _parse_date_range(start_date, end_date, 365)
    payload = await search_usage_impl(
        tracker=tracker,
        root=root,
        start=start,
        end=end,
        tool_name=tool_name,
        success=success,
        limit=limit,
        query=query,
    )
    return format_search_usage_response(root, payload, response_format)


# Tool consolidated into query_usage (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_timeline(
    around_id: str,
    limit: int = 20,
    ctx: MCPContext | None = None,
) -> str:
    """Get chronological usage context around a given observation ID."""
    if ctx is not None:
        await log_client(ctx, "debug", f"get_usage_timeline: starting id={around_id}")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    return await get_usage_timeline_impl(
        around_id=around_id,
        limit=limit,
        root=root,
        tracker=tracker,
    )


# Tool consolidated into query_usage (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_report(
    format: str = "markdown",
    include_recommendations: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Generate comprehensive usage report."""
    if ctx is not None:
        await log_client(ctx, "debug", "get_tool_usage_report: starting")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"}
        )
    start, end = _parse_date_range(None, None, 90)
    out = await fetch_report_data(tracker, root, start, end, include_recommendations)
    return json.dumps(out, indent=2)


# Tool consolidated into query_usage (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_optimization_recommendations(
    min_usage_threshold: int = 5,
    days: int = 90,
    ctx: MCPContext | None = None,
) -> str:
    """Get recommendations for tool optimization."""
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
    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    return await get_unused_tools(
        days=config["days"],
        min_usage_count=config["min_usage_count"],
        ctx=None,
    )


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
    """Resource: Optimization recommendations. Read via cortex://usage/optimization-recommendations."""
    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    return await get_optimization_recommendations(
        min_usage_threshold=config["min_usage_threshold"],
        days=config["days"],
        ctx=None,
    )


@mcp.resource(uri="cortex://usage/observation/{id}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_observation_resource(id: str) -> str:
    """Resource: Usage observation by ID. Read via cortex://usage/observation/{id}."""
    return await get_usage_observation(id=id, ctx=None)
