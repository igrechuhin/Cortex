"""Structured JSON results for step-by-step plan operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.wiki.glossary_models import TerminologyFinding


class StepContinueResult(BaseModel):
    """Result of ``plan(operation='continue_step')``."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    status: str = Field(description="'success' or 'error'")
    message: str = Field(description="Human-readable summary")
    error: str | None = Field(None, description="Error detail when status is error")
    section_key: str | None = Field(None, description="Section key that was drafted")
    file_path: str | None = Field(None, description="Absolute path to draft file")


class StepApproveResult(BaseModel):
    """Result of ``plan(operation='approve_step')``."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    status: str = Field(description="'success' or 'error'")
    message: str = Field(description="Human-readable summary")
    error: str | None = Field(None, description="Error detail when status is error")
    file_path: str | None = Field(None, description="Absolute path to draft file")
    section_key: str | None = Field(None, description="Section key acted on")
    next_hint: str | None = Field(None, description="Suggested next orchestration step")


class StepFinalizeResult(BaseModel):
    """Result of ``plan(operation='finalize_step')``."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    status: str = Field(description="'success' or 'error'")
    message: str = Field(description="Human-readable summary")
    error: str | None = Field(None, description="Error detail when status is error")
    final_path: str | None = Field(None, description="Published plan path")
    draft_removed: str | None = Field(None, description="Former draft path if removed")
    register_json: str | None = Field(
        None,
        description="JSON string returned by register_plan_in_roadmap",
    )
    terminology_findings: list[TerminologyFinding] = Field(
        default_factory=lambda: [],
        description="Advisory glossary collisions; never affects status",
    )
    terminology_summary: str | None = Field(
        default=None,
        description="One-line Terminology row for the /cortex/plan final report",
    )
