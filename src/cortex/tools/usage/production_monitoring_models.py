"""Pydantic models for production monitoring (Plan: Evaluation Framework Maturation Step 5).

Used by production_monitoring_helpers and query_usage(query_type="production_monitoring").
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID


class ToolMetricSummary(BaseModel):
    """Per-tool metrics for a time window."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

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

    model_config = ConfigDict(extra=EXTRA_FORBID)

    total_calls: int = Field(ge=0)
    successful_calls: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    avg_duration_ms: float = Field(ge=0.0)
    tools_count: int = Field(ge=0)


class DriftAlert(BaseModel):
    """Single drift alert: metric deviates > sigma from baseline."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    tool_name: str = Field(description='Tool (or "global")')
    metric_name: str = Field(description="e.g. success_rate, avg_duration_ms")
    current_value: float = Field(description="Current window value")
    baseline_mean: float = Field(description="Baseline mean")
    baseline_std: float = Field(ge=0.0, description="Baseline standard deviation")
    z_score: float = Field(description="(current - mean) / std when std > 0")


def _default_tool_metric_summaries() -> list[ToolMetricSummary]:
    return []


def _default_drift_alerts() -> list[DriftAlert]:
    return []


class ProductionMonitoringPayload(BaseModel):
    """Full payload for query_usage(query_type=\"production_monitoring\")."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    status: str = Field(description="success or unavailable")
    project_root: str = Field(default="", description="Project root path")
    baseline_days: int = Field(ge=1, le=30, description="Baseline window in days")
    current_window_hours: int = Field(
        ge=1, le=168, description="Current window in hours"
    )
    generated_at: str = Field(description="ISO timestamp of report generation")
    metrics_current_tools: list[ToolMetricSummary] = Field(
        default_factory=_default_tool_metric_summaries,
        description="Per-tool metrics for current window",
    )
    metrics_baseline_tools: list[ToolMetricSummary] = Field(
        default_factory=_default_tool_metric_summaries,
        description="Per-tool metrics for baseline",
    )
    metrics_current_global: GlobalMetricSummary = Field(
        description="Global metrics for current window"
    )
    metrics_baseline_global: GlobalMetricSummary = Field(
        description="Global metrics for baseline"
    )
    drift_alerts: list[DriftAlert] = Field(
        default_factory=_default_drift_alerts,
        description="Alerts when metric >2σ from baseline",
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
