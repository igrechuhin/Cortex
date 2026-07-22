"""Synchronous SQLite core for the task-embedding index.

Mirrors ``cortex.experience.store_core.ExperienceStoreCore`` conventions
(short-lived ``sqlite3`` connections, parameterized queries). Top-k query is
a brute-force scan over all stored vectors; acceptable at dev-tool scale per
the plan's risk table (add an ANN index only if measured p95 exceeds target).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from cortex.experience.embedding_math import (
    cosine_similarity,
    pack_vector,
    unpack_vector,
)
from cortex.experience.embedding_models import ScoredTaskEmbedding, TaskEmbeddingRecord
from cortex.experience.embedding_schema import migrate_embeddings

_BUSY_TIMEOUT_SECONDS = 5.0


class EmbeddingIndexCore:
    """Sync repository over the ``task_embeddings`` table (upsert; top-k scan)."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            migrate_embeddings(connection)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=_BUSY_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        return connection

    def upsert(self, record: TaskEmbeddingRecord) -> TaskEmbeddingRecord:
        """Insert or replace a task's embedding (idempotent by task_id)."""
        query = """
        INSERT INTO task_embeddings (task_id, vector, dim, encoder_version, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(task_id) DO UPDATE SET
            vector = excluded.vector,
            dim = excluded.dim,
            encoder_version = excluded.encoder_version,
            created_at = excluded.created_at
        """
        with self._connect() as connection:
            _ = connection.execute(
                query,
                (
                    record.task_id,
                    pack_vector(record.vector),
                    record.dim,
                    record.encoder_version,
                    record.created_at,
                ),
            )
            connection.commit()
        return record

    def get(self, task_id: str) -> TaskEmbeddingRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_embeddings WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def _row_to_record(self, row: sqlite3.Row) -> TaskEmbeddingRecord:
        return TaskEmbeddingRecord(
            task_id=row["task_id"],
            vector=unpack_vector(row["vector"]),
            dim=row["dim"],
            encoder_version=row["encoder_version"],
            created_at=row["created_at"],
        )

    def top_k(self, query_vector: list[float], k: int) -> list[ScoredTaskEmbedding]:
        """Return the k most cosine-similar stored embeddings, best first.

        Rows whose stored vector dimension no longer matches ``query_vector``
        (encoder version changed since indexing) are skipped rather than
        raising, per the plan's embedding-drift mitigation.
        """
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM task_embeddings").fetchall()
        scored: list[ScoredTaskEmbedding] = []
        for row in rows:
            stored_vector = unpack_vector(row["vector"])
            if len(stored_vector) != len(query_vector):
                continue
            scored.append(
                ScoredTaskEmbedding(
                    task_id=row["task_id"],
                    similarity=cosine_similarity(query_vector, stored_vector),
                )
            )
        scored.sort(key=lambda item: item.similarity, reverse=True)
        return scored[:k]
