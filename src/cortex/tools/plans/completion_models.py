"""Models for plan completion tool."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import OperationStatus


class CompletePlanResult(BaseModel):
    """Result of completing a plan (move from roadmap to activeContext, optional progress and archive)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: OperationStatus = Field(
        description="Operation status: 'success' or 'error'"
    )
    message: str = Field(description="Success or error message")
    roadmap_line_removed: int | None = Field(
        None, ge=1, description="Line number removed from roadmap (on success)"
    )
    active_context_line_inserted: int | None = Field(
        None, ge=1, description="Line number inserted in activeContext (on success)"
    )
    progress_line_inserted: int | None = Field(
        None,
        ge=1,
        description="Line number inserted in progress.md (if progress_entry provided)",
    )
    archive_path: str | None = Field(
        None,
        description="Path where plan file was archived (if plan_file_name provided)",
    )
    error: str | None = Field(None, description="Error message if status is error")
    plans_unblocked: int | None = Field(
        default=None,
        description="Plans moved from BLOCKED to READY after dependency graph resync",
    )
