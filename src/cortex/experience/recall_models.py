"""Pydantic result models for similar-task recall."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaskRecallMatch(BaseModel):
    """One prior task recalled as similar to the current goal."""

    task_id: str = Field(min_length=1)
    spec: str = Field(min_length=1)
    similarity: float = Field(ge=-1.0, le=1.0)
    hybrid_score: float | None = Field(
        default=None, description="Combined vector+BM25 score used for ranking"
    )
    best_fitness: float | None = Field(
        default=None, description="Highest fitness recorded across the task's nodes"
    )
    best_fitness_label: str | None = Field(
        default=None, description="Label of the node that reached best_fitness"
    )
    dead_end_label: str | None = Field(
        default=None,
        description="Label that failed repeatedly (>=2x) across the task's nodes",
    )


def _default_matches() -> list[TaskRecallMatch]:
    return []


class RecallResult(BaseModel):
    """Result of a similar-task recall query for one goal."""

    goal: str = Field(min_length=1)
    matches: list[TaskRecallMatch] = Field(default_factory=_default_matches)
