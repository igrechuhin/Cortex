"""Pydantic models for plan enrich operations."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.tools.models_base import ToolResultStatus


class EnrichPlanResult(BaseModel):
    """Result of enriching a plan with clarification resolutions."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID, validate_assignment=True, use_enum_values=True
    )

    status: ToolResultStatus = Field(description="Operation status")
    file_path: str | None = Field(
        default=None, description="Absolute path to the enriched plan"
    )
    message: str = Field(description="Success or error message")
    resolved_markers: int = Field(
        default=0, ge=0, description="Count of markers resolved in this call"
    )
    remaining_markers: int = Field(
        default=0, ge=0, description="Count of unresolved markers after enrichment"
    )
    error: str | None = Field(default=None, description="Error message if failed")
