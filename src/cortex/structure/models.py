"""
Pydantic models for structure module.

This module contains Pydantic models for structure lifecycle operations,
health checking, setup, and symlink management.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import JsonDict
from cortex.core.path_resolver import CortexResourceType
from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID

# ============================================================================
# Base Model
# ============================================================================


class StructureBaseModel(BaseModel):
    """Base model for structure types with strict validation."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )


# ============================================================================
# Structure Configuration Models
# ============================================================================


class LayoutConfig(StructureBaseModel):
    """Layout configuration for directory structure."""

    root: str = Field(
        default=CortexResourceType.CORTEX_DIR.value, description="Root directory name"
    )
    memory_bank: str = Field(
        default=CortexResourceType.MEMORY_BANK.value,
        description="Memory bank directory",
    )
    rules: str = Field(
        default=CortexResourceType.RULES.value, description="Rules directory"
    )
    plans: str = Field(
        default=CortexResourceType.PLANS.value, description="Plans directory"
    )
    config: str = Field(
        default=CortexResourceType.CONFIG.value, description="Config directory"
    )
    archived: str = Field(
        default=CortexResourceType.ARCHIVED.value, description="Archived directory"
    )
    reviews: str = Field(
        default=CortexResourceType.REVIEWS.value, description="Reviews directory"
    )


class HousekeepingConfig(StructureBaseModel):
    """Housekeeping configuration for automatic maintenance."""

    auto_cleanup: bool = Field(default=True, description="Enable auto cleanup")
    stale_plan_days: int = Field(
        default=90, ge=1, description="Days before plan is considered stale"
    )
    archive_completed_plans: bool = Field(
        default=True, description="Archive completed plans"
    )
    detect_duplicates: bool = Field(default=True, description="Detect duplicates")


class RulesConfig(StructureBaseModel):
    """Rules configuration for shared/local rules."""

    use_submodule: bool = Field(
        default=False, description="Use git submodule for rules"
    )
    submodule_path: str = Field(
        default="rules/shared", description="Path for shared rules submodule"
    )
    local_rules_path: str = Field(
        default="rules/local", description="Path for local rules"
    )
    shared_repo_url: str | None = Field(
        default=None, description="URL for shared rules repository"
    )


class StructureConfigModel(StructureBaseModel):
    """Complete structure configuration model.

    This model represents the full structure.json configuration file.
    """

    model_config = ConfigDict(
        extra=EXTRA_ALLOW,  # Allow extra fields for forward compatibility
        validate_assignment=True,
        validate_default=True,
    )

    version: str = Field(default="2.0", description="Configuration version")
    layout: LayoutConfig = Field(
        default_factory=LayoutConfig, description="Directory layout"
    )
    housekeeping: HousekeepingConfig = Field(
        default_factory=HousekeepingConfig, description="Housekeeping settings"
    )
    rules: RulesConfig = Field(
        default_factory=RulesConfig, description="Rules configuration"
    )


# ============================================================================
# Health Check Models
# ============================================================================


class HealthGrade(str, Enum):
    """Letter grade for structure health score."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class HealthStatus(str, Enum):
    """Health status for structure check."""

    HEALTHY = "healthy"
    GOOD = "good"
    FAIR = "fair"
    WARNING = "warning"
    CRITICAL = "critical"


class HealthCheckResult(StructureBaseModel):
    """Result of structure health check."""

    score: int = Field(..., ge=0, le=100, description="Health score 0-100")
    grade: HealthGrade = Field(..., description="Letter grade")
    status: HealthStatus = Field(..., description="Health status")
    checks: list[str] = Field(default_factory=list, description="Passed checks")
    issues: list[str] = Field(default_factory=list, description="Issues found")
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )


# ============================================================================
# Setup Models
# ============================================================================


class SetupReport(StructureBaseModel):
    """Report of structure setup operation."""

    created_directories: list[str] = Field(
        default_factory=list, description="Directories created"
    )
    created_files: list[str] = Field(default_factory=list, description="Files created")
    skipped: list[str] = Field(
        default_factory=list, description="Items skipped (already exist)"
    )
    errors: list[str] = Field(default_factory=list, description="Errors encountered")


# ============================================================================
# Structure Info Models
# ============================================================================


class StructurePaths(StructureBaseModel):
    """Structure paths information."""

    root: str = Field(..., description="Root directory path")
    memory_bank: str = Field(..., description="Memory bank directory path")
    rules: str = Field(..., description="Rules directory path")
    plans: str = Field(..., description="Plans directory path")
    config: str = Field(..., description="Config directory path")
    reviews: str = Field(..., description="Reviews directory path")


class StructureInfoResult(StructureBaseModel):
    """Result of get_structure_info operation."""

    model_config = ConfigDict(
        extra=EXTRA_ALLOW,  # Allow extra fields for forward compatibility
        validate_assignment=True,
        validate_default=True,
    )

    version: str = Field(..., description="Structure version")
    paths: StructurePaths = Field(..., description="Structure paths")
    configuration: StructureConfigModel = Field(
        default_factory=StructureConfigModel,
        description="Structure configuration",
    )
    exists: bool = Field(..., description="Whether structure exists")
    health: HealthCheckResult | None = Field(
        None, description="Health check result if structure exists"
    )


# ============================================================================
# Migration Models
# ============================================================================


class FileMappingEntry(StructureBaseModel):
    """File mapping entry for migration."""

    source: str = Field(..., description="Source file path")
    destination: str = Field(..., description="Destination file path")


class MigrationReport(StructureBaseModel):
    """Report of structure migration operation."""

    success: bool = Field(..., description="Whether migration succeeded")
    legacy_type: str | None = Field(
        default=None, description="Type of legacy structure found"
    )
    files_migrated: int = Field(default=0, ge=0, description="Number of files migrated")
    file_mappings: list[FileMappingEntry] = Field(
        default_factory=lambda: list[FileMappingEntry](),
        description="File mappings from source to destination",
    )
    backup_location: str | None = Field(
        default=None, description="Path to backup directory"
    )
    archive_location: str | None = Field(
        default=None, description="Path to archive directory"
    )
    structure_creation: SetupReport | None = Field(
        default=None, description="Structure creation report"
    )
    detected_languages: list[str] = Field(
        default_factory=list,
        description="Detected primary language(s) for the project root",
    )
    scaffolded_languages: list[str] = Field(
        default_factory=list,
        description="Languages for which migration scaffolding was applied",
    )
    scripts_scaffolded: list[str] = Field(
        default_factory=list,
        description="Language scripts stubs created during migration",
    )
    rules_scaffolded: list[str] = Field(
        default_factory=list,
        description="Rule files scaffolded from language templates during migration",
    )
    scaffolding_warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about scaffolded language script stubs needing customization",
    )
    errors: list[str] = Field(default_factory=list, description="Errors encountered")
    error: str | None = Field(
        default=None, description="Error message if migration failed"
    )


# ============================================================================
# Health Result Models
# ============================================================================


class HealthResult(StructureBaseModel):
    """Health result with summary information."""

    success: bool = Field(..., description="Whether operation succeeded")
    health: JsonDict = Field(..., description="Health report from structure manager")
    summary: str = Field(..., description="Summary message")
    action_required: bool = Field(..., description="Whether action is required")


# ============================================================================
# Cleanup Report Models
# ============================================================================


class CleanupActionEntry(StructureBaseModel):
    """Single cleanup action entry."""

    action: str = Field(..., description="Action performed")
    description: str = Field(..., description="Action description")
    files_affected: list[str] = Field(
        default_factory=list, description="Files affected by action"
    )


class CleanupReport(StructureBaseModel):
    """Report of cleanup operations."""

    dry_run: bool = Field(..., description="Whether this was a dry run")
    actions_performed: list[CleanupActionEntry] = Field(
        default_factory=lambda: list[CleanupActionEntry](),
        description="Actions performed",
    )
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )
    post_cleanup_health: JsonDict | None = Field(
        default=None, description="Health after cleanup"
    )
