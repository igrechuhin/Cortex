"""Unit tests for vector-seeded similar-task recall (AAA pattern)."""

from __future__ import annotations

from pathlib import Path

from cortex.experience.embedding_index_core import EmbeddingIndexCore
from cortex.experience.embedding_models import TaskEmbeddingRecord
from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.recall import recall_similar_tasks
from cortex.experience.store_core import ExperienceStoreCore
from tests.experience.embedding_fixtures import FakeEncoder


def _seed_task_with_nodes(
    core: ExperienceStoreCore,
    index: EmbeddingIndexCore,
    encoder: FakeEncoder,
    task_id: str,
    spec: str,
) -> ExperienceTask:
    task = core.create_task(ExperienceTask(id=task_id, spec=spec))
    vector = encoder.encode(spec)
    _ = index.upsert(
        TaskEmbeddingRecord(
            task_id=task.id,
            vector=vector,
            dim=encoder.dim,
            encoder_version=encoder.version,
        )
    )
    session = core.create_session(
        ExperienceSession(task_id=task.id, algorithm="commit", owner="sess-" + task_id)
    )
    _ = core.append_node(
        ExperienceNode(
            session_id=session.id,
            status=ExperienceNodeStatus.COMPLETED,
            label="quality-gate",
            fitness=1.0,
            step_number=1,
        )
    )
    return task


def _seed_dead_end(core: ExperienceStoreCore, task: ExperienceTask) -> None:
    session = core.create_session(
        ExperienceSession(task_id=task.id, algorithm="commit", owner="dead-" + task.id)
    )
    for step in (1, 2):
        _ = core.append_node(
            ExperienceNode(
                session_id=session.id,
                status=ExperienceNodeStatus.FAILED,
                label="markdown-lint-retry",
                step_number=step,
            )
        )


def test_recall_similar_tasks_finds_semantically_similar_task(tmp_path: Path) -> None:
    # Arrange
    db_path = tmp_path / "experience.db"
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    encoder = FakeEncoder(keyword_dims={"auth": 0, "cake": 1}, dim=4)
    auth_task = _seed_task_with_nodes(core, index, encoder, "auth-task", "fix auth bug")
    _ = _seed_task_with_nodes(core, index, encoder, "cake-task", "bake a cake recipe")

    # Act
    result = recall_similar_tasks(
        core, index, encoder, "auth token expired again", k=3, similarity_threshold=0.5
    )

    # Assert
    assert [m.task_id for m in result.matches] == [auth_task.id]


def test_recall_similar_tasks_attaches_best_fitness_and_dead_end(
    tmp_path: Path,
) -> None:
    # Arrange
    db_path = tmp_path / "experience.db"
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)
    task = _seed_task_with_nodes(core, index, encoder, "auth-task", "fix auth bug")
    _seed_dead_end(core, task)

    # Act
    result = recall_similar_tasks(
        core, index, encoder, "auth bug", k=1, similarity_threshold=0.5
    )

    # Assert
    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.best_fitness == 1.0
    assert match.best_fitness_label == "quality-gate"
    assert match.dead_end_label == "markdown-lint-retry"


def test_recall_similar_tasks_below_threshold_returns_no_matches(
    tmp_path: Path,
) -> None:
    # Arrange
    db_path = tmp_path / "experience.db"
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)
    _ = _seed_task_with_nodes(core, index, encoder, "auth-task", "fix auth bug")

    # Act
    result = recall_similar_tasks(
        core, index, encoder, "completely unrelated goal", k=3, similarity_threshold=0.9
    )

    # Assert
    assert result.matches == []


def test_recall_similar_tasks_empty_store_returns_no_matches(tmp_path: Path) -> None:
    # Arrange
    db_path = tmp_path / "experience.db"
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)

    # Act
    result = recall_similar_tasks(
        core, index, encoder, "auth bug", k=3, similarity_threshold=0.0
    )

    # Assert
    assert result.matches == []


def _seed_task_without_fitness(
    core: ExperienceStoreCore, index: EmbeddingIndexCore, encoder: FakeEncoder
) -> None:
    """Task with only a still-RUNNING node (no fitness recorded yet)."""
    task = core.create_task(ExperienceTask(id="auth-task", spec="fix auth bug"))
    _ = index.upsert(
        TaskEmbeddingRecord(
            task_id=task.id,
            vector=encoder.encode(task.spec),
            dim=encoder.dim,
            encoder_version=encoder.version,
        )
    )
    session = core.create_session(
        ExperienceSession(task_id=task.id, algorithm="commit", owner="sess")
    )
    _ = core.append_node(
        ExperienceNode(
            session_id=session.id,
            status=ExperienceNodeStatus.RUNNING,
            label="preflight",
            step_number=1,
        )
    )


def test_recall_similar_tasks_task_without_fitness_nodes_has_no_best_fitness(
    tmp_path: Path,
) -> None:
    # Arrange: task has only non-fitness nodes (e.g. a still-running attempt).
    db_path = tmp_path / "experience.db"
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)
    _seed_task_without_fitness(core, index, encoder)

    # Act
    result = recall_similar_tasks(
        core, index, encoder, "auth bug", k=1, similarity_threshold=0.5
    )

    # Assert
    assert len(result.matches) == 1
    assert result.matches[0].best_fitness is None


def test_recall_similar_tasks_skips_dangling_embedding_without_task_row(
    tmp_path: Path,
) -> None:
    # Arrange: an embedding row with no matching task (e.g. task row pruned).
    db_path = tmp_path / "experience.db"
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)
    _ = index.upsert(
        TaskEmbeddingRecord(
            task_id="orphan-task",
            vector=encoder.encode("fix auth bug"),
            dim=encoder.dim,
            encoder_version=encoder.version,
        )
    )

    # Act
    result = recall_similar_tasks(
        core, index, encoder, "auth bug", k=3, similarity_threshold=0.5
    )

    # Assert
    assert result.matches == []


def test_recall_similar_tasks_respects_k(tmp_path: Path) -> None:
    # Arrange
    db_path = tmp_path / "experience.db"
    core = ExperienceStoreCore(db_path)
    index = EmbeddingIndexCore(db_path)
    encoder = FakeEncoder(keyword_dims={"auth": 0}, dim=4)
    for i in range(5):
        _ = _seed_task_with_nodes(
            core, index, encoder, f"auth-task-{i}", "fix auth bug"
        )

    # Act
    result = recall_similar_tasks(
        core, index, encoder, "auth bug", k=2, similarity_threshold=0.0
    )

    # Assert
    assert len(result.matches) == 2
