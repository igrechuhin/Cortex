"""
Pydantic models for plan CRUD tool (create_plan, list_plans, get_plan).
"""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.wiki.glossary_models import TerminologyFinding


def _empty_task_graph() -> list[dict[str, object]]:
    return []


class CreatePlanResult(BaseModel):
    """Result of creating a plan file."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    file_path: str | None = Field(
        None, description="Absolute path to created plan file (on success)"
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")
    planning_mode: str | None = Field(
        default=None,
        description="When set, echoes create-time planning mode (ff or step)",
    )
    review_prompt: str | None = Field(
        default=None,
        description="Human-facing next step hint for step-by-step drafts",
    )
    terminology_findings: list[TerminologyFinding] = Field(
        default_factory=lambda: [],
        description="Advisory glossary collisions; never affects status",
    )
    terminology_summary: str | None = Field(
        default=None,
        description="One-line Terminology row for the /cortex/plan final report",
    )


class PlanEntry(BaseModel):
    """Single plan entry for list_plans response."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    slug: str = Field(description="Filename without .md (e.g. phase-60-feature)")
    title: str | None = Field(
        None, description="First # heading from plan content, if available"
    )


class ListPlansResult(BaseModel):
    """Result of listing plans."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    plans: list[PlanEntry] = Field(
        default_factory=lambda: [],
        description="List of plan entries (slug, optional title)",
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")


class GetPlanResult(BaseModel):
    """Result of reading a plan (content or metadata)."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    slug: str | None = Field(None, description="Plan slug (filename without .md)")
    content: str | None = Field(
        None, description="Full plan content when response_format='content'"
    )
    title: str | None = Field(None, description="First # heading (metadata)")
    plan_status: str | None = Field(
        None,
        description="Value of **Status**: line (metadata); alias to avoid 'status' clash",
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")
    change_count: int = Field(
        default=0,
        ge=0,
        description="Number of entries under ## Change History",
    )
    latest_delta: str | None = Field(
        default=None,
        description="One-line summary of the most recent change history entry",
    )
    task_graph: list[dict[str, object]] = Field(
        default_factory=_empty_task_graph,
        description="Parsed implementation steps (TaskNode.model_dump) on success",
    )
    can_parallelize: bool = Field(
        default=False,
        description="True when any step uses a [P] parallel marker",
    )
