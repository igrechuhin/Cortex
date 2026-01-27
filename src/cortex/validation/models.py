"""
Pydantic models for validation module return types.

These models are used by validation/* modules to return structured data.
They are separate from tools/models.py which defines MCP tool return types.
"""

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from cortex.core.constants import (
    DEFAULT_TOKEN_BUDGET,
    MIN_SECTION_LENGTH_CHARS,
    QUALITY_WEIGHT_COMPLETENESS,
    QUALITY_WEIGHT_CONSISTENCY,
    QUALITY_WEIGHT_EFFICIENCY,
    QUALITY_WEIGHT_FRESHNESS,
    QUALITY_WEIGHT_STRUCTURE,
    SIMILARITY_THRESHOLD_DUPLICATE,
)
from cortex.core.models import DictLikeModel, JsonValue, ModelDict

# ============================================================================
# Validation Config Models (from validation_config.py)
# ============================================================================


class TokenBudgetConfigModel(BaseModel):
    """Token budget configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_total_tokens: int = Field(
        default=DEFAULT_TOKEN_BUDGET, ge=1, description="Maximum total tokens allowed"
    )
    warn_at_percentage: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Warning threshold percentage (0-100)",
    )
    per_file_max: int = Field(
        default=15000, ge=1, description="Maximum tokens per file"
    )
    per_file_warn: int = Field(
        default=12000, ge=1, description="Warning threshold per file"
    )


class DuplicationConfigModel(BaseModel):
    """Duplication detection configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = Field(
        default=True, description="Whether duplication detection is enabled"
    )
    threshold: float = Field(
        default=SIMILARITY_THRESHOLD_DUPLICATE,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for duplicate detection (0.0-1.0)",
    )
    min_length: int = Field(
        default=MIN_SECTION_LENGTH_CHARS,
        ge=0,
        description="Minimum section length in characters",
    )
    suggest_transclusion: bool = Field(
        default=True, description="Whether to suggest transclusion for duplicates"
    )


class FileSchemaModel(BaseModel):
    """Schema definition for a single Memory Bank file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    required_sections: list[str] = Field(
        default_factory=list, description="Required sections for the file"
    )
    recommended_sections: list[str] = Field(
        default_factory=list, description="Recommended sections for the file"
    )
    heading_level: int = Field(
        default=2, ge=1, le=6, description="Expected heading level"
    )
    max_nesting: int = Field(default=3, ge=1, le=6, description="Maximum nesting depth")


class SchemasConfigModel(BaseModel):
    """Schema validation configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enforce_required_sections: bool = Field(
        default=True, description="Whether to enforce required sections"
    )
    enforce_section_order: bool = Field(
        default=False, description="Whether to enforce section order"
    )
    custom_schemas: dict[str, list[str]] = Field(
        default_factory=dict, description="Custom schema definitions by file name"
    )


class QualityWeightsModel(BaseModel):
    """Quality score weight configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    completeness: float = Field(
        default=QUALITY_WEIGHT_COMPLETENESS,
        ge=0.0,
        le=1.0,
        description="Weight for completeness (0.0-1.0)",
    )
    consistency: float = Field(
        default=QUALITY_WEIGHT_CONSISTENCY,
        ge=0.0,
        le=1.0,
        description="Weight for consistency (0.0-1.0)",
    )
    freshness: float = Field(
        default=QUALITY_WEIGHT_FRESHNESS,
        ge=0.0,
        le=1.0,
        description="Weight for freshness (0.0-1.0)",
    )
    structure: float = Field(
        default=QUALITY_WEIGHT_STRUCTURE,
        ge=0.0,
        le=1.0,
        description="Weight for structure (0.0-1.0)",
    )
    token_efficiency: float = Field(
        default=QUALITY_WEIGHT_EFFICIENCY,
        ge=0.0,
        le=1.0,
        description="Weight for token efficiency (0.0-1.0)",
    )


class QualityConfigModel(BaseModel):
    """Quality metrics configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    minimum_score: float = Field(
        default=70.0, ge=0.0, le=100.0, description="Minimum acceptable quality score"
    )
    fail_below: float = Field(
        default=50.0, ge=0.0, le=100.0, description="Score below which validation fails"
    )
    weights: QualityWeightsModel = Field(
        default_factory=QualityWeightsModel, description="Quality score weights"
    )


# ============================================================================
# Infrastructure Validator Models
# ============================================================================


class JobStepModel(BaseModel):
    """A single step in a CI/CD job configuration.

    This model replaces `ModelDict` for job step definitions.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str = Field(..., description="Step name")
    run: str | None = Field(default=None, description="Command to run")
    uses: str | None = Field(default=None, description="Action to use")


class JobConfigModel(BaseModel):
    """CI/CD job configuration.

    This model replaces `ModelDict` for job configuration.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    name: str | None = Field(default=None, description="Job name")
    steps: list[JobStepModel] = Field(
        default_factory=lambda: list[JobStepModel](),
        description="Job steps",
    )

    @classmethod
    def from_dict(cls, data: ModelDict) -> "JobConfigModel":
        """Create JobConfigModel from a dictionary.

        Args:
            data: Dictionary with job configuration

        Returns:
            JobConfigModel instance
        """
        steps_data_raw = data.get("steps", [])
        steps_data: list[JsonValue] = (
            cast(list[JsonValue], steps_data_raw)
            if isinstance(steps_data_raw, list)
            else []
        )
        steps = [
            JobStepModel.model_validate(step)
            for step in steps_data
            if isinstance(step, dict)
        ]
        return cls.model_validate({**data, "steps": steps})


class ValidationConfigModel(BaseModel):
    """Complete validation configuration."""

    # NOTE: Allow extra keys so users/tests can store experimental settings.
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    enabled: str | StrictBool = Field(
        default=True,
        description=(
            "Whether validation is enabled (may be invalid when loaded "
            "from user config)"
        ),
    )
    auto_validate_on_write: bool = Field(
        default=True, description="Whether to auto-validate on write"
    )
    strict_mode: bool = Field(
        default=False, description="Whether to use strict validation mode"
    )
    token_budget: TokenBudgetConfigModel = Field(
        default_factory=TokenBudgetConfigModel, description="Token budget configuration"
    )
    duplication: DuplicationConfigModel = Field(
        default_factory=DuplicationConfigModel,
        description="Duplication detection configuration",
    )
    schemas: SchemasConfigModel = Field(
        default_factory=SchemasConfigModel,
        description="Schema validation configuration",
    )
    quality: QualityConfigModel = Field(
        default_factory=QualityConfigModel, description="Quality metrics configuration"
    )


# ============================================================================
# File Metadata Models (for quality_metrics.py parameters)
# ============================================================================


class FileMetadataForQuality(BaseModel):
    """File metadata used in quality calculations."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    last_modified: str | None = Field(
        default=None, description="ISO timestamp of last modification"
    )
    token_count: int = Field(default=0, ge=0, description="Token count")
    size_bytes: int = Field(default=0, ge=0, description="File size in bytes")
    read_count: int = Field(default=0, ge=0, description="Number of reads")
    write_count: int = Field(default=0, ge=0, description="Number of writes")


class DuplicateEntryData(BaseModel):
    """Duplicate entry data structure."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    file: str = Field(default="", description="File name")
    section: str = Field(default="", description="Section name")
    content: str = Field(default="", description="Content")


class DuplicationDataModel(BaseModel):
    """Duplication scan result data for quality calculations."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    duplicates_found: int = Field(
        default=0, ge=0, description="Number of duplicates found"
    )
    exact_duplicates: list[DuplicateEntryData] = Field(
        default_factory=lambda: list[DuplicateEntryData](),
        description="Exact duplicate entries",
    )
    similar_content: list[DuplicateEntryData] = Field(
        default_factory=lambda: list[DuplicateEntryData](),
        description="Similar content entries",
    )


class LinkValidationErrorData(BaseModel):
    """Link validation error data structure."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    file: str = Field(default="", description="File name")
    target: str = Field(default="", description="Link target")
    error: str = Field(default="", description="Error message")


class LinkValidationDataModel(BaseModel):
    """Link validation result data for quality calculations."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    validation_errors: list[LinkValidationErrorData] = Field(
        default_factory=lambda: list[LinkValidationErrorData](),
        description="Validation errors",
    )
    validation_warnings: list[LinkValidationErrorData] = Field(
        default_factory=lambda: list[LinkValidationErrorData](),
        description="Validation warnings",
    )
    broken_links: int = Field(default=0, ge=0, description="Number of broken links")


# ============================================================================
# Duplication Detector Models
# ============================================================================


class SectionEntry(BaseModel):
    """Section entry for duplication detection."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(..., description="File name")
    section: str = Field(..., description="Section name")
    content_hash: str = Field(..., description="Content hash")


class HashMapEntry(BaseModel):
    """Entry in the hash map for duplicate detection."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(..., description="File name")
    section: str = Field(..., description="Section name")
    content: str = Field(..., description="Section content")


class ValidationError(BaseModel):
    """Validation error structure."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    type: str = Field(description="Error type identifier")
    severity: Literal["error", "warning", "info"] = Field(
        description="Error severity level"
    )
    message: str = Field(description="Error message")
    suggestion: str | None = Field(default=None, description="Suggested fix")


class ValidationResult(BaseModel):
    """Result of file validation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    valid: bool = Field(description="Whether validation passed")
    errors: list[ValidationError] = Field(
        default_factory=lambda: list[ValidationError](), description="Validation errors"
    )
    warnings: list[ValidationError] = Field(
        default_factory=lambda: list[ValidationError](),
        description="Validation warnings",
    )
    score: int = Field(ge=0, le=100, description="Validation score 0-100")


class DuplicateEntry(DictLikeModel):
    """Duplicate content entry."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file1: str = Field(description="First file name")
    section1: str = Field(description="First section name")
    file2: str = Field(description="Second file name")
    section2: str = Field(description="Second section name")
    similarity: float = Field(ge=0.0, le=1.0, description="Similarity score 0.0-1.0")
    type: str = Field(description="Duplicate type (exact or similar)")
    suggestion: str = Field(description="Refactoring suggestion")


class DuplicationScanResult(DictLikeModel):
    """Result of duplication scan across files."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    duplicates_found: int = Field(ge=0, description="Total number of duplicates found")
    exact_duplicates: list[DuplicateEntry] = Field(
        default_factory=lambda: list[DuplicateEntry](),
        description="Exact duplicate entries",
    )
    similar_content: list[DuplicateEntry] = Field(
        default_factory=lambda: list[DuplicateEntry](),
        description="Similar content entries",
    )


class CategoryBreakdown(BaseModel):
    """Quality score category breakdown."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    completeness: int = Field(ge=0, le=100, description="Completeness score")
    consistency: int = Field(ge=0, le=100, description="Consistency score")
    freshness: int = Field(ge=0, le=100, description="Freshness score")
    structure: int = Field(ge=0, le=100, description="Structure score")
    token_efficiency: int = Field(ge=0, le=100, description="Token efficiency score")


class QualityScoreResult(BaseModel):
    """Overall Memory Bank quality score result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    overall_score: int = Field(ge=0, le=100, description="Overall quality score")
    breakdown: CategoryBreakdown = Field(description="Score breakdown by category")
    grade: Literal["A", "B", "C", "D", "F"] = Field(description="Letter grade")
    status: Literal["healthy", "warning", "critical"] = Field(
        description="Health status"
    )
    issues: list[str] = Field(default_factory=list, description="Identified issues")
    recommendations: list[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )


class FileQualityScore(BaseModel):
    """Quality score for individual file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file_name: str = Field(description="File name")
    score: int = Field(ge=0, le=100, description="File quality score")
    grade: Literal["A", "B", "C", "D", "F"] = Field(description="Letter grade")
    validation: ValidationResult = Field(description="Validation results")
    freshness: int = Field(ge=0, le=100, description="Freshness score")
    structure: int = Field(ge=0, le=100, description="Structure score")


# ============================================================================
# Roadmap Sync Models (from roadmap_sync.py)
# ============================================================================


class TodoItemModel(BaseModel):
    """Represents a TODO item found in the codebase."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file_path: str = Field(description="File path containing TODO")
    line: int = Field(ge=1, description="Line number")
    snippet: str = Field(description="Code snippet")
    category: str = Field(description="TODO category")


class RoadmapReferenceModel(BaseModel):
    """Represents a file reference found in the roadmap."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file_path: str = Field(description="Referenced file path")
    line: int | None = Field(None, ge=1, description="Line number if specified")
    context: str = Field(description="Context of reference")
    phase: str | None = Field(None, description="Phase if specified")


class SyncValidationResultModel(BaseModel):
    """Result of roadmap synchronization validation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    valid: bool = Field(description="Whether sync is valid")
    missing_roadmap_entries: list[TodoItemModel] = Field(
        default_factory=lambda: list[TodoItemModel](),
        description="TODOs missing from roadmap",
    )
    invalid_references: list[RoadmapReferenceModel] = Field(
        default_factory=lambda: list[RoadmapReferenceModel](),
        description="Invalid roadmap references",
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings")


# ============================================================================
# Infrastructure Validator Models (from infrastructure_validator.py)
# ============================================================================


class InfrastructureIssueModel(BaseModel):
    """Infrastructure validation issue."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    type: str = Field(description="Issue type")
    severity: Literal["high", "medium", "low"] = Field(description="Issue severity")
    description: str = Field(description="Issue description")
    location: str = Field(description="Issue location")
    suggestion: str = Field(description="Suggested fix")
    ci_check: str | None = Field(None, description="Related CI check")
    missing_in_commit: bool = Field(description="Whether missing in commit prompt")


class InfrastructureValidationResultModel(BaseModel):
    """Infrastructure validation result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: Literal["success", "error"] = Field(description="Validation status")
    check_type: Literal["infrastructure"] = Field(description="Type of check")
    checks_performed: dict[str, bool] = Field(
        default_factory=lambda: dict[str, bool](),
        description="Checks performed and results",
    )
    issues_found: list[InfrastructureIssueModel] = Field(
        default_factory=lambda: list[InfrastructureIssueModel](),
        description="Issues found",
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )


# ============================================================================
# Timestamp Validator Models (from timestamp_validator.py)
# ============================================================================


class TimestampViolationModel(BaseModel):
    """Timestamp format violation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    line: int = Field(..., ge=1, description="Line number")
    content: str = Field(..., description="Line content (truncated)")
    timestamp: str = Field(..., description="Timestamp found")
    issue: str = Field(..., description="Issue description")


class TimestampScanResult(BaseModel):
    """Result of scanning content for timestamps."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    valid_count: int = Field(..., ge=0, description="Number of valid timestamps")
    invalid_format_count: int = Field(
        ..., ge=0, description="Number of invalid format timestamps"
    )
    invalid_with_time_count: int = Field(
        ..., ge=0, description="Number of timestamps with time components"
    )
    violations: list[TimestampViolationModel] = Field(
        default_factory=lambda: list[TimestampViolationModel](),
        description="Violation details (limited to 20)",
    )


class FileTimestampResultModel(BaseModel):
    """Timestamp validation result for a single file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    valid_count: int = Field(..., ge=0, description="Number of valid timestamps")
    invalid_format_count: int = Field(
        ..., ge=0, description="Number of invalid format timestamps"
    )
    invalid_with_time_count: int = Field(
        ..., ge=0, description="Number of timestamps with time components"
    )
    violations: list[TimestampViolationModel] = Field(
        default_factory=lambda: list[TimestampViolationModel](),
        description="Violation details",
    )
    valid: bool = Field(..., description="Whether file passes validation")


class SingleFileTimestampResult(BaseModel):
    """Result of timestamp validation for a single file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: Literal["success", "error"] = Field(..., description="Operation status")
    check_type: Literal["timestamps"] = Field(
        default="timestamps", description="Type of check"
    )
    file_name: str | None = Field(default=None, description="File name validated")
    valid_count: int = Field(default=0, ge=0, description="Number of valid timestamps")
    invalid_format_count: int = Field(
        default=0, ge=0, description="Number of invalid format timestamps"
    )
    invalid_with_time_count: int = Field(
        default=0, ge=0, description="Number of timestamps with time components"
    )
    violations: list[TimestampViolationModel] = Field(
        default_factory=lambda: list[TimestampViolationModel](),
        description="Violation details",
    )
    valid: bool = Field(default=True, description="Whether validation passed")
    error: str | None = Field(default=None, description="Error message if status=error")


class AllFilesTimestampResult(BaseModel):
    """Result of timestamp validation for all files."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: Literal["success"] = Field(
        default="success", description="Operation status"
    )
    check_type: Literal["timestamps"] = Field(
        default="timestamps", description="Type of check"
    )
    total_valid: int = Field(..., ge=0, description="Total valid timestamps")
    total_invalid_format: int = Field(
        ..., ge=0, description="Total invalid format timestamps"
    )
    total_invalid_with_time: int = Field(
        ..., ge=0, description="Total timestamps with time components"
    )
    files_valid: bool = Field(..., description="Whether all files pass validation")
    results: dict[str, FileTimestampResultModel] = Field(
        default_factory=dict, description="Results by file name"
    )
    valid: bool = Field(..., description="Whether overall validation passed")


# ============================================================================
# Duplication Fix Models (for validation_helpers.py)
# ============================================================================


class TransclusionFix(BaseModel):
    """Transclusion fix suggestion for duplicated files."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    files: list[str] = Field(
        ..., min_length=2, description="List of files with duplicate content"
    )
    suggestion: str = Field(
        ...,
        description="Suggestion text for using transclusion",
    )
    steps: list[str] = Field(
        ...,
        min_length=1,
        description="Step-by-step instructions for applying the fix",
    )
