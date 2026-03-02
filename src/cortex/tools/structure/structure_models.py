"""
Models for check_structure_health and get_structure_info tool results.
"""

from __future__ import annotations

from enum import Enum

from pydantic import ConfigDict, Field

from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


class HealthGrade(str, Enum):
    """Health grade (A–F)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class HealthStatus(str, Enum):
    """Health status level."""

    HEALTHY = "healthy"
    GOOD = "good"
    FAIR = "fair"
    WARNING = "warning"
    CRITICAL = "critical"
    NOT_INITIALIZED = "not_initialized"


class HealthChecks(StrictBaseModel):
    """Health check results."""

    required_directories: bool
    symlinks_valid: bool
    config_exists: bool
    files_organized: bool | None = None
    memory_bank_files: bool | None = None


class HealthInfo(StrictBaseModel):
    """Health information structure."""

    score: int
    grade: HealthGrade
    status: HealthStatus
    checks: HealthChecks
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class CleanupActionResult(StrictBaseModel):
    """Result of a single cleanup action."""

    action: str = Field(..., min_length=1, description="Action performed")
    stale_plans_found: int | None = Field(
        None, ge=0, description="Number of stale plans found"
    )
    files: list[str] = Field(default_factory=list, description="Files affected")
    symlinks_fixed: int | None = Field(
        None, ge=0, description="Number of symlinks fixed"
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class PostCleanupHealth(StrictBaseModel):
    """Health status after cleanup."""

    score: int
    grade: HealthGrade
    status: HealthStatus


class CleanupInfo(StrictBaseModel):
    """Cleanup operation information."""

    dry_run: bool
    actions_performed: list[CleanupActionResult] = Field(
        default_factory=lambda: list[CleanupActionResult]()
    )
    files_modified: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    post_cleanup_health: PostCleanupHealth | None = None


class CheckStructureHealthResult(ToolResultBase):
    """Result of check_structure_health operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    health: HealthInfo
    summary: str
    action_required: bool
    cleanup: CleanupInfo | None = None


class CheckStructureHealthErrorResult(ErrorResultBase):
    """Error result for check_structure_health operations."""


CheckStructureHealthResultUnion = (
    CheckStructureHealthResult | CheckStructureHealthErrorResult
)


class StructurePaths(StrictBaseModel):
    """Structure paths configuration."""

    cursor_dir: str
    memory_bank: str
    memory_bank_symlink: str
    plans: str
    plans_active: str
    plans_completed: str
    plans_archived: str
    rules: str
    rules_symlink: str
    config: str


class StructureExists(StrictBaseModel):
    """Structure existence status."""

    cursor_dir: bool
    memory_bank: bool
    memory_bank_symlink: bool
    plans: bool
    plans_active: bool
    plans_completed: bool
    plans_archived: bool
    rules: bool
    rules_symlink: bool
    config: bool


class SymlinkInfo(StrictBaseModel):
    """Symlink information."""

    path: str
    target: str
    valid: bool
    exists: bool


class StructureSymlinks(StrictBaseModel):
    """Structure symlinks information."""

    memory_bank: SymlinkInfo | None = None
    rules: SymlinkInfo | None = None


class StructureConfig(StrictBaseModel):
    """Structure configuration."""

    version: str
    stale_days: int
    auto_archive: bool
    symlink_targets: dict[str, str] = Field(default_factory=dict)


class HealthSummary(StrictBaseModel):
    """Health summary information."""

    score: int
    grade: HealthGrade
    status: HealthStatus
    initialized: bool


class StructureInfo(StrictBaseModel):
    """Complete structure information."""

    version: str
    root: str
    paths: StructurePaths
    exists: StructureExists
    symlinks: StructureSymlinks
    config: StructureConfig | None = None
    health_summary: HealthSummary


class GetStructureInfoResult(ToolResultBase):
    """Result of get_structure_info operation (success)."""

    status: ToolResultStatus = Field(default=ToolResultStatus.SUCCESS)
    structure_info: StructureInfo
    message: str


class GetStructureInfoErrorResult(ErrorResultBase):
    """Error result for get_structure_info operations."""


GetStructureInfoResultUnion = GetStructureInfoResult | GetStructureInfoErrorResult
