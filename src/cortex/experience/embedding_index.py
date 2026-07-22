"""Async facade over the task-embedding index.

Thin async wrapper over :class:`EmbeddingIndexCore`; every method offloads
the blocking SQLite call via ``asyncio.to_thread`` (mirrors
``cortex.experience.store.ExperienceStore``).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from cortex.experience.embedding_index_core import EmbeddingIndexCore
from cortex.experience.embedding_models import ScoredTaskEmbedding, TaskEmbeddingRecord


class EmbeddingIndex:
    """Async task-embedding repository (upsert; top-k cosine query)."""

    def __init__(self, core: EmbeddingIndexCore) -> None:
        self._core = core

    @classmethod
    def from_db_path(cls, db_path: Path) -> EmbeddingIndex:
        return cls(core=EmbeddingIndexCore(db_path))

    @property
    def core(self) -> EmbeddingIndexCore:
        return self._core

    async def upsert(self, record: TaskEmbeddingRecord) -> TaskEmbeddingRecord:
        return await asyncio.to_thread(self._core.upsert, record)

    async def get(self, task_id: str) -> TaskEmbeddingRecord | None:
        return await asyncio.to_thread(self._core.get, task_id)

    async def top_k(
        self, query_vector: list[float], k: int
    ) -> list[ScoredTaskEmbedding]:
        return await asyncio.to_thread(self._core.top_k, query_vector, k)
