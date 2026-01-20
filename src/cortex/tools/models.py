"""
Pydantic Models for MCP Tool Return Types

This module defines Pydantic models for all Cortex MCP tool return types,
enabling FastMCP 2.0 structured output with better schema generation,
automatic validation, and improved IDE support.

All models follow Pydantic v2 best practices:
- Use `model_config` instead of `class Config` (Pydantic v2 style)
- `extra="forbid"` to prevent extra fields and catch typos
- `validate_assignment=True` for validation on attribute assignment
- Field constraints (ge, le, min_length, etc.) for data validation
- Comprehensive Field descriptions for API documentation
- Base class with shared configuration (ToolResultBase)
- Operation-specific models for different tool behaviors
- Optional fields with None defaults for conditional responses

Design principles:
- Single responsibility: Each model represents one domain concept
- Type precision: Use concrete types (list[str], dict[str, int]) over generics
- Validation: Leverage Field() constraints for business rules
- Documentation: All fields have descriptions for schema generation
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import HealthMetrics, IndexStats

# Re-export ManagersDict from managers.types for backward compatibility
from cortex.managers.types import ManagersDict
from cortex.refactoring.models import RefactoringImpactMetrics
from cortex.validation.models import (
    AllFilesTimestampResult,
    InfrastructureValidationResultModel,
    SingleFileTimestampResult,
)

__all__ = ["ManagersDict"]


# ConfigValue type for configuration values - supports primitive and nested structures.
# This type union is designed to support the dynamic nature of configuration systems
# while maintaining some type safety. The configuration system (validation, optimization,
# adaptation) stores structured data that may have arbitrarily nested structures.
#
# Accepted value types:
# - Primitives: str, int, float, bool, None
# - Lists of primitives: list[str], list[int], list[float]
# - Nested string-keyed dicts with primitive or dict values
#
# Note: This is one of the few acceptable uses of dynamic dict types
# in the codebase because configuration data is inherently dynamic and
# can have arbitrarily nested structures (e.g., schemas.custom_schemas,
# quality.weights).
#
# ConfigValue uses `object` for dict values because:
# 1. Configuration data can be arbitrarily nested (dict within dict within dict)
# 2. Python's type system doesn't support true recursive type aliases
# 3. Pydantic Union type matching fails for nested dicts with specific types
# 4. This is a serialization boundary where `object` is acceptable
ConfigValuePrimitive = str | int | float | bool | None
ConfigValueList = list[str] | list[int] | list[float] | list[bool]
ConfigValueDict = dict[str, object]  # Supports arbitrary nesting
ConfigValue = ConfigValuePrimitive | ConfigValueList | ConfigValueDict


# ============================================================================
# Base Models
# ============================================================================


class StrictBaseModel(BaseModel):
    """Strict base model with maximum Pydantic validation.

    All models should inherit from this or ToolResultBase to ensure:
    - No extra fields allowed (extra = "forbid")
    - Validation on assignment (validate_assignment = True)
    - Validation of default values (validate_default = True)
    - Strict type checking (strict = True)
    """

    model_config = ConfigDict(
        # Prevent extra fields to catch typos and enforce strict contracts
        extra="forbid",
        # Validate when attributes are set after model creation
        validate_assignment=True,
        # Validate default values
        validate_default=True,
        # Strict mode for maximum validation
        strict=True,
    )


class ToolResultBase(StrictBaseModel):
    """Base class for all tool results with common status and error handling.

    This base model enforces:
    - No extra fields allowed (extra = "forbid")
    - Validation on assignment (validate_assignment = True)
    - Validation of default values (validate_default = True)
    - Strict type checking (strict = True)
    - Enum values used directly (use_enum_values = True)
    """

    status: Literal["success", "error", "warning"] = Field(
        ..., description="Operation status"
    )

    model_config = ConfigDict(
        # Prevent extra fields to catch typos and enforce strict contracts
        extra="forbid",
        # Validate when attributes are set after model creation
        validate_assignment=True,
        # Validate default values
        validate_default=True,
        # Use enum values instead of names for serialization
        use_enum_values=True,
        # Strict mode for maximum validation
        strict=True,
        # Enable JSON serialization
        json_schema_extra={
            "examples": [
                {"status": "success"},
                {"status": "error", "error": "Operation failed"},
            ]
        },
    )


class ErrorResultBase(ToolResultBase):
    """Base class for error responses."""

    status: Literal["error"] = Field(default="error")  # type: ignore[assignment]
    error: str = Field(..., min_length=1, description="Error message")
    error_type: str | None = Field(
        default=None, description="Type/class name of the error"
    )


# ============================================================================
# File Operations Models (manage_file)
# ============================================================================


class FileMetadataSection(StrictBaseModel):
    """Section information in file metadata."""

    heading: str = Field(..., min_length=1, description="Section heading text")
    level: int = Field(..., ge=1, description="Heading level (1-6)")


class FileVersionEntry(StrictBaseModel):
    """Version history entry."""

    version: int = Field(..., ge=1, description="Version number (1-based)")
    timestamp: str = Field(..., min_length=1, description="ISO timestamp")
    change_type: str | None = Field(None, description="Type of change")
    change_description: str | None = Field(None, description="Description of change")
    size_bytes: int | None = Field(None, ge=0, description="File size in bytes")
    token_count: int | None = Field(None, ge=0, description="Token count")


class FileMetrics(StrictBaseModel):
    """Computed metrics for a file (size, tokens, hash)."""

    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    token_count: int = Field(..., ge=0, description="Token count")
    content_hash: str = Field(..., min_length=1, description="Content hash")


class FileMetadata(StrictBaseModel):
    """File metadata structure."""

    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    token_count: int = Field(..., ge=0, description="Token count")
    content_hash: str = Field(..., min_length=1, description="Content hash")
    sections: list[FileMetadataSection] = Field(
        default_factory=lambda: list[FileMetadataSection](),
        description="File sections with headings",
    )
    version_history: list[FileVersionEntry] = Field(
        default_factory=lambda: list[FileVersionEntry](),
        description="Version history entries",
    )


class ManageFileReadResult(ToolResultBase):
    """Result of manage_file read operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    file_name: str = Field(..., min_length=1, description="Name of the file")
    content: str = Field(..., description="File content")
    metadata: FileMetadata | None = Field(None, description="Optional file metadata")


class ManageFileWriteResult(ToolResultBase):
    """Result of manage_file write operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    file_name: str = Field(..., min_length=1, description="Name of the file")
    message: str = Field(..., min_length=1, description="Operation message")
    snapshot_id: str | None = Field(None, description="Snapshot ID if created")
    version: int | None = Field(None, ge=1, description="File version number")
    tokens: int | None = Field(None, ge=0, description="Token count")


class ManageFileMetadataResult(ToolResultBase):
    """Result of manage_file metadata operation."""

    status: Literal["success", "warning"] = Field(default="success")  # type: ignore[assignment]
    file_name: str
    metadata: FileMetadata | None = None
    message: str | None = None  # Only for warning status


class ManageFileErrorResult(ErrorResultBase):
    """Error result for manage_file operations."""

    file_name: str | None = None
    available_files: list[str] = Field(default_factory=list)
    suggestion: str | None = None
    valid_operations: list[str] = Field(default_factory=list)


# Union type for manage_file return (handled by operation type)
ManageFileResult = (
    ManageFileReadResult
    | ManageFileWriteResult
    | ManageFileMetadataResult
    | ManageFileErrorResult
)


# ============================================================================
# Validation Models (validate)
# ============================================================================


class SchemaValidationError(StrictBaseModel):
    """Schema validation error entry."""

    message: str
    line: int | None = None
    column: int | None = None


class SchemaValidationWarning(StrictBaseModel):
    """Schema validation warning entry."""

    message: str
    line: int | None = None
    column: int | None = None


class SchemaValidationResult(StrictBaseModel):
    """Schema validation result for a single file."""

    valid: bool
    errors: list[SchemaValidationError] = Field(
        default_factory=lambda: list[SchemaValidationError]()
    )
    warnings: list[SchemaValidationWarning] = Field(
        default_factory=lambda: list[SchemaValidationWarning]()
    )


class ValidateSchemaSingleResult(ToolResultBase):
    """Result of validate schema check for single file."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    check_type: Literal["schema"] = "schema"
    file_name: str
    validation: SchemaValidationResult


class ValidateSchemaAllResult(ToolResultBase):
    """Result of validate schema check for all files."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    check_type: Literal["schema"] = "schema"
    results: dict[str, SchemaValidationResult]


class DuplicateLocation(StrictBaseModel):
    """Location of duplicate content."""

    file: str
    line: int


class ExactDuplicate(StrictBaseModel):
    """Exact duplicate content entry."""

    content: str
    files: list[str]
    locations: list[DuplicateLocation] = Field(
        default_factory=lambda: list[DuplicateLocation]()
    )


class SimilarContent(StrictBaseModel):
    """Similar content entry."""

    similarity: float
    files: list[str]
    content_preview: str


class DuplicationFixSuggestion(StrictBaseModel):
    """Fix suggestion for duplication."""

    files: list[str]
    suggestion: str
    steps: list[str] = Field(default_factory=list)


class ValidateDuplicationsResult(ToolResultBase):
    """Result of validate duplications check."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    check_type: Literal["duplications"] = "duplications"
    threshold: float
    duplicates_found: int
    exact_duplicates: list[ExactDuplicate] = Field(
        default_factory=lambda: list[ExactDuplicate]()
    )
    similar_content: list[SimilarContent] = Field(
        default_factory=lambda: list[SimilarContent]()
    )
    suggested_fixes: list[DuplicationFixSuggestion] = Field(
        default_factory=lambda: list[DuplicationFixSuggestion]()
    )


class QualityScore(StrictBaseModel):
    """Quality score breakdown."""

    overall: float
    completeness: float | None = None
    structure: float | None = None
    content_quality: float | None = None
    issues: list[str] = Field(default_factory=list)


class ValidateQualitySingleResult(ToolResultBase):
    """Result of validate quality check for single file."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    check_type: Literal["quality"] = "quality"
    file_name: str
    score: QualityScore


class QualityMetricsBreakdown(StrictBaseModel):
    """Quality metrics breakdown for all files validation."""

    completeness: float = Field(default=0.0, ge=0.0, le=100.0)
    consistency: float = Field(default=0.0, ge=0.0, le=100.0)
    freshness: float = Field(default=0.0, ge=0.0, le=100.0)
    structure: float = Field(default=0.0, ge=0.0, le=100.0)
    token_efficiency: float = Field(default=0.0, ge=0.0, le=100.0)
    grade: str = Field(default="")
    issues_count: int = Field(default=0, ge=0)
    recommendations_count: int = Field(default=0, ge=0)


class ValidateQualityAllResult(ToolResultBase):
    """Result of validate quality check for all files."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    check_type: Literal["quality"] = "quality"
    overall_score: float
    health_status: Literal["healthy", "good", "fair", "warning", "critical"]
    file_scores: dict[str, float]
    metrics: QualityMetricsBreakdown = Field(default_factory=QualityMetricsBreakdown)


class InfrastructureIssue(StrictBaseModel):
    """Infrastructure validation issue."""

    type: str
    severity: Literal["high", "medium", "low"]
    description: str
    location: str | None = None
    suggestion: str | None = None
    ci_check: str | None = None
    missing_in_commit: bool | None = None


class ValidateInfrastructureResult(ToolResultBase):
    """Result of validate infrastructure check."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    check_type: Literal["infrastructure"] = "infrastructure"
    checks_performed: dict[str, bool] = Field(default_factory=dict)
    issues_found: list[InfrastructureIssue] = Field(
        default_factory=lambda: list[InfrastructureIssue]()
    )
    recommendations: list[str] = Field(default_factory=list)


class TimestampViolation(StrictBaseModel):
    """Timestamp format violation."""

    line: int
    content: str
    timestamp: str
    issue: str


class FileTimestampResult(StrictBaseModel):
    """Timestamp validation result for a single file."""

    valid_count: int
    invalid_format_count: int
    invalid_with_time_count: int
    violations: list[TimestampViolation] = Field(
        default_factory=lambda: list[TimestampViolation]()
    )
    valid: bool


class ValidateTimestampsResult(ToolResultBase):
    """Result of validate timestamps check."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    check_type: Literal["timestamps"] = "timestamps"
    total_valid: int
    total_invalid_format: int
    total_invalid_with_time: int
    files_valid: bool
    results: dict[str, FileTimestampResult] = Field(default_factory=dict)
    valid: bool


class RoadmapEntry(StrictBaseModel):
    """Missing roadmap entry."""

    file_path: str
    line: int
    snippet: str
    category: str


class InvalidReference(StrictBaseModel):
    """Invalid roadmap reference."""

    file_path: str
    line: int
    context: str
    phase: str


class RoadmapSyncSummary(StrictBaseModel):
    """Roadmap sync validation summary."""

    total_todos_found: int
    missing_entries_count: int
    invalid_references_count: int
    warnings_count: int


class ValidateRoadmapSyncResult(ToolResultBase):
    """Result of validate roadmap_sync check."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    check_type: Literal["roadmap_sync"] = "roadmap_sync"
    valid: bool
    missing_roadmap_entries: list[RoadmapEntry] = Field(
        default_factory=lambda: list[RoadmapEntry]()
    )
    invalid_references: list[InvalidReference] = Field(
        default_factory=lambda: list[InvalidReference]()
    )
    warnings: list[str] = Field(default_factory=list)
    summary: RoadmapSyncSummary


class ValidateErrorResult(ErrorResultBase):
    """Error result for validate operations."""

    check_type: str | None = None
    file_name: str | None = None


# Union type for validate return (handled by check_type)
# Includes both tools/models.py types and validation/models.py types
ValidateResult = (
    ValidateSchemaSingleResult
    | ValidateSchemaAllResult
    | ValidateDuplicationsResult
    | ValidateQualitySingleResult
    | ValidateQualityAllResult
    | ValidateInfrastructureResult
    | ValidateTimestampsResult
    | ValidateRoadmapSyncResult
    | ValidateErrorResult
    # Validation module models (used by validation handlers)
    | SingleFileTimestampResult
    | AllFilesTimestampResult
    | InfrastructureValidationResultModel
)


# ============================================================================
# Analysis Models (analyze)
# ============================================================================


class CoAccessPatternEntry(StrictBaseModel):
    """Co-access pattern between files."""

    files: list[str] = Field(..., description="Files accessed together")
    co_access_count: int = Field(
        ..., ge=0, description="Number of co-access occurrences"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class AccessFrequencyData(StrictBaseModel):
    """Access frequency data for a file."""

    read_count: int = Field(default=0, ge=0)
    write_count: int = Field(default=0, ge=0)
    frequency: float = Field(default=0.0, ge=0.0)
    last_access: str | None = None


class TaskPatternData(StrictBaseModel):
    """Task pattern data entry."""

    task_id: str
    description: str
    file_count: int = Field(default=0, ge=0)
    files: list[str] = Field(default_factory=list)
    timestamp: str


class UnusedFileData(StrictBaseModel):
    """Unused file information."""

    file_name: str
    days_since_access: int = Field(default=0, ge=0)
    last_access: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    recommendation: str | None = None


class AccessFrequencyPattern(StrictBaseModel):
    """Access frequency pattern data."""

    access_frequency: dict[str, AccessFrequencyData] = Field(default_factory=dict)
    co_access_patterns: list[CoAccessPatternEntry] = Field(
        default_factory=lambda: list[CoAccessPatternEntry]()
    )
    task_patterns: list[TaskPatternData] = Field(
        default_factory=lambda: list[TaskPatternData]()
    )
    unused_files: list[UnusedFileData] = Field(
        default_factory=lambda: list[UnusedFileData]()
    )


class AntiPattern(StrictBaseModel):
    """Anti-pattern detection result."""

    type: str
    path: str
    severity: Literal["high", "medium", "low"]
    recommendation: str
    size_tokens: int | None = None


class OrganizationMetrics(StrictBaseModel):
    """Organization metrics."""

    total_files: int
    total_directories: int
    max_depth: int
    avg_files_per_directory: float


class ComplexityMetrics(StrictBaseModel):
    """Complexity metrics."""

    avg_directory_depth: float = Field(
        ..., ge=0.0, description="Average directory depth"
    )
    max_dependencies: int = Field(
        ..., ge=0, description="Maximum number of dependencies"
    )
    circular_dependencies: list[str] = Field(
        default_factory=list,
        description="List of files involved in circular dependencies",
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class StructureAnalysis(StrictBaseModel):
    """Structure analysis result."""

    organization: OrganizationMetrics
    anti_patterns: list[AntiPattern] = Field(
        default_factory=lambda: list[AntiPattern]()
    )
    complexity_metrics: ComplexityMetrics


class InsightEntry(StrictBaseModel):
    """Individual insight entry."""

    category: str
    description: str
    impact_score: float
    recommendation: str
    affected_files: list[str] = Field(default_factory=list)


class InsightsData(StrictBaseModel):
    """Insights data structure."""

    high_impact: list[InsightEntry] = Field(
        default_factory=lambda: list[InsightEntry](),
        description="High impact insights",
    )
    medium_impact: list[InsightEntry] = Field(
        default_factory=lambda: list[InsightEntry](),
        description="Medium impact insights",
    )
    low_impact: list[InsightEntry] = Field(
        default_factory=lambda: list[InsightEntry](),
        description="Low impact insights",
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class AnalyzeUsagePatternsResult(ToolResultBase):
    """Result of analyze usage_patterns target."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    target: Literal["usage_patterns"] = "usage_patterns"
    time_window_days: int
    patterns: AccessFrequencyPattern


class AnalyzeStructureResult(ToolResultBase):
    """Result of analyze structure target."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    target: Literal["structure"] = "structure"
    analysis: StructureAnalysis


class AnalyzeInsightsResult(ToolResultBase):
    """Result of analyze insights target."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    target: Literal["insights"] = "insights"
    format: str
    insights: (
        InsightsData | str
    )  # Structured data for JSON, formatted string for markdown/text


class AnalyzeErrorResult(ErrorResultBase):
    """Error result for analyze operations."""

    target: str | None = None


# Union type for analyze return (handled by target)
AnalyzeResult = (
    AnalyzeUsagePatternsResult
    | AnalyzeStructureResult
    | AnalyzeInsightsResult
    | AnalyzeErrorResult
)


# ============================================================================
# Refactoring Models (suggest_refactoring)
# ============================================================================


class ConsolidationOpportunity(StrictBaseModel):
    """Consolidation opportunity."""

    id: str
    files: list[str]
    similarity: float
    shared_content_tokens: int
    potential_savings_tokens: int
    recommendation: str
    suggested_transclusion: str
    confidence: str


class SuggestRefactoringConsolidationResult(ToolResultBase):
    """Result of suggest_refactoring consolidation type."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    type: Literal["consolidation"] = "consolidation"
    min_similarity: float
    opportunities: list[ConsolidationOpportunity] = Field(
        default_factory=lambda: list[ConsolidationOpportunity]()
    )


class SuggestedSplit(StrictBaseModel):
    """Suggested file split."""

    name: str
    sections: list[str] = Field(default_factory=list)
    estimated_tokens: int


class SplitImpact(StrictBaseModel):
    """Impact of splitting a file."""

    improved_context_loading: bool
    reduced_cognitive_load: bool
    better_organization: bool


class SplitRecommendation(StrictBaseModel):
    """Split recommendation entry."""

    id: str
    file: str
    current_size_tokens: int
    current_size_bytes: int
    reason: str
    suggested_splits: list[SuggestedSplit] = Field(
        default_factory=lambda: list[SuggestedSplit]()
    )
    confidence: str
    impact: SplitImpact


class SuggestRefactoringSplitsResult(ToolResultBase):
    """Result of suggest_refactoring splits type."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    type: Literal["splits"] = "splits"
    size_threshold: int
    recommendations: list[SplitRecommendation] = Field(
        default_factory=lambda: list[SplitRecommendation]()
    )


class FileMove(StrictBaseModel):
    """File move suggestion."""

    from_path: str = Field(alias="from", description="Source file path")
    to_path: str = Field(alias="to", description="Destination file path")
    reason: str = Field(..., description="Reason for the move")

    model_config = ConfigDict(
        # Allow both alias and field name for serialization
        populate_by_name=True,
        # Prevent extra fields
        extra="forbid",
        # Validate on assignment
        validate_assignment=True,
    )


class CurrentState(StrictBaseModel):
    """Current state metrics."""

    max_depth: int
    total_files: int
    total_directories: int


class ProposedState(StrictBaseModel):
    """Proposed state metrics."""

    max_depth: int
    total_files: int
    total_directories: int


class NewStructure(StrictBaseModel):
    """New structure organization."""

    root: list[str] = Field(default_factory=list)
    architecture: list[str] = Field(default_factory=list)
    tracking: list[str] = Field(default_factory=list)


class EstimatedImprovement(StrictBaseModel):
    """Estimated improvement metrics."""

    dependency_depth_reduction: str | None = None
    access_time_improvement: str | None = None
    cognitive_load_reduction: str | None = None
    category_cohesion: str | None = None
    file_discoverability: str | None = None
    logical_grouping: str | None = None


class ReorganizationPlan(StrictBaseModel):
    """Reorganization plan structure."""

    current_state: CurrentState
    proposed_state: ProposedState
    moves: list[FileMove] = Field(default_factory=lambda: list[FileMove]())
    new_structure: NewStructure
    estimated_improvement: EstimatedImprovement


class SuggestRefactoringReorganizationResult(ToolResultBase):
    """Result of suggest_refactoring reorganization type."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    type: Literal["reorganization"] = "reorganization"
    goal: str
    plan: ReorganizationPlan


class SuggestRefactoringPreviewResult(ToolResultBase):
    """Result of suggest_refactoring preview mode."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    preview_mode: bool = True
    suggestion_id: str
    message: str
    note: str | None = None


class SuggestRefactoringErrorResult(ErrorResultBase):
    """Error result for suggest_refactoring operations."""

    type: str | None = None


# Union type for suggest_refactoring return (handled by type)
SuggestRefactoringResult = (
    SuggestRefactoringConsolidationResult
    | SuggestRefactoringSplitsResult
    | SuggestRefactoringReorganizationResult
    | SuggestRefactoringPreviewResult
    | SuggestRefactoringErrorResult
)


# ============================================================================
# Context Optimization Models (optimize_context)
# ============================================================================


class OptimizeContextResult(ToolResultBase):
    """Result of optimize_context operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    task_description: str
    token_budget: int
    strategy: str
    selected_files: list[str] = Field(default_factory=list)
    selected_sections: dict[str, list[str]] = Field(default_factory=dict)
    total_tokens: int
    utilization: float
    excluded_files: list[str] = Field(default_factory=list)
    relevance_scores: dict[str, float] = Field(default_factory=dict)


class OptimizeContextErrorResult(ErrorResultBase):
    """Error result for optimize_context operations."""

    task_description: str | None = None
    token_budget: int | None = None
    strategy: str | None = None


# Union type for optimize_context return
OptimizeContextResultUnion = OptimizeContextResult | OptimizeContextErrorResult


# ============================================================================
# Configuration Models (configure)
# ============================================================================


class ConfigureViewResult(ToolResultBase):
    """Result of configure view action."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    component: Literal["validation", "optimization", "learning"]
    # Configuration can have arbitrarily nested dicts (e.g., schemas.custom_schemas,
    # quality.weights), so we use dict[str, object] to accept any JSON structure
    configuration: dict[str, object] = Field(default_factory=dict)
    learned_patterns: dict[str, object] | None = None  # Only for learning component


class ConfigureUpdateResult(ToolResultBase):
    """Result of configure update action."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    component: Literal["validation", "optimization", "learning"]
    message: str
    # Configuration can have arbitrarily nested dicts, so we use dict[str, object]
    configuration: dict[str, object] = Field(default_factory=dict)
    action: str | None = (
        None  # Optional action field for special operations like export_patterns
    )
    patterns: dict[str, object] | None = (
        None  # Optional patterns field for export_patterns
    )


class ConfigureResetResult(ToolResultBase):
    """Result of configure reset action."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    message: str
    component: Literal["validation", "optimization", "learning"]
    # Configuration can have arbitrarily nested dicts, so we use dict[str, object]
    configuration: dict[str, object] = Field(default_factory=dict)


class ConfigureErrorResult(ErrorResultBase):
    """Error result for configure operations."""

    component: str | None = None
    valid_components: list[str] = Field(default_factory=list)
    valid_actions: list[str] = Field(default_factory=list)


# Union type for configure return (handled by action)
ConfigureResult = (
    ConfigureViewResult
    | ConfigureUpdateResult
    | ConfigureResetResult
    | ConfigureErrorResult
)


# ============================================================================
# Memory Bank Statistics Models (get_memory_bank_stats)
# ============================================================================


class MemoryBankSummary(StrictBaseModel):
    """Memory Bank summary statistics."""

    total_files: int
    total_tokens: int
    total_size_bytes: int
    total_size_kb: float
    total_reads: int
    history_size_bytes: int
    history_size_kb: float


class TokenBudgetStatus(StrictBaseModel):
    """Token budget status information."""

    status: Literal["healthy", "warning", "over_budget"]
    total_tokens: int
    max_tokens: int
    remaining_tokens: int
    usage_percentage: float
    warn_threshold: float


class RefactoringHistoryEntry(StrictBaseModel):
    """Individual refactoring history entry."""

    type: str
    timestamp: str
    files_affected: list[str] = Field(default_factory=list)
    status: Literal["success", "failed", "rolled_back"]


class RefactoringHistory(StrictBaseModel):
    """Refactoring history data."""

    total_refactorings: int
    successful: int
    rolled_back: int
    recent: list[RefactoringHistoryEntry] = Field(
        default_factory=lambda: list[RefactoringHistoryEntry]()
    )


class GetMemoryBankStatsResult(ToolResultBase):
    """Result of get_memory_bank_stats operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    project_root: str
    summary: MemoryBankSummary
    last_updated: str | None = None
    index_stats: IndexStats | None = None
    token_budget: TokenBudgetStatus | None = None
    refactoring_history: RefactoringHistory | None = None


class GetMemoryBankStatsErrorResult(ErrorResultBase):
    """Error result for get_memory_bank_stats operations."""

    project_root: str | None = None


# Union type for get_memory_bank_stats return
GetMemoryBankStatsResultUnion = GetMemoryBankStatsResult | GetMemoryBankStatsErrorResult


# ============================================================================
# Version History Models (get_version_history)
# ============================================================================


class VersionHistoryEntry(StrictBaseModel):
    """Version history entry."""

    version: int
    timestamp: str
    change_type: str | None = None
    change_description: str | None = None
    size_bytes: int | None = None
    token_count: int | None = None


class GetVersionHistoryResult(ToolResultBase):
    """Result of get_version_history operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    file_name: str
    total_versions: int
    versions: list[VersionHistoryEntry] = Field(
        default_factory=lambda: list[VersionHistoryEntry]()
    )


class GetVersionHistoryErrorResult(ErrorResultBase):
    """Error result for get_version_history operations."""

    file_name: str | None = None


# Union type for get_version_history return
GetVersionHistoryResultUnion = GetVersionHistoryResult | GetVersionHistoryErrorResult


# ============================================================================
# Dependency Graph Models (get_dependency_graph)
# ============================================================================


class FileDependencyInfoModel(StrictBaseModel):
    """File dependency information in graph."""

    priority: int
    dependencies: list[str] = Field(default_factory=list)


class DependencyGraphData(StrictBaseModel):
    """Dependency graph data structure."""

    files: dict[str, FileDependencyInfoModel] = Field(default_factory=dict)


class GetDependencyGraphJsonResult(ToolResultBase):
    """Result of get_dependency_graph operation (JSON format)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    format: Literal["json"] = "json"
    graph: DependencyGraphData
    loading_order: list[str] = Field(default_factory=list)


class GetDependencyGraphMermaidResult(ToolResultBase):
    """Result of get_dependency_graph operation (Mermaid format)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    format: Literal["mermaid"] = "mermaid"
    diagram: str


class GetDependencyGraphErrorResult(ErrorResultBase):
    """Error result for get_dependency_graph operations."""

    format: str | None = None


# Union type for get_dependency_graph return (handled by format)
GetDependencyGraphResult = (
    GetDependencyGraphJsonResult
    | GetDependencyGraphMermaidResult
    | GetDependencyGraphErrorResult
)


# ============================================================================
# Transclusion Resolution Models (resolve_transclusions)
# ============================================================================


class CacheStats(StrictBaseModel):
    """Cache statistics for transclusion resolution."""

    hits: int
    misses: int
    size: int


class ResolveTransclusionsResult(ToolResultBase):
    """Result of resolve_transclusions operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    file: str
    original_content: str
    resolved_content: str
    has_transclusions: bool
    cache_stats: CacheStats | None = None
    message: str | None = None


class ResolveTransclusionsErrorResult(ErrorResultBase):
    """Error result for resolve_transclusions operations."""

    file: str | None = None
    message: str | None = None


# Union type for resolve_transclusions return
ResolveTransclusionsResultUnion = (
    ResolveTransclusionsResult | ResolveTransclusionsErrorResult
)


# ============================================================================
# validate_links Models
# ============================================================================


class ValidationError(StrictBaseModel):
    """Validation error for a broken link."""

    file: str
    line: int
    link_type: str  # "markdown" or "transclusion"
    target: str
    error: str
    suggestion: str
    section: str | None = None


class ValidationWarning(StrictBaseModel):
    """Validation warning for a non-critical issue."""

    file: str
    line: int
    link_type: str  # "markdown" or "transclusion"
    target: str
    warning: str
    suggestion: str
    section: str | None = None
    available_sections: list[str] | None = None


class ValidateLinksSingleFileResult(ToolResultBase):
    """Result of validate_links operation for single file (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    mode: Literal["single_file"] = "single_file"
    file: str
    files_checked: int = 1
    total_links: int
    valid_links: int
    broken_links: int
    warnings: int
    validation_errors: list[ValidationError]
    validation_warnings: list[ValidationWarning]


class ValidateLinksAllFilesResult(ToolResultBase):
    """Result of validate_links operation for all files (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    mode: Literal["all_files"] = "all_files"
    files_checked: int
    total_links: int
    valid_links: int
    broken_links: int
    warnings: int
    validation_errors: list[ValidationError]
    validation_warnings: list[ValidationWarning]
    report: str


class ValidateLinksErrorResult(ErrorResultBase):
    """Error result for validate_links operations."""

    mode: str | None = None
    files_checked: int | None = None


# Union type for validate_links return
ValidateLinksResultUnion = (
    ValidateLinksSingleFileResult
    | ValidateLinksAllFilesResult
    | ValidateLinksErrorResult
)


# ============================================================================
# get_link_graph Models
# ============================================================================


class LinkGraphNode(StrictBaseModel):
    """Node in the link graph."""

    id: str
    type: str = "file"
    exists: bool


class LinkGraphEdge(StrictBaseModel):
    """Edge in the link graph."""

    source: str
    target: str
    type: str  # "reference" or "transclusion"
    line: int


class LinkGraphSummary(StrictBaseModel):
    """Summary statistics for the link graph."""

    total_files: int
    total_links: int
    reference_links: int
    transclusion_links: int
    has_cycles: bool
    cycle_count: int


class GetLinkGraphJsonResult(ToolResultBase):
    """Result of get_link_graph operation in JSON format (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    format: Literal["json"] = "json"
    nodes: list[LinkGraphNode]
    edges: list[LinkGraphEdge]
    cycles: list[list[str]]
    summary: LinkGraphSummary


class GetLinkGraphMermaidResult(ToolResultBase):
    """Result of get_link_graph operation in Mermaid format (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    format: Literal["mermaid"] = "mermaid"
    diagram: str
    cycles: list[list[str]]


class GetLinkGraphErrorResult(ErrorResultBase):
    """Error result for get_link_graph operations."""

    format: str | None = None


# Union type for get_link_graph return
GetLinkGraphResultUnion = (
    GetLinkGraphJsonResult | GetLinkGraphMermaidResult | GetLinkGraphErrorResult
)


# ============================================================================
# load_progressive_context Models
# ============================================================================


class LoadedFileInfo(StrictBaseModel):
    """Information about a loaded file in progressive context."""

    file_name: str
    tokens: int
    cumulative_tokens: int
    priority: int | None = None
    relevance_score: float | None = None
    more_available: bool = False


class LoadProgressiveContextResult(ToolResultBase):
    """Result of load_progressive_context operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    task_description: str
    loading_strategy: str
    token_budget: int
    files_loaded: int
    total_tokens: int
    loaded_files: list[LoadedFileInfo]


class LoadProgressiveContextErrorResult(ErrorResultBase):
    """Error result for load_progressive_context operations."""

    loading_strategy: str | None = None
    token_budget: int | None = None


# Union type for load_progressive_context return
LoadProgressiveContextResultUnion = (
    LoadProgressiveContextResult | LoadProgressiveContextErrorResult
)


# ============================================================================
# get_relevance_scores Models
# ============================================================================


class FileRelevanceScore(StrictBaseModel):
    """Relevance score information for a file."""

    total_score: float
    keyword_score: float | None = None
    dependency_score: float | None = None
    recency_score: float | None = None
    quality_score: float | None = None
    reason: str | None = None


class SectionRelevanceScore(StrictBaseModel):
    """Relevance score information for a section."""

    section: str
    score: float
    reason: str | None = None


class GetRelevanceScoresResult(ToolResultBase):
    """Result of get_relevance_scores operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    task_description: str
    files_scored: int
    file_scores: dict[str, FileRelevanceScore]
    section_scores: dict[str, list[SectionRelevanceScore]] | None = None


class GetRelevanceScoresErrorResult(ErrorResultBase):
    """Error result for get_relevance_scores operations."""

    task_description: str | None = None


# Union type for get_relevance_scores return
GetRelevanceScoresResultUnion = GetRelevanceScoresResult | GetRelevanceScoresErrorResult


# ============================================================================
# summarize_content Models
# ============================================================================


class SummarizationResult(StrictBaseModel):
    """Result of summarizing a single file."""

    file_name: str
    original_tokens: int
    summarized_tokens: int
    reduction: float
    cached: bool = False
    summary: str


class SummarizeContentResult(ToolResultBase):
    """Result of summarize_content operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    strategy: str
    target_reduction: float
    files_summarized: int
    total_original_tokens: int
    total_summarized_tokens: int
    total_reduction: float
    results: list[SummarizationResult]


class SummarizeContentErrorResult(ErrorResultBase):
    """Error result for summarize_content operations."""

    strategy: str | None = None
    target_reduction: float | None = None


# Union type for summarize_content return
SummarizeContentResultUnion = SummarizeContentResult | SummarizeContentErrorResult


# ============================================================================
# apply_refactoring Models
# ============================================================================


class ApplyRefactoringApproveResult(ToolResultBase):
    """Result of apply_refactoring approve action (success)."""

    status: Literal["approved"] = Field(default="approved")  # type: ignore[assignment]
    approval_id: str
    suggestion_id: str
    auto_apply: bool
    message: str = "Suggestion approved"


class ApplyRefactoringApplySuccessResult(ToolResultBase):
    """Result of apply_refactoring apply action (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    execution_id: str
    operations_completed: int
    snapshot_id: str | None = None
    actual_impact: RefactoringImpactMetrics | None = None
    dry_run: bool


class ApplyRefactoringApplyFailureResult(ToolResultBase):
    """Result of apply_refactoring apply action (validation/execution failure)."""

    status: Literal["failed"] = Field(default="failed")  # type: ignore[assignment]
    execution_id: str
    error: str
    operations_completed: int
    rollback_available: bool


class ApplyRefactoringRollbackSuccessResult(ToolResultBase):
    """Result of apply_refactoring rollback action (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    rollback_id: str
    execution_id: str
    files_restored: int
    conflicts_detected: int
    conflicts: list[str] = Field(default_factory=list)
    dry_run: bool


class ApplyRefactoringRollbackFailureResult(ToolResultBase):
    """Result of apply_refactoring rollback action (failure)."""

    status: Literal["failed"] = Field(default="failed")  # type: ignore[assignment]
    rollback_id: str
    error: str


class ApplyRefactoringErrorResult(ErrorResultBase):
    """Error result for apply_refactoring operations (general errors)."""

    action: str | None = None
    suggestion_id: str | None = None
    execution_id: str | None = None


# Union type for apply_refactoring return
ApplyRefactoringResultUnion = (
    ApplyRefactoringApproveResult
    | ApplyRefactoringApplySuccessResult
    | ApplyRefactoringApplyFailureResult
    | ApplyRefactoringRollbackSuccessResult
    | ApplyRefactoringRollbackFailureResult
    | ApplyRefactoringErrorResult
)


# ============================================================================
# rollback_file_version Models
# ============================================================================


class RollbackFileVersionResult(ToolResultBase):
    """Result of rollback_file_version operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    file_name: str
    rolled_back_from_version: int
    new_version: int
    token_count: int | None = None


class RollbackFileVersionErrorResult(ErrorResultBase):
    """Error result for rollback_file_version operations."""

    file_name: str | None = None
    version: int | None = None


# Union type for rollback_file_version return
RollbackFileVersionResultUnion = (
    RollbackFileVersionResult | RollbackFileVersionErrorResult
)


# ============================================================================
# check_structure_health Models
# ============================================================================


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
    grade: Literal["A", "B", "C", "D", "F"]
    status: Literal["healthy", "good", "fair", "warning", "critical", "not_initialized"]
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
    grade: Literal["A", "B", "C", "D", "F"]
    status: Literal["healthy", "good", "fair", "warning", "critical"]


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

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    health: HealthInfo
    summary: str
    action_required: bool
    cleanup: CleanupInfo | None = None


class CheckStructureHealthErrorResult(ErrorResultBase):
    """Error result for check_structure_health operations."""


# Union type for check_structure_health return
CheckStructureHealthResultUnion = (
    CheckStructureHealthResult | CheckStructureHealthErrorResult
)


# ============================================================================
# get_structure_info Models
# ============================================================================


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
    grade: Literal["A", "B", "C", "D", "F"]
    status: Literal["healthy", "good", "fair", "warning", "critical", "not_initialized"]
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

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    structure_info: StructureInfo
    message: str


class GetStructureInfoErrorResult(ErrorResultBase):
    """Error result for get_structure_info operations."""


# Union type for get_structure_info return
GetStructureInfoResultUnion = GetStructureInfoResult | GetStructureInfoErrorResult


# ============================================================================
# rules Models
# ============================================================================


class RulesIndexResult(StrictBaseModel):
    """Result of rules index operation."""

    indexed: int
    total_tokens: int
    cache_hit: bool
    index_time_seconds: float
    rules_folder: str
    rules_by_category: dict[str, int] = Field(default_factory=dict)


class RulesIndexOperationResult(ToolResultBase):
    """Result of rules index operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    operation: Literal["index"]
    result: RulesIndexResult


class RuleMetadata(StrictBaseModel):
    """Metadata for a single rule."""

    language: str | None = None
    tags: list[str] = Field(default_factory=list)


class RuleInfo(StrictBaseModel):
    """Information about a single rule."""

    file: str
    category: str
    relevance_score: float
    tokens: int
    title: str | None = None
    content: str | None = None
    metadata: RuleMetadata | None = None


class RulesManagerStatus(StrictBaseModel):
    """Rules manager status information."""

    indexed_count: int
    last_indexed: str
    rules_folder: str


class RulesContext(StrictBaseModel):
    """Rules context information."""

    filtered_count: int
    truncated_count: int


class RulesGetRelevantResult(ToolResultBase):
    """Result of rules get_relevant operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    operation: Literal["get_relevant"]
    task_description: str
    max_tokens: int
    min_relevance_score: float
    rules_count: int
    total_tokens: int
    rules: list[RuleInfo] = Field(default_factory=lambda: list[RuleInfo]())
    rules_manager_status: RulesManagerStatus | None = None
    rules_context: RulesContext | None = None
    rules_source: str | None = None


class RulesDisabledResult(ToolResultBase):
    """Result when rules indexing is disabled."""

    status: Literal["disabled"] = Field(default="disabled")  # type: ignore[assignment]
    message: str


class RulesErrorResult(ErrorResultBase):
    """Error result for rules operations."""

    operation: str | None = None
    valid_operations: list[str] = Field(default_factory=list)


# Union type for rules return
RulesResultUnion = (
    RulesIndexOperationResult
    | RulesGetRelevantResult
    | RulesDisabledResult
    | RulesErrorResult
)


# ============================================================================
# execute_pre_commit_checks Models
# ============================================================================


class CheckResult(StrictBaseModel):
    """Result of a single pre-commit check."""

    status: Literal["passed", "failed", "skipped", "error"]
    errors: int | None = None
    warnings: int | None = None
    message: str | None = None
    files_formatted: int | None = None
    score: float | None = None
    tests_run: int | None = None
    tests_passed: int | None = None
    coverage: float | None = None


class CheckStats(StrictBaseModel):
    """Statistics for pre-commit checks."""

    total_errors: int
    total_warnings: int
    files_modified: list[str] = Field(default_factory=list)
    checks_performed: list[str] = Field(default_factory=list)


class ExecutePreCommitChecksResult(ToolResultBase):
    """Result of execute_pre_commit_checks operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    language: str
    checks: dict[str, CheckResult] = Field(default_factory=dict)
    stats: CheckStats


class ExecutePreCommitChecksErrorResult(ErrorResultBase):
    """Error result for execute_pre_commit_checks operations."""

    language: str | None = None


# Union type for execute_pre_commit_checks return
ExecutePreCommitChecksResultUnion = (
    ExecutePreCommitChecksResult | ExecutePreCommitChecksErrorResult
)


# ============================================================================
# fix_quality_issues Models
# ============================================================================


class FixQualityIssuesResult(ToolResultBase):
    """Result of fix_quality_issues operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    errors_fixed: int
    warnings_fixed: int
    formatting_issues_fixed: int
    markdown_issues_fixed: int
    type_errors_fixed: int
    files_modified: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    error_message: str | None = None


class FixQualityIssuesErrorResult(ErrorResultBase):
    """Error result for fix_quality_issues operations."""

    errors_fixed: int = 0
    warnings_fixed: int = 0
    formatting_issues_fixed: int = 0
    markdown_issues_fixed: int = 0
    type_errors_fixed: int = 0
    files_modified: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    error_message: str | None = None


# Union type for fix_quality_issues return
FixQualityIssuesResultUnion = FixQualityIssuesResult | FixQualityIssuesErrorResult


# ============================================================================
# cleanup_metadata_index Models
# ============================================================================


class CleanupMetadataIndexResult(ToolResultBase):
    """Result of cleanup_metadata_index operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    dry_run: bool
    stale_files_found: int
    stale_files: list[str] = Field(default_factory=list)
    entries_cleaned: int
    message: str


class CleanupMetadataIndexErrorResult(ErrorResultBase):
    """Error result for cleanup_metadata_index operations."""


# Union type for cleanup_metadata_index return
CleanupMetadataIndexResultUnion = (
    CleanupMetadataIndexResult | CleanupMetadataIndexErrorResult
)


# ============================================================================
# provide_feedback Models
# ============================================================================


class LearningSummary(StrictBaseModel):
    """Learning engine summary statistics."""

    total_feedback: int
    approval_rate: float
    min_confidence_threshold: float


class ProvideFeedbackResult(ToolResultBase):
    """Result of provide_feedback operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    feedback_id: str
    learning_enabled: bool
    message: str
    learning_summary: LearningSummary | None = None


class ProvideFeedbackErrorResult(ErrorResultBase):
    """Error result for provide_feedback operations."""

    suggestion_id: str | None = None
    feedback_type: str | None = None


# Union type for provide_feedback return
ProvideFeedbackResultUnion = ProvideFeedbackResult | ProvideFeedbackErrorResult


# ============================================================================
# Synapse Tools Models
# ============================================================================


class PromptInfo(StrictBaseModel):
    """Information about a prompt."""

    file: str
    name: str
    category: str
    description: str
    keywords: list[str] = Field(default_factory=list)


class GetSynapsePromptsResult(ToolResultBase):
    """Result of get_synapse_prompts operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    category: str | None = None
    categories: list[str] = Field(default_factory=list)
    prompts: list[PromptInfo] = Field(default_factory=lambda: list[PromptInfo]())
    total_count: int


class GetSynapsePromptsErrorResult(ErrorResultBase):
    """Error result for get_synapse_prompts operations."""


# Union type for get_synapse_prompts return
GetSynapsePromptsResultUnion = GetSynapsePromptsResult | GetSynapsePromptsErrorResult


class UpdateSynapsePromptResult(ToolResultBase):
    """Result of update_synapse_prompt operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    category: str
    file: str
    message: str
    type: Literal["prompt"] = Field(default="prompt")
    commit_hash: str | None = None


class UpdateSynapsePromptErrorResult(ErrorResultBase):
    """Error result for update_synapse_prompt operations."""


# Union type for update_synapse_prompt return
UpdateSynapsePromptResultUnion = (
    UpdateSynapsePromptResult | UpdateSynapsePromptErrorResult
)


# ============================================================================
# fix_roadmap_corruption Models
# ============================================================================


class CorruptionMatch(StrictBaseModel):
    """A detected corruption match."""

    line_num: int = Field(
        ..., ge=1, description="Line number where corruption was found"
    )
    original: str = Field(..., min_length=1, description="Original corrupted content")
    fixed: str = Field(..., description="Fixed content")
    pattern: str = Field(
        ..., min_length=1, description="Pattern that matched the corruption"
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )


class FixRoadmapCorruptionResult(ToolResultBase):
    """Result of fix_roadmap_corruption operation (success)."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    file_name: str
    corruption_count: int
    fixes_applied: list[CorruptionMatch] = Field(
        default_factory=lambda: list[CorruptionMatch]()
    )
    error_message: str | None = None


class FixRoadmapCorruptionErrorResult(ErrorResultBase):
    """Error result for fix_roadmap_corruption operations."""

    file_name: str
    corruption_count: int = 0
    fixes_applied: list[CorruptionMatch] = Field(
        default_factory=lambda: list[CorruptionMatch]()
    )
    error_message: str | None = None


# Union type for fix_roadmap_corruption return
FixRoadmapCorruptionResultUnion = (
    FixRoadmapCorruptionResult | FixRoadmapCorruptionErrorResult
)


# ============================================================================
# Synapse Tools Models (sync_synapse, update_synapse_rule, get_synapse_rules)
# ============================================================================


class SynapseChanges(StrictBaseModel):
    """Changes detected during sync."""

    added: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


class SyncSynapseResult(ToolResultBase):
    """Result of sync_synapse operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    pulled: bool
    pushed: bool
    changes: SynapseChanges
    reindex_triggered: bool
    last_sync: str


class SyncSynapseErrorResult(ErrorResultBase):
    """Error result for sync_synapse operations."""


# Union type for sync_synapse return
SyncSynapseResultUnion = SyncSynapseResult | SyncSynapseErrorResult


class RuleInfoModel(StrictBaseModel):
    """Information about a rule."""

    file: str
    tokens: int
    priority: str | None = None
    relevance_score: float | None = None
    category: str | None = None


class ContextInfo(StrictBaseModel):
    """Context information for rules."""

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    task_type: str | None = None


class RulesLoaded(StrictBaseModel):
    """Loaded rules by category."""

    generic: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())
    language: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())
    local: list[RuleInfoModel] = Field(default_factory=lambda: list[RuleInfoModel]())


class GetSynapseRulesResult(ToolResultBase):
    """Result of get_synapse_rules operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    task_description: str
    context: ContextInfo
    rules_loaded: RulesLoaded
    total_tokens: int
    token_budget: int
    source: str
    keywords: list[str] = Field(default_factory=list)


class GetSynapseRulesErrorResult(ErrorResultBase):
    """Error result for get_synapse_rules operations."""


# Union type for get_synapse_rules return
GetSynapseRulesResultUnion = GetSynapseRulesResult | GetSynapseRulesErrorResult


class UpdateSynapseRuleResult(ToolResultBase):
    """Result of update_synapse_rule operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    category: str
    file: str
    message: str
    commit_hash: str | None = None


class UpdateSynapseRuleErrorResult(ErrorResultBase):
    """Error result for update_synapse_rule operations."""


# Union type for update_synapse_rule return
UpdateSynapseRuleResultUnion = UpdateSynapseRuleResult | UpdateSynapseRuleErrorResult


# ============================================================================
# Markdown Operations Models (fix_markdown_lint)
# ============================================================================


class FileResult(StrictBaseModel):
    """Result for a single file processing."""

    file: str
    fixed: bool
    errors: list[str] = Field(default_factory=list)
    error_message: str | None = None


class FixMarkdownLintResult(ToolResultBase):
    """Result of markdown lint fixing operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    files_processed: int
    files_fixed: int
    files_unchanged: int
    files_with_errors: int
    results: list[FileResult] = Field(default_factory=lambda: list[FileResult]())
    error_message: str | None = None


class FixMarkdownLintErrorResult(ErrorResultBase):
    """Error result for fix_markdown_lint operations."""


# Union type for fix_markdown_lint return
FixMarkdownLintResultUnion = FixMarkdownLintResult | FixMarkdownLintErrorResult


# ============================================================================
# Connection Health Models (check_mcp_connection_health)
# ============================================================================


class ConnectionHealthResult(ToolResultBase):
    """Result of connection health check."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    health: HealthMetrics


class ConnectionHealthErrorResult(ErrorResultBase):
    """Error result for check_mcp_connection_health operations."""


# Union type for check_mcp_connection_health return
ConnectionHealthResultUnion = ConnectionHealthResult | ConnectionHealthErrorResult


# ============================================================================
# Link Parser Models (parse_file_links)
# ============================================================================


class LinkLocation(StrictBaseModel):
    """Location of a link in a file."""

    line: int
    column: int


class LinkSummary(StrictBaseModel):
    """Summary statistics for parsed links."""

    markdown_links: int
    transclusions: int
    total: int
    unique_files: int


class ParsedMarkdownLink(StrictBaseModel):
    """Parsed markdown link information."""

    text: str = Field(..., description="Link text")
    target: str = Field(..., description="Link target path or URL")
    line: int = Field(..., ge=1, description="Line number")
    column: int = Field(default=1, ge=1, description="Column number")
    is_external: bool = Field(default=False, description="Whether link is external")


class ParsedTransclusion(StrictBaseModel):
    """Parsed transclusion reference."""

    target: str = Field(..., description="Transclusion target path")
    line: int = Field(..., ge=1, description="Line number")
    section: str | None = Field(default=None, description="Target section if specified")
    full_syntax: str = Field(..., description="Full transclusion syntax")


class ParseFileLinksResult(ToolResultBase):
    """Result of parse_file_links operation."""

    status: Literal["success"] = Field(default="success")  # type: ignore[assignment]
    file: str
    summary: LinkSummary
    markdown_links: list[ParsedMarkdownLink] = Field(
        default_factory=lambda: list[ParsedMarkdownLink]()
    )
    transclusions: list[ParsedTransclusion] = Field(
        default_factory=lambda: list[ParsedTransclusion]()
    )


class ParseFileLinksErrorResult(ErrorResultBase):
    """Error result for parse_file_links operations."""

    file: str | None = None


# Union type for parse_file_links return
ParseFileLinksResultUnion = ParseFileLinksResult | ParseFileLinksErrorResult


# ============================================================================
# Project Config Status Models (from config_status.py)
# ============================================================================


class ProjectConfigStatusModel(StrictBaseModel):
    """Project configuration status flags."""

    memory_bank_initialized: bool = Field(
        ..., description="Whether memory bank is initialized"
    )
    structure_configured: bool = Field(
        ..., description="Whether .cortex structure is configured"
    )
    cursor_integration_configured: bool = Field(
        ..., description="Whether Cursor integration is configured"
    )
    migration_needed: bool = Field(
        ..., description="Whether migration is needed from legacy formats"
    )
    tiktoken_cache_available: bool = Field(
        ..., description="Whether tiktoken cache is available"
    )


# ============================================================================
# Pre-Commit Result Models (from pre_commit_tools.py)
# ============================================================================


class PreCommitCheckResult(StrictBaseModel):
    """Result of a single pre-commit check."""

    passed: bool = Field(..., description="Whether check passed")
    errors: int = Field(default=0, ge=0, description="Number of errors")
    warnings: int = Field(default=0, ge=0, description="Number of warnings")
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified by this check"
    )
    output: str | None = Field(default=None, description="Check output")


class PreCommitResultModel(StrictBaseModel):
    """Result of pre-commit checks execution."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    status: Literal["success", "error"] = Field(..., description="Operation status")
    language: str | None = Field(None, description="Detected language")
    checks_performed: list[str] = Field(
        default_factory=list, description="Checks performed"
    )
    results: dict[str, PreCommitCheckResult] = Field(
        default_factory=dict, description="Results by check type"
    )
    total_errors: int = Field(default=0, ge=0, description="Total errors")
    total_warnings: int = Field(default=0, ge=0, description="Total warnings")
    files_modified: list[str] = Field(
        default_factory=list, description="Files modified"
    )
    success: bool = Field(default=True, description="Whether checks succeeded")
    error: str | None = Field(None, description="Error message if status is error")
    error_type: str | None = Field(None, description="Error type if status is error")
