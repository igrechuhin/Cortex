"""Tests for session continuity helpers (Anthropic Step 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.session.continuity_helpers import (
    compute_session_continuity,
    get_session_continuity_payload,
)


def test_compute_session_continuity_session_start_then_productive() -> None:
    """Turns until productive: session_start (0) then manage_file (1) = 1."""
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
    result = compute_session_continuity(events)
    assert result == [1]


def test_compute_session_continuity_orientation_then_productive() -> None:
    """Turns: session_start, load_context, manage_file = 2."""
    events = [
        ToolUsageEvent(
            tool_name="session_start",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=5.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:00:01Z",
            duration_ms=50.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:00:02Z",
            duration_ms=10.0,
            success=True,
        ),
    ]
    result = compute_session_continuity(events)
    assert result == [2]


def test_compute_session_continuity_no_productive_excluded() -> None:
    """Session with no productive call is excluded."""
    events = [
        ToolUsageEvent(
            tool_name="session_start",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=5.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:00:01Z",
            duration_ms=50.0,
            success=True,
        ),
    ]
    result = compute_session_continuity(events)
    assert result == []


def test_compute_session_continuity_two_sessions() -> None:
    """Two sessions with session_start boundaries."""
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
            tool_name="load_context",
            timestamp="2026-02-21T13:00:01Z",
            duration_ms=50.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="compact_session",
            timestamp="2026-02-21T13:00:02Z",
            duration_ms=100.0,
            success=True,
        ),
    ]
    result = compute_session_continuity(events)
    assert result == [1, 2]


def test_compute_session_continuity_empty() -> None:
    """Empty events returns empty list."""
    assert compute_session_continuity([]) == []


@pytest.mark.asyncio
async def test_get_session_continuity_payload_empty_events(tmp_path: Path) -> None:
    """When no usage events, payload has zero sessions."""
    from cortex.managers.usage_tracker import UsageTracker

    tracker = UsageTracker(tmp_path)
    payload = await get_session_continuity_payload(tmp_path, tracker, days=7)
    assert payload.status == "success"
    assert payload.sessions_with_session_start == 0
    assert payload.sessions_with_productive_call == 0
    assert payload.turns_until_productive == []
    assert payload.avg_turns_until_productive is None
    assert payload.median_turns_until_productive is None
