"""Tests for structured LogEvent emission and agent formatting."""

from __future__ import annotations

import io
import json
from typing import cast

from cortex.tools.logging import emit, format_for_agent
from cortex.tools.logging.models import LogEvent, LogLevel


def test_log_event_model_dump_round_trip() -> None:
    ev = LogEvent(
        event="quality_gate.failed",
        level=LogLevel.ERROR,
        component="run_quality_gate",
        trace_id="abc123",
        requirement_id="step-2",
        commit_hash="deadbeef",
        message="gate failed",
        details={"check": "type_check", "error": "1 issue"},
    )
    raw = ev.model_dump(mode="json")
    assert raw["event"] == "quality_gate.failed"
    assert raw["level"] == "error"
    assert raw["details"] == {"check": "type_check", "error": "1 issue"}
    restored = LogEvent.model_validate(raw)
    assert restored.event == ev.event
    assert restored.level == LogLevel.ERROR


def test_emit_writes_json_line_to_stream() -> None:
    buf = io.StringIO()
    ev = LogEvent(
        event="test.event",
        level=LogLevel.INFO,
        component="test",
        message="hello",
    )
    emit(ev, stream=buf)
    line = buf.getvalue().strip()
    data = cast(dict[str, object], json.loads(line))
    assert data["event"] == "test.event"
    assert data["level"] == "info"
    assert data["message"] == "hello"


def test_format_for_agent_empty() -> None:
    assert format_for_agent([]) == ""


def test_format_for_agent_builds_table() -> None:
    events = [
        LogEvent(
            event="a.b",
            level=LogLevel.WARN,
            component="mod",
            message="msg|x",
            details={"k": True},
        )
    ]
    out = format_for_agent(events)
    assert "| event | level | component | message | details |" in out
    assert "a.b" in out
    assert "warn" in out
    assert "\\|x" in out or "msg" in out
    assert '"k": true' in out or "true" in out


def test_md_cell_escapes_pipe_in_message() -> None:
    ev = LogEvent(
        event="e",
        level=LogLevel.DEBUG,
        component="c",
        message="a|b",
    )
    table = format_for_agent([ev])
    assert "\\|" in table
