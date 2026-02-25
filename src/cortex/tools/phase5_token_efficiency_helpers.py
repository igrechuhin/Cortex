"""Token efficiency analysis (Anthropic context engineering Step 2).

Identifies top token-expensive tools from usage events with response_tokens.
Used by query_usage(query_type="token_efficiency").
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker


class TokenEfficiencyEntry(BaseModel):
    """Per-tool token efficiency summary."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(description="MCP tool name")
    total_response_tokens: int = Field(
        ge=0,
        description="Sum of response_tokens across all calls",
    )
    call_count: int = Field(ge=0, description="Number of calls with token data")
    avg_tokens_per_call: float = Field(
        ge=0.0,
        description="Average response tokens per call",
    )


def _empty_token_entries() -> list[TokenEfficiencyEntry]:
    """Return empty list for Pydantic Field default_factory."""
    return []


class TokenEfficiencyPayload(BaseModel):
    """Response payload for token efficiency analysis."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(description="success or unavailable")
    project_root: str = Field(default="", description="Project root path")
    days: int = Field(ge=1, description="Analysis window in days")
    event_count_with_tokens: int = Field(
        default=0,
        ge=0,
        description="Total events with response_tokens in window",
    )
    top_by_total: list[TokenEfficiencyEntry] = Field(
        default_factory=_empty_token_entries,
        description="Top 10 tools by total response tokens",
    )
    top_by_avg: list[TokenEfficiencyEntry] = Field(
        default_factory=_empty_token_entries,
        description="Top 10 tools by average tokens per call",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable message (e.g. when no data)",
    )


def _aggregate_by_tool(events: list[ToolUsageEvent]) -> list[TokenEfficiencyEntry]:
    """Aggregate events with response_tokens by tool_name."""
    by_tool: dict[str, list[int]] = {}
    for ev in events:
        if ev.response_tokens is not None and ev.response_tokens > 0:
            by_tool.setdefault(ev.tool_name, []).append(ev.response_tokens)
    out: list[TokenEfficiencyEntry] = []
    for tool_name, tokens_list in sorted(by_tool.items()):
        total = sum(tokens_list)
        count = len(tokens_list)
        avg = total / count if count else 0.0
        out.append(
            TokenEfficiencyEntry(
                tool_name=tool_name,
                total_response_tokens=total,
                call_count=count,
                avg_tokens_per_call=round(avg, 1),
            )
        )
    return out


def _top_n(
    entries: list[TokenEfficiencyEntry],
    n: int,
    key: str,
) -> list[TokenEfficiencyEntry]:
    """Return top n entries by total_response_tokens or avg_tokens_per_call."""
    if key == "total":
        sorted_entries = sorted(
            entries,
            key=lambda e: e.total_response_tokens,
            reverse=True,
        )
    else:
        sorted_entries = sorted(
            entries,
            key=lambda e: e.avg_tokens_per_call,
            reverse=True,
        )
    return sorted_entries[:n]


def _unavailable_payload(days: int) -> TokenEfficiencyPayload:
    """Return payload when tracker is unavailable."""
    return TokenEfficiencyPayload(
        status="unavailable",
        message="Usage tracker not available",
        days=days,
        event_count_with_tokens=0,
    )


def _no_data_payload(root: Path, days: int) -> TokenEfficiencyPayload:
    """Return payload when no events have response_tokens."""
    return TokenEfficiencyPayload(
        status="success",
        project_root=str(root),
        days=days,
        event_count_with_tokens=0,
        message=(
            f"No events with response_tokens in the last {days} days. "
            "Token counting is instrumented; run tools to collect data."
        ),
    )


def _success_payload(
    root: Path,
    days: int,
    with_tokens: list[ToolUsageEvent],
    entries: list[TokenEfficiencyEntry],
    top_n: int,
) -> TokenEfficiencyPayload:
    """Build success payload with top tools by total and avg."""
    top_total = _top_n(entries, top_n, "total")
    top_avg = _top_n(entries, top_n, "avg")
    return TokenEfficiencyPayload(
        status="success",
        project_root=str(root),
        days=days,
        event_count_with_tokens=len(with_tokens),
        top_by_total=top_total,
        top_by_avg=top_avg,
    )


async def get_token_efficiency_payload(
    root: Path,
    tracker: UsageTracker | None,
    days: int = 30,
    top_n: int = 10,
) -> TokenEfficiencyPayload:
    """Build token efficiency payload from usage events with response_tokens.

    Aggregates events in the last `days` days that have response_tokens set,
    computes per-tool totals and averages, and returns top N by total and by avg.
    """
    if tracker is None:
        return _unavailable_payload(days)
    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    events = await tracker.search_usage(
        start_date=start,
        end_date=now,
        tool_name=None,
        success=None,
        limit=5000,
        query=None,
    )
    with_tokens = [
        e for e in events if e.response_tokens is not None and e.response_tokens > 0
    ]
    if not with_tokens:
        return _no_data_payload(root, days)
    entries = _aggregate_by_tool(with_tokens)
    return _success_payload(root, days, with_tokens, entries, top_n)
