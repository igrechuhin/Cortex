"""Unified usage analytics query tool (Phase 50).

Single entry point for tool usage stats, unused tools, report, recommendations,
search, events, observation, and timeline.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import cast

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
    days: int = 30
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
    production_baseline_days: int = 7
    production_window_hours: int = 24
    days_baseline: int = 7
    current_window_hours: int = 24


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


async def _run_tool_description_optimization(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Tool description optimization: suggestions and A/B plan from usage/error data."""
    if not params.tool_name or not params.tool_name.strip():
        return _usage_error_payload(
            "tool_name is required for query_type=tool_description_optimization"
        )
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools import usage_analytics
    from cortex.tools.phase5_evaluation_optimization_helpers import (
        get_tool_description_optimization_payload,
    )

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    payload = await get_tool_description_optimization_payload(
        root, tracker, params.tool_name.strip(), days=params.days
    )
    return payload.model_dump_json(indent=2)


async def _run_production_monitoring(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Production monitoring: rolling baseline, current metrics, drift alerts, weekly report."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools import usage_analytics
    from cortex.tools.phase5_production_monitoring_helpers import (
        get_production_monitoring_payload,
    )

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    days_baseline = max(1, min(30, params.production_baseline_days))
    current_window_hours = max(1, min(168, params.production_window_hours))
    payload = await get_production_monitoring_payload(
        root,
        tracker,
        days_baseline=days_baseline,
        current_window_hours=current_window_hours,
    )
    return payload.model_dump_json(indent=2)


async def _run_token_efficiency(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Token efficiency: top token-expensive tools by total and by avg (Anthropic Step 2)."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools import usage_analytics
    from cortex.tools.phase5_token_efficiency_helpers import (
        get_token_efficiency_payload,
    )

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    days = max(1, min(365, params.days))
    payload = await get_token_efficiency_payload(root, tracker, days=days)
    return payload.model_dump_json(indent=2)


async def _run_redundancy(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    """Redundant tool call detection (Anthropic Step 3)."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools import usage_analytics
    from cortex.tools.phase5_redundancy_helpers import get_redundancy_payload

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    if tracker is None:
        return json.dumps(
            {
                "status": "unavailable",
                "message": "Usage tracker not available",
            },
            indent=2,
        )
    days = max(1, min(365, params.days))
    payload = await get_redundancy_payload(root, tracker, days=days)
    return payload.model_dump_json(indent=2)


async def _run_session_continuity(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Session continuity score (Anthropic Step 5): turns until productive."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools import usage_analytics
    from cortex.tools.phase5_session_continuity_helpers import (
        get_session_continuity_payload,
    )

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    if tracker is None:
        return json.dumps(
            {
                "status": "unavailable",
                "message": "Usage tracker not available",
            },
            indent=2,
        )
    days = max(1, min(365, params.days))
    payload = await get_session_continuity_payload(root, tracker, days=days)
    return payload.model_dump_json(indent=2)


async def _run_tool_frequency(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    """Tool frequency (Anthropic Step 6): tools per session, tier token impact."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools import usage_analytics
    from cortex.tools.phase5_tool_frequency_helpers import get_tool_frequency_payload

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    days = max(1, min(365, params.days))
    payload = await get_tool_frequency_payload(root, tracker, days=days)
    return payload.model_dump_json(indent=2)


def _build_tool_classification_rows(
    tools_list: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Build classification rows from usage stats, merging with tool_categories."""
    from cortex.tools import tool_categories

    rows: list[dict[str, object]] = []
    for t in tools_list:
        name_val = t.get("tool_name")
        name = str(name_val) if isinstance(name_val, str) else ""
        total_val = t.get("total_calls")
        total_calls = int(total_val) if isinstance(total_val, (int, float)) else 0
        entry = next(
            (e for e in tool_categories.TOOL_CATEGORIES if e.name == name), None
        )
        cat: str | None = entry.category.value if entry else None
        rationale = entry.rationale if entry else ""
        rows.append(
            {
                "tool_name": name,
                "total_calls": total_calls,
                "category": cat,
                "rationale": rationale,
            }
        )

    def _total(r: dict[str, object]) -> int:
        v = r.get("total_calls", 0)
        return int(v) if isinstance(v, (int, float)) else 0

    rows.sort(key=_total, reverse=True)
    return rows


def _build_tool_classification_by_category(
    rows: list[dict[str, object]],
) -> dict[str, int]:
    """Count tools per category from classification rows."""
    by_cat: dict[str, int] = {}
    for r in rows:
        c = r.get("category")
        key = str(c) if c is not None else "uncategorized"
        by_cat[key] = by_cat.get(key, 0) + 1
    return by_cat


def _build_tool_classification_payload(
    root: object,
    days: int,
    result: dict[str, object],
) -> str:
    """Build JSON payload from usage stats result for tool_classification."""
    tools_raw: object = result.get("tools", []) or []
    raw_list = cast(list[object], tools_raw if isinstance(tools_raw, list) else [])
    tools_list: list[dict[str, object]] = [
        cast(dict[str, object], x) for x in raw_list if isinstance(x, dict)
    ]
    rows = _build_tool_classification_rows(tools_list)
    by_cat = _build_tool_classification_by_category(rows)
    ev_val = result.get("total_events", 0)
    total_events = int(ev_val) if isinstance(ev_val, (int, float)) else 0
    return json.dumps(
        {
            "status": "success",
            "project_root": str(root),
            "days": days,
            "total_tools": len(rows),
            "total_events": total_events,
            "by_category": by_cat,
            "tools": rows,
        },
        indent=2,
    )


async def _run_tool_classification(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Tool classification (agent-skills Step 3): usage + category for core vs extended."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    if tracker is None:
        return json.dumps(
            {
                "status": "unavailable",
                "message": "Usage tracker not available for tool classification",
            },
            indent=2,
        )
    days = max(1, min(365, params.days))
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    result = await tracker.get_usage_stats(start_date=start, end_date=end)
    return _build_tool_classification_payload(root, days, result)


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
    "tool_description_optimization": _run_tool_description_optimization,
    "production_monitoring": _run_production_monitoring,
    "token_efficiency": _run_token_efficiency,
    "redundancy": _run_redundancy,
    "session_continuity": _run_session_continuity,
    "tool_frequency": _run_tool_frequency,
    "tool_classification": _run_tool_classification,
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


def _build_query_usage_params_from_locals(
    locals_dict: dict[str, str | int | bool | list[str] | None],
) -> QueryUsageParams:
    """Build QueryUsageParams from query_usage's locals (excludes query_type, ctx)."""
    return _params_from_tool_args(
        {k: v for k, v in locals_dict.items() if k not in ("query_type", "ctx")}
    )


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
    days: int = 30,
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
    production_baseline_days: int = 7,
    production_window_hours: int = 24,
    ctx: MCPContext | None = None,
) -> str:
    """Query tool usage analytics: stats, unused tools, report, recommendations, anomalies.

    USE WHEN: User needs usage stats, low-usage tool list, optimization
    recommendations, session anomalies, or production monitoring.

    EXAMPLES: 'query_usage(query_type="stats")', 'get usage statistics',
    'query_usage(query_type="recommendations", days=90)',
    'query_usage(query_type="anomalies", hours=24)'.

    RETURNS: JSON (or markdown when format=markdown) with result for
    query_type: stats, unused, report, recommendations, search, events,
    observation, timeline, anomalies, tool_description_optimization,
    production_monitoring, token_efficiency, redundancy, session_continuity,
    tool_frequency, tool_classification. tool_name required for
    tool_description_optimization.     tool_classification returns usage-ranked
    tools with current category (agent-skills Step 3).
    token_efficiency shows top token-expensive tools (Anthropic Step 2).
    redundancy shows repeated identical calls (Step 3). session_continuity
    tracks turns until productive (Step 5). tool_frequency shows tools by
    session presence and token savings when tiered loading is enabled (Step 6).

    Args:
        query_type: stats, unused, report, recommendations, anomalies, etc.
        tool_name: Required for tool_description_optimization. Optional for others.
        days, hours, limit: Query-specific window and limit parameters.
    """
    await _log_query_usage_start(ctx, query_type)
    params = _build_query_usage_params_from_locals(locals())
    return await _query_usage_impl(query_type, params, ctx)
