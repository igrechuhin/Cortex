"""Pydantic models for the task-embedding index."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class TaskEmbeddingRecord(BaseModel):
    """One task's stored embedding (vector persisted as a BLOB in SQLite)."""

    task_id: str = Field(min_length=1)
    vector: list[float] = Field(min_length=1)
    dim: int = Field(gt=0)
    encoder_version: str = Field(min_length=1)
    created_at: str = Field(default_factory=_utc_now_iso)


class ScoredTaskEmbedding(BaseModel):
    """One top-k query result: a task id with its cosine similarity."""

    task_id: str = Field(min_length=1)
    similarity: float = Field(ge=-1.0, le=1.0)
