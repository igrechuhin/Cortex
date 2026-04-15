"""Phase 57 / Anthropic Step 3: Redundant tool call detection helpers.

Detects repeated identical calls, sequential same-tool runs, and tool
error rate by parameter from usage events. Used by query_usage(redundancy)
and the Phase 57 evaluation dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker


def _parse_ts(ts: str) -> datetime:
    """Parse ISO timestamp; return epoch on failure."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.fromtimestamp(0, tz=UTC)


def _infer_sessions(
    events: list[ToolUsageEvent],
    gap_minutes: int = 5,
) -> list[list[ToolUsageEvent]]:
    """Group events into sessions by time gap. Gaps > gap_minutes = new session."""
    if not events:
        return []
    sorted_evs = sorted(events, key=lambda e: e.timestamp)
    sessions: list[list[ToolUsageEvent]] = []
    current: list[ToolUsageEvent] = [sorted_evs[0]]
    for ev in sorted_evs[1:]:
        prev_ts = _parse_ts(current[-1].timestamp)
        curr_ts = _parse_ts(ev.timestamp)
        if (curr_ts - prev_ts).total_seconds() > gap_minutes * 60:
            sessions.append(current)
            current = [ev]
        else:
            current.append(ev)
    sessions.append(current)
    return sessions


@dataclass
class RepeatedIdenticalPattern:
    """Pattern: same tool + same params_hash called repeatedly in sessions."""

    tool_name: str
    params_hash: str | None
    total_occurrences: int
    session_count: int
    max_per_session: int


@dataclass
class SequentialSameToolPattern:
    """Pattern: sequential runs of the same tool (may indicate pagination need)."""

    tool_name: str
    max_run_length: int
    session_count: int
    total_sequential_runs: int


@dataclass
class ErrorByParamPattern:
    """Pattern: error rate by param_validation_failure or error_type."""

    tool_name: str
    param_or_error: str
    error_count: int
    total_calls: int
    error_rate: float


def _compute_repeated_identical(
    sessions: list[list[ToolUsageEvent]],
) -> list[RepeatedIdenticalPattern]:
    """Find repeated identical calls (tool_name + params_hash) per session."""
    patterns: list[RepeatedIdenticalPattern] = []
    seen: dict[tuple[str, str | None], list[int]] = {}
    for session in sessions:
        by_key: dict[tuple[str, str | None], int] = {}
        for ev in session:
            key = (ev.tool_name, ev.params_hash)
            by_key[key] = by_key.get(key, 0) + 1
        for key, count in by_key.items():
            if count > 1:
                seen.setdefault(key, []).append(count)
    for (tool_name, params_hash), counts in seen.items():
        patterns.append(
            RepeatedIdenticalPattern(
                tool_name=tool_name,
                params_hash=params_hash,
                total_occurrences=sum(counts),
                session_count=len(counts),
                max_per_session=max(counts),
            )
        )
    return sorted(patterns, key=lambda p: -p.total_occurrences)


def _runs_in_session(session: list[ToolUsageEvent]) -> list[tuple[str, int]]:
    """Extract (tool_name, run_length) for runs of length >= 2 in a session."""
    if not session:
        return []
    runs: list[tuple[str, int]] = []
    prev = session[0].tool_name
    run_len = 1
    for ev in session[1:]:
        if ev.tool_name == prev:
            run_len += 1
        else:
            if run_len >= 2:
                runs.append((prev, run_len))
            prev = ev.tool_name
            run_len = 1
    if run_len >= 2:
        runs.append((prev, run_len))
    return runs


def _compute_sequential_same_tool(
    sessions: list[list[ToolUsageEvent]],
) -> list[SequentialSameToolPattern]:
    """Find longest sequential runs of same tool per session."""
    by_tool: dict[str, list[int]] = {}
    for session in sessions:
        runs = _runs_in_session(session)
        max_per_tool_in_session: dict[str, int] = {}
        for tool_name, length in runs:
            max_per_tool_in_session[tool_name] = max(
                max_per_tool_in_session.get(tool_name, 0), length
            )
        for tool_name, max_len in max_per_tool_in_session.items():
            by_tool.setdefault(tool_name, []).append(max_len)
    return sorted(
        (
            SequentialSameToolPattern(
                tool_name=tool_name,
                max_run_length=max(max_per_session),
                session_count=len(max_per_session),
                total_sequential_runs=len(max_per_session),
            )
            for tool_name, max_per_session in by_tool.items()
        ),
        key=lambda p: -p.max_run_length,
    )


def _compute_error_rate_by_param(
    events: list[ToolUsageEvent],
) -> list[ErrorByParamPattern]:
    """Compute error rate by param_validation_failure or error_type per tool."""
    by_tool_param: dict[tuple[str, str], int] = {}
    by_tool: dict[str, int] = {}
    for ev in events:
        by_tool[ev.tool_name] = by_tool.get(ev.tool_name, 0) + 1
        if not ev.success:
            param = ev.param_validation_failure or ev.error_type or "unknown"
            key = (ev.tool_name, param)
            by_tool_param[key] = by_tool_param.get(key, 0) + 1
    out: list[ErrorByParamPattern] = []
    for (tool_name, param), err_count in by_tool_param.items():
        total = by_tool.get(tool_name, err_count)
        if total <= 0:
            continue
        rate = err_count / total
        out.append(
            ErrorByParamPattern(
                tool_name=tool_name,
                param_or_error=param,
                error_count=err_count,
                total_calls=total,
                error_rate=rate,
            )
        )
    return sorted(out, key=lambda p: (-p.error_rate, -p.error_count))


def compute_redundancy_from_events(
    events: list[ToolUsageEvent],
    gap_minutes: int = 5,
) -> tuple[
    list[RepeatedIdenticalPattern],
    list[SequentialSameToolPattern],
    list[ErrorByParamPattern],
]:
    """Compute redundancy metrics from usage events."""
    sessions = _infer_sessions(events, gap_minutes)
    repeated = _compute_repeated_identical(sessions)
    sequential = _compute_sequential_same_tool(sessions)
    error_by_param = _compute_error_rate_by_param(events)
    return repeated, sequential, error_by_param


# --- Pydantic models for JSON output ---


class RepeatedIdenticalEntry(BaseModel):
    """JSON-serializable repeated identical call pattern."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    tool_name: str = Field(description="MCP tool name")
    params_hash: str | None = Field(description="Hash of params or None")
    total_occurrences: int = Field(ge=0)
    session_count: int = Field(ge=0)
    max_per_session: int = Field(ge=0)


class SequentialSameToolEntry(BaseModel):
    """JSON-serializable sequential same-tool pattern."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    tool_name: str = Field(description="MCP tool name")
    max_run_length: int = Field(ge=0)
    session_count: int = Field(ge=0)
    total_sequential_runs: int = Field(ge=0)


class ErrorByParamEntry(BaseModel):
    """JSON-serializable error-by-param pattern."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    tool_name: str = Field(description="MCP tool name")
    param_or_error: str = Field(description="param_validation_failure or error_type")
    error_count: int = Field(ge=0)
    total_calls: int = Field(ge=0)
    error_rate: float = Field(ge=0.0, le=1.0)


class RedundancyStatus(str, Enum):
    """Status for redundancy payload."""

    SUCCESS = "success"
    UNAVAILABLE = "unavailable"


class RedundancyPayload(BaseModel):
    """Full redundancy metrics payload for query_usage(redundancy)."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    status: RedundancyStatus = RedundancyStatus.SUCCESS
    project_root: str = Field(description="Project root path")
    days: int = Field(ge=1, description="Window in days")
    start: str = Field(description="Window start ISO timestamp")
    end: str = Field(description="Window end ISO timestamp")
    total_events: int = Field(ge=0)
    repeated_identical: list[RepeatedIdenticalEntry] = Field(
        default_factory=lambda: cast(list[RepeatedIdenticalEntry], [])
    )
    sequential_same_tool: list[SequentialSameToolEntry] = Field(
        default_factory=lambda: cast(list[SequentialSameToolEntry], [])
    )
    error_rate_by_param: list[ErrorByParamEntry] = Field(
        default_factory=lambda: cast(list[ErrorByParamEntry], [])
    )
    tool_improvement_hints: list[str] = Field(
        default_factory=list,
        description="Suggestions for tools to improve based on redundancy data",
    )


def _build_improvement_hints(
    repeated: list[RepeatedIdenticalPattern],
    sequential: list[SequentialSameToolPattern],
    error_by_param: list[ErrorByParamPattern],
) -> list[str]:
    """Generate tool improvement hints from redundancy patterns."""
    hints: list[str] = []
    seen_tools: set[str] = set()
    for p in repeated[:5]:
        if p.tool_name not in seen_tools:
            hints.append(
                f"{p.tool_name}: repeated identical calls ({p.total_occurrences} in "
                + f"{p.session_count} sessions, max {p.max_per_session}/session) — "
                + "consider caching or batching."
            )
            seen_tools.add(p.tool_name)
    for p in sequential[:5]:
        if p.tool_name not in seen_tools:
            hints.append(
                f"{p.tool_name}: sequential same-tool runs (max {p.max_run_length}) — "
                + "consider pagination or range parameters."
            )
            seen_tools.add(p.tool_name)
    for p in error_by_param[:5]:
        if p.tool_name not in seen_tools and p.error_rate >= 0.05:
            hints.append(
                f"{p.tool_name}: high error rate for '{p.param_or_error}' "
                + f"({p.error_rate:.0%}) — improve description or defaults."
            )
            seen_tools.add(p.tool_name)
    return hints[:10]


def _to_repeated_entries(
    repeated: list[RepeatedIdenticalPattern],
) -> list[RepeatedIdenticalEntry]:
    """Convert dataclass patterns to Pydantic entries."""
    return [
        RepeatedIdenticalEntry(
            tool_name=p.tool_name,
            params_hash=p.params_hash,
            total_occurrences=p.total_occurrences,
            session_count=p.session_count,
            max_per_session=p.max_per_session,
        )
        for p in repeated[:20]
    ]


def _to_sequential_entries(
    sequential: list[SequentialSameToolPattern],
) -> list[SequentialSameToolEntry]:
    """Convert dataclass patterns to Pydantic entries."""
    return [
        SequentialSameToolEntry(
            tool_name=p.tool_name,
            max_run_length=p.max_run_length,
            session_count=p.session_count,
            total_sequential_runs=p.total_sequential_runs,
        )
        for p in sequential[:20]
    ]


def _to_error_entries(
    error_by_param: list[ErrorByParamPattern],
) -> list[ErrorByParamEntry]:
    """Convert dataclass patterns to Pydantic entries."""
    return [
        ErrorByParamEntry(
            tool_name=p.tool_name,
            param_or_error=p.param_or_error,
            error_count=p.error_count,
            total_calls=p.total_calls,
            error_rate=p.error_rate,
        )
        for p in error_by_param[:20]
    ]


async def get_redundancy_payload(
    root: Path,
    tracker: UsageTracker,
    days: int = 30,
    gap_minutes: int = 5,
) -> RedundancyPayload:
    """Fetch usage events and build redundancy payload."""
    end = datetime.now(UTC)
    start = end - timedelta(days=max(1, min(days, 365)))
    events = await tracker.search_usage(
        start_date=start,
        end_date=end,
        tool_name=None,
        success=None,
        limit=5000,
    )
    repeated, sequential, error_by_param = compute_redundancy_from_events(
        events, gap_minutes
    )
    hints = _build_improvement_hints(repeated, sequential, error_by_param)
    return RedundancyPayload(
        status=RedundancyStatus.SUCCESS,
        project_root=str(root),
        days=days,
        start=start.isoformat(),
        end=end.isoformat(),
        total_events=len(events),
        repeated_identical=_to_repeated_entries(repeated),
        sequential_same_tool=_to_sequential_entries(sequential),
        error_rate_by_param=_to_error_entries(error_by_param),
        tool_improvement_hints=hints,
    )
