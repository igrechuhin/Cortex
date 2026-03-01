"""
Validation and link-graph result models for validate and get_link_graph tools.

Used by validate_operations, validate_links, get_link_graph.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, Field

from cortex.tools.models_base import (
    ErrorResultBase,
    StrictBaseModel,
    ToolResultBase,
    ToolResultStatus,
)


def _coerce_str_enum[E: Enum](v: str | Enum, enum_cls: type[E]) -> E:
    """Coerce string to enum for Pydantic (e.g. from JSON or dict input)."""
    if isinstance(v, enum_cls):
        return v
    return enum_cls(v)


class ValidateCheckType(str, Enum):
    """Validate tool check type."""

    SCHEMA = "schema"
    DUPLICATIONS = "duplications"
    QUALITY = "quality"
    INFRASTRUCTURE = "infrastructure"
    TIMESTAMPS = "timestamps"
    ROADMAP_SYNC = "roadmap_sync"


class QualityHealthStatus(str, Enum):
    """Quality validation health status."""

    HEALTHY = "healthy"
    GOOD = "good"
    FAIR = "fair"
    WARNING = "warning"
    CRITICAL = "critical"


class IssueSeverity(str, Enum):
    """Severity for validation issues."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidateLinksMode(str, Enum):
    """validate_links operation mode."""

    SINGLE_FILE = "single_file"
    ALL_FILES = "all_files"


class LinkGraphFormat(str, Enum):
    """get_link_graph output format."""

    JSON = "json"
    MERMAID = "mermaid"


# Annotated types that accept str or enum (for model_validate/dict/JSON input)
_CheckTypeField = Annotated[
    ValidateCheckType,
    BeforeValidator(lambda x: _coerce_str_enum(x, ValidateCheckType)),
]
_QualityHealthStatusField = Annotated[
    QualityHealthStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, QualityHealthStatus)),
]
_IssueSeverityField = Annotated[
    IssueSeverity,
    BeforeValidator(lambda x: _coerce_str_enum(x, IssueSeverity)),
]
_StatusField = Annotated[
    ToolResultStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, ToolResultStatus)),
]


# ============================================================================
# Schema validation
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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    check_type: _CheckTypeField = Field(default=ValidateCheckType.SCHEMA)
    file_name: str
    validation: SchemaValidationResult


class ValidateSchemaAllResult(ToolResultBase):
    """Result of validate schema check for all files."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    check_type: _CheckTypeField = Field(default=ValidateCheckType.SCHEMA)
    results: dict[str, SchemaValidationResult]


# ============================================================================
# Duplications
# ============================================================================


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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    check_type: _CheckTypeField = Field(default=ValidateCheckType.DUPLICATIONS)
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


# ============================================================================
# Quality
# ============================================================================


class QualityScore(StrictBaseModel):
    """Quality score breakdown."""

    overall: float
    completeness: float | None = None
    structure: float | None = None
    content_quality: float | None = None
    issues: list[str] = Field(default_factory=list)


class ValidateQualitySingleResult(ToolResultBase):
    """Result of validate quality check for single file."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    check_type: _CheckTypeField = Field(default=ValidateCheckType.QUALITY)
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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    check_type: _CheckTypeField = Field(default=ValidateCheckType.QUALITY)
    overall_score: float
    health_status: _QualityHealthStatusField
    file_scores: dict[str, float]
    metrics: QualityMetricsBreakdown = Field(default_factory=QualityMetricsBreakdown)


# ============================================================================
# Infrastructure
# ============================================================================


class InfrastructureIssue(StrictBaseModel):
    """Infrastructure validation issue."""

    type: str
    severity: _IssueSeverityField
    description: str
    location: str | None = None
    suggestion: str | None = None
    ci_check: str | None = None
    missing_in_commit: bool | None = None


class ValidateInfrastructureResult(ToolResultBase):
    """Result of validate infrastructure check."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    check_type: _CheckTypeField = Field(default=ValidateCheckType.INFRASTRUCTURE)
    checks_performed: dict[str, bool] = Field(default_factory=dict)
    issues_found: list[InfrastructureIssue] = Field(
        default_factory=lambda: list[InfrastructureIssue]()
    )
    recommendations: list[str] = Field(default_factory=list)


# ============================================================================
# Timestamps
# ============================================================================


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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    check_type: _CheckTypeField = Field(default=ValidateCheckType.TIMESTAMPS)
    total_valid: int
    total_invalid_format: int
    total_invalid_with_time: int
    files_valid: bool
    results: dict[str, FileTimestampResult] = Field(default_factory=dict)
    valid: bool


# ============================================================================
# Roadmap sync
# ============================================================================


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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    check_type: _CheckTypeField = Field(default=ValidateCheckType.ROADMAP_SYNC)
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
