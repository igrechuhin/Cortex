"""MCP resource handlers for usage analytics (cortex://usage/...)."""

from __future__ import annotations

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.mcp_stability import ensure_usage_context, mcp_resource_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.usage_tracker import get_tool_optimization_config


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_stats_resource() -> str:
    """Resource: Tool usage statistics (default date range). Read via cortex://usage/stats."""
    from . import usage_analytics as ua

    return await ua.get_tool_usage_stats(start_date=None, end_date=None, tool_name=None)


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_unused_tools_resource() -> str:
    """Resource: Unused tools report (default days/min_usage). Read via cortex://usage/unused."""
    from . import usage_analytics as ua

    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    return await ua.get_unused_tools(
        days=config["days"],
        min_usage_count=config["min_usage_count"],
        ctx=None,
    )


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_report_resource() -> str:
    """Resource: Usage report (default format and recommendations). Read via cortex://usage/report."""
    from . import usage_analytics as ua

    return await ua.get_tool_usage_report(
        format="markdown", include_recommendations=True
    )


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_optimization_recommendations_resource() -> str:
    """Resource: Optimization recommendations. Read via cortex://usage/optimization-recommendations."""
    from . import usage_analytics as ua

    root = await resolve_project_root_async(None, None)
    config = get_tool_optimization_config(root)
    return await ua.get_optimization_recommendations(
        min_usage_threshold=config["min_usage_threshold"],
        days=config["days"],
        ctx=None,
    )


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_observation_resource(id: str) -> str:
    """Resource: Usage observation by ID. Read via cortex://usage/observation/{id}."""
    from . import usage_analytics as ua

    return await ua.get_usage_observation(id=id, ctx=None)


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


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_events_resource() -> str:
    """Resource: Recent usage events (limit 50). Read via cortex://usage/events."""
    from . import usage_analytics as ua

    return await ua.search_usage(limit=50, ctx=None)


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_search_resource(query: str) -> str:
    """Resource: Search usage events. Read via cortex://usage/search/{query}."""
    from urllib.parse import unquote

    from . import usage_analytics as ua

    decoded = unquote(query) if query else ""
    return await ua.search_usage(query=decoded, limit=50, ctx=None)


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_timeline_resource(around_id: str) -> str:
    """Resource: Usage timeline around observation ID. Read via cortex://usage/timeline/{around_id}."""
    from urllib.parse import unquote

    from . import usage_analytics as ua

    decoded = unquote(around_id) if around_id else ""
    return await ua.get_usage_timeline(around_id=decoded, limit=20, ctx=None)


@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_production_monitoring_resource() -> str:
    """Resource: Production monitoring metrics. Read via cortex://usage/production-monitoring."""
    from .query_handlers import run_production_monitoring
    from .query_models import QueryUsageParams

    params = QueryUsageParams()
    return await run_production_monitoring(params, None)


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
