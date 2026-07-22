"""Crash-simulation integration tests: kill after each phase, then resume.

Simulates a crashed pipeline by invoking the same handoff operations the
orchestrator uses (mark_running / write_result) and stopping at a phase
boundary; op_resume must reconstruct completed phases from the store
frontier so no phase runs twice and no committed work is lost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from cortex.experience.recorder import record_phase_event
from cortex.tools.session.pipeline_handoff_io import (
    op_clear,
    op_init,
    op_mark_running,
    op_write_result,
)
from cortex.tools.session.pipeline_handoff_resume import op_resume
from cortex.tools.session.start_tools import scan_incomplete_pipeline_entries

_PHASES = ["select", "code", "review", "finalize"]


@pytest.fixture
def session_env(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("CORTEX_SESSION_ID", "resumesess")
    monkeypatch.delenv("CORTEX_EXPERIENCE_RECORDING", raising=False)
    return "resumesess"


def _complete_phase(root: Path, pipeline: str, phase: str) -> None:
    _ = op_mark_running(root, pipeline, phase)
    _ = op_write_result(root, pipeline, phase, '{"status": "passed"}')


def _resume(root: Path, pipeline: str) -> dict[str, object]:
    parsed: object = json.loads(op_resume(root, pipeline))
    assert isinstance(parsed, dict)
    return cast(dict[str, object], parsed)


@pytest.mark.parametrize("crash_after", range(1, len(_PHASES) + 1))
def test_crash_after_each_phase_resumes_at_next(
    tmp_path: Path, session_env: str, crash_after: int
) -> None:
    # Arrange: run the pipeline up to the crash boundary, then "die".
    _ = op_init(tmp_path, "implement", None)
    done = _PHASES[:crash_after]
    for phase in done:
        _complete_phase(tmp_path, "implement", phase)

    # Act: a fresh invocation asks for the resume plan.
    plan = _resume(tmp_path, "implement")

    # Assert: completed phases are skipped; none is lost or repeated.
    assert plan["resumable"] is True
    assert plan["completed_phases"] == done
    assert plan["frontier_phase"] == done[-1]
    assert plan["session_id"] == session_env


def test_crash_mid_phase_resumes_at_running_phase(
    tmp_path: Path, session_env: str
) -> None:
    # Arrange: crash while "code" was running.
    _complete_phase(tmp_path, "implement", "select")
    _ = op_mark_running(tmp_path, "implement", "code")

    # Act
    plan = _resume(tmp_path, "implement")

    # Assert: "code" never committed, so it is not skipped on resume.
    assert plan["resumable"] is True
    assert plan["completed_phases"] == ["select"]
    assert plan["frontier_phase"] == "code"
    assert plan["frontier_status"] == "running"


def test_failed_phase_blocks_resume(tmp_path: Path, session_env: str) -> None:
    # Arrange
    _complete_phase(tmp_path, "implement", "select")
    _ = op_mark_running(tmp_path, "implement", "code")
    _ = op_write_result(tmp_path, "implement", "code", '{"status": "failed"}')

    # Act
    plan = _resume(tmp_path, "implement")

    # Assert: a failed frontier forces the fix path instead of resume.
    assert plan["resumable"] is False
    assert "fix path" in str(plan["reason"])


def test_cleared_pipeline_is_not_resumable(tmp_path: Path, session_env: str) -> None:
    # Arrange
    for phase in _PHASES:
        _complete_phase(tmp_path, "implement", phase)
    _ = op_clear(tmp_path, "implement")

    # Act
    plan = _resume(tmp_path, "implement")

    # Assert: a completed (cleared) run must never be offered for resume.
    assert plan["resumable"] is False
    assert "no incomplete run" in str(plan["reason"])


def test_stale_init_abandons_prior_run(
    tmp_path: Path, session_env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: run one phase, then make the handoff state look ancient.
    _ = op_init(tmp_path, "implement", None)
    _complete_phase(tmp_path, "implement", "select")
    state_file = (
        tmp_path / ".cortex" / ".session" / session_env / "implement" / "pipeline.json"
    )
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["started_at"] = "2020-01-01T00:00:00"
    _ = state_file.write_text(json.dumps(state), encoding="utf-8")

    # Act: re-init detects staleness and closes the store window.
    _ = op_init(tmp_path, "implement", None)
    plan = _resume(tmp_path, "implement")

    # Assert
    assert plan["resumable"] is False
    assert "no incomplete run" in str(plan["reason"])


def test_resume_reports_consistent_handoff_projection(
    tmp_path: Path, session_env: str
) -> None:
    # Arrange
    _complete_phase(tmp_path, "implement", "select")
    _complete_phase(tmp_path, "implement", "code")

    # Act
    plan = _resume(tmp_path, "implement")

    # Assert: store and pipeline.json agree, so no mismatch is reported.
    assert plan["handoff_mismatch"] == []
    assert plan["completed_phases"] == ["select", "code"]


def test_session_scan_includes_frontier_phase(tmp_path: Path, session_env: str) -> None:
    # Arrange: interrupted run recorded in the store and handoff log.
    _complete_phase(tmp_path, "implement", "select")
    _ = op_mark_running(tmp_path, "implement", "code")

    # Act
    entries = scan_incomplete_pipeline_entries(tmp_path)

    # Assert: session() surfaces the run with its frontier phase.
    assert f"{session_env}/implement:code" in entries


def test_session_scan_survives_broken_store(tmp_path: Path, session_env: str) -> None:
    # Arrange: break the experience database after recording.
    _ = record_phase_event(
        tmp_path, session_env, "implement", "select", "running", enabled=True
    )
    db_path = tmp_path / ".cortex" / "experience" / "experience.db"
    # AI: replace the db (and its WAL sidecars) with a directory so sqlite
    # cannot open it — overwriting bytes alone is masked by the WAL file.
    db_path.unlink()
    for suffix in ("-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    db_path.mkdir()

    # Act / Assert: orientation never fails on a broken store.
    assert scan_incomplete_pipeline_entries(tmp_path) == []
