"""Models for step-by-step plan section state."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID

from ._enums import PlanSectionStatus


class PlanSection(BaseModel):
    """One section of a plan while iterating in step-by-step mode."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    name: str = Field(
        ...,
        description="Stable section id (e.g. goal, context, steps).",
    )
    status: PlanSectionStatus = Field(
        ...,
        description="Whether the section is pending, drafted, approved, or skipped.",
    )
    content: str = Field(
        default="",
        description="Markdown body for this section (may be empty while pending).",
    )
    approved_at: datetime | None = Field(
        default=None,
        description="When the section was approved, if applicable.",
    )
