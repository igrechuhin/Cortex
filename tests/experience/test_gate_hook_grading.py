"""Prediction grading fires from the quality-gate hook, and never breaks it."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.core.models import ModelDict
from cortex.experience.claims import Verdict, parse_claims
from cortex.experience.gate_hook import NO_PREDICTIONS_NOTICE, record_gate_result
from cortex.experience.predictions import (
    open_predictions,
    recent_verdicts,
    record_prediction,
    record_verdicts,
)
from cortex.experience.recorder import recording_enabled


@pytest.fixture(autouse=True)
def _session(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SESSION_ID", "predictsess")


@pytest.fixture(autouse=True)
def _no_git(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the diff so grading does not depend on the real working tree."""

    def _pinned(root: Path) -> frozenset[str]:
        del root
        return frozenset({"src/a.py"})

    monkeypatch.setattr("cortex.experience.gate_hook._changed_files", _pinned)


@pytest.mark.asyncio
async def test_gate_grades_open_predictions(tmp_path: Path) -> None:
    # Arrange
    _ = record_prediction(
        tmp_path,
        "predictsess",
        parse_claims("gate clean; touches src/a.py; touches src/missing.py"),
        because="refactor should be behaviour-preserving",
    )
    result: ModelDict = {"preflight_passed": True, "summary": "ok"}

    # Act
    _ = await record_gate_result(tmp_path, result)

    # Assert
    assert "3 claim(s)" in str(result["predictions"])
    assert "2 HIT" in str(result["predictions"])
    assert "1 MISS" in str(result["predictions"])
    assert "touches src/missing.py" in str(result["predictions"])


@pytest.mark.asyncio
async def test_grading_closes_the_open_window(tmp_path: Path) -> None:
    # Arrange
    _ = record_prediction(tmp_path, "predictsess", parse_claims("gate clean"))
    assert len(open_predictions(tmp_path, "predictsess")) == 1

    # Act
    _ = await record_gate_result(tmp_path, {"preflight_passed": True})

    # Assert
    assert open_predictions(tmp_path, "predictsess") == []
    graded = recent_verdicts(tmp_path, "predictsess")
    assert [v.verdict for v in graded] == [Verdict.HIT]


@pytest.mark.asyncio
async def test_notice_when_nothing_was_predicted(tmp_path: Path) -> None:
    # Arrange
    result: ModelDict = {"preflight_passed": True}

    # Act
    _ = await record_gate_result(tmp_path, result)

    # Assert
    assert result["predictions"] == NO_PREDICTIONS_NOTICE


@pytest.mark.asyncio
async def test_recorder_failure_leaves_gate_result_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _ = record_prediction(tmp_path, "predictsess", parse_claims("gate clean"))

    def _boom(*args: object, **kwargs: object) -> list[object]:
        raise OSError("experience store is on fire")

    monkeypatch.setattr("cortex.experience.gate_hook.open_predictions", _boom)
    result: ModelDict = {"preflight_passed": True, "summary": "ok"}

    # Act
    node_id = await record_gate_result(tmp_path, result)

    # Assert
    assert node_id is not None
    assert result["preflight_passed"] is True
    assert result["summary"] == "ok"
    assert "predictions" not in result


def test_prediction_recorder_swallows_storage_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    before = recording_enabled()

    def _boom(*args: object, **kwargs: object) -> str:
        raise OSError("disk full")

    monkeypatch.setattr("cortex.experience.predictions.store_artifact", _boom)

    # Act
    node_id = record_prediction(tmp_path, "predictsess", parse_claims("gate clean"))

    # Assert
    assert before is True
    assert node_id is None


def test_open_predictions_is_noop_without_a_store(tmp_path: Path) -> None:
    # Arrange / Act / Assert
    assert open_predictions(tmp_path, "predictsess") == []
    assert recent_verdicts(tmp_path, "predictsess") == []


def test_record_verdicts_ignores_an_empty_list(tmp_path: Path) -> None:
    # Arrange / Act / Assert
    assert record_verdicts(tmp_path, "predictsess", []) is None


def test_recording_disabled_skips_predictions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv("CORTEX_EXPERIENCE_RECORDING", "0")

    # Act
    node_id = record_prediction(tmp_path, "predictsess", parse_claims("gate clean"))

    # Assert
    assert node_id is None
    assert open_predictions(tmp_path, "predictsess") == []
