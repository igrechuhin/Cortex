"""Integration test: no-progress monitor evaluated over real pipeline_handoff state.

Simulates a fix-tests-style subagent loop that writes an attempt record to
its own ``pipeline_handoff`` phase payload after each retry, then evaluates
``detect_no_progress`` against what is read back. Asserts the pause/report
signal trips exactly at the configured threshold — never earlier, never for
fewer than N attempts against different targets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.core.no_progress_monitor import (
    AttemptRecord,
    build_report_message,
    detect_no_progress,
    extract_attempt_history,
)
from cortex.tools.session.pipeline_handoff import pipeline_handoff
from tests.tools.pipeline_handoff_test_support import (
    patch_pipeline_handoff_project_root,
)

_THRESHOLD = 3
_TARGET = "tests/test_widget.py::test_renders"
_OUTCOME = "AssertionError: expected 'ready' got 'loading'"


async def _write_attempt_history(
    history: list[dict[str, object]],
) -> dict[str, object]:
    """Write the full attempt_history list to the fix/tests phase, as a
    subagent would after each retry, and return the parsed write response.
    """
    raw = await pipeline_handoff(
        operation="write",
        pipeline="fix",
        phase="tests",
        data=json.dumps({"attempt_history": history, "status": "running"}),
    )
    return json.loads(raw)


async def _read_attempt_records() -> list[AttemptRecord]:
    """Read back the phase payload and parse its attempt_history."""
    raw = await pipeline_handoff(operation="read", pipeline="fix", phase="tests")
    parsed: dict[str, object] = json.loads(raw)
    # BELIEF: no explicit write_task call happens in this subagent flow, so
    # op_read_task falls back to the cumulative pipeline_state wrapper —
    # the phase payload lives one level deeper under phases.tests.
    pipeline_state = parsed.get("pipeline_state")
    if not isinstance(pipeline_state, dict):
        return []
    state_dict = cast(dict[str, object], pipeline_state)
    phases = state_dict.get("phases")
    if not isinstance(phases, dict):
        return []
    phases_dict = cast(dict[str, object], phases)
    phase_payload = phases_dict.get("tests")
    if not isinstance(phase_payload, dict):
        return []
    return extract_attempt_history(cast(dict[str, object], phase_payload))


@pytest.mark.asyncio
class TestNoProgressMonitorPipelineIntegration:
    async def test_trips_exactly_at_threshold_not_before(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="fix")
        history: list[dict[str, object]] = []
        tripped_at: int | None = None

        # Act: simulate identical-outcome retries against the same target.
        for attempt_number in range(1, _THRESHOLD + 1):
            history.append(
                {
                    "target": _TARGET,
                    "outcome_signature": _OUTCOME,
                    "attempt_number": attempt_number,
                }
            )
            _ = await _write_attempt_history(history)
            records = await _read_attempt_records()
            result = detect_no_progress(records, threshold=_THRESHOLD)

            # Assert: never trips before the configured threshold.
            if attempt_number < _THRESHOLD:
                assert (
                    result.tripped is False
                ), f"tripped prematurely at attempt {attempt_number}"
            else:
                assert result.tripped is True
                tripped_at = attempt_number

        # Assert: trips exactly once, at the threshold-th attempt.
        assert tripped_at == _THRESHOLD
        final_records = await _read_attempt_records()
        final_result = detect_no_progress(final_records, threshold=_THRESHOLD)
        message = build_report_message(final_result, threshold=_THRESHOLD)
        assert "No-progress monitor" in message
        assert _TARGET in message

    async def test_fewer_than_threshold_attempts_never_trips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="fix")
        history: list[dict[str, object]] = [
            {
                "target": _TARGET,
                "outcome_signature": _OUTCOME,
                "attempt_number": 1,
            },
            {
                "target": _TARGET,
                "outcome_signature": _OUTCOME,
                "attempt_number": 2,
            },
        ]

        # Act
        _ = await _write_attempt_history(history)
        records = await _read_attempt_records()
        result = detect_no_progress(records, threshold=_THRESHOLD)

        # Assert
        assert result.tripped is False

    async def test_switching_targets_never_trips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange: agent resolves each issue and moves to a new target/error
        # every attempt — this must never be mistaken for a stuck loop.
        patch_pipeline_handoff_project_root(monkeypatch, tmp_path)
        _ = await pipeline_handoff(operation="init", pipeline="fix")
        history: list[dict[str, object]] = [
            {
                "target": f"tests/test_{i}.py::test_case",
                "outcome_signature": f"AssertionError: case {i}",
                "attempt_number": 1,
            }
            for i in range(1, _THRESHOLD + 2)
        ]

        # Act
        _ = await _write_attempt_history(history)
        records = await _read_attempt_records()
        result = detect_no_progress(records, threshold=_THRESHOLD)

        # Assert
        assert result.tripped is False
