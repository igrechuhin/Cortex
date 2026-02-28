"""Drift detection for production monitoring (Plan: Evaluation Framework Maturation Step 5).

Compares current vs baseline metrics and emits alerts when |z| > sigma_threshold.
Used by phase5_production_monitoring_helpers.
"""

from __future__ import annotations

from cortex.tools.phase5_production_monitoring_metrics import mean_std
from cortex.tools.phase5_production_monitoring_models import (
    DriftAlert,
    GlobalMetricSummary,
    ToolMetricSummary,
)


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
    rate_mean, rate_std = mean_std(rates)
    dur_mean, dur_std = mean_std(durations)
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


def compute_drift_alerts(
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
