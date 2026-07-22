"""Unit tests for the embedding index (sync core + async facade), AAA pattern."""

from __future__ import annotations

from pathlib import Path

import pytest

from cortex.experience.embedding_index import EmbeddingIndex
from cortex.experience.embedding_index_core import EmbeddingIndexCore
from cortex.experience.embedding_models import TaskEmbeddingRecord


def _record(task_id: str, vector: list[float]) -> TaskEmbeddingRecord:
    return TaskEmbeddingRecord(
        task_id=task_id, vector=vector, dim=len(vector), encoder_version="hashing-v1"
    )


def test_core_db_path_property_returns_configured_path(tmp_path: Path) -> None:
    # Arrange
    db_path = tmp_path / "experience.db"
    core = EmbeddingIndexCore(db_path)

    # Act / Assert
    assert core.db_path == db_path


def test_async_facade_core_property_returns_wrapped_core(tmp_path: Path) -> None:
    # Arrange
    index = EmbeddingIndex.from_db_path(tmp_path / "experience.db")

    # Act / Assert
    assert isinstance(index.core, EmbeddingIndexCore)


def test_core_upsert_and_get_round_trip(tmp_path: Path) -> None:
    # Arrange
    core = EmbeddingIndexCore(tmp_path / "experience.db")
    record = _record("task-1", [0.6, 0.8])

    # Act
    _ = core.upsert(record)
    fetched = core.get("task-1")

    # Assert
    assert fetched is not None
    assert fetched.task_id == "task-1"
    assert fetched.vector == pytest.approx([0.6, 0.8])  # type: ignore[arg-type]


def test_core_upsert_is_idempotent_replace(tmp_path: Path) -> None:
    # Arrange
    core = EmbeddingIndexCore(tmp_path / "experience.db")
    _ = core.upsert(_record("task-1", [1.0, 0.0]))

    # Act
    _ = core.upsert(_record("task-1", [0.0, 1.0]))
    fetched = core.get("task-1")

    # Assert
    assert fetched is not None
    assert fetched.vector == pytest.approx([0.0, 1.0])  # type: ignore[arg-type]


def test_core_get_missing_task_returns_none(tmp_path: Path) -> None:
    # Arrange
    core = EmbeddingIndexCore(tmp_path / "experience.db")

    # Act
    fetched = core.get("missing")

    # Assert
    assert fetched is None


def test_core_top_k_ranks_by_cosine_similarity_descending(tmp_path: Path) -> None:
    # Arrange
    core = EmbeddingIndexCore(tmp_path / "experience.db")
    _ = core.upsert(_record("close", [1.0, 0.0]))
    _ = core.upsert(_record("far", [0.0, 1.0]))
    _ = core.upsert(_record("mid", [0.7, 0.3]))

    # Act
    results = core.top_k([1.0, 0.0], k=2)

    # Assert
    assert [r.task_id for r in results] == ["close", "mid"]


def test_core_top_k_empty_index_returns_empty_list(tmp_path: Path) -> None:
    # Arrange
    core = EmbeddingIndexCore(tmp_path / "experience.db")

    # Act
    results = core.top_k([1.0, 0.0], k=5)

    # Assert
    assert results == []


def test_core_top_k_skips_dimension_mismatch_rows(tmp_path: Path) -> None:
    # Arrange
    core = EmbeddingIndexCore(tmp_path / "experience.db")
    _ = core.upsert(_record("stale", [1.0, 0.0, 0.0]))
    _ = core.upsert(_record("current", [1.0, 0.0]))

    # Act
    results = core.top_k([1.0, 0.0], k=5)

    # Assert
    assert [r.task_id for r in results] == ["current"]


@pytest.mark.asyncio
async def test_async_facade_round_trips_via_to_thread(tmp_path: Path) -> None:
    # Arrange
    index = EmbeddingIndex.from_db_path(tmp_path / "experience.db")

    # Act
    _ = await index.upsert(_record("task-1", [0.6, 0.8]))
    fetched = await index.get("task-1")
    top = await index.top_k([0.6, 0.8], k=1)

    # Assert
    assert fetched is not None and fetched.task_id == "task-1"
    assert len(top) == 1
    assert top[0].task_id == "task-1"
