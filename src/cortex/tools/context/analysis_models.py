"""
Analysis result models for analyze tool (usage_patterns, structure, insights).
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, ConfigDict, Field

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


class SeverityLevel(str, Enum):
    """Severity for anti-patterns and insights."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AnalyzeTarget(str, Enum):
    """Analyze tool target type."""

    USAGE_PATTERNS = "usage_patterns"
    STRUCTURE = "structure"
    INSIGHTS = "insights"


_StatusField = Annotated[
    ToolResultStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, ToolResultStatus)),
]
_SeverityField = Annotated[
    SeverityLevel,
    BeforeValidator(lambda x: _coerce_str_enum(x, SeverityLevel)),
]
_TargetField = Annotated[
    AnalyzeTarget,
    BeforeValidator(lambda x: _coerce_str_enum(x, AnalyzeTarget)),
]


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
    severity: _SeverityField
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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    target: _TargetField = Field(default=AnalyzeTarget.USAGE_PATTERNS)
    time_window_days: int
    patterns: AccessFrequencyPattern


class AnalyzeStructureResult(ToolResultBase):
    """Result of analyze structure target."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    target: _TargetField = Field(default=AnalyzeTarget.STRUCTURE)
    analysis: StructureAnalysis


class AnalyzeInsightsResult(ToolResultBase):
    """Result of analyze insights target."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    target: _TargetField = Field(default=AnalyzeTarget.INSIGHTS)
    format: str
    insights: InsightsData | str  # Structured or formatted string


class AnalyzeErrorResult(ErrorResultBase):
    """Error result for analyze operations."""

    target: str | None = None


AnalyzeResult = (
    AnalyzeUsagePatternsResult
    | AnalyzeStructureResult
    | AnalyzeInsightsResult
    | AnalyzeErrorResult
)
