"""Tests for redundancy helpers (Anthropic context engineering Step 3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.redundancy_helpers import (
    compute_redundancy_from_events,
    get_redundancy_payload,
)


def test_compute_redundancy_repeated_identical() -> None:
    """Repeated identical calls (same tool + params_hash) are detected."""
    events = [
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=10.0,
            success=True,
            params_hash="abc123",
        ),
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:01:00Z",
            duration_ms=8.0,
            success=True,
            params_hash="abc123",
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:02:00Z",
            duration_ms=5.0,
            success=True,
            params_hash="xyz",
        ),
    ]
    repeated, _sequential, _error_by_param = compute_redundancy_from_events(
        events, gap_minutes=5
    )
    assert len(repeated) == 1
    assert repeated[0].tool_name == "load_context"
    assert repeated[0].params_hash == "abc123"
    assert repeated[0].total_occurrences == 2
    assert repeated[0].session_count == 1
    assert repeated[0].max_per_session == 2


def test_compute_redundancy_sequential_same_tool() -> None:
    """Sequential same-tool runs are detected."""
    events = [
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=10.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:00:01Z",
            duration_ms=9.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:00:02Z",
            duration_ms=8.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:00:03Z",
            duration_ms=5.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:00:04Z",
            duration_ms=4.0,
            success=True,
        ),
    ]
    _repeated, sequential, _error_by_param = compute_redundancy_from_events(
        events, gap_minutes=5
    )
    assert len(sequential) == 2
    by_name = {p.tool_name: p for p in sequential}
    assert by_name["load_context"].max_run_length == 3
    assert by_name["manage_file"].max_run_length == 2


def test_compute_redundancy_error_by_param() -> None:
    """Error rate by param_validation_failure is computed."""
    events = [
        ToolUsageEvent(
            tool_name="query_usage",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=10.0,
            success=False,
            param_validation_failure="operation required",
        ),
        ToolUsageEvent(
            tool_name="query_usage",
            timestamp="2026-02-21T12:01:00Z",
            duration_ms=8.0,
            success=False,
            param_validation_failure="operation required",
        ),
        ToolUsageEvent(
            tool_name="query_usage",
            timestamp="2026-02-21T12:02:00Z",
            duration_ms=5.0,
            success=True,
        ),
    ]
    _repeated, _sequential, error_by_param = compute_redundancy_from_events(
        events, gap_minutes=5
    )
    assert len(error_by_param) == 1
    assert error_by_param[0].tool_name == "query_usage"
    assert error_by_param[0].param_or_error == "operation required"
    assert error_by_param[0].error_count == 2
    assert error_by_param[0].total_calls == 3
    assert 0.66 <= error_by_param[0].error_rate <= 0.67


def test_compute_redundancy_empty_events() -> None:
    """Empty events returns empty lists."""
    repeated, sequential, error_by_param = compute_redundancy_from_events(
        [], gap_minutes=5
    )
    assert repeated == []
    assert sequential == []
    assert error_by_param == []
    assert repeated == []
    assert sequential == []
    assert error_by_param == []


@pytest.mark.asyncio
async def test_get_redundancy_payload_with_data(tmp_path: Path) -> None:
    """get_redundancy_payload returns payload with redundancy metrics."""
    tracker = AsyncMock()
    tracker.search_usage = AsyncMock(
        return_value=[
            ToolUsageEvent(
                tool_name="load_context",
                timestamp="2026-02-21T12:00:00Z",
                duration_ms=10.0,
                success=True,
                params_hash="h1",
            ),
            ToolUsageEvent(
                tool_name="load_context",
                timestamp="2026-02-21T12:00:30Z",
                duration_ms=9.0,
                success=True,
                params_hash="h1",
            ),
        ]
    )
    payload = await get_redundancy_payload(tmp_path, tracker, days=30)
    assert payload.status == "success"
    assert payload.total_events == 2
    assert len(payload.repeated_identical) >= 1
    assert payload.repeated_identical[0].tool_name == "load_context"
    assert payload.repeated_identical[0].total_occurrences == 2
    assert isinstance(payload.tool_improvement_hints, list)


@pytest.mark.asyncio
async def test_get_redundancy_payload_empty_events(tmp_path: Path) -> None:
    """get_redundancy_payload handles empty events."""
    tracker = AsyncMock()
    tracker.search_usage = AsyncMock(return_value=[])
    payload = await get_redundancy_payload(tmp_path, tracker, days=7)
    assert payload.status == "success"
    assert payload.total_events == 0
    assert payload.repeated_identical == []
    assert payload.sequential_same_tool == []
    assert payload.error_rate_by_param == []
