"""Integration tests: pipeline_handoff phase transitions record experience nodes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.experience.models import ExperienceNodeStatus
from cortex.experience.recorder import experience_db_path, experience_session_id
from cortex.experience.store_core import ExperienceStoreCore
from cortex.tools.session.pipeline_handoff_io import (
    op_mark_running,
    op_write_result,
)


@pytest.fixture
def session_env(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("CORTEX_SESSION_ID", "handoffsess")
    monkeypatch.delenv("CORTEX_EXPERIENCE_RECORDING", raising=False)
    return "handoffsess"


def _nodes(root: Path, session_id: str, pipeline: str) -> list[ExperienceNodeStatus]:
    core = ExperienceStoreCore(experience_db_path(root))
    nodes = core.list_nodes(experience_session_id(session_id, pipeline))
    return [node.status for node in nodes]


def test_mark_running_records_running_node(tmp_path: Path, session_env: str) -> None:
    # Arrange / Act
    out = json.loads(op_mark_running(tmp_path, "implement", "code"))

    # Assert
    assert out["status"] == "ok"
    assert _nodes(tmp_path, session_env, "implement") == [ExperienceNodeStatus.RUNNING]


def test_write_result_records_phase_outcome_lineage(
    tmp_path: Path, session_env: str
) -> None:
    # Arrange
    _ = op_mark_running(tmp_path, "implement", "code")

    # Act
    _ = op_write_result(tmp_path, "implement", "code", '{"status": "passed"}')
    _ = op_write_result(tmp_path, "implement", "review", '{"status": "failed"}')

    # Assert
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    nodes = core.list_nodes(experience_session_id(session_env, "implement"))
    assert [node.status for node in nodes] == [
        ExperienceNodeStatus.RUNNING,
        ExperienceNodeStatus.COMPLETED,
        ExperienceNodeStatus.FAILED,
    ]
    assert [node.step_number for node in nodes] == [1, 2, 3]
    assert nodes[1].parent_id == nodes[0].id
    assert nodes[2].parent_id == nodes[1].id
    assert nodes[1].label == "code:completed"


def test_write_result_succeeds_when_recording_storage_broken(
    tmp_path: Path, session_env: str
) -> None:
    # Arrange: force recording failure by blocking the experience directory.
    (tmp_path / ".cortex").mkdir()
    _ = (tmp_path / ".cortex" / "experience").write_text("not a dir", encoding="utf-8")

    # Act
    out = json.loads(
        op_write_result(tmp_path, "implement", "code", '{"status": "passed"}')
    )

    # Assert: pipeline write still succeeds (best-effort recording).
    assert out["status"] == "ok"


def test_write_result_respects_disabled_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv("CORTEX_SESSION_ID", "handoffsess")
    monkeypatch.setenv("CORTEX_EXPERIENCE_RECORDING", "off")

    # Act
    out = json.loads(
        op_write_result(tmp_path, "implement", "code", '{"status": "passed"}')
    )

    # Assert
    assert out["status"] == "ok"
    assert not experience_db_path(tmp_path).exists()
