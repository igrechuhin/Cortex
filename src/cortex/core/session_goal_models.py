"""Session goal anchor and drift-check result models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID

# strict=False so JSON round-trip accepts ISO datetime strings from model_dump_json().
_CORE_GOAL = ConfigDict(
    extra=EXTRA_FORBID,
    validate_assignment=True,
    validate_default=True,
    strict=False,
)


class _SessionGoalBase(BaseModel):
    """Strict Pydantic base without importing cortex.tools (avoids import cycles)."""

    model_config = _CORE_GOAL


class SessionGoal(_SessionGoalBase):
    """Primary session goal and scope patterns for drift detection."""

    goal: str = Field(
        ..., min_length=1, description="One-sentence primary session goal."
    )
    plan_slug: str | None = Field(
        None,
        description="Plan filename or slug this session implements, if any.",
    )
    allowed_files: list[str] = Field(
        default_factory=list,
        description="Glob patterns considered in scope.",
    )
    blocked_files: list[str] = Field(
        default_factory=list,
        description="Glob patterns explicitly out of scope.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this anchor was written.",
    )
    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=1,
        description="Unique id for this session goal anchor.",
    )


class DriftResult(_SessionGoalBase):
    """Outcome of comparing a path against a session goal."""

    drifted: bool = Field(description="True if the path looks out of scope.")
    reason: str = Field(default="", description="Short explanation.")
    allowed: bool = Field(
        default=False,
        description="True when an allowed_files pattern matched.",
    )
