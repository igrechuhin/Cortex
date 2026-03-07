"""Usage event aggregation and filtering (Phase 81 split from usage_tracker)."""

from datetime import UTC, datetime
from typing import cast

from cortex.managers.usage_models import ToolUsageEvent, ToolUsageStats


def to_row_dict(obj: ToolUsageStats | dict[str, object]) -> dict[str, object]:
    """Convert tool stat to dict for get_unused_tools iteration."""
    if isinstance(obj, dict):
        return obj
    out = obj.model_dump()
    return cast(dict[str, object], out)


def error_types_from_events(events: list[ToolUsageEvent]) -> dict[str, int]:
    """Build error_type -> count from events."""
    out: dict[str, int] = {}
    for e in events:
        if e.error_type:
            out[e.error_type] = out.get(e.error_type, 0) + 1
    return out


def aggregate_events(tool_name: str, events: list[ToolUsageEvent]) -> ToolUsageStats:
    """Aggregate a list of events into ToolUsageStats."""
    empty_ts = datetime.now(UTC).isoformat()
    if not events:
        return ToolUsageStats(
            tool_name=tool_name,
            total_calls=0,
            successful_calls=0,
            failed_calls=0,
            avg_duration_ms=0.0,
            min_duration_ms=0.0,
            max_duration_ms=0.0,
            error_types={},
            first_used=empty_ts,
            last_used=empty_ts,
        )
    durations = [e.duration_ms for e in events]
    success_count = sum(1 for e in events if e.success)
    timestamps = [e.timestamp for e in events]
    return ToolUsageStats(
        tool_name=tool_name,
        total_calls=len(events),
        successful_calls=success_count,
        failed_calls=len(events) - success_count,
        avg_duration_ms=sum(durations) / len(durations),
        min_duration_ms=min(durations),
        max_duration_ms=max(durations),
        error_types=error_types_from_events(events),
        first_used=min(timestamps),
        last_used=max(timestamps),
    )


def filter_events_by_success(
    events: list[ToolUsageEvent],
    success: bool | None,
) -> list[ToolUsageEvent]:
    """Filter events by success flag when provided."""
    if success is None:
        return events
    return [e for e in events if e.success is success]


def filter_events_by_query(
    events: list[ToolUsageEvent],
    query: str | None,
) -> list[ToolUsageEvent]:
    """Filter events by case-insensitive keyword across basic text fields."""
    if not query:
        return events
    needle = query.lower()
    filtered: list[ToolUsageEvent] = []
    for event in events:
        fields = [
            event.tool_name,
            event.error_type or "",
            event.result_summary or "",
        ]
        if any(needle in value.lower() for value in fields):
            filtered.append(event)
    return filtered
