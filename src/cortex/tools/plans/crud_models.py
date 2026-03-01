"""
Pydantic models for plan CRUD tool (create_plan, list_plans, get_plan).
"""

from pydantic import BaseModel, ConfigDict, Field


class CreatePlanResult(BaseModel):
    """Result of creating a plan file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    file_path: str | None = Field(
        None, description="Absolute path to created plan file (on success)"
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")


class PlanEntry(BaseModel):
    """Single plan entry for list_plans response."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    slug: str = Field(description="Filename without .md (e.g. phase-60-feature)")
    title: str | None = Field(
        None, description="First # heading from plan content, if available"
    )


class ListPlansResult(BaseModel):
    """Result of listing plans."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(description="Operation status: 'success' or 'error'")
    plans: list[PlanEntry] = Field(
        default_factory=lambda: [],
        description="List of plan entries (slug, optional title)",
    )
    message: str = Field(description="Success or error message")
    error: str | None = Field(None, description="Error message if status is error")


class GetPlanResult(BaseModel):
    """Result of reading a plan (content or metadata)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

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
