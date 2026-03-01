"""Tests for production monitoring helpers (Plan: Evaluation Framework Maturation Step 5)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.production_monitoring_helpers import (
    get_production_monitoring_payload,
)
from cortex.tools.production_monitoring_models import (
    DriftAlert,
    GlobalMetricSummary,
    ToolMetricSummary,
)


def test_tool_metric_summary_model() -> None:
    """ToolMetricSummary accepts valid fields."""
    m = ToolMetricSummary(
        tool_name="manage_file",
        total_calls=10,
        successful_calls=8,
        success_rate=0.8,
        avg_duration_ms=5.0,
        error_types={"ValidationError": 2},
    )
    assert m.tool_name == "manage_file"
    assert m.success_rate == 0.8


def test_global_metric_summary_model() -> None:
    """GlobalMetricSummary accepts valid fields."""
    g = GlobalMetricSummary(
        total_calls=100,
        successful_calls=95,
        success_rate=0.95,
        avg_duration_ms=20.0,
        tools_count=5,
    )
    assert g.total_calls == 100
    assert g.tools_count == 5


def test_drift_alert_model() -> None:
    """DriftAlert accepts valid fields."""
    a = DriftAlert(
        tool_name="global",
        metric_name="success_rate",
        current_value=0.7,
        baseline_mean=0.95,
        baseline_std=0.05,
        z_score=-5.0,
    )
    assert a.tool_name == "global"
    assert a.z_score == -5.0


@pytest.mark.asyncio
async def test_get_production_monitoring_payload_unavailable(tmp_path: Path) -> None:
    """When tracker is None, payload status is unavailable."""
    payload = await get_production_monitoring_payload(
        tmp_path, None, days_baseline=7, current_window_hours=24
    )
    assert payload.status == "unavailable"
    assert payload.message == "Usage tracker not available"
    assert payload.baseline_days == 7
    assert payload.current_window_hours == 24
    assert payload.metrics_current_global.total_calls == 0
    assert payload.metrics_baseline_global.total_calls == 0


@pytest.mark.asyncio
async def test_get_production_monitoring_payload_success(tmp_path: Path) -> None:
    """When tracker returns events, payload has success and metrics."""
    tracker = AsyncMock()
    tracker.search_usage = AsyncMock(
        return_value=[
            ToolUsageEvent(
                tool_name="manage_file",
                timestamp="2026-02-21T12:00:00Z",
                duration_ms=5.0,
                success=True,
            ),
        ]
    )
    payload = await get_production_monitoring_payload(
        tmp_path, tracker, days_baseline=7, current_window_hours=24
    )
    assert payload.status == "success"
    assert payload.project_root == str(tmp_path)
    assert payload.baseline_days == 7
    assert payload.current_window_hours == 24
    assert payload.generated_at
    assert len(payload.metrics_current_tools) >= 0
    assert payload.metrics_current_global.total_calls >= 0
    assert "Production monitoring report" in payload.weekly_summary_text


@pytest.mark.asyncio
async def test_get_production_monitoring_payload_aggregates_events(
    tmp_path: Path,
) -> None:
    """Payload aggregates multiple events into correct success_rate and counts."""
    tracker = AsyncMock()
    tracker.search_usage = AsyncMock(
        return_value=[
            ToolUsageEvent(
                tool_name="manage_file",
                timestamp="2026-02-21T12:00:00Z",
                duration_ms=10.0,
                success=True,
            ),
            ToolUsageEvent(
                tool_name="manage_file",
                timestamp="2026-02-21T12:01:00Z",
                duration_ms=20.0,
                success=False,
                error_type="ValidationError",
            ),
        ]
    )
    payload = await get_production_monitoring_payload(
        tmp_path, tracker, days_baseline=7, current_window_hours=24
    )
    assert payload.status == "success"
    assert payload.metrics_current_global.total_calls == 2
    assert payload.metrics_current_global.successful_calls == 1
    assert payload.metrics_current_global.success_rate == 0.5
    assert payload.metrics_current_global.avg_duration_ms == 15.0
    assert len(payload.metrics_current_tools) == 1
    assert payload.metrics_current_tools[0].tool_name == "manage_file"
    assert payload.metrics_current_tools[0].success_rate == 0.5


@pytest.mark.asyncio
async def test_production_monitoring_payload_serializable(tmp_path: Path) -> None:
    """Payload is JSON-serializable for query_usage response."""
    tracker = AsyncMock()
    tracker.search_usage = AsyncMock(return_value=[])
    payload = await get_production_monitoring_payload(
        tmp_path, tracker, days_baseline=7, current_window_hours=24
    )
    dumped = payload.model_dump(mode="json")
    json_str = json.dumps(dumped)
    data = json.loads(json_str)
    assert data["status"] == "success"
    assert "baseline_days" in data
    assert "drift_alerts" in data
    assert "weekly_summary_text" in data
