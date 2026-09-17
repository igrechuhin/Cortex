"""Models for plan completion tool."""

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import OperationStatus
from cortex.core.pydantic_extra import EXTRA_FORBID


class CompletePlanResult(BaseModel):
    """Result of completing a plan (move from roadmap to activeContext, optional progress and archive)."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    status: OperationStatus = Field(
        description="Operation status: 'success' or 'error'"
    )
    message: str = Field(description="Success or error message")
    roadmap_line_removed: int | None = Field(
        default=None,
        ge=1,
        description="Line number removed from roadmap (on success)",
    )
    active_context_line_inserted: int | None = Field(
        default=None,
        ge=1,
        description="Line number inserted in activeContext (on success)",
    )
    progress_line_inserted: int | None = Field(
        default=None,
        ge=1,
        description="Line number inserted in progress.md (if progress_entry provided)",
    )
    archive_path: str | None = Field(
        default=None,
        description="Path where plan file was archived (if plan_file_name provided)",
    )
    error: str | None = Field(
        default=None, description="Error message if status is error"
    )
    plans_unblocked: int | None = Field(
        default=None,
        description="Plans moved from BLOCKED to READY after dependency graph resync",
    )
    operation_id: str | None = Field(
        default=None, description="Persisted completion operation identifier"
    )
    idempotent_replay: bool = Field(
        default=False,
        description="True when an identical completed request was a no-op",
    )
    recovery_required: bool = Field(
        default=False, description="True when persisted recovery work remains"
    )
