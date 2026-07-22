"""Typed results for experience-store frontier and resume queries."""

from __future__ import annotations

from pydantic import BaseModel, Field

from cortex.experience.models import ExperienceNode, ExperienceNodeStatus


class FrontierView(BaseModel):
    """Deepest state of the current run window inside an experience session."""

    session_id: str = Field(min_length=1)
    latest: ExperienceNode
    last_committed: ExperienceNode | None = None
    completed_phases: list[str] = Field(default_factory=list)
    frontier_phase: str | None = None


class IncompleteRun(BaseModel):
    """One experience session whose current run window has not ended."""

    session_id: str = Field(min_length=1)
    owner: str | None = None
    pipeline: str = Field(min_length=1)
    frontier_phase: str | None = None
    frontier_status: ExperienceNodeStatus
    last_activity_at: str = Field(min_length=1)
    age_seconds: float = Field(ge=0)
