"""Tests for token efficiency helpers (Anthropic context engineering Step 2)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.phase5_token_efficiency_helpers import (
    TokenEfficiencyEntry,
    TokenEfficiencyPayload,
    get_token_efficiency_payload,
)


def test_token_efficiency_entry_model() -> None:
    """TokenEfficiencyEntry accepts valid fields."""
    e = TokenEfficiencyEntry(
        tool_name="load_context",
        total_response_tokens=5000,
        call_count=10,
        avg_tokens_per_call=500.0,
    )
    assert e.tool_name == "load_context"
    assert e.total_response_tokens == 5000
    assert e.avg_tokens_per_call == 500.0


def test_token_efficiency_payload_model() -> None:
    """TokenEfficiencyPayload accepts valid fields."""
    p = TokenEfficiencyPayload(
        status="success",
        project_root="/tmp",
        days=30,
        event_count_with_tokens=100,
        top_by_total=[],
        top_by_avg=[],
    )
    assert p.status == "success"
    assert p.days == 30


@pytest.mark.asyncio
async def test_get_token_efficiency_payload_unavailable(tmp_path: Path) -> None:
    """When tracker is None, payload status is unavailable."""
    payload = await get_token_efficiency_payload(tmp_path, None, days=30)
    assert payload.status == "unavailable"
    assert payload.message == "Usage tracker not available"
    assert payload.days == 30


@pytest.mark.asyncio
async def test_get_token_efficiency_payload_no_events_with_tokens(
    tmp_path: Path,
) -> None:
    """When no events have response_tokens, payload has event_count_with_tokens=0."""
    tracker = AsyncMock()
    tracker.search_usage = AsyncMock(
        return_value=[
            ToolUsageEvent(
                tool_name="manage_file",
                timestamp="2026-02-21T12:00:00Z",
                duration_ms=5.0,
                success=True,
                response_tokens=None,
            ),
        ]
    )
    payload = await get_token_efficiency_payload(tmp_path, tracker, days=30)
    assert payload.status == "success"
    assert payload.event_count_with_tokens == 0
    assert payload.top_by_total == []
    assert payload.top_by_avg == []
    assert "No events" in (payload.message or "")


@pytest.mark.asyncio
async def test_get_token_efficiency_payload_with_data(tmp_path: Path) -> None:
    """When events have response_tokens, payload aggregates and returns top tools."""
    tracker = AsyncMock()
    tracker.search_usage = AsyncMock(
        return_value=[
            ToolUsageEvent(
                tool_name="load_context",
                timestamp="2026-02-21T12:00:00Z",
                duration_ms=100.0,
                success=True,
                response_tokens=3000,
            ),
            ToolUsageEvent(
                tool_name="load_context",
                timestamp="2026-02-21T12:01:00Z",
                duration_ms=80.0,
                success=True,
                response_tokens=2000,
            ),
            ToolUsageEvent(
                tool_name="manage_file",
                timestamp="2026-02-21T12:02:00Z",
                duration_ms=5.0,
                success=True,
                response_tokens=500,
            ),
        ]
    )
    payload = await get_token_efficiency_payload(tmp_path, tracker, days=30, top_n=5)
    assert payload.status == "success"
    assert payload.event_count_with_tokens == 3
    assert len(payload.top_by_total) == 2
    assert payload.top_by_total[0].tool_name == "load_context"
    assert payload.top_by_total[0].total_response_tokens == 5000
    assert payload.top_by_total[0].call_count == 2
    assert payload.top_by_total[0].avg_tokens_per_call == 2500.0
    assert payload.top_by_total[1].tool_name == "manage_file"
    assert payload.top_by_total[1].total_response_tokens == 500
    assert len(payload.top_by_avg) == 2
    assert payload.top_by_avg[0].tool_name == "load_context"
    assert payload.top_by_avg[0].avg_tokens_per_call == 2500.0
    # Optimization recommendations generated for top tools with hints
    assert isinstance(payload.optimization_recommendations, list)
    assert any("load_context" in r for r in payload.optimization_recommendations)
    assert any("manage_file" in r for r in payload.optimization_recommendations)
