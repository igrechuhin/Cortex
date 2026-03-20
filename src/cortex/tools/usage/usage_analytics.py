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


async def get_usage_tracker(project_root: Path) -> UsageTracker | None:
    """Public helper to resolve UsageTracker for project root."""
    return await _get_tracker(project_root)


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
# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_stats_resource() -> str:
    """Resource: Tool usage statistics (default date range). Read via cortex://usage/stats."""
    return await get_tool_usage_stats(start_date=None, end_date=None, tool_name=None)


# MCP resource registration removed
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


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_report_resource() -> str:
    """Resource: Usage report (default format and recommendations). Read via cortex://usage/report."""
    return await get_tool_usage_report(format="markdown", include_recommendations=True)


# MCP resource registration removed
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


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_observation_resource(id: str) -> str:
    """Resource: Usage observation by ID. Read via cortex://usage/observation/{id}."""
    return await get_usage_observation(id=id, ctx=None)


# Phase: query_usage Resources for 11 Uncovered Query Types
# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_anomalies_resource(hours: str) -> str:
    """Resource: Session tool anomalies (last N hours). Read via cortex://usage/anomalies/{hours}."""
    from urllib.parse import unquote

    from .query_handlers import run_anomalies
    from .query_models import QueryUsageParams

    try:
        h = int(unquote(hours))
    except (ValueError, TypeError):
        h = 24
    params = QueryUsageParams(hours=h)
    return await run_anomalies(params, None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_optimization_resource(tool_name: str) -> str:
    """Resource: Tool description optimization. Read via cortex://usage/tool-optimization/{tool_name}."""
    from urllib.parse import unquote

    from .query_handlers import run_tool_description_optimization
    from .query_models import QueryUsageParams

    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    days = config.get("days", 90)
    decoded = unquote(tool_name)
    params = QueryUsageParams(tool_name=decoded, days=days)
    return await run_tool_description_optimization(params, None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_events_resource() -> str:
    """Resource: Recent usage events (limit 50). Read via cortex://usage/events."""
    return await search_usage(limit=50, ctx=None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_search_resource(query: str) -> str:
    """Resource: Search usage events. Read via cortex://usage/search/{query}."""
    from urllib.parse import unquote

    decoded = unquote(query) if query else ""
    return await search_usage(query=decoded, limit=50, ctx=None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_timeline_resource(around_id: str) -> str:
    """Resource: Usage timeline around observation ID. Read via cortex://usage/timeline/{around_id}."""
    from urllib.parse import unquote

    decoded = unquote(around_id) if around_id else ""
    return await get_usage_timeline(around_id=decoded, limit=20, ctx=None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_production_monitoring_resource() -> str:
    """Resource: Production monitoring metrics. Read via cortex://usage/production-monitoring."""
    from .query_handlers import run_production_monitoring
    from .query_models import QueryUsageParams

    params = QueryUsageParams()
    return await run_production_monitoring(params, None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_token_efficiency_resource() -> str:
    """Resource: Token efficiency metrics. Read via cortex://usage/token-efficiency."""
    from .query_handlers import run_token_efficiency
    from .query_models import QueryUsageParams

    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    days = config.get("days", 90)
    params = QueryUsageParams(days=days)
    return await run_token_efficiency(params, None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_redundancy_resource() -> str:
    """Resource: Redundant tool call detection. Read via cortex://usage/redundancy."""
    from .query_handlers import run_redundancy
    from .query_models import QueryUsageParams

    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    days = config.get("days", 90)
    params = QueryUsageParams(days=days)
    return await run_redundancy(params, None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_session_continuity_resource() -> str:
    """Resource: Session continuity score. Read via cortex://usage/session-continuity."""
    from .query_handlers import run_session_continuity
    from .query_models import QueryUsageParams

    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    days = config.get("days", 90)
    params = QueryUsageParams(days=days)
    return await run_session_continuity(params, None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_frequency_resource() -> str:
    """Resource: Tool frequency metrics. Read via cortex://usage/tool-frequency."""
    from .query_handlers import run_tool_frequency
    from .query_models import QueryUsageParams

    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    days = config.get("days", 90)
    params = QueryUsageParams(days=days)
    return await run_tool_frequency(params, None)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_classification_resource() -> str:
    """Resource: Tool classification by usage and category. Read via cortex://usage/tool-classification."""
    from .query_handlers import run_tool_classification
    from .query_models import QueryUsageParams

    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    days = config.get("days", 90)
    params = QueryUsageParams(days=days)
    return await run_tool_classification(params, None)
