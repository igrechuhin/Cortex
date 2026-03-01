"""Phase 57 / Anthropic Step 6: Tool frequency and tier token impact helpers.

Analyzes which tools are used in >80% of sessions (core) vs <10% (rare) for
tier refinement. Estimates token savings when tiered loading is enabled.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker
from cortex.tools.tool_categories import (
    get_always_loaded_tool_names,
    get_category_summary,
    get_deferred_tool_names,
)


def _empty_str_list() -> list[str]:
    """Return empty list typed as list[str] for Pydantic default_factory."""
    return []


def _infer_sessions_by_session_start(
    events: list[ToolUsageEvent],
) -> list[list[ToolUsageEvent]]:
    """Group events into sessions by session(operation=start) or session_start boundaries."""
    if not events:
        return []
    sorted_evs = sorted(events, key=lambda e: e.timestamp)
    sessions: list[list[ToolUsageEvent]] = []
    current: list[ToolUsageEvent] = []
    for ev in sorted_evs:
        if ev.tool_name in ("session", "session_start"):
            if current:
                sessions.append(current)
            current = [ev]
        else:
            if current:
                current.append(ev)
    if current:
        sessions.append(current)
    return sessions


def _tools_per_session(sessions: list[list[ToolUsageEvent]]) -> list[set[str]]:
    """Return the set of unique tools used in each session."""
    return [{e.tool_name for e in sess} for sess in sessions]


def compute_tool_frequency(
    events: list[ToolUsageEvent],
) -> dict[str, float]:
    """Compute per-tool session presence fraction (0..1).

    Returns mapping: tool_name -> sessions_where_used / total_sessions.
    """
    sessions = _infer_sessions_by_session_start(events)
    if not sessions:
        return {}
    tool_sessions: dict[str, int] = {}
    for tools_in_sess in _tools_per_session(sessions):
        for t in tools_in_sess:
            tool_sessions[t] = tool_sessions.get(t, 0) + 1
    total = len(sessions)
    return {t: count / total for t, count in tool_sessions.items()}


def _classify_by_frequency(
    freq: dict[str, float],
    core_threshold: float = 0.80,
    rare_threshold: float = 0.10,
) -> tuple[list[str], list[str], list[str]]:
    """Classify tools into core (>80%), medium (10-80%), rare (<10%)."""
    core: list[str] = []
    medium: list[str] = []
    rare: list[str] = []
    for tool, pct in sorted(freq.items()):
        if pct >= core_threshold:
            core.append(tool)
        elif pct >= rare_threshold:
            medium.append(tool)
        else:
            rare.append(tool)
    return (core, medium, rare)


# Approximate tokens per MCP tool definition (name, description, params).
# Used to estimate initial context savings when tiered loading is enabled.
_TOKENS_PER_TOOL_ESTIMATE = 150


def _estimate_token_impact() -> tuple[int, int, int, float]:
    """Estimate token counts: all tools, always_loaded, reduction %."""
    summary = get_category_summary()
    always = summary.get("always_loaded", 0)
    deferred_m = summary.get("deferred_medium", 0)
    deferred_l = summary.get("deferred_low", 0)
    total = always + deferred_m + deferred_l
    all_tokens = total * _TOKENS_PER_TOOL_ESTIMATE
    tier1_tokens = always * _TOKENS_PER_TOOL_ESTIMATE
    reduction = (
        (all_tokens - tier1_tokens) / all_tokens * 100.0 if all_tokens > 0 else 0.0
    )
    return (all_tokens, tier1_tokens, total, reduction)


def _build_token_impact_dict() -> dict[str, int | float | str]:
    """Build token impact dict for payload."""
    all_tokens, tier1_tokens, total_tools, reduction_pct = _estimate_token_impact()
    return {
        "all_tools_count": total_tools,
        "always_loaded_count": len(get_always_loaded_tool_names()),
        "deferred_count": len(get_deferred_tool_names()),
        "tokens_per_tool_estimate": _TOKENS_PER_TOOL_ESTIMATE,
        "all_tools_tokens_estimate": all_tokens,
        "tier1_only_tokens_estimate": tier1_tokens,
        "reduction_pct_when_tiered": round(reduction_pct, 1),
        "note": (
            "When MCP supports defer_loading, sending only tier1 reduces "
            "initial tool-definition context by this percentage."
        ),
    }


class ToolFrequencyPayload(BaseModel):
    """Tool frequency and tier token impact for query_usage(tool_frequency)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(description="success or unavailable")
    project_root: str = Field(description="Project root path")
    days: int = Field(ge=1, description="Window in days")
    start: str = Field(description="Window start ISO timestamp")
    end: str = Field(description="Window end ISO timestamp")
    total_events: int = Field(ge=0)
    total_sessions: int = Field(ge=0, description="Sessions (by session_start)")
    tools_core_pct80: list[str] = Field(
        default_factory=_empty_str_list,
        description="Tools used in ≥80% of sessions (candidate always_loaded)",
    )
    tools_medium_pct10_80: list[str] = Field(
        default_factory=_empty_str_list,
        description="Tools used in 10-80% of sessions",
    )
    tools_rare_pct10: list[str] = Field(
        default_factory=_empty_str_list,
        description="Tools used in <10% of sessions",
    )
    per_tool_pct: dict[str, float] = Field(
        default_factory=dict,
        description="Tool -> session presence fraction (0..1)",
    )
    token_impact: dict[str, int | float | str] = Field(
        default_factory=dict,
        description="Token savings when tiered loading enabled",
    )


async def _fetch_and_classify(
    tracker: UsageTracker | None,
    start: datetime,
    end: datetime,
) -> tuple[
    list[ToolUsageEvent], dict[str, float], list[str], list[str], list[str], str
]:
    """Fetch events and classify tools; return (events, freq, core, medium, rare, status)."""
    events: list[ToolUsageEvent] = []
    freq: dict[str, float] = {}
    core: list[str] = []
    medium: list[str] = []
    rare: list[str] = []
    status = "success"
    if tracker is None:
        return (events, freq, core, medium, rare, "unavailable")
    events = await tracker.search_usage(
        start_date=start,
        end_date=end,
        tool_name=None,
        success=None,
        limit=10000,
    )
    freq = compute_tool_frequency(events)
    core, medium, rare = _classify_by_frequency(freq)
    return (events, freq, core, medium, rare, status)


async def get_tool_frequency_payload(
    root: Path,
    tracker: UsageTracker | None,
    days: int = 30,
) -> ToolFrequencyPayload:
    """Build tool frequency and token impact payload."""
    end = datetime.now(UTC)
    start = end - timedelta(days=max(1, min(days, 365)))
    events, freq, core, medium, rare, status = await _fetch_and_classify(
        tracker, start, end
    )
    sessions_count = len(_infer_sessions_by_session_start(events))
    token_impact = _build_token_impact_dict()
    return ToolFrequencyPayload(
        status=status,
        project_root=str(root),
        days=days,
        start=start.isoformat(),
        end=end.isoformat(),
        total_events=len(events),
        total_sessions=sessions_count,
        tools_core_pct80=sorted(core),
        tools_medium_pct10_80=sorted(medium),
        tools_rare_pct10=sorted(rare),
        per_tool_pct={k: round(v, 3) for k, v in freq.items()},
        token_impact=token_impact,
    )
