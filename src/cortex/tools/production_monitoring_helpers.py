"""Production monitoring and drift detection (Plan: Evaluation Framework Maturation Step 5).

Computes rolling baseline metrics, current-window metrics, drift alerts (>2σ),
and weekly report summary. Used by query_usage(query_type="production_monitoring").
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker
from cortex.tools.production_monitoring_drift import compute_drift_alerts
from cortex.tools.production_monitoring_metrics import (
    aggregate_events_to_metrics,
    daily_global_metrics,
)
from cortex.tools.production_monitoring_models import (
    DriftAlert,
    GlobalMetricSummary,
    ProductionMonitoringPayload,
    ToolMetricSummary,
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
    baseline_daily = daily_global_metrics(baseline_events)
    drift_alerts = compute_drift_alerts(
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
    current_tools, current_global = aggregate_events_to_metrics(current_events)
    baseline_tools, baseline_global = aggregate_events_to_metrics(baseline_events)
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
