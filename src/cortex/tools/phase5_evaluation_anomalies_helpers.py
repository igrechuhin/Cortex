"""Phase 57: Session tool anomalies helpers (extracted for file size limits)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker


class SessionToolUsageEntry(BaseModel):
    """Per-tool usage and anomaly counts for a session window."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(description="MCP tool name")
    calls: int = Field(ge=0, description="Number of calls")
    retries: int = Field(ge=0, description="Total retry count")
    errors: int = Field(ge=0, description="Number of failed calls")


def _empty_tools_used() -> list[SessionToolUsageEntry]:
    """Typed default factory for tools_used fields."""
    return []


class SessionAnomaliesAggregate(BaseModel):
    """Aggregated session tool usage and anomaly lists."""

    model_config = ConfigDict(extra="forbid")

    tools_used: list[SessionToolUsageEntry] = Field(
        default_factory=_empty_tools_used, description="Per-tool usage entries"
    )
    high_retry_tools: list[str] = Field(
        default_factory=list, description="Tools with at least one retry"
    )
    high_error_tools: list[str] = Field(
        default_factory=list, description="Tools with at least one error"
    )


class UnavailableSessionAnomaliesResponse(BaseModel):
    """Response when usage tracker is not available."""

    model_config = ConfigDict(extra="forbid")

    status: str = "unavailable"
    message: str = Field(description="Reason unavailable")
    session_window_hours: int = Field(ge=1, description="Requested window in hours")


class SessionAnomaliesPayload(BaseModel):
    """Full success payload for get_session_tool_anomalies."""

    model_config = ConfigDict(extra="forbid")

    status: str = "success"
    project_root: str = Field(description="Project root path")
    session_window_hours: int = Field(ge=1, description="Window in hours")
    start: str = Field(description="Window start ISO timestamp")
    end: str = Field(description="Window end ISO timestamp")
    total_events: int = Field(ge=0, description="Number of usage events")
    tools_used: list[SessionToolUsageEntry] = Field(default_factory=_empty_tools_used)
    high_retry_tools: list[str] = Field(default_factory=list)
    high_error_tools: list[str] = Field(default_factory=list)


def unavailable_session_anomalies_response(hours: int) -> str:
    """Return JSON response when usage tracker is not available."""
    model = UnavailableSessionAnomaliesResponse(
        message="Usage tracker not available",
        session_window_hours=hours,
    )
    return json.dumps(model.model_dump(mode="json"), indent=2)


def aggregate_session_tool_anomalies(
    events: list[ToolUsageEvent],
) -> SessionAnomaliesAggregate:
    """Group usage events by tool and compute retry/error anomalies."""
    by_tool: dict[str, list[ToolUsageEvent]] = {}
    for ev in events:
        by_tool.setdefault(ev.tool_name, []).append(ev)
    tools_used: list[SessionToolUsageEntry] = []
    high_retry_tools: list[str] = []
    high_error_tools: list[str] = []
    for tool_name, evs in sorted(by_tool.items()):
        retries = sum((e.retry_count or 0) for e in evs)
        errors = sum(1 for e in evs if not e.success)
        tools_used.append(
            SessionToolUsageEntry(
                tool_name=tool_name,
                calls=len(evs),
                retries=retries,
                errors=errors,
            )
        )
        if retries > 0:
            high_retry_tools.append(tool_name)
        if errors > 0:
            high_error_tools.append(tool_name)
    return SessionAnomaliesAggregate(
        tools_used=tools_used,
        high_retry_tools=high_retry_tools,
        high_error_tools=high_error_tools,
    )


async def get_session_tool_anomalies_payload(
    root: Path,
    tracker: UsageTracker,
    hours: int,
) -> SessionAnomaliesPayload:
    """Fetch recent usage events and build success payload for get_session_tool_anomalies."""
    end = datetime.now(UTC)
    start = end - timedelta(hours=max(1, min(hours, 168)))
    events = await tracker.search_usage(
        start_date=start,
        end_date=end,
        tool_name=None,
        success=None,
        limit=2000,
    )
    aggregated = aggregate_session_tool_anomalies(events)
    return SessionAnomaliesPayload(
        status="success",
        project_root=str(root),
        session_window_hours=hours,
        start=start.isoformat(),
        end=end.isoformat(),
        total_events=len(events),
        tools_used=aggregated.tools_used,
        high_retry_tools=aggregated.high_retry_tools,
        high_error_tools=aggregated.high_error_tools,
    )
