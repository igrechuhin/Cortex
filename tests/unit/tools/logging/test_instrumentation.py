"""Tests for structured logging instrumentation helpers."""

from __future__ import annotations

from typing import cast
from unittest.mock import patch

from cortex.core.models import ModelDict
from cortex.tools.logging.instrumentation import (
    append_agent_log_to_quality_result,
    build_quality_gate_log_events,
    emit_pipeline_handoff_log,
)


def test_build_quality_gate_log_events_passed() -> None:
    with patch(
        "cortex.tools.logging.instrumentation.get_agent_log_context",
        return_value=("tid", None, "abc"),
    ):
        events = build_quality_gate_log_events(
            cast(ModelDict, {"preflight_passed": True})
        )
    assert len(events) == 1
    assert events[0].event == "quality_gate.passed"


def test_build_quality_gate_log_events_failed_preflight() -> None:
    with patch(
        "cortex.tools.logging.instrumentation.get_agent_log_context",
        return_value=("tid", "step1", None),
    ):
        events = build_quality_gate_log_events(
            cast(
                ModelDict,
                {
                    "preflight_passed": False,
                    "checks": [
                        {
                            "name": "lint",
                            "status": "error",
                            "message": "bad",
                        }
                    ],
                },
            )
        )
    assert len(events) == 1
    assert events[0].event == "quality_gate.failed"
    assert events[0].details is not None
    assert events[0].details.get("check") == "lint"


def test_append_agent_log_omits_response_field_on_pass() -> None:
    """Passing runs still emit events but omit bulky ``agent_log`` from the MCP payload."""
    r: ModelDict = cast(ModelDict, {"preflight_passed": True})
    with patch(
        "cortex.tools.logging.instrumentation.get_agent_log_context",
        return_value=("t", None, None),
    ):
        with patch("cortex.tools.logging.instrumentation.emit"):
            append_agent_log_to_quality_result(r)
    assert "agent_log" not in r


def test_append_agent_log_mutates_result_on_failure() -> None:
    r: ModelDict = cast(
        ModelDict,
        {
            "preflight_passed": False,
            "checks": [
                {"name": "lint", "status": "error", "message": "bad"},
            ],
        },
    )
    with patch(
        "cortex.tools.logging.instrumentation.get_agent_log_context",
        return_value=("t", None, None),
    ):
        with patch("cortex.tools.logging.instrumentation.emit"):
            append_agent_log_to_quality_result(r)
    assert "agent_log" in r
    assert "quality_gate.failed" in str(r["agent_log"])


def test_emit_pipeline_handoff_log_skips_unknown_op() -> None:
    with patch("cortex.tools.logging.instrumentation.emit") as mock_emit:
        emit_pipeline_handoff_log("unknown", "p", "x")
    mock_emit.assert_not_called()


def test_emit_pipeline_handoff_log_writes() -> None:
    with patch("cortex.tools.logging.instrumentation.emit") as mock_emit:
        emit_pipeline_handoff_log("write", "implement", "select")
    mock_emit.assert_called_once()
