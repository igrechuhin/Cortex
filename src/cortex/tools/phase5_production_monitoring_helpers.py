"""Production monitoring and drift detection (Plan: Evaluation Framework Maturation Step 5).

Computes rolling baseline metrics, current-window metrics, drift alerts (>2σ),
and weekly report summary. Used by query_usage(query_type="production_monitoring").
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker


class ToolMetricSummary(BaseModel):
    """Per-tool metrics for a time window."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(description="MCP tool name")
    total_calls: int = Field(ge=0, description="Total calls in window")
    successful_calls: int = Field(ge=0, description="Successful calls")
    success_rate: float = Field(
        ge=0.0, le=1.0, description="successful_calls / total_calls"
    )
    avg_duration_ms: float = Field(ge=0.0, description="Average duration in ms")
    error_types: dict[str, int] = Field(
        default_factory=dict, description="Error type to count"
    )


class GlobalMetricSummary(BaseModel):
    """Global (all-tools) metrics for a time window."""

    model_config = ConfigDict(extra="forbid")

    total_calls: int = Field(ge=0)
    successful_calls: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    avg_duration_ms: float = Field(ge=0.0)
    tools_count: int = Field(ge=0)


class DriftAlert(BaseModel):
    """Single drift alert: metric deviates > sigma from baseline."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(description='Tool (or "global")')
    metric_name: str = Field(description="e.g. success_rate, avg_duration_ms")
    current_value: float = Field(description="Current window value")
    baseline_mean: float = Field(description="Baseline mean")
    baseline_std: float = Field(ge=0.0, description="Baseline standard deviation")
    z_score: float = Field(description="(current - mean) / std when std > 0")


def _one_tool_metric(tool_name: str, evs: list[ToolUsageEvent]) -> ToolMetricSummary:
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


def _aggregate_events_to_metrics(
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
        m = _one_tool_metric(tool_name, evs)
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


def _daily_global_metrics(events: list[ToolUsageEvent]) -> list[tuple[float, float]]:
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


def _mean_std(values: list[float]) -> tuple[float, float]:
    """Return (mean, std). std is 0 if len < 2; else sample std."""
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(variance) if variance >= 0 else 0.0


def _drift_alerts_per_tool(
    current_tools: list[ToolMetricSummary],
    baseline_tools: list[ToolMetricSummary],
    sigma_threshold: float,
) -> list[DriftAlert]:
    """Build drift alerts for per-tool metrics."""
    alerts: list[DriftAlert] = []
    baseline_by_tool = {m.tool_name: m for m in baseline_tools}
    for cur in current_tools:
        base = baseline_by_tool.get(cur.tool_name)
        if base is None:
            continue
        for metric in ("success_rate", "avg_duration_ms"):
            cur_val = getattr(cur, metric)
            base_mean = getattr(base, metric)
            std = 1e-6 if metric == "success_rate" else max(1.0, base_mean * 0.1)
            z = (cur_val - base_mean) / std if std > 0 else 0.0
            if abs(z) > sigma_threshold:
                alerts.append(
                    DriftAlert(
                        tool_name=cur.tool_name,
                        metric_name=metric,
                        current_value=round(cur_val, 4),
                        baseline_mean=round(base_mean, 4),
                        baseline_std=round(std, 4),
                        z_score=round(z, 2),
                    )
                )
    return alerts


def _one_global_drift_alert(
    metric_name: str,
    current_val: float,
    base_mean: float,
    base_std: float,
    z: float,
) -> DriftAlert:
    """Build one DriftAlert for global metric."""
    return DriftAlert(
        tool_name="global",
        metric_name=metric_name,
        current_value=round(current_val, 4),
        baseline_mean=round(base_mean, 4),
        baseline_std=round(base_std, 4),
        z_score=round(z, 2),
    )


def _append_global_rate_alert(
    alerts: list[DriftAlert],
    current_global: GlobalMetricSummary,
    rate_mean: float,
    rate_std: float,
    sigma_threshold: float,
) -> None:
    """Append success_rate drift alert if z > threshold."""
    z_rate = (current_global.success_rate - rate_mean) / (rate_std or 1e-6)
    if abs(z_rate) <= sigma_threshold:
        return
    alerts.append(
        _one_global_drift_alert(
            "success_rate",
            current_global.success_rate,
            rate_mean,
            rate_std or 1e-6,
            z_rate,
        )
    )


def _drift_alerts_global(
    current_global: GlobalMetricSummary,
    baseline_daily: list[tuple[float, float]],
    sigma_threshold: float,
) -> list[DriftAlert]:
    """Build drift alerts for global metrics from daily baseline."""
    if not baseline_daily or current_global.total_calls < 1:
        return []
    rates = [r for r, _ in baseline_daily]
    durations = [d for _, d in baseline_daily]
    rate_mean, rate_std = _mean_std(rates)
    dur_mean, dur_std = _mean_std(durations)
    alerts: list[DriftAlert] = []
    _append_global_rate_alert(
        alerts, current_global, rate_mean, rate_std or 1e-6, sigma_threshold
    )
    dur_std = dur_std or max(1.0, dur_mean * 0.1)
    z_dur = (current_global.avg_duration_ms - dur_mean) / dur_std
    if abs(z_dur) > sigma_threshold:
        alerts.append(
            _one_global_drift_alert(
                "avg_duration_ms",
                current_global.avg_duration_ms,
                dur_mean,
                dur_std,
                z_dur,
            )
        )
    return alerts


def _compute_drift_alerts(
    current_tools: list[ToolMetricSummary],
    baseline_tools: list[ToolMetricSummary],
    current_global: GlobalMetricSummary,
    baseline_global: GlobalMetricSummary,
    baseline_daily: list[tuple[float, float]],
    sigma_threshold: float = 2.0,
) -> list[DriftAlert]:
    """Compare current vs baseline; return alerts when |z| > sigma_threshold."""
    alerts = _drift_alerts_per_tool(current_tools, baseline_tools, sigma_threshold)
    alerts.extend(_drift_alerts_global(current_global, baseline_daily, sigma_threshold))
    return alerts


def _format_drift_section(drift_alerts: list[DriftAlert]) -> list[str]:
    """Format drift alerts section lines."""
    if not drift_alerts:
        return ["## Drift alerts: none (within 2σ of baseline)", ""]
    lines = ["## Drift alerts (>2σ from baseline)"]
    for a in drift_alerts[:20]:
        lines.append(
            f"- {a.tool_name} / {a.metric_name}: current={a.current_value}, baseline_mean={a.baseline_mean}, z={a.z_score}"
        )
    if len(drift_alerts) > 20:
        lines.append(f"- ... and {len(drift_alerts) - 20} more.")
    lines.append("")
    return lines


def _build_weekly_summary_text(
    baseline_days: int,
    current_window_hours: int,
    global_current: GlobalMetricSummary,
    drift_alerts: list[DriftAlert],
    generated_at: str,
) -> str:
    """Generate human-readable weekly summary."""
    lines = [
        f"# Production monitoring report ({generated_at})",
        "",
        f"Baseline: rolling {baseline_days}-day window.",
        f"Current: last {current_window_hours} hours.",
        "",
        "## Global metrics (current window)",
        f"- Total calls: {global_current.total_calls}",
        f"- Success rate: {global_current.success_rate:.1%}",
        f"- Avg duration (ms): {global_current.avg_duration_ms:.1f}",
        f"- Tools used: {global_current.tools_count}",
        "",
    ]
    lines.extend(_format_drift_section(drift_alerts))
    lines.append(
        "Suggested next steps: Run eval suite after tool changes; "
        + "add failure-based eval tasks from recurring anomalies (see .cortex/evals/tasks/failure_based_evals.json)."
    )
    return "\n".join(lines)


class ProductionMonitoringPayload(BaseModel):
    """Full payload for query_usage(query_type=\"production_monitoring\")."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(description="success or unavailable")
    project_root: str = Field(default="", description="Project root path")
    baseline_days: int = Field(ge=1, le=30, description="Baseline window in days")
    current_window_hours: int = Field(
        ge=1, le=168, description="Current window in hours"
    )
    generated_at: str = Field(description="ISO timestamp of report generation")
    metrics_current_tools: list[ToolMetricSummary] = Field(  # type: ignore[reportUnknownVariableType]
        default_factory=list, description="Per-tool metrics for current window"
    )
    metrics_baseline_tools: list[ToolMetricSummary] = Field(  # type: ignore[reportUnknownVariableType]
        default_factory=list, description="Per-tool metrics for baseline"
    )
    metrics_current_global: GlobalMetricSummary = Field(
        description="Global metrics for current window"
    )
    metrics_baseline_global: GlobalMetricSummary = Field(
        description="Global metrics for baseline"
    )
    drift_alerts: list[DriftAlert] = Field(  # type: ignore[reportUnknownVariableType]
        default_factory=list, description="Alerts when metric >2σ from baseline"
    )
    weekly_summary_text: str = Field(
        default="", description="Human-readable weekly summary"
    )
    suggested_eval_tasks: list[str] = Field(
        default_factory=list,
        description="Suggested failure-based eval tasks from anomalies",
    )
    message: str | None = Field(
        default=None, description="Reason when status is unavailable"
    )


def _empty_global_metric() -> GlobalMetricSummary:
    """Empty global metric summary."""
    return GlobalMetricSummary(
        total_calls=0,
        successful_calls=0,
        success_rate=0.0,
        avg_duration_ms=0.0,
        tools_count=0,
    )


def _suggest_eval_tasks_from_drift(drift_alerts: list[DriftAlert]) -> list[str]:
    """Suggest eval tasks from drift alerts (feed anomalies into eval creation)."""
    suggestions: list[str] = []
    for a in drift_alerts[:10]:
        if a.metric_name == "success_rate" and a.z_score < -2:
            suggestions.append(
                f"Add eval task: verify {a.tool_name} success rate under load (drift detected)"
            )
        if a.metric_name == "avg_duration_ms" and a.z_score > 2:
            suggestions.append(
                f"Add eval task: verify {a.tool_name} latency within baseline (regression)"
            )
    return suggestions[:5]


def _compute_drift_and_summary(
    current_tools: list[ToolMetricSummary],
    baseline_tools: list[ToolMetricSummary],
    current_global: GlobalMetricSummary,
    baseline_global: GlobalMetricSummary,
    baseline_events: list[ToolUsageEvent],
    days_baseline: int,
    current_window_hours: int,
    sigma_threshold: float,
    generated_at: str,
) -> tuple[list[DriftAlert], str, list[str]]:
    """Compute drift alerts, weekly summary text, and suggested eval tasks."""
    baseline_daily = _daily_global_metrics(baseline_events)
    drift_alerts = _compute_drift_alerts(
        current_tools,
        baseline_tools,
        current_global,
        baseline_global,
        baseline_daily,
        sigma_threshold=sigma_threshold,
    )
    weekly_summary_text = _build_weekly_summary_text(
        days_baseline,
        current_window_hours,
        current_global,
        drift_alerts,
        generated_at,
    )
    suggested_eval_tasks = _suggest_eval_tasks_from_drift(drift_alerts)
    return drift_alerts, weekly_summary_text, suggested_eval_tasks


def _make_success_payload(
    root: Path,
    days_baseline: int,
    current_window_hours: int,
    generated_at: str,
    data: tuple[
        list[ToolMetricSummary],
        list[ToolMetricSummary],
        GlobalMetricSummary,
        GlobalMetricSummary,
        list[DriftAlert],
        str,
        list[str],
    ],
) -> ProductionMonitoringPayload:
    """Build ProductionMonitoringPayload from precomputed metrics and drift."""
    (cur_t, base_t, cur_g, base_g, drift, weekly_text, suggested) = data
    return ProductionMonitoringPayload(
        status="success",
        project_root=str(root),
        baseline_days=days_baseline,
        current_window_hours=current_window_hours,
        generated_at=generated_at,
        metrics_current_tools=cur_t,
        metrics_baseline_tools=base_t,
        metrics_current_global=cur_g,
        metrics_baseline_global=base_g,
        drift_alerts=drift,
        weekly_summary_text=weekly_text,
        suggested_eval_tasks=suggested,
    )


def _aggregate_both_windows(
    current_events: list[ToolUsageEvent],
    baseline_events: list[ToolUsageEvent],
) -> tuple[
    list[ToolMetricSummary],
    GlobalMetricSummary,
    list[ToolMetricSummary],
    GlobalMetricSummary,
]:
    """Aggregate current and baseline events to per-tool and global metrics."""
    current_tools, current_global = _aggregate_events_to_metrics(current_events)
    baseline_tools, baseline_global = _aggregate_events_to_metrics(baseline_events)
    return current_tools, current_global, baseline_tools, baseline_global


def _compute_metrics_and_drift(
    baseline_events: list[ToolUsageEvent],
    current_events: list[ToolUsageEvent],
    days_baseline: int,
    current_window_hours: int,
    sigma_threshold: float,
    generated_at: str,
) -> tuple[
    list[ToolMetricSummary],
    list[ToolMetricSummary],
    GlobalMetricSummary,
    GlobalMetricSummary,
    list[DriftAlert],
    str,
    list[str],
]:
    """Aggregate events to metrics and compute drift/summary; return all for payload."""
    cur_t, cur_g, base_t, base_g = _aggregate_both_windows(
        current_events, baseline_events
    )
    drift_alerts, weekly_text, suggested = _compute_drift_and_summary(
        cur_t,
        base_t,
        cur_g,
        base_g,
        baseline_events,
        days_baseline,
        current_window_hours,
        sigma_threshold,
        generated_at,
    )
    return cur_t, base_t, cur_g, base_g, drift_alerts, weekly_text, suggested


def _build_success_payload_from_events(
    root: Path,
    baseline_events: list[ToolUsageEvent],
    current_events: list[ToolUsageEvent],
    days_baseline: int,
    current_window_hours: int,
    sigma_threshold: float,
    generated_at: str,
) -> ProductionMonitoringPayload:
    """Compute metrics from event lists and build success payload."""
    cur_t, base_t, cur_g, base_g, drift, weekly_text, suggested = (
        _compute_metrics_and_drift(
            baseline_events,
            current_events,
            days_baseline,
            current_window_hours,
            sigma_threshold,
            generated_at,
        )
    )
    return _make_success_payload(
        root,
        days_baseline,
        current_window_hours,
        generated_at,
        (cur_t, base_t, cur_g, base_g, drift, weekly_text, suggested),
    )


async def _fetch_baseline_and_current_events(
    tracker: UsageTracker,
    now: datetime,
    days_baseline: int,
    current_window_hours: int,
) -> tuple[list[ToolUsageEvent], list[ToolUsageEvent]]:
    """Fetch baseline and current window events from tracker."""
    baseline_start = now - timedelta(days=days_baseline)
    current_start = now - timedelta(hours=min(current_window_hours, 168))
    baseline_events = await tracker.search_usage(
        start_date=baseline_start,
        end_date=now,
        tool_name=None,
        success=None,
        limit=5000,
        query=None,
    )
    current_events = await tracker.search_usage(
        start_date=current_start,
        end_date=now,
        tool_name=None,
        success=None,
        limit=5000,
        query=None,
    )
    return baseline_events, current_events


async def _fetch_and_build_success_payload(
    root: Path,
    tracker: UsageTracker,
    days_baseline: int,
    current_window_hours: int,
    sigma_threshold: float,
    now: datetime,
) -> ProductionMonitoringPayload:
    """Fetch usage events and build success ProductionMonitoringPayload."""
    baseline_events, current_events = await _fetch_baseline_and_current_events(
        tracker, now, days_baseline, current_window_hours
    )
    return _build_success_payload_from_events(
        root,
        baseline_events,
        current_events,
        days_baseline,
        current_window_hours,
        sigma_threshold,
        now.isoformat(),
    )


async def get_production_monitoring_payload(
    root: Path,
    tracker: UsageTracker | None,
    days_baseline: int = 7,
    current_window_hours: int = 24,
    sigma_threshold: float = 2.0,
) -> ProductionMonitoringPayload:
    """Build production monitoring report with baseline, current metrics, and drift."""
    if tracker is None:
        return ProductionMonitoringPayload(
            status="unavailable",
            project_root=str(root),
            baseline_days=days_baseline,
            current_window_hours=current_window_hours,
            generated_at=datetime.now(UTC).isoformat(),
            metrics_current_global=_empty_global_metric(),
            metrics_baseline_global=_empty_global_metric(),
            weekly_summary_text="",
            message="Usage tracker not available",
        )
    now = datetime.now(UTC)
    return await _fetch_and_build_success_payload(
        root, tracker, days_baseline, current_window_hours, sigma_threshold, now
    )
