"""Metric aggregation for production monitoring (Plan: Evaluation Framework Maturation Step 5).

Computes per-tool and global metrics from usage events. Used by phase5_production_monitoring_helpers.
"""

from __future__ import annotations

import math

from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.phase5_production_monitoring_models import (
    GlobalMetricSummary,
    ToolMetricSummary,
)


def one_tool_metric(tool_name: str, evs: list[ToolUsageEvent]) -> ToolMetricSummary:
    """Build ToolMetricSummary for one tool's events."""
    n = len(evs)
    success = sum(1 for e in evs if e.success)
    rate = (success / n) if n else 0.0
    avg_ms = sum(e.duration_ms for e in evs) / n if n else 0.0
    error_types: dict[str, int] = {}
    for e in evs:
        if e.error_type:
            error_types[e.error_type] = error_types.get(e.error_type, 0) + 1
    return ToolMetricSummary(
        tool_name=tool_name,
        total_calls=n,
        successful_calls=success,
        success_rate=rate,
        avg_duration_ms=avg_ms,
        error_types=error_types,
    )


def aggregate_events_to_metrics(
    events: list[ToolUsageEvent],
) -> tuple[list[ToolMetricSummary], GlobalMetricSummary]:
    """Compute per-tool and global metrics from events."""
    by_tool: dict[str, list[ToolUsageEvent]] = {}
    for ev in events:
        by_tool.setdefault(ev.tool_name, []).append(ev)
    tool_metrics: list[ToolMetricSummary] = []
    total_calls = 0
    total_success = 0
    total_duration = 0.0
    for tool_name, evs in sorted(by_tool.items()):
        m = one_tool_metric(tool_name, evs)
        tool_metrics.append(m)
        total_calls += m.total_calls
        total_success += m.successful_calls
        total_duration += m.avg_duration_ms * m.total_calls
    global_summary = GlobalMetricSummary(
        total_calls=total_calls,
        successful_calls=total_success,
        success_rate=(total_success / total_calls) if total_calls else 0.0,
        avg_duration_ms=(total_duration / total_calls) if total_calls else 0.0,
        tools_count=len(by_tool),
    )
    return tool_metrics, global_summary


def daily_global_metrics(events: list[ToolUsageEvent]) -> list[tuple[float, float]]:
    """Return list of (success_rate, avg_duration_ms) per day for baseline std."""
    by_day: dict[str, list[ToolUsageEvent]] = {}
    for ev in events:
        day = ev.timestamp[:10] if len(ev.timestamp) >= 10 else ev.timestamp
        by_day.setdefault(day, []).append(ev)
    out: list[tuple[float, float]] = []
    for evs in by_day.values():
        n = len(evs)
        if n == 0:
            continue
        success = sum(1 for e in evs if e.success)
        rate = (success / n) if n else 0.0
        avg_ms = sum(e.duration_ms for e in evs) / n
        out.append((rate, avg_ms))
    return out


def mean_std(values: list[float]) -> tuple[float, float]:
    """Return (mean, std). std is 0 if len < 2; else sample std."""
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(variance) if variance >= 0 else 0.0
