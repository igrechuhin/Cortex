"""Tests for tool frequency helpers (Anthropic Step 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.usage.tool_frequency_helpers import (
    compute_tool_frequency,
    get_tool_frequency_payload,
)


def test_compute_tool_frequency_empty() -> None:
    """Empty events returns empty dict."""
    assert compute_tool_frequency([]) == {}


def test_compute_tool_frequency_single_session() -> None:
    """Single session: all used tools have 1.0 presence."""
    events = [
        ToolUsageEvent(
            tool_name="session_start",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=5.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:00:01Z",
            duration_ms=10.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:00:02Z",
            duration_ms=50.0,
            success=True,
        ),
    ]
    freq = compute_tool_frequency(events)
    assert freq == {"manage_file": 1.0, "load_context": 1.0, "session_start": 1.0}


def test_compute_tool_frequency_two_sessions() -> None:
    """Two sessions: manage_file in both (1.0), compact_session in one (0.5)."""
    events = [
        ToolUsageEvent(
            tool_name="session_start",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=5.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:00:01Z",
            duration_ms=10.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="session_start",
            timestamp="2026-02-21T13:00:00Z",
            duration_ms=5.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T13:00:01Z",
            duration_ms=10.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="compact_session",
            timestamp="2026-02-21T13:00:02Z",
            duration_ms=100.0,
            success=True,
        ),
    ]
    freq = compute_tool_frequency(events)
    assert freq["manage_file"] == 1.0
    assert freq["session_start"] == 1.0
    assert freq["compact_session"] == 0.5


def test_compute_tool_frequency_classifies_via_payload() -> None:
    """Payload reflects frequency classification (core/medium/rare from presence)."""
    events = [
        ToolUsageEvent(
            tool_name="session_start",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=5.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:00:01Z",
            duration_ms=10.0,
            success=True,
        ),
    ]
    freq = compute_tool_frequency(events)
    assert freq["manage_file"] == 1.0
    assert freq["session_start"] == 1.0


@pytest.mark.asyncio
async def test_get_tool_frequency_payload_empty_events(tmp_path: Path) -> None:
    """When no usage events, payload has zero sessions but token_impact present."""
    from cortex.managers.usage_tracker import UsageTracker

    tracker = UsageTracker(tmp_path)
    payload = await get_tool_frequency_payload(tmp_path, tracker, days=7)
    assert payload.status == "success"
    assert payload.total_sessions == 0
    assert payload.total_events == 0
    assert payload.tools_core_pct80 == []
    assert payload.tools_medium_pct10_80 == []
    assert payload.tools_rare_pct10 == []
    assert payload.per_tool_pct == {}
    assert "reduction_pct_when_tiered" in payload.token_impact
    reduction = payload.token_impact["reduction_pct_when_tiered"]
    assert isinstance(reduction, (int, float))
    assert float(reduction) >= 0
    # Plan target: 15%+ reduction when tiered loading enabled
    assert float(reduction) >= 15.0
