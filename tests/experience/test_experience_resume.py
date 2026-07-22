"""Unit tests for resume planning from the experience-store frontier."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cortex.experience.models import ExperienceNodeStatus
from cortex.experience.recorder import record_phase_event
from cortex.experience.resume import (
    RESUME_TTL_ENV,
    build_resume_plan,
    resume_ttl_seconds,
    scan_incomplete_runs,
)


def _record(root: Path, session: str, pipeline: str, phase: str, status: str) -> None:
    node_id = record_phase_event(root, session, pipeline, phase, status, enabled=True)
    assert node_id is not None


def test_resume_ttl_seconds_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange / Act / Assert
    monkeypatch.delenv(RESUME_TTL_ENV, raising=False)
    assert resume_ttl_seconds() == 4 * 3600.0
    monkeypatch.setenv(RESUME_TTL_ENV, "600")
    assert resume_ttl_seconds() == 600.0
    monkeypatch.setenv(RESUME_TTL_ENV, "-1")
    assert resume_ttl_seconds() == 4 * 3600.0
    monkeypatch.setenv(RESUME_TTL_ENV, "not-a-number")
    assert resume_ttl_seconds() == 4 * 3600.0


def test_scan_incomplete_runs_without_store_is_empty(tmp_path: Path) -> None:
    # Arrange / Act / Assert: must not create the database as a side effect.
    assert scan_incomplete_runs(tmp_path) == []
    assert not (tmp_path / ".cortex" / "experience" / "experience.db").exists()


def test_scan_incomplete_runs_marks_stale_and_lists_fresh(tmp_path: Path) -> None:
    # Arrange
    _record(tmp_path, "sess", "commit", "preflight", "running")

    # Act
    fresh = scan_incomplete_runs(tmp_path)
    future = datetime.now(UTC) + timedelta(hours=9)
    later = scan_incomplete_runs(tmp_path, now=future)

    # Assert
    assert [run.owner for run in fresh] == ["sess"]
    assert later == []
    # Stale window was closed; the run is gone even at the original time.
    assert scan_incomplete_runs(tmp_path) == []


def test_build_resume_plan_without_store(tmp_path: Path) -> None:
    # Arrange / Act
    plan = build_resume_plan(tmp_path, "sess", "commit")

    # Assert
    assert plan.resumable is False
    assert "no experience store" in plan.reason


def test_build_resume_plan_no_matching_run(tmp_path: Path) -> None:
    # Arrange
    _record(tmp_path, "sess", "implement", "select", "completed")

    # Act
    plan = build_resume_plan(tmp_path, "sess", "commit")

    # Assert
    assert plan.resumable is False
    assert "no incomplete run" in plan.reason


def test_build_resume_plan_resumes_after_committed_phase(tmp_path: Path) -> None:
    # Arrange: crash after checks completed, docs never started.
    _record(tmp_path, "sess", "commit", "preflight", "completed")
    _record(tmp_path, "sess", "commit", "checks", "completed")

    # Act
    plan = build_resume_plan(tmp_path, "sess", "commit")

    # Assert
    assert plan.resumable is True
    assert plan.session_id == "sess"
    assert plan.completed_phases == ["preflight", "checks"]
    assert plan.frontier_phase == "checks"
    assert plan.frontier_status is ExperienceNodeStatus.COMPLETED
    assert plan.handoff_dir is not None
    assert plan.handoff_dir.endswith("sess/commit")


def test_build_resume_plan_failed_frontier_forces_fix_path(tmp_path: Path) -> None:
    # Arrange
    _record(tmp_path, "sess", "commit", "checks", "failed")

    # Act
    plan = build_resume_plan(tmp_path, "sess", "commit")

    # Assert
    assert plan.resumable is False
    assert "fix path" in plan.reason
    assert plan.frontier_status is ExperienceNodeStatus.FAILED


def test_build_resume_plan_stale_run_not_offered(tmp_path: Path) -> None:
    # Arrange
    _record(tmp_path, "sess", "commit", "checks", "completed")

    # Act: evaluate long after the TTL expired.
    future = datetime.now(UTC) + timedelta(hours=9)
    plan = build_resume_plan(tmp_path, "sess", "commit", now=future)

    # Assert
    assert plan.resumable is False
    assert "no incomplete run" in plan.reason


def test_build_resume_plan_picks_other_session_run(tmp_path: Path) -> None:
    # Arrange: prior crashed session recorded progress; new session resumes.
    _record(tmp_path, "old-session", "commit", "preflight", "completed")

    # Act
    plan = build_resume_plan(tmp_path, "new-session", "commit")

    # Assert
    assert plan.resumable is True
    assert plan.session_id == "old-session"
    assert plan.completed_phases == ["preflight"]


def test_build_resume_plan_reports_handoff_mismatch(tmp_path: Path) -> None:
    # Arrange: store says preflight done; handoff projection also claims docs.
    _record(tmp_path, "sess", "commit", "preflight", "completed")
    handoff_dir = tmp_path / ".cortex" / ".session" / "sess" / "commit"
    handoff_dir.mkdir(parents=True)
    state = {
        "phases": {
            "preflight": {"phase_status": "completed"},
            "docs": {"phase_status": "completed"},
        }
    }
    _ = (handoff_dir / "pipeline.json").write_text(json.dumps(state), encoding="utf-8")

    # Act
    plan = build_resume_plan(tmp_path, "sess", "commit")

    # Assert: the store wins; the mismatch is surfaced.
    assert plan.completed_phases == ["preflight"]
    assert plan.handoff_mismatch == ["docs"]


def test_build_resume_plan_ignores_corrupted_handoff_state(tmp_path: Path) -> None:
    # Arrange
    _record(tmp_path, "sess", "commit", "preflight", "completed")
    handoff_dir = tmp_path / ".cortex" / ".session" / "sess" / "commit"
    handoff_dir.mkdir(parents=True)
    _ = (handoff_dir / "pipeline.json").write_text("{not json", encoding="utf-8")

    # Act
    plan = build_resume_plan(tmp_path, "sess", "commit")

    # Assert
    assert plan.resumable is True
    assert plan.handoff_mismatch == ["preflight"]
