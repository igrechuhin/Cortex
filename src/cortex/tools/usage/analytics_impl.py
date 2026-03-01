"""Implementation helpers for usage analytics MCP tools (Phase 29).

Extracted from usage_analytics.py for Phase 9.1 file size compliance.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker
from cortex.tools.usage.analytics_formatters import build_usage_report_text
from cortex.tools.usage.analytics_models import (
    SearchUsageResponse,
    UsageEventPayload,
    UsageEventsResponse,
    UsageSearchResultEntry,
    UsageTimelineEntry,
)


def build_usage_events_payload(
    root: Path,
    events: list[ToolUsageEvent],
    requested_ids: list[str],
) -> UsageEventsResponse:
    """Build response model for usage events lookup."""
    payload_events: list[UsageEventPayload] = []
    present_ids: set[str] = set()

    for ev in events:
        if hasattr(ev, "model_dump"):
            raw = ev.model_dump()
            data: dict[str, object] = cast(dict[str, object], raw)
        elif isinstance(ev, dict):
            data = cast(dict[str, object], ev)
        else:
            data = {k: v for k, v in vars(ev).items() if not k.startswith("_")}
        if "id" not in data and hasattr(ev, "id"):
            try:
                data["id"] = cast(object, ev.id)
            except AttributeError:
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


def build_search_results(
    events: list[ToolUsageEvent],
) -> list[UsageSearchResultEntry]:
    """Build compact search result entries from usage events."""
    return [
        UsageSearchResultEntry(
            id=ev.id,
            tool_name=ev.tool_name,
            timestamp=ev.timestamp,
            duration_ms=ev.duration_ms,
            success=ev.success,
            error_type=ev.error_type,
            handler_kind=str(ev.handler_kind),
        )
        for ev in events
    ]


def build_timeline_results(
    events: list[ToolUsageEvent],
) -> list[UsageTimelineEntry]:
    """Build compact timeline entries from usage events."""
    return [
        UsageTimelineEntry(
            id=ev.id,
            tool_name=ev.tool_name,
            timestamp=ev.timestamp,
            duration_ms=ev.duration_ms,
            success=ev.success,
            error_type=ev.error_type,
            handler_kind=str(ev.handler_kind),
        )
        for ev in events
    ]


async def get_usage_observation_impl(
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


async def get_usage_events_impl(
    root: Path,
    tracker: UsageTracker | None,
    normalized_ids: list[str],
) -> str:
    """Implementation helper for get_usage_events MCP tool."""
    if tracker is None:
        return json.dumps(
            {"status": "unavailable", "message": "Usage tracker not available"},
            indent=2,
        )
    if not normalized_ids:
        payload = build_usage_events_payload(root=root, events=[], requested_ids=[])
        return json.dumps(payload.model_dump(), indent=2)
    events = await tracker.get_events_by_ids(event_ids=normalized_ids)
    payload = build_usage_events_payload(
        root=root,
        events=events,
        requested_ids=normalized_ids,
    )
    return json.dumps(payload.model_dump(), indent=2)


async def search_usage_impl(
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
    entries = build_search_results(events)
    return SearchUsageResponse(
        status="success",
        project_root=str(root),
        results=entries,
        total=len(entries),
    )


async def get_usage_timeline_impl(
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
    timeline_entries = build_timeline_results(events)
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


async def fetch_report_data(
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
    report = build_usage_report_text(tools, start, end, total)
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
