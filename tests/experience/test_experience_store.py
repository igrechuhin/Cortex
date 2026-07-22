"""Unit tests for the experience repository (sync core + async facade)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from cortex.experience.models import (
    ExperienceNode,
    ExperienceNodeStatus,
    ExperienceSession,
    ExperienceTask,
)
from cortex.experience.store import ExperienceStore
from cortex.experience.store_core import ExperienceStoreCore


def _seed_session(core: ExperienceStoreCore) -> ExperienceSession:
    task = core.create_task(ExperienceTask(spec="pipeline:commit"))
    return core.create_session(
        ExperienceSession(task_id=task.id, algorithm="commit", owner="sess")
    )


def test_core_round_trips_task_session_node(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)

    # Act
    node = core.append_node(
        ExperienceNode(session_id=session.id, label="preflight:running")
    )

    # Assert
    assert core.get_task(session.task_id) is not None
    assert core.get_session(session.id) is not None
    fetched = core.get_node(node.id)
    assert fetched is not None
    assert fetched.label == "preflight:running"


def test_core_get_missing_rows_return_none(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")

    # Act / Assert
    assert core.get_task("missing") is None
    assert core.get_session("missing") is None
    assert core.get_node("missing") is None
    assert core.latest_node("missing") is None
    assert core.list_nodes("missing") == []


def test_core_set_fitness_and_link_artifact(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    node = core.append_node(ExperienceNode(session_id=session.id))

    # Act
    fitness_set = core.set_fitness(node.id, 1.0)
    artifact_set = core.link_artifact(node.id, ".cortex/experience/artifacts/a.json")

    # Assert
    assert fitness_set is True
    assert artifact_set is True
    fetched = core.get_node(node.id)
    assert fetched is not None
    assert fetched.fitness == 1.0
    assert fetched.artifact_ref == ".cortex/experience/artifacts/a.json"


def test_core_updates_on_missing_node_return_false(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")

    # Act / Assert
    assert core.set_fitness("missing", 0.0) is False
    assert core.link_artifact("missing", ".cortex/experience/artifacts/a.json") is False


def test_core_list_nodes_ordered_by_step_number(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    for step in (2, 1, 3):
        _ = core.append_node(ExperienceNode(session_id=session.id, step_number=step))

    # Act
    nodes = core.list_nodes(session.id)

    # Assert
    assert [node.step_number for node in nodes] == [1, 2, 3]
    latest = core.latest_node(session.id)
    assert latest is not None
    assert latest.step_number == 3


def test_core_accepts_node_with_unknown_parent(tmp_path: Path) -> None:
    # Arrange: append-only best-effort store does not enforce parent FK.
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)

    # Act
    node = core.append_node(
        ExperienceNode(session_id=session.id, parent_id="missing-parent")
    )

    # Assert
    assert core.get_node(node.id) is not None
    assert core.get_node("missing-parent") is None


def test_core_concurrent_appends_all_persist(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)

    # Act
    def append(step: int) -> None:
        _ = core.append_node(ExperienceNode(session_id=session.id, step_number=step))

    with ThreadPoolExecutor(max_workers=8) as pool:
        _ = list(pool.map(append, range(1, 17)))

    # Assert
    assert len(core.list_nodes(session.id)) == 16


def test_core_preference_pairs_returns_sibling_divergence(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    parent = core.append_node(ExperienceNode(session_id=session.id))
    passed = core.append_node(
        ExperienceNode(
            session_id=session.id,
            parent_id=parent.id,
            status=ExperienceNodeStatus.COMPLETED,
            fitness=1.0,
            step_number=2,
        )
    )
    failed = core.append_node(
        ExperienceNode(
            session_id=session.id,
            parent_id=parent.id,
            status=ExperienceNodeStatus.FAILED,
            step_number=2,
        )
    )

    # Act
    pairs = core.preference_pairs(session.id)

    # Assert
    assert len(pairs) == 1
    assert pairs[0].passed_node.id == passed.id
    assert pairs[0].failed_node.id == failed.id


def test_core_repeated_failures_clusters_labels(tmp_path: Path) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    for step in (1, 2):
        _ = core.append_node(
            ExperienceNode(
                session_id=session.id,
                status=ExperienceNodeStatus.FAILED,
                label="quality-gate",
                step_number=step,
            )
        )

    # Act
    clusters = core.repeated_failures(session.id)

    # Assert
    assert len(clusters) == 1
    assert clusters[0].label == "quality-gate"
    assert clusters[0].count == 2


def test_core_fitness_by_task_type_aggregates_across_sessions(
    tmp_path: Path,
) -> None:
    # Arrange
    core = ExperienceStoreCore(tmp_path / "experience.db")
    session = _seed_session(core)
    _ = core.append_node(
        ExperienceNode(
            session_id=session.id,
            status=ExperienceNodeStatus.COMPLETED,
            fitness=0.8,
        )
    )

    # Act
    stats = core.fitness_by_task_type()

    # Assert
    assert len(stats) == 1
    assert stats[0].task_type == "commit"
    assert stats[0].sample_count == 1
    assert stats[0].avg_fitness == 0.8


@pytest.mark.asyncio
async def test_async_store_delegates_analytics_to_core(tmp_path: Path) -> None:
    # Arrange
    store = ExperienceStore.from_db_path(tmp_path / "experience.db")
    task = await store.create_task(ExperienceTask(spec="pipeline:commit"))
    session = await store.create_session(
        ExperienceSession(task_id=task.id, algorithm="commit")
    )
    parent = await store.append_node(ExperienceNode(session_id=session.id))
    _ = await store.append_node(
        ExperienceNode(
            session_id=session.id,
            parent_id=parent.id,
            status=ExperienceNodeStatus.COMPLETED,
            fitness=1.0,
            step_number=2,
        )
    )
    _ = await store.append_node(
        ExperienceNode(
            session_id=session.id,
            parent_id=parent.id,
            status=ExperienceNodeStatus.FAILED,
            step_number=2,
        )
    )

    # Act
    pairs = await store.preference_pairs(session.id)
    clusters = await store.repeated_failures(session.id)
    fitness_stats = await store.fitness_by_task_type()

    # Assert
    assert len(pairs) == 1
    assert clusters == []
    assert len(fitness_stats) == 1
    assert fitness_stats[0].task_type == "commit"


@pytest.mark.asyncio
async def test_async_store_delegates_to_core(tmp_path: Path) -> None:
    # Arrange
    store = ExperienceStore.from_db_path(tmp_path / "experience.db")
    task = await store.create_task(ExperienceTask(spec="pipeline:implement"))
    session = await store.create_session(
        ExperienceSession(task_id=task.id, algorithm="implement")
    )

    # Act
    node = await store.append_node(ExperienceNode(session_id=session.id))
    _ = await store.set_fitness(node.id, 0.5)
    _ = await store.link_artifact(node.id, ".cortex/experience/artifacts/b.json")

    # Assert
    assert await store.get_task(task.id) == task
    assert await store.get_session(session.id) == session
    fetched = await store.get_node(node.id)
    assert fetched is not None
    assert fetched.fitness == 0.5
    assert (await store.list_nodes(session.id)) == [fetched]
    assert await store.latest_node(session.id) == fetched
    assert store.core.db_path == tmp_path / "experience.db"
