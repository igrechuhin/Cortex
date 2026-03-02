"""Tests for tool description optimization (Phase 57 Step 4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.evaluation.evaluation_optimization_helpers import (
    ERROR_RATE_THRESHOLD,
    ToolDescriptionOptimizationPayload,
    get_tool_description_optimization_payload,
)
from cortex.tools.query_usage_operations import query_usage


@pytest.mark.asyncio
async def test_get_tool_description_optimization_payload_unavailable(
    tmp_path: Path,
) -> None:
    """When tracker is None, payload status is unavailable with message."""
    payload = await get_tool_description_optimization_payload(
        tmp_path, None, "load_context", days=90
    )
    assert payload.status == "unavailable"
    assert payload.tool_name == "load_context"
    assert payload.message == "Usage tracker not available"
    assert payload.total_calls == 0
    assert payload.error_rate == 0.0
    assert payload.ab_test_plan


@pytest.mark.asyncio
async def test_get_tool_description_optimization_payload_empty_tools(
    tmp_path: Path,
) -> None:
    """When tracker returns no tools for tool_name, payload has zero stats and suggestions."""
    tracker = AsyncMock()
    tracker.get_usage_stats = AsyncMock(return_value={"tools": [], "total_events": 0})
    payload = await get_tool_description_optimization_payload(
        tmp_path, tracker, "unknown_tool", days=30
    )
    assert payload.status == "success"
    assert payload.tool_name == "unknown_tool"
    assert payload.total_calls == 0
    assert payload.error_rate == 0.0
    assert payload.meets_optimization_threshold is False
    assert any(
        "No usage data" in s for s in payload.suggestions
    ), "Expected suggestion for no usage"
    assert len(payload.ab_test_plan) >= 3


@pytest.mark.asyncio
async def test_get_tool_description_optimization_payload_with_stats(
    tmp_path: Path,
) -> None:
    """When tracker returns one tool with stats, payload has error_rate and suggestions."""
    tracker = AsyncMock()
    tracker.get_usage_stats = AsyncMock(
        return_value={
            "tools": [
                {
                    "tool_name": "manage_file",
                    "total_calls": 100,
                    "successful_calls": 92,
                    "failed_calls": 8,
                    "error_types": {"ValidationError": 5, "TimeoutError": 3},
                    "avg_duration_ms": 50.0,
                    "min_duration_ms": 10.0,
                    "max_duration_ms": 200.0,
                    "first_used": "2025-01-01T00:00:00+00:00",
                    "last_used": "2025-02-01T00:00:00+00:00",
                }
            ],
            "total_events": 100,
        }
    )
    tracker.search_usage = AsyncMock(return_value=[])
    payload = await get_tool_description_optimization_payload(
        tmp_path, tracker, "manage_file", days=90
    )
    assert payload.status == "success"
    assert payload.tool_name == "manage_file"
    assert payload.total_calls == 100
    assert payload.error_rate == 0.08
    assert payload.error_rate > ERROR_RATE_THRESHOLD
    assert payload.meets_optimization_threshold is True
    assert payload.error_types == {"ValidationError": 5, "TimeoutError": 3}
    assert any("USE WHEN" in s or "Clarify" in s for s in payload.suggestions)
    assert len(payload.ab_test_plan) >= 3


@pytest.mark.asyncio
async def test_get_tool_description_optimization_payload_with_failed_events(
    tmp_path: Path,
) -> None:
    """Failed events with param_validation_failure or retry_count influence suggestions."""
    tracker = AsyncMock()
    tracker.get_usage_stats = AsyncMock(
        return_value={
            "tools": [
                {
                    "tool_name": "load_context",
                    "total_calls": 20,
                    "successful_calls": 18,
                    "failed_calls": 2,
                    "error_types": {},
                    "avg_duration_ms": 100.0,
                    "min_duration_ms": 50.0,
                    "max_duration_ms": 200.0,
                    "first_used": "2025-01-01T00:00:00+00:00",
                    "last_used": "2025-01-15T00:00:00+00:00",
                }
            ],
            "total_events": 20,
        }
    )
    failed_event = ToolUsageEvent(
        tool_name="load_context",
        timestamp="2025-01-15T12:00:00+00:00",
        duration_ms=100.0,
        success=False,
        error_type="ValidationError",
        param_validation_failure="token_budget required",
        retry_count=1,
    )
    tracker.search_usage = AsyncMock(return_value=[failed_event])
    payload = await get_tool_description_optimization_payload(
        tmp_path, tracker, "load_context", days=90
    )
    assert payload.status == "success"
    assert payload.meets_optimization_threshold is True
    assert any(
        "parameter" in s.lower() or "param" in s.lower() or "retry" in s.lower()
        for s in payload.suggestions
    )


@pytest.mark.asyncio
async def test_query_usage_tool_description_optimization_returns_json(
    tmp_path: Path,
) -> None:
    """query_usage(query_type=tool_description_optimization) returns valid JSON."""
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result = await query_usage(
            query_type="tool_description_optimization",
            tool_name="get_structure_info",
            days=90,
            ctx=None,
        )
    data = json.loads(result)
    assert data["status"] == "unavailable"
    assert data["tool_name"] == "get_structure_info"
    assert "ab_test_plan" in data
    assert "suggestions" in data
    _ = ToolDescriptionOptimizationPayload.model_validate(data)


@pytest.mark.asyncio
async def test_query_usage_tool_description_optimization_requires_tool_name() -> None:
    """query_usage(tool_description_optimization) without tool_name returns error."""
    result = await query_usage(
        query_type="tool_description_optimization",
        tool_name=None,
        ctx=None,
    )
    data = json.loads(result)
    assert data["status"] == "error"
    assert "tool_name" in data.get("error", "").lower()


@pytest.mark.asyncio
async def test_query_usage_tool_description_optimization_with_tracker(
    tmp_path: Path,
) -> None:
    """query_usage(tool_description_optimization) with mocked tracker returns success."""
    tracker = AsyncMock()
    tracker.get_usage_stats = AsyncMock(
        return_value={
            "tools": [
                {
                    "tool_name": "validate",
                    "total_calls": 10,
                    "successful_calls": 10,
                    "failed_calls": 0,
                    "error_types": {},
                    "avg_duration_ms": 20.0,
                    "min_duration_ms": 10.0,
                    "max_duration_ms": 50.0,
                    "first_used": "2025-01-01T00:00:00+00:00",
                    "last_used": "2025-01-10T00:00:00+00:00",
                }
            ],
            "total_events": 10,
        }
    )
    tracker.search_usage = AsyncMock(return_value=[])
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=tmp_path,
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=tracker,
        ),
    ):
        result = await query_usage(
            query_type="tool_description_optimization",
            tool_name="validate",
            days=30,
            ctx=None,
        )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool_name"] == "validate"
    assert data["total_calls"] == 10
    assert data["error_rate"] == 0.0
    assert data["meets_optimization_threshold"] is False
    assert isinstance(data["suggestions"], list)
    assert isinstance(data["ab_test_plan"], list)
