"""
Models for check_structure_health cleanup results.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field

from cortex.core.models import JsonDict
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.tools.models_base import StrictBaseModel


class CleanupActionResult(StrictBaseModel):
    """Result of a single cleanup action."""

    action: str = Field(..., min_length=1, description="Action performed")
    stale_plans_found: int | None = Field(
        None, ge=0, description="Number of stale plans found"
    )
    files: list[str] = Field(default_factory=list, description="Files affected")
    legacy_cursor_artifacts_removed: int | None = Field(
        None, ge=0, description="Number of leftover .cursor/ artifacts removed"
    )

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
    )


class CleanupReport(StrictBaseModel):
    """Complete cleanup operation report."""

    dry_run: bool = Field(description="Whether this was a dry run")
    actions_performed: list[CleanupActionResult] = Field(
        default_factory=lambda: list[CleanupActionResult](),
        description="List of actions performed",
    )
    files_modified: list[str] = Field(
        default_factory=list, description="List of files modified"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations for further cleanup"
    )
    post_cleanup_health: JsonDict = Field(
        description="Health check result after cleanup"
    )

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)
