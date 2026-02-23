"""Unified usage analytics query tool (Phase 50).

Single entry point for tool usage stats, unused tools, report, recommendations,
search, events, observation, and timeline.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.models import ResponseFormat
from cortex.server import mcp


class QueryUsageParams(BaseModel):
    """Parameters for query_usage dispatch; all query types use a subset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_date: str | None = None
    end_date: str | None = None
    tool_name: str | None = None
    response_format: ResponseFormat = ResponseFormat.CONCISE
    days: int = 90
    min_usage_count: int = 0
    min_usage_threshold: int = 5
    ids: list[str] = Field(default_factory=list)
    observation_id: str | None = None
    around_id: str | None = None
    success: bool | None = None
    limit: int = 50
    query: str | None = None
    format: str = "markdown"
    include_recommendations: bool = True
    hours: int | None = None


def _usage_error_payload(message: str) -> str:
    """Return a JSON error payload for query_usage."""
    return json.dumps(
        {"status": "error", "error": message, "error_type": "ValueError"},
        indent=2,
    )


async def _run_usage_stats(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from cortex.tools import usage_analytics

    return await usage_analytics.get_tool_usage_stats(
        start_date=params.start_date,
        end_date=params.end_date,
        tool_name=params.tool_name,
        response_format=params.response_format,
        ctx=ctx,
    )


async def _run_unused(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.managers.usage_tracker import get_tool_optimization_config
    from cortex.tools import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    config = get_tool_optimization_config(root)
    return await usage_analytics.get_unused_tools(
        days=config["days"],
        min_usage_count=config["min_usage_count"],
        ctx=ctx,
    )


async def _run_report(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from cortex.tools import usage_analytics

    return await usage_analytics.get_tool_usage_report(
        format=params.format,
        include_recommendations=params.include_recommendations,
        ctx=ctx,
    )


async def _run_recommendations(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.managers.usage_tracker import get_tool_optimization_config
    from cortex.tools import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    config = get_tool_optimization_config(root)
    return await usage_analytics.get_optimization_recommendations(
        min_usage_threshold=config["min_usage_threshold"],
        days=config["days"],
        ctx=ctx,
    )


async def _run_search(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from cortex.tools import usage_analytics

    return await usage_analytics.search_usage(
        start_date=params.start_date,
        end_date=params.end_date,
        tool_name=params.tool_name,
        success=params.success,
        limit=params.limit,
        query=params.query,
        response_format=params.response_format,
        ctx=ctx,
    )


async def _run_events(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from cortex.tools import usage_analytics

    return await usage_analytics.get_usage_events(ids=params.ids, ctx=ctx)


async def _run_observation(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    if not params.observation_id:
        return _usage_error_payload(
            "observation_id is required for query_type=observation"
        )
    from cortex.tools import usage_analytics

    return await usage_analytics.get_usage_observation(
        id=params.observation_id, ctx=ctx
    )


async def _run_timeline(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    if not params.around_id:
        return _usage_error_payload("around_id is required for query_type=timeline")
    from cortex.tools import usage_analytics

    return await usage_analytics.get_usage_timeline(
        around_id=params.around_id,
        limit=params.limit,
        ctx=ctx,
    )


async def _run_anomalies(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    """Session tool anomalies: tools used in last N hours with retry/error flags."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools import usage_analytics
    from cortex.tools.phase5_evaluation_anomalies_helpers import (
        get_session_tool_anomalies_payload,
        unavailable_session_anomalies_response,
    )

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    hours = params.hours if params.hours is not None else 24
    if tracker is None:
        return unavailable_session_anomalies_response(hours)
    payload = await get_session_tool_anomalies_payload(root, tracker, hours)
    return json.dumps(payload.model_dump(mode="json"), indent=2)


_Handler = Callable[[QueryUsageParams, MCPContext | None], Awaitable[str]]
_USAGE_HANDLERS: dict[str, _Handler] = {
    "stats": _run_usage_stats,
    "unused": _run_unused,
    "report": _run_report,
    "recommendations": _run_recommendations,
    "search": _run_search,
    "events": _run_events,
    "observation": _run_observation,
    "timeline": _run_timeline,
    "anomalies": _run_anomalies,
}


def _params_from_tool_args(
    locals_dict: dict[str, str | int | bool | list[str] | None],
) -> QueryUsageParams:
    """Build QueryUsageParams from query_usage's locals (excluding query_type, ctx)."""
    d: dict[str, str | int | bool | list[str] | None] = {
        k: v for k, v in locals_dict.items() if k not in ("query_type", "ctx")
    }
    d["ids"] = d.get("ids") or []
    rf = d.get("response_format", ResponseFormat.CONCISE)
    d["response_format"] = ResponseFormat(rf) if isinstance(rf, str) else rf
    return QueryUsageParams.model_validate(d)


async def _query_usage_impl(
    query_type: str,
    params: QueryUsageParams,
    ctx: MCPContext | None,
) -> str:
    """Dispatch to the handler for query_type; catch and return errors as JSON."""
    handler = _USAGE_HANDLERS.get(query_type)
    if handler is None:
        return _usage_error_payload(f"Unknown query_type: {query_type}")
    try:
        return await handler(params, ctx)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _log_query_usage_start(ctx: MCPContext | None, query_type: str) -> None:
    """Log that query_usage is starting."""
    await log_client(
        ctx,
        "info",
        f"query_usage: starting query_type={query_type}",
        logger_name=__name__,
    )


@mcp.tool(annotations=read_only_annotations("Query Usage"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def query_usage(
    query_type: str,
    start_date: str | None = None,
    end_date: str | None = None,
    tool_name: str | None = None,
    response_format: str = "concise",
    days: int = 90,
    min_usage_count: int = 0,
    min_usage_threshold: int = 5,
    ids: list[str] | None = None,
    observation_id: str | None = None,
    around_id: str | None = None,
    success: bool | None = None,
    limit: int = 50,
    query: str | None = None,
    format: str = "markdown",
    include_recommendations: bool = True,
    hours: int = 24,
    ctx: MCPContext | None = None,
) -> str:
    """Query usage. query_type: stats|unused|report|recommendations|search|events|observation|timeline|anomalies."""
    await _log_query_usage_start(ctx, query_type)
    params = _params_from_tool_args(locals())
    return await _query_usage_impl(query_type, params, ctx)
