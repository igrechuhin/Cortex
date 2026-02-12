"""
Usage Analytics Tools (Phase 29)

MCP tools for querying MCP tool usage statistics and optimization recommendations.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

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
from cortex.managers.usage_models import ToolUsageEvent
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


def _normalize_ids(ids: list[str]) -> list[str]:
    """Normalize requested IDs while preserving order."""
    return [i for i in ids if i]


class UsageEventPayload(BaseModel):
    """Looser wire model for usage events returned to external callers.

    This sits at the communication boundary (JSON returned by the MCP tool).
    Internally we still use the strict `ToolUsageEvent` model; this payload
    only enforces a stable subset of fields and allows additional data via
    Pydantic's ``extra='allow'`` configuration.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    tool_name: str | None = None
    result_summary: str | None = None


class UsageEventsResponse(BaseModel):
    """Pydantic response model for usage events lookup."""

    status: str
    project_root: str
    events: list[UsageEventPayload]
    missing_ids: list[str]


def _build_usage_events_payload(
    root: Path,
    events: list[ToolUsageEvent],
    requested_ids: list[str],
) -> UsageEventsResponse:
    """Build response model for usage events lookup."""
    payload_events: list[UsageEventPayload] = []
    present_ids: set[str] = set()

    for ev in events:
        # Prefer model_dump when available (pydantic models and test fakes).
        if hasattr(ev, "model_dump"):
            raw = ev.model_dump()  # type: ignore[call-arg, attr-defined]
            data: dict[str, object] = cast(dict[str, object], raw)
        elif isinstance(ev, dict):
            data = cast(dict[str, object], ev)
        else:
            # Fallback: use public attributes on arbitrary objects.
            data = {k: v for k, v in vars(ev).items() if not k.startswith("_")}

        # Ensure we have an ID in the payload; fall back to attribute access if needed.
        if "id" not in data and hasattr(ev, "id"):
            try:
                data["id"] = cast(object, ev.id)  # type: ignore[assignment]
            except AttributeError:
                # If we still can't obtain an ID, let Pydantic validation surface it.
                pass

        payload = UsageEventPayload.model_validate(data)
        payload_events.append(payload)

        ev_id: str | None = payload.id
        present_ids.add(ev_id)

    missing_ids = [eid for eid in requested_ids if eid not in present_ids]
    return UsageEventsResponse(
        status="success",
        project_root=str(root),
        events=payload_events,
        missing_ids=missing_ids,
    )


async def _get_usage_events_impl(
    ids: list[str],
    root: Path,
    tracker: UsageTracker | None,
) -> str:
    """Implementation helper for get_usage_events MCP tool."""
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"},
            indent=2,
        )
    normalized_ids = _normalize_ids(ids)
    if not normalized_ids:
        payload = _build_usage_events_payload(root=root, events=[], requested_ids=[])
        return json.dumps(payload.model_dump(), indent=2)
    events = await tracker.get_events_by_ids(event_ids=normalized_ids)
    payload = _build_usage_events_payload(
        root=root,
        events=events,
        requested_ids=normalized_ids,
    )
    return json.dumps(payload.model_dump(), indent=2)


@mcp.tool(annotations=read_only_annotations("Get Usage Events"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_usage_events(
    ids: list[str],
    ctx: MCPContext | None = None,
) -> str:
    """Get full usage events for a list of observation IDs.

    This complements search_usage's compact index by allowing callers to fetch
    full event payloads only for selected IDs, enabling the recommended
    search → select IDs → get_usage_events(ids=[...]) workflow.
    """
    if ctx is not None:
        await log_client(ctx, "debug", f"get_usage_events: starting ids={len(ids)}")
    root = await resolve_project_root_async(None, ctx)
    tracker = await _get_tracker(root)
    return await _get_usage_events_impl(ids=ids, root=root, tracker=tracker)


@mcp.tool(annotations=read_only_annotations("Get Tool Usage Stats"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_tool_usage_stats(
    start_date: str | None = None,
    end_date: str | None = None,
    tool_name: str | None = None,
    response_format: Literal["concise", "detailed"] = "concise",
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
    return _format_tool_usage_stats_response(root, result, response_format)


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


class UsageSearchResultEntry(BaseModel):
    """Pydantic model for compact search result entries."""

    id: str
    tool_name: str
    timestamp: str
    duration_ms: float
    success: bool
    error_type: str | None
    handler_kind: str


class SearchUsageResponse(BaseModel):
    """Pydantic response model for search_usage results."""

    status: str
    project_root: str
    results: list[UsageSearchResultEntry]
    total: int


async def _search_usage_impl(
    tracker: UsageTracker,
    root: Path,
    start: datetime,
    end: datetime,
    tool_name: str | None,
    success: bool | None,
    limit: int,
    query: str | None,
) -> SearchUsageResponse:
    """Implementation helper for search_usage MCP tool."""
    limit_val = max(1, min(limit, 500))
    events = await tracker.search_usage(
        start_date=start,
        end_date=end,
        tool_name=tool_name,
        success=success,
        limit=limit_val,
        query=query,
    )
    entries = _build_search_results(events)
    return SearchUsageResponse(
        status="success",
        project_root=str(root),
        results=entries,
        total=len(entries),
    )


def _build_search_results(events: list[ToolUsageEvent]) -> list[UsageSearchResultEntry]:
    """Build compact search result entries from usage events."""
    return [
        UsageSearchResultEntry(
            id=ev.id,
            tool_name=ev.tool_name,
            timestamp=ev.timestamp,
            duration_ms=ev.duration_ms,
            success=ev.success,
            error_type=ev.error_type,
            handler_kind=ev.handler_kind,
        )
        for ev in events
    ]


class UsageTimelineEntry(BaseModel):
    """Pydantic model for compact usage timeline entries.

    NOTE: This model is part of the canonical Pydantic v2 usage pattern for
    usage analytics. Its schema is documented in the tech context Pydantic v2
    section and the Python Pydantic v2 rule; keep fields stable for external
    callers and update docs/tests together with any changes.
    """

    id: str
    tool_name: str
    timestamp: str
    duration_ms: float
    success: bool
    error_type: str | None
    handler_kind: str


def _build_timeline_results(events: list[ToolUsageEvent]) -> list[UsageTimelineEntry]:
    """Build compact timeline entries from usage events."""
    return [
        UsageTimelineEntry(
            id=ev.id,
            tool_name=ev.tool_name,
            timestamp=ev.timestamp,
            duration_ms=ev.duration_ms,
            success=ev.success,
            error_type=ev.error_type,
            handler_kind=ev.handler_kind,
        )
        for ev in events
    ]


@mcp.tool(annotations=read_only_annotations("Search Usage Events"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def search_usage(
    start_date: str | None = None,
    end_date: str | None = None,
    tool_name: str | None = None,
    success: bool | None = None,
    limit: int = 50,
    query: str | None = None,
    response_format: Literal["concise", "detailed"] = "concise",
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
    payload = await _search_usage_impl(
        tracker=tracker,
        root=root,
        start=start,
        end=end,
        tool_name=tool_name,
        success=success,
        limit=limit,
        query=query,
    )
    return _format_search_usage_response(root, payload, response_format)


def _format_tool_usage_stats_response(
    root: Path,
    result: dict[str, object],
    response_format: Literal["concise", "detailed"],
) -> str:
    """Format get_tool_usage_stats response based on response_format."""
    if response_format == "concise":
        tools_raw: list[dict[str, object]] = cast(
            list[dict[str, object]], result.get("tools") or []
        )
        # Sort by total_calls descending; reuse same semantics as report builder.
        top_tools = sorted(tools_raw, key=_calls_key)[:5]
        concise_tools: list[dict[str, object]] = []
        for t in top_tools:
            name = str(t.get("tool_name", "?"))
            calls_val = t.get("total_calls", 0)
            calls = int(calls_val) if isinstance(calls_val, (int, float)) else 0
            concise_tools.append({"tool_name": name, "total_calls": calls})
        concise_payload: dict[str, object] = {
            "status": "success",
            "project_root": str(root),
            "top_5_tools": concise_tools,
        }
        return json.dumps(concise_payload, indent=2)
    return json.dumps(
        {"status": "success", "project_root": str(root), **result},
        indent=2,
    )


def _format_search_usage_response(
    root: Path,
    payload: SearchUsageResponse,
    response_format: Literal["concise", "detailed"],
) -> str:
    """Format search_usage response based on response_format."""
    data = payload.model_dump()
    if response_format == "concise":
        results_raw: list[dict[str, object]] = cast(
            list[dict[str, object]], data.get("results") or []
        )
        concise_results: list[dict[str, object]] = []
        for entry in results_raw:
            concise_results.append(
                {
                    "id": entry.get("id"),
                    "summary": _build_search_usage_summary(entry),
                }
            )
        concise_payload: dict[str, object] = {
            "status": data.get("status", "success"),
            "project_root": data.get("project_root", str(root)),
            "total": data.get("total", len(concise_results)),
            "results": concise_results,
        }
        return json.dumps(concise_payload, indent=2)
    return json.dumps(data, indent=2)


def _build_search_usage_summary(entry: dict[str, object]) -> str:
    """Build a one-line summary string for a search_usage entry."""
    tool = str(entry.get("tool_name", "?"))
    ts = str(entry.get("timestamp", ""))
    success_flag = bool(entry.get("success"))
    duration_val = entry.get("duration_ms", 0.0)
    duration_ms = float(duration_val) if isinstance(duration_val, (int, float)) else 0.0
    status = "success" if success_flag else "error"
    return f"{tool} at {ts} - {status} ({duration_ms:.1f} ms)"


async def _get_usage_timeline_impl(
    around_id: str,
    limit: int,
    root: Path,
    tracker: UsageTracker | None,
) -> str:
    """Implementation helper for get_usage_timeline MCP tool."""
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"},
            indent=2,
        )
    limit_val = max(1, min(limit, 500))
    events = await tracker.get_usage_timeline(around_id=around_id, limit=limit_val)
    timeline_entries = _build_timeline_results(events)
    results = [entry.model_dump() for entry in timeline_entries]
    return json.dumps(
        {
            "status": "success",
            "project_root": str(root),
            "around_id": around_id,
            "results": results,
            "total": len(results),
        },
        indent=2,
    )


@mcp.tool(annotations=read_only_annotations("Get Usage Timeline"))
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
    return await _get_usage_timeline_impl(
        around_id=around_id,
        limit=limit,
        root=root,
        tracker=tracker,
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
