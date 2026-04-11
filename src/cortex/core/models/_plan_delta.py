"""Structured record for plan revision deltas (change history)."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class PlanDelta(BaseModel):
    """One revision record appended to a plan's ``## Change History`` section."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    timestamp: datetime = Field(
        ...,
        description="UTC time when the revision was recorded.",
    )
    author: str = Field(
        ...,
        description="Agent or human identifier associated with the change.",
    )
    renamed: list[str] = Field(
        default_factory=list,
        description="Renamed implementation steps (old header → new header).",
    )
    removed: list[str] = Field(
        default_factory=list,
        description="Removed step headers or identifiers.",
    )
    modified: list[str] = Field(
        default_factory=list,
        description="Steps whose body changed (human-readable summaries).",
    )
    added: list[str] = Field(
        default_factory=list,
        description="Newly added step headers or descriptions.",
    )
    reason: str = Field(
        ...,
        description="Why the change was made.",
    )

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(timezone.utc)
