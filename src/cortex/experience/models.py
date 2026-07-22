"""Pydantic 2 models for the unified experience store.

Mirrors the Trellis-style hierarchy from the Experience Graphs paper:
task -> session -> node, with large payloads stored on disk and linked
by relative ``artifact_ref`` paths.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_experience_id() -> str:
    """Return a random hex id for experience rows."""
    return uuid.uuid4().hex


class ExperienceNodeStatus(StrEnum):
    """Lifecycle status of an experience node (one pipeline-phase attempt).

    Lifecycle: ``pending`` -> ``running`` -> ``completed`` | ``failed``.
    ``completed`` is the committed (resumable) terminal state; transitions are
    enforced by :func:`cortex.experience.lifecycle.can_transition`.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperienceTask(BaseModel):
    """Top-level task row: what the pipeline run is trying to achieve."""

    id: str = Field(default_factory=new_experience_id)
    spec: str = Field(min_length=1)
    success_metric: str | None = None
    created_at: str = Field(default_factory=_utc_now_iso)


class ExperienceSession(BaseModel):
    """One pipeline run (search episode) belonging to a task."""

    id: str = Field(default_factory=new_experience_id)
    task_id: str = Field(min_length=1)
    algorithm: str = Field(min_length=1)
    owner: str | None = None
    progress: str | None = None
    created_at: str = Field(default_factory=_utc_now_iso)


class ExperienceNode(BaseModel):
    """One attempt (phase transition / gate run) within a session."""

    id: str = Field(default_factory=new_experience_id)
    parent_id: str | None = None
    session_id: str = Field(min_length=1)
    artifact_ref: str | None = None
    fitness: float | None = None
    status: ExperienceNodeStatus = ExperienceNodeStatus.RUNNING
    step_number: int = Field(default=1, ge=1)
    label: str | None = None
    created_at: str = Field(default_factory=_utc_now_iso)
