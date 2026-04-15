"""Token efficiency analysis (Anthropic context engineering Step 2).

Identifies top token-expensive tools from usage events with response_tokens.
Used by query_usage(query_type="token_efficiency").
Includes optimization recommendations for expensive tools.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker

# Tool-specific optimization recommendations (Anthropic Step 2)
_TOOL_OPTIMIZATION_HINTS: dict[str, str] = {
    "load_context": "Use depth=metadata_only or summary for lighter responses; response_format=concise.",
    "manage_file": "Use sections=[...] to fetch only needed sections; avoid full file reads when possible.",
    "query_usage": "Use response_format=concise; add limit for search/report; days=7 for recent-only.",
    "rules": "Use task_description to narrow rules; avoid loading all rules when few are needed.",
    "get_synapse_rules": "Use task_description for relevance filtering.",
    "execute_pre_commit_checks": 'Run focused checks (e.g. checks=["format"]) instead of full pipeline.',
    "run_tool_evaluation": "Use mode=fast for quicker runs; category to limit scope.",
}


class TokenEfficiencyEntry(BaseModel):
    """Per-tool token efficiency summary."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

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

    model_config = ConfigDict(extra=EXTRA_FORBID)

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
    optimization_recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations for top expensive tools",
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


def _build_optimization_recommendations(
    top_total: list[TokenEfficiencyEntry],
    top_avg: list[TokenEfficiencyEntry],
) -> list[str]:
    """Build optimization recommendations for top expensive tools."""
    seen: set[str] = set()
    recs: list[str] = []
    threshold_avg = 500  # Suggest optimization when avg > 500 tokens/call
    for entry in top_total[:5] + top_avg[:5]:
        if entry.tool_name in seen:
            continue
        seen.add(entry.tool_name)
        hint = _TOOL_OPTIMIZATION_HINTS.get(entry.tool_name)
        if hint:
            recs.append(f"{entry.tool_name}: {hint}")
        elif entry.avg_tokens_per_call >= threshold_avg:
            recs.append(
                f"{entry.tool_name}: avg {entry.avg_tokens_per_call:.0f} tokens/call; "
                + "consider truncation, pagination, or response_format=concise."
            )
    return recs


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
    recommendations = _build_optimization_recommendations(top_total, top_avg)
    return TokenEfficiencyPayload(
        status="success",
        project_root=str(root),
        days=days,
        event_count_with_tokens=len(with_tokens),
        top_by_total=top_total,
        top_by_avg=top_avg,
        optimization_recommendations=recommendations,
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
