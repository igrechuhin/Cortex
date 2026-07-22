"""Unit and integration tests for best-effort experience recording."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from cortex.experience.artifacts import load_artifact
from cortex.experience.embedding_index_core import EmbeddingIndexCore
from cortex.experience.lifecycle import RUN_ABANDONED_LABEL, RUN_CLEARED_LABEL
from cortex.experience.models import ExperienceNode, ExperienceNodeStatus
from cortex.experience.recorder import (
    RECORDING_ENV_FLAG,
    experience_db_path,
    experience_session_id,
    record_gate_fitness,
    record_phase_event,
    record_run_end,
    recording_enabled,
    recording_failure_count,
)
from cortex.experience.store_core import ExperienceStoreCore


def _session_nodes(root: Path, session_id: str, pipeline: str) -> list[ExperienceNode]:
    core = ExperienceStoreCore(experience_db_path(root))
    return core.list_nodes(experience_session_id(session_id, pipeline))


def test_recording_enabled_default_and_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv(RECORDING_ENV_FLAG, raising=False)

    # Act / Assert
    assert recording_enabled() is True
    monkeypatch.setenv(RECORDING_ENV_FLAG, "false")
    assert recording_enabled() is False
    assert recording_enabled(override=True) is True
    assert recording_enabled(override=False) is False


def test_record_phase_event_creates_task_session_and_node(tmp_path: Path) -> None:
    # Arrange / Act
    node_id = record_phase_event(
        tmp_path, "sess", "commit", "preflight", "running", enabled=True
    )

    # Assert
    assert node_id is not None
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    session = core.get_session(experience_session_id("sess", "commit"))
    assert session is not None
    assert session.owner == "sess"
    assert core.get_task(session.task_id) is not None
    node = core.get_node(node_id)
    assert node is not None
    assert node.status is ExperienceNodeStatus.RUNNING
    assert node.step_number == 1


def test_phase_sequence_builds_parent_lineage(tmp_path: Path) -> None:
    # Arrange
    phases = [
        ("preflight", "running"),
        ("preflight", "completed"),
        ("checks", "failed"),
    ]

    # Act
    for phase, status in phases:
        _ = record_phase_event(tmp_path, "sess", "commit", phase, status, enabled=True)

    # Assert
    nodes = _session_nodes(tmp_path, "sess", "commit")
    assert [node.step_number for node in nodes] == [1, 2, 3]
    assert nodes[0].parent_id is None
    assert nodes[1].parent_id == nodes[0].id
    assert nodes[2].parent_id == nodes[1].id
    assert nodes[2].status is ExperienceNodeStatus.FAILED


def test_record_gate_fitness_attaches_to_latest_unscored_node(tmp_path: Path) -> None:
    # Arrange
    node_id = record_phase_event(
        tmp_path, "sess", "commit", "checks", "completed", enabled=True
    )
    assert node_id is not None

    # Act
    scored_id = record_gate_fitness(
        tmp_path, "sess", "commit", True, '{"preflight_passed": true}', enabled=True
    )

    # Assert
    assert scored_id == node_id
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    node = core.get_node(node_id)
    assert node is not None
    assert node.fitness == 1.0
    assert node.artifact_ref is not None
    assert json.loads(load_artifact(tmp_path, node.artifact_ref)) == {
        "preflight_passed": True
    }


def test_record_gate_fitness_rerun_appends_child_node(tmp_path: Path) -> None:
    # Arrange
    _ = record_phase_event(
        tmp_path, "sess", "commit", "checks", "completed", enabled=True
    )
    first = record_gate_fitness(tmp_path, "sess", "commit", False, "{}", enabled=True)

    # Act
    second = record_gate_fitness(tmp_path, "sess", "commit", True, "{}", enabled=True)

    # Assert: every gate invocation maps to exactly one node.
    assert first is not None
    assert second is not None
    assert first != second
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    child = core.get_node(second)
    assert child is not None
    assert child.parent_id == first
    assert child.fitness == 1.0
    assert child.status is ExperienceNodeStatus.COMPLETED


def test_record_gate_fitness_without_prior_node_creates_root(tmp_path: Path) -> None:
    # Arrange / Act
    node_id = record_gate_fitness(tmp_path, "sess", "commit", False, "{}", enabled=True)

    # Assert
    assert node_id is not None
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    node = core.get_node(node_id)
    assert node is not None
    assert node.parent_id is None
    assert node.fitness == 0.0
    assert node.status is ExperienceNodeStatus.FAILED


def test_record_phase_event_rejects_late_pending(tmp_path: Path) -> None:
    # Arrange
    _ = record_phase_event(
        tmp_path, "sess", "commit", "checks", "running", enabled=True
    )

    # Act
    rejected = record_phase_event(
        tmp_path, "sess", "commit", "checks", "pending", enabled=True
    )

    # Assert: late pending violates the lifecycle and is dropped.
    assert rejected is None
    assert len(_session_nodes(tmp_path, "sess", "commit")) == 1


def test_record_phase_event_allows_pending_as_first_event(tmp_path: Path) -> None:
    # Arrange / Act
    node_id = record_phase_event(
        tmp_path, "sess", "commit", "checks", "pending", enabled=True
    )

    # Assert
    assert node_id is not None
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    node = core.get_node(node_id)
    assert node is not None
    assert node.status is ExperienceNodeStatus.PENDING


def test_record_run_end_closes_window(tmp_path: Path) -> None:
    # Arrange
    _ = record_phase_event(
        tmp_path, "sess", "commit", "checks", "completed", enabled=True
    )

    # Act
    cleared_id = record_run_end(tmp_path, "sess", "commit", "cleared", enabled=True)
    repeat_id = record_run_end(tmp_path, "sess", "commit", "cleared", enabled=True)

    # Assert: one marker per open window; a closed window records nothing.
    assert cleared_id is not None
    assert repeat_id is None
    nodes = _session_nodes(tmp_path, "sess", "commit")
    assert nodes[-1].label == RUN_CLEARED_LABEL
    assert nodes[-1].status is ExperienceNodeStatus.COMPLETED


def test_record_run_end_abandoned_marks_failed(tmp_path: Path) -> None:
    # Arrange
    _ = record_phase_event(
        tmp_path, "sess", "commit", "checks", "running", enabled=True
    )

    # Act
    node_id = record_run_end(tmp_path, "sess", "commit", "abandoned", enabled=True)

    # Assert
    assert node_id is not None
    nodes = _session_nodes(tmp_path, "sess", "commit")
    assert nodes[-1].label == RUN_ABANDONED_LABEL
    assert nodes[-1].status is ExperienceNodeStatus.FAILED


def test_record_run_end_without_store_is_noop(tmp_path: Path) -> None:
    # Arrange / Act
    node_id = record_run_end(tmp_path, "sess", "commit", "cleared", enabled=True)

    # Assert: no database is created just to close a nonexistent run.
    assert node_id is None
    assert not experience_db_path(tmp_path).exists()


def test_record_phase_event_indexes_task_embedding_once(tmp_path: Path) -> None:
    # Arrange / Act
    _ = record_phase_event(
        tmp_path, "sess", "commit", "preflight", "running", enabled=True
    )

    # Assert
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    session = core.get_session(experience_session_id("sess", "commit"))
    assert session is not None
    index = EmbeddingIndexCore(experience_db_path(tmp_path))
    embedding = index.get(session.task_id)
    assert embedding is not None
    assert embedding.encoder_version == "hashing-v1"
    assert len(embedding.vector) == embedding.dim


def test_record_phase_event_repeat_calls_upsert_same_embedding(tmp_path: Path) -> None:
    # Arrange
    _ = record_phase_event(
        tmp_path, "sess", "commit", "preflight", "running", enabled=True
    )
    core = ExperienceStoreCore(experience_db_path(tmp_path))
    session = core.get_session(experience_session_id("sess", "commit"))
    assert session is not None
    index = EmbeddingIndexCore(experience_db_path(tmp_path))
    first = index.get(session.task_id)

    # Act: second phase event on the same pipeline re-runs _ensure_lineage
    _ = record_phase_event(
        tmp_path, "sess", "commit", "preflight", "completed", enabled=True
    )
    second = index.get(session.task_id)

    # Assert: idempotent upsert produces an identical vector.
    assert first is not None and second is not None
    assert first.vector == second.vector


def test_disabled_flag_skips_recording(tmp_path: Path) -> None:
    # Arrange / Act
    phase_id = record_phase_event(
        tmp_path, "sess", "commit", "checks", "running", enabled=False
    )
    gate_id = record_gate_fitness(tmp_path, "sess", "commit", True, "{}", enabled=False)

    # Assert
    assert phase_id is None
    assert gate_id is None
    assert not experience_db_path(tmp_path).exists()


def test_embedding_failure_is_swallowed_without_breaking_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    import cortex.experience.recorder as recorder_module

    class _BrokenEncoder:
        dim = 8
        version = "broken-v1"

        def encode(self, text: str) -> list[float]:
            raise RuntimeError("encoder unavailable")

    monkeypatch.setattr(recorder_module, "_task_encoder", _BrokenEncoder())
    failures_before = recording_failure_count()

    # Act
    node_id = record_phase_event(
        tmp_path, "sess", "commit", "preflight", "running", enabled=True
    )

    # Assert: recording still succeeds even though embedding failed.
    assert node_id is not None
    assert recording_failure_count() == failures_before + 1


def test_storage_failure_is_swallowed_and_logged(tmp_path: Path) -> None:
    # Arrange: a file where the experience directory should be forces an OSError.
    # AI: the cortex logger sets propagate=False, so capture via a direct handler
    # instead of caplog (which listens on the root logger).
    (tmp_path / ".cortex").mkdir()
    _ = (tmp_path / ".cortex" / "experience").write_text("not a dir", encoding="utf-8")
    failures_before = recording_failure_count()
    records: list[logging.LogRecord] = []
    handler = _ListHandler(records)
    recorder_logger = logging.getLogger("cortex.experience.recorder")
    recorder_logger.addHandler(handler)

    # Act
    try:
        phase_id = record_phase_event(
            tmp_path, "sess", "commit", "checks", "running", enabled=True
        )
        gate_id = record_gate_fitness(
            tmp_path, "sess", "commit", True, "{}", enabled=True
        )
    finally:
        recorder_logger.removeHandler(handler)

    # Assert
    assert phase_id is None
    assert gate_id is None
    assert recording_failure_count() == failures_before + 2
    messages = [record.getMessage() for record in records]
    assert any("experience recording failed" in message for message in messages)
    assert any("trace_id=sess" in message for message in messages)


class _ListHandler(logging.Handler):
    """Test helper collecting emitted log records into a list."""

    def __init__(self, records: list[logging.LogRecord]) -> None:
        super().__init__(level=logging.WARNING)
        self._records = records

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(record)
