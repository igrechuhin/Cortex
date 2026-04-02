from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.session.gate_feedback import (
    GateError,
    GateFeedback,
    GateName,
    feedback_from_docs_result,
    feedback_from_quality_result,
    persist_gate_feedback,
)


def test_feedback_from_quality_result_returns_none_on_success() -> None:
    result: dict[str, object] = {"preflight_passed": True, "checks": []}
    assert feedback_from_quality_result(result) is None


def test_feedback_from_quality_result_builds_structured_payload() -> None:
    result: dict[str, object] = {
        "preflight_passed": False,
        "checks": [
            {
                "name": "type_check",
                "status": "error",
                "errors": 3,
                "message": "3 errors",
            },
            {"name": "format", "status": "success", "errors": 0, "message": "ok"},
        ],
    }
    feedback = feedback_from_quality_result(result)
    assert feedback is not None
    assert feedback.gate == GateName.QUALITY
    assert len(feedback.errors) == 1
    assert feedback.top_files == ["<type_check>"]
    assert "Quality gate failed" in feedback.summary


def test_feedback_from_quality_result_builds_fallback_on_empty_checks() -> None:
    result: dict[str, object] = {"preflight_passed": False, "checks": []}
    feedback = feedback_from_quality_result(result)
    assert feedback is not None
    assert len(feedback.errors) == 1
    assert feedback.errors[0].file == "<quality>"
    assert feedback.errors[0].check == "quality-gate"


def test_feedback_from_docs_result_returns_none_on_success() -> None:
    result: dict[str, object] = {"docs_phase_passed": True, "checks": []}
    assert feedback_from_docs_result(result) is None


def test_feedback_from_docs_result_builds_fallback_error_when_checks_missing() -> None:
    result: dict[str, object] = {"docs_phase_passed": False}
    feedback = feedback_from_docs_result(result)
    assert feedback is not None
    assert feedback.gate == GateName.DOCS
    assert len(feedback.errors) == 1
    assert feedback.errors[0].file == "<docs>"


def test_check_to_error_uses_name_when_message_empty() -> None:
    """When message is empty, GateError.message falls back to the check name."""
    result: dict[str, object] = {
        "preflight_passed": False,
        "checks": [{"name": "lint", "status": "failed", "message": "  "}],
    }
    feedback = feedback_from_quality_result(result)
    assert feedback is not None
    assert feedback.errors[0].message == "lint"


@pytest.mark.asyncio
async def test_persist_gate_feedback_clears_on_none() -> None:
    with patch(
        "cortex.tools.session.pipeline_handoff.pipeline_handoff",
        new_callable=AsyncMock,
    ) as mock_handoff:
        mock_handoff.return_value = json.dumps({"status": "ok"})
        await persist_gate_feedback(None, ctx=None)

    mock_handoff.assert_called_once_with(
        operation="clear",
        pipeline="implement",
        phase="gate_feedback",
        ctx=None,
    )


@pytest.mark.asyncio
async def test_persist_gate_feedback_writes_on_failure() -> None:
    feedback = GateFeedback(
        gate=GateName.QUALITY,
        errors=[GateError(file="<quality>", check="q", message="fail")],
        top_files=["<quality>"],
        summary="Quality gate failed with 1 issue group(s).",
    )
    with patch(
        "cortex.tools.session.pipeline_handoff.pipeline_handoff",
        new_callable=AsyncMock,
    ) as mock_handoff:
        mock_handoff.return_value = json.dumps({"status": "ok"})
        await persist_gate_feedback(feedback, ctx=None)

    mock_handoff.assert_called_once()
    call_kwargs = mock_handoff.call_args.kwargs
    assert call_kwargs["operation"] == "write"
    assert call_kwargs["pipeline"] == "implement"
    assert call_kwargs["phase"] == "gate_feedback"
    payload: object = call_kwargs["data"]
    assert isinstance(payload, dict)
    assert payload["gate"] == "quality"


@pytest.mark.asyncio
async def test_persist_gate_feedback_logs_warning_on_handoff_error() -> None:
    with patch(
        "cortex.tools.session.pipeline_handoff.pipeline_handoff",
        new_callable=AsyncMock,
    ) as mock_handoff:
        mock_handoff.return_value = {"status": "error", "error": "disk full"}
        with patch("cortex.tools.session.gate_feedback._log") as mock_log:
            await persist_gate_feedback(None, ctx=None)

    mock_log.warning.assert_called_once()
    args = mock_log.warning.call_args.args
    assert "disk full" in args[-1]
