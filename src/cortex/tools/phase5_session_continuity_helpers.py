"""Phase 57 / Anthropic Step 5: Session continuity score helpers.

Measures how effectively sessions hand off context — tracks turns until first
productive tool call after session_start. Used by query_usage(session_continuity).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker


def _empty_int_list() -> list[int]:
    """Return empty list typed as list[int] for Pydantic default_factory."""
    return []


# Tools that are orientation-only (not productive); first call to other tool = productive
_ORIENTATION_TOOLS: frozenset[str] = frozenset(
    {
        "session_start",
        "load_context",
        "get_relevance_scores",
        "get_structure_info",
        "check_mcp_connection_health",
        "think",
        "query_memory_bank",
        "query_usage",
        "rules",
    }
)


def _infer_sessions_by_session_start(
    events: list[ToolUsageEvent],
) -> list[list[ToolUsageEvent]]:
    """Group events into sessions by session_start boundaries.

    Each session starts at a session_start call and runs until the next
    session_start or end of data.
    """
    if not events:
        return []
    sorted_evs = sorted(events, key=lambda e: e.timestamp)
    sessions: list[list[ToolUsageEvent]] = []
    current: list[ToolUsageEvent] = []
    for ev in sorted_evs:
        if ev.tool_name == "session_start":
            if current:
                sessions.append(current)
            current = [ev]
        else:
            if current:
                current.append(ev)
    if current:
        sessions.append(current)
    return sessions


def _turns_until_productive(session: list[ToolUsageEvent]) -> int | None:
    """Return number of tool calls (0-indexed) until first productive call.

    session_start is index 0. Productive = first call to a tool not in
    _ORIENTATION_TOOLS. Returns None if no productive call in session.
    """
    for i, ev in enumerate(session):
        if ev.tool_name not in _ORIENTATION_TOOLS:
            return i
    return None


def compute_session_continuity(
    events: list[ToolUsageEvent],
) -> list[int]:
    """Compute turns_until_productive for each session that has session_start.

    Returns list of turn counts (excludes sessions with no productive call).
    """
    sessions = _infer_sessions_by_session_start(events)
    result: list[int] = []
    for sess in sessions:
        turns = _turns_until_productive(sess)
        if turns is not None:
            result.append(turns)
    return result


class SessionContinuityPayload(BaseModel):
    """Session continuity metrics for query_usage(session_continuity)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(description="success or unavailable")
    project_root: str = Field(description="Project root path")
    days: int = Field(ge=1, description="Window in days")
    start: str = Field(description="Window start ISO timestamp")
    end: str = Field(description="Window end ISO timestamp")
    total_events: int = Field(ge=0)
    sessions_with_session_start: int = Field(
        ge=0, description="Sessions that began with session_start"
    )
    sessions_with_productive_call: int = Field(
        ge=0, description="Sessions that had at least one productive tool call"
    )
    turns_until_productive: list[int] = Field(
        default_factory=_empty_int_list,
        description="Per-session turn count until first productive call",
    )
    avg_turns_until_productive: float | None = Field(
        None,
        description="Average turns until productive (None if no data)",
    )
    median_turns_until_productive: float | None = Field(
        None,
        description="Median turns until productive (None if no data)",
    )


def _compute_avg_median(turns: list[int]) -> tuple[float | None, float | None]:
    """Return (avg, median) for turns list; (None, None) if empty."""
    if not turns:
        return (None, None)
    avg = sum(turns) / len(turns)
    st = sorted(turns)
    mid = len(st) // 2
    median = st[mid] if len(st) % 2 else (st[mid - 1] + st[mid]) / 2.0
    return (avg, median)


async def get_session_continuity_payload(
    root: Path,
    tracker: UsageTracker,
    days: int = 30,
) -> SessionContinuityPayload:
    """Fetch usage events and build session continuity payload."""
    end = datetime.now(UTC)
    start = end - timedelta(days=max(1, min(days, 365)))
    events = await tracker.search_usage(
        start_date=start,
        end_date=end,
        tool_name=None,
        success=None,
        limit=10000,
    )
    turns_list: list[int] = compute_session_continuity(events)
    sessions = _infer_sessions_by_session_start(events)
    avg_val, median_val = _compute_avg_median(turns_list)
    turns_slice: list[int] = turns_list[:100]
    return SessionContinuityPayload(
        status="success",
        project_root=str(root),
        days=days,
        start=start.isoformat(),
        end=end.isoformat(),
        total_events=len(events),
        sessions_with_session_start=len(sessions),
        sessions_with_productive_call=len(turns_list),
        turns_until_productive=turns_slice,
        avg_turns_until_productive=avg_val,
        median_turns_until_productive=median_val,
    )
