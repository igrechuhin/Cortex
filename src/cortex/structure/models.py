"""
Pydantic models for structure module.

This module contains Pydantic models for structure lifecycle operations,
health checking, setup, and symlink management.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import JsonDict
from cortex.core.path_resolver import CortexResourceType, CursorResourceType

# ============================================================================
# Base Model
# ============================================================================


class StructureBaseModel(BaseModel):
    """Base model for structure types with strict validation."""

    model_config = ConfigDict(
        extra="forbid",
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


class SymlinksConfig(StructureBaseModel):
    """Symlinks configuration for Cursor integration."""

    memory_bank: bool = Field(default=True, description="Create memory bank symlink")
    rules: bool = Field(default=True, description="Create rules symlink")
    plans: bool = Field(default=True, description="Create plans symlink")


class CursorIntegrationConfigModel(StructureBaseModel):
    """Cursor IDE integration configuration."""

    enabled: bool = Field(default=True, description="Whether integration is enabled")
    symlink_location: str = Field(
        default=CursorResourceType.CURSOR_DIR.value,
        description="Symlink location directory",
    )
    symlinks: SymlinksConfig = Field(
        default_factory=SymlinksConfig, description="Symlink settings"
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
        extra="allow",  # Allow extra fields for forward compatibility
        validate_assignment=True,
        validate_default=True,
    )

    version: str = Field(default="2.0", description="Configuration version")
    layout: LayoutConfig = Field(
        default_factory=LayoutConfig, description="Directory layout"
    )
    cursor_integration: CursorIntegrationConfigModel = Field(
        default_factory=CursorIntegrationConfigModel,
        description="Cursor IDE integration",
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
# Symlink Models
# ============================================================================


class SymlinkEntry(StructureBaseModel):
    """Information about a created symlink."""

    link: str = Field(..., description="Symlink path")
    target: str = Field(..., description="Target path")
    relative_path: str = Field(..., description="Relative path from link to target")


class SymlinkReport(StructureBaseModel):
    """Report of symlink creation operation."""

    success: bool = Field(..., description="Whether operation succeeded")
    symlinks_created: list[SymlinkEntry] = Field(
        default_factory=lambda: list[SymlinkEntry](),
        description="Symlinks created",
    )
    errors: list[str] = Field(default_factory=list, description="Errors encountered")
    platform: str = Field(..., description="Operating system platform")


class SymlinkSuccess(Enum):
    """Success value for symlink error response (always False)."""

    FAILURE = False


class SymlinkErrorResponse(StructureBaseModel):
    """Error response for symlink operations."""

    success: SymlinkSuccess = Field(default=SymlinkSuccess.FAILURE)
    error: str = Field(..., description="Error message")


# ============================================================================
# Validation Models
# ============================================================================


class CursorIntegrationConfig(StructureBaseModel):
    """Cursor integration configuration."""

    enabled: bool = Field(default=True, description="Whether integration is enabled")
    memory_bank_path: str | None = Field(
        default=None, description="Memory bank path in Cursor"
    )
    rules_path: str | None = Field(default=None, description="Rules path in Cursor")
    auto_sync: bool = Field(default=True, description="Whether to auto-sync")


class SymlinkConfig(StructureBaseModel):
    """Symlink configuration."""

    memory_bank: str | None = Field(
        default=None, description="Memory bank symlink target"
    )
    rules: str | None = Field(default=None, description="Rules symlink target")
    enabled: bool = Field(default=True, description="Whether symlinks are enabled")


class CursorIntegrationValidation(StructureBaseModel):
    """Result of cursor integration config validation."""

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for schema evolution
    )

    valid: bool = Field(..., description="Whether config is valid")
    cursor_integration: CursorIntegrationConfigModel | None = Field(
        default=None, description="Cursor integration config"
    )
    symlink_location: str | None = Field(default=None, description="Symlink location")
    symlink_config: SymlinksConfig | None = Field(
        default=None, description="Symlinks config"
    )
    error_response: SymlinkErrorResponse | None = Field(
        default=None, description="Error response if invalid"
    )


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
        extra="allow",  # Allow extra fields for forward compatibility
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
# Template Models
# ============================================================================


class PlanTemplateResult(StructureBaseModel):
    """Result of plan template creation."""

    created: list[str] = Field(default_factory=list, description="Templates created")
    skipped: list[str] = Field(
        default_factory=list, description="Templates skipped (already exist)"
    )
    errors: list[str] = Field(default_factory=list, description="Errors encountered")


class ProjectSetupQuestionType(str, Enum):
    """Type of project setup question."""

    SELECT = "select"
    MULTISELECT = "multiselect"
    TEXT = "text"
    CONFIRM = "confirm"


class ProjectType(str, Enum):
    """Type of project."""

    UNSPECIFIED = ""
    WEB = "web"
    MOBILE = "mobile"
    BACKEND = "backend"
    LIBRARY = "library"
    CLI = "cli"
    DESKTOP = "desktop"


class TeamSize(str, Enum):
    """Team size category."""

    UNSPECIFIED = ""
    SOLO = "Solo"
    SMALL = "2-5"
    MEDIUM = "6-20"
    LARGE = "21+"


class DevelopmentProcess(str, Enum):
    """Development process."""

    UNSPECIFIED = ""
    AGILE_SCRUM = "Agile/Scrum"
    KANBAN = "Kanban"
    WATERFALL = "Waterfall"
    CONTINUOUS = "Continuous"
    INFORMAL = "Informal"


class ProjectSetupQuestion(StructureBaseModel):
    """Interactive project setup question."""

    id: str = Field(..., description="Question identifier")
    question: str = Field(..., description="Question text")
    type: ProjectSetupQuestionType = Field(..., description="Question type")
    options: list[str] = Field(default_factory=list, description="Options for select")
    default: str | bool | None = Field(None, description="Default value")


class ProjectSetupResult(StructureBaseModel):
    """Result of interactive project setup."""

    questions: list[ProjectSetupQuestion] = Field(
        default_factory=lambda: list[ProjectSetupQuestion](),
        description="Setup questions",
    )


class MemoryBankGenerationResult(StructureBaseModel):
    """Result of memory bank file generation."""

    files_created: list[str] = Field(default_factory=list, description="Files created")
    errors: list[str] = Field(default_factory=list, description="Errors encountered")


# ============================================================================
# Project Info Models (for template_manager and template_renderer)
# ============================================================================


class ProjectInfo(StructureBaseModel):
    """Project information collected from interactive setup.

    This model provides type-safe access to project information
    used in template rendering and file generation.
    """

    model_config = ConfigDict(extra="allow")  # Allow additional fields

    project_name: str = Field(default="", description="Project name")
    project_description: str = Field(default="", description="Project description")
    project_type: ProjectType = Field(
        default=ProjectType.UNSPECIFIED, description="Type of project"
    )
    primary_language: str = Field(
        default="", description="Primary programming language"
    )
    frameworks: str = Field(default="", description="Main frameworks/libraries used")
    team_size: TeamSize = Field(default=TeamSize.UNSPECIFIED, description="Team size")
    development_process: DevelopmentProcess = Field(
        default=DevelopmentProcess.UNSPECIFIED,
        description="Development process",
    )
    use_shared_rules: bool = Field(
        default=False, description="Use shared rules repository"
    )

    def to_template_dict(self) -> dict[str, str]:
        """Convert to dictionary for template substitution.

        Returns:
            Dictionary with string values for template substitution
        """
        return {
            "project_name": self.project_name,
            "project_description": self.project_description,
            "project_type": self.project_type.value,
            "primary_language": self.primary_language,
            "frameworks": self.frameworks,
            "team_size": self.team_size.value,
            "development_process": self.development_process.value,
            "use_shared_rules": str(self.use_shared_rules),
        }


class InteractiveSetupQuestionType(str, Enum):
    """Type of interactive setup question."""

    TEXT = "text"
    CHOICE = "choice"
    BOOLEAN = "boolean"


class InteractiveSetupQuestion(StructureBaseModel):
    """Question for interactive project setup.

    More flexible than ProjectSetupQuestion for various question types.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Question identifier")
    question: str = Field(..., description="Question text")
    type: InteractiveSetupQuestionType = Field(..., description="Question type")
    options: list[str] = Field(
        default_factory=list, description="Options for choice type"
    )


class InteractiveSetupResult(StructureBaseModel):
    """Result of interactive setup returning questions to ask."""

    questions: list[InteractiveSetupQuestion] = Field(
        default_factory=lambda: list[InteractiveSetupQuestion](),
        description="Questions to ask user",
    )


class InitialFilesResult(StructureBaseModel):
    """Result of generating initial memory bank files."""

    generated: list[str] = Field(default_factory=list, description="Files generated")
    errors: list[str] = Field(default_factory=list, description="Errors encountered")


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
