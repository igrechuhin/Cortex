"""Handler functions for query_usage dispatch (Phase 50)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import cast

# Import MCPContext for type hints; avoid circular import
from cortex.core.context_logging import MCPContext

from .query_models import QueryUsageParams


def _usage_error_payload(message: str) -> str:
    """Return a JSON error payload for query_usage."""
    return json.dumps(
        {"status": "error", "error": message, "error_type": "ValueError"},
        indent=2,
    )


async def run_usage_stats(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from . import usage_analytics

    return await usage_analytics.get_tool_usage_stats(
        start_date=params.start_date,
        end_date=params.end_date,
        tool_name=params.tool_name,
        response_format=params.response_format,
        ctx=ctx,
    )


async def run_unused(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.managers.usage_tracker import get_tool_optimization_config

    from . import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    config = get_tool_optimization_config(root)
    return await usage_analytics.get_unused_tools(
        days=config["days"],
        min_usage_count=config["min_usage_count"],
        ctx=ctx,
    )


async def run_report(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from . import usage_analytics

    return await usage_analytics.get_tool_usage_report(
        format=params.format,
        include_recommendations=params.include_recommendations,
        ctx=ctx,
    )


async def run_recommendations(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.managers.usage_tracker import get_tool_optimization_config

    from . import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    config = get_tool_optimization_config(root)
    return await usage_analytics.get_optimization_recommendations(
        min_usage_threshold=config["min_usage_threshold"],
        days=config["days"],
        ctx=ctx,
    )


async def run_search(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from . import usage_analytics

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


async def run_events(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    from . import usage_analytics

    return await usage_analytics.get_usage_events(ids=params.ids, ctx=ctx)


async def run_observation(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    if not params.observation_id:
        return _usage_error_payload(
            "observation_id is required for query_type=observation"
        )
    from . import usage_analytics

    return await usage_analytics.get_usage_observation(
        id=params.observation_id, ctx=ctx
    )


async def run_timeline(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    if not params.around_id:
        return _usage_error_payload("around_id is required for query_type=timeline")
    from . import usage_analytics

    return await usage_analytics.get_usage_timeline(
        around_id=params.around_id,
        limit=params.limit,
        ctx=ctx,
    )


async def run_anomalies(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    """Session tool anomalies: tools used in last N hours with retry/error flags."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools.evaluation.evaluation_anomalies_helpers import (
        get_session_tool_anomalies_payload,
        unavailable_session_anomalies_response,
    )

    from . import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    hours = params.hours if params.hours is not None else 24
    if tracker is None:
        return unavailable_session_anomalies_response(hours)
    payload = await get_session_tool_anomalies_payload(root, tracker, hours)
    return json.dumps(payload.model_dump(mode="json"), indent=2)


async def run_tool_description_optimization(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Tool description optimization: suggestions and A/B plan from usage/error data."""
    if not params.tool_name or not params.tool_name.strip():
        return _usage_error_payload(
            "tool_name is required for query_type=tool_description_optimization"
        )
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools.evaluation.evaluation_optimization_helpers import (
        get_tool_description_optimization_payload,
    )

    from . import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    payload = await get_tool_description_optimization_payload(
        root, tracker, params.tool_name.strip(), days=params.days
    )
    return payload.model_dump_json(indent=2)


async def run_production_monitoring(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Production monitoring: rolling baseline, current metrics, drift alerts."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools.usage.production_monitoring_helpers import (
        get_production_monitoring_payload,
    )

    from . import usage_analytics

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


async def run_token_efficiency(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    """Token efficiency: top token-expensive tools by total and by avg."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools.usage.token_efficiency_helpers import get_token_efficiency_payload

    from . import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    days = max(1, min(365, params.days))
    payload = await get_token_efficiency_payload(root, tracker, days=days)
    return payload.model_dump_json(indent=2)


async def run_redundancy(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    """Redundant tool call detection (Anthropic Step 3)."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools.usage.redundancy_helpers import get_redundancy_payload

    from . import usage_analytics

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


async def run_session_continuity(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Session continuity score (Anthropic Step 5): turns until productive."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools.session.continuity_helpers import (
        get_session_continuity_payload,
    )

    from . import usage_analytics

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


async def run_tool_frequency(params: QueryUsageParams, ctx: MCPContext | None) -> str:
    """Tool frequency (Anthropic Step 6): tools per session, tier token impact."""
    from cortex.core.project_root_resolver import resolve_project_root_async
    from cortex.tools.usage.tool_frequency_helpers import get_tool_frequency_payload

    from . import usage_analytics

    root = await resolve_project_root_async(None, ctx)
    tracker = await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]
    days = max(1, min(365, params.days))
    payload = await get_tool_frequency_payload(root, tracker, days=days)
    return payload.model_dump_json(indent=2)


def _build_tool_classification_rows(
    tools_list: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Build classification rows from usage stats, merging with categories."""
    from cortex.tools.structure.categories import TOOL_CATEGORIES

    rows: list[dict[str, object]] = []
    for t in tools_list:
        name_val = t.get("tool_name")
        name = str(name_val) if isinstance(name_val, str) else ""
        total_val = t.get("total_calls")
        total_calls = int(total_val) if isinstance(total_val, (int, float)) else 0
        entry = next((e for e in TOOL_CATEGORIES if e.name == name), None)
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


async def run_tool_classification(
    params: QueryUsageParams, ctx: MCPContext | None
) -> str:
    """Tool classification (agent-skills Step 3): usage + category for core vs extended."""
    from cortex.core.project_root_resolver import resolve_project_root_async

    from . import usage_analytics

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
USAGE_HANDLERS: dict[str, _Handler] = {
    "stats": run_usage_stats,
    "unused": run_unused,
    "report": run_report,
    "recommendations": run_recommendations,
    "search": run_search,
    "events": run_events,
    "observation": run_observation,
    "timeline": run_timeline,
    "anomalies": run_anomalies,
    "tool_description_optimization": run_tool_description_optimization,
    "production_monitoring": run_production_monitoring,
    "token_efficiency": run_token_efficiency,
    "redundancy": run_redundancy,
    "session_continuity": run_session_continuity,
    "tool_frequency": run_tool_frequency,
    "tool_classification": run_tool_classification,
}
