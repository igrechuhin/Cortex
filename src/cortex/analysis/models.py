"""
Pydantic models for analysis module.

This module contains Pydantic models for pattern analysis and insight types,
migrated from TypedDict definitions for better validation and IDE support.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Import FileOrganizationResult from core.models to avoid duplication
from cortex.core.models import FileOrganizationResult as CoreFileOrganizationResult

# ============================================================================
# Base Model
# ============================================================================


class AnalysisBaseModel(BaseModel):
    """Base model for analysis types with strict validation."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )


# ============================================================================
# Pattern Types (from pattern_types.py)
# ============================================================================


class AccessRecord(AnalysisBaseModel):
    """Single file access event record."""

    timestamp: str = Field(..., description="ISO timestamp of access")
    file: str = Field(..., description="File that was accessed")
    task_id: str | None = Field(None, description="Task ID if available")
    task_description: str | None = Field(None, description="Task description")
    context_files: list[str] = Field(
        default_factory=list, description="Files accessed in same context"
    )


class FileStatsEntry(AnalysisBaseModel):
    """Aggregated statistics for a single file."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    total_accesses: int | None = Field(None, ge=0, description="Total access count")
    first_access: str | None = Field(None, description="ISO timestamp of first access")
    last_access: str | None = Field(None, description="ISO timestamp of last access")
    tasks: list[str] | None = Field(None, description="Task IDs that accessed file")


class TaskPatternEntry(AnalysisBaseModel):
    """Task-based access pattern entry."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    description: str | None = Field(None, description="Task description")
    files: list[str] | None = Field(None, description="Files accessed for task")
    timestamp: str | None = Field(None, description="ISO timestamp")


class UnusedFileEntry(AnalysisBaseModel):
    """Unused file entry with access information."""

    file: str = Field(..., description="File path")
    last_access: str | None = Field(None, description="ISO timestamp of last access")
    days_since_access: int | None = Field(
        None, ge=0, description="Days since last access"
    )
    total_accesses: int = Field(..., ge=0, description="Total access count")
    status: Literal["stale", "never_accessed"] = Field(..., description="File status")


class TaskPatternResult(AnalysisBaseModel):
    """Task pattern result entry."""

    task_id: str = Field(..., description="Task identifier")
    description: str = Field(..., description="Task description")
    file_count: int = Field(..., ge=0, description="Number of files")
    files: list[str] = Field(default_factory=list, description="List of files")
    timestamp: str = Field(..., description="ISO timestamp")


class TemporalPatternsResult(AnalysisBaseModel):
    """Temporal patterns result."""

    time_range_days: int = Field(..., ge=0, description="Time range in days")
    total_accesses: int = Field(..., ge=0, description="Total access count")
    hourly_distribution: dict[int, int] = Field(
        default_factory=lambda: dict[int, int](),
        description="Access count by hour (0-23)",
    )
    daily_distribution: dict[str, int] = Field(
        default_factory=dict, description="Access count by day of week"
    )
    weekly_distribution: dict[str, int] = Field(
        default_factory=dict, description="Access count by week"
    )
    peak_hour: int | None = Field(None, ge=0, le=23, description="Peak access hour")
    peak_day: str | None = Field(None, description="Peak access day")
    avg_accesses_per_day: float = Field(
        ..., ge=0.0, description="Average accesses per day"
    )


class AccessLog(AnalysisBaseModel):
    """Structured access log stored on disk."""

    version: str = Field(..., description="Log format version")
    accesses: list[AccessRecord] = Field(
        default_factory=lambda: list[AccessRecord](), description="Access records"
    )
    file_stats: dict[str, FileStatsEntry] = Field(
        default_factory=dict, description="Per-file statistics"
    )
    co_access_patterns: dict[str, int] = Field(
        default_factory=dict, description="Co-access pattern counts"
    )
    task_patterns: dict[str, TaskPatternEntry] = Field(
        default_factory=dict, description="Task-based patterns"
    )


class FileAccessStats(AnalysisBaseModel):
    """Statistics for file access frequency analysis.

    Used by pattern_analysis.py for tracking access counts during analysis.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    access_count: int = Field(default=0, ge=0, description="Number of accesses")
    last_access: str | None = Field(
        default=None, description="ISO timestamp of last access"
    )
    task_count: int = Field(default=0, ge=0, description="Number of unique tasks")
    avg_accesses_per_day: float = Field(
        default=0.0, ge=0.0, description="Average accesses per day"
    )


# ============================================================================
# Insight Types (from insight_types.py)
# ============================================================================


class InsightEvidence(AnalysisBaseModel):
    """Evidence supporting an insight."""

    files_analyzed: list[str] = Field(
        default_factory=list, description="Files analyzed"
    )
    patterns_found: list[str] = Field(
        default_factory=list, description="Patterns found"
    )
    metrics: dict[str, float] = Field(
        default_factory=dict, description="Relevant metrics"
    )
    examples: list[str] = Field(default_factory=list, description="Example snippets")


class InsightModel(AnalysisBaseModel):
    """Pydantic model for insight data."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    id: str | None = Field(default=None, description="Insight identifier")
    category: str | None = Field(default=None, description="Insight category")
    title: str | None = Field(default=None, description="Insight title")
    description: str | None = Field(default=None, description="Insight description")
    impact_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Impact score 0-1"
    )
    severity: Literal["high", "medium", "low"] | None = Field(
        default=None, description="Severity level"
    )
    evidence: InsightEvidence | None = Field(
        default=None, description="Supporting evidence"
    )
    recommendations: list[str] | None = Field(
        default=None, description="Recommendations"
    )
    estimated_token_savings: int | None = Field(
        default=None, ge=0, description="Estimated token savings"
    )
    affected_files: list[str] | None = Field(default=None, description="Affected files")


class RecommendationEntry(AnalysisBaseModel):
    """A single recommendation entry."""

    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Recommendation description")
    priority: Literal["high", "medium", "low"] = Field(
        default="medium", description="Priority level"
    )
    estimated_impact: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Estimated impact 0-1"
    )


class SummaryModel(AnalysisBaseModel):
    """Pydantic model for summary data."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    status: Literal["success", "error", "warning"] | None = Field(
        default=None, description="Summary status"
    )
    message: str | None = Field(default=None, description="Summary message")
    high_severity_count: int | None = Field(
        default=None, ge=0, description="High severity count"
    )
    medium_severity_count: int | None = Field(
        default=None, ge=0, description="Medium severity count"
    )
    low_severity_count: int | None = Field(
        default=None, ge=0, description="Low severity count"
    )
    top_recommendations: list[RecommendationEntry] | None = Field(
        default=None, description="Top recommendations"
    )


class InsightsResult(AnalysisBaseModel):
    """Pydantic model for generate_insights return value."""

    generated_at: str = Field(..., description="ISO timestamp of generation")
    total_insights: int = Field(..., ge=0, description="Total insight count")
    high_impact_count: int = Field(..., ge=0, description="High impact count")
    medium_impact_count: int = Field(..., ge=0, description="Medium impact count")
    low_impact_count: int = Field(..., ge=0, description="Low impact count")
    estimated_total_token_savings: int = Field(
        ..., ge=0, description="Total estimated token savings"
    )
    insights: list[InsightModel] = Field(
        default_factory=lambda: list[InsightModel](), description="List of insights"
    )
    summary: SummaryModel = Field(..., description="Summary data")


# ============================================================================
# Protocol Return Type Models (for PatternAnalyzerProtocol)
# ============================================================================


class AccessFrequencyEntry(AnalysisBaseModel):
    """Access frequency data for a single file.

    Note: Both old (read_count, frequency) and new (access_count, avg_accesses_per_day)
    field names are supported for compatibility.
    """

    # Access count fields (support both names)
    read_count: int = Field(
        default=0, ge=0, description="Number of reads (alias: access_count)"
    )
    write_count: int = Field(default=0, ge=0, description="Number of writes")
    access_count: int = Field(
        default=0, ge=0, description="Total access count (alias: read_count)"
    )
    task_count: int = Field(default=0, ge=0, description="Number of unique tasks")

    # Frequency fields (support both names)
    frequency: float = Field(
        default=0.0,
        ge=0.0,
        description="Access frequency (alias: avg_accesses_per_day)",
    )
    avg_accesses_per_day: float = Field(
        default=0.0, ge=0.0, description="Average accesses per day"
    )

    # Timestamps
    last_access: str | None = Field(
        default=None, description="ISO timestamp of last access"
    )


class CoAccessPattern(AnalysisBaseModel):
    """Co-access pattern between files.

    Note: Supports both structural (files, correlation, occurrences) and
    legacy (file_1, file_2, co_access_count, correlation_strength) field names.
    """

    # File references - support both list and individual fields
    files: list[str] = Field(
        default_factory=list, description="Files accessed together"
    )
    file_1: str | None = Field(default=None, description="First file in the pair")
    file_2: str | None = Field(default=None, description="Second file in the pair")

    # Correlation/co-access count - support both names
    correlation: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Correlation strength (0-1)"
    )
    correlation_strength: str | None = Field(
        default=None, description="Correlation strength label (high/medium/low)"
    )
    occurrences: int = Field(
        default=0, ge=0, description="Number of co-access occurrences"
    )
    co_access_count: int = Field(
        default=0, ge=0, description="Co-access count (alias: occurrences)"
    )

    # Context
    context: str | None = Field(default=None, description="Context of co-access")


class UnusedFileInfo(AnalysisBaseModel):
    """Information about an unused file.

    Note: Supports both 'file_name' and 'file' field names for compatibility.
    """

    file_name: str = Field(..., description="File name")
    file: str = Field(default="", description="File path (alias for file_name)")
    days_since_access: int = Field(
        default=0, ge=0, description="Days since last access"
    )
    last_access: str | None = Field(
        default=None, description="ISO timestamp of last access"
    )
    size_bytes: int = Field(default=0, ge=0, description="File size in bytes")
    recommendation: str | None = Field(
        default=None, description="Recommendation for the file"
    )
    status: Literal["stale", "never_accessed"] | None = Field(
        default=None, description="File status"
    )


# ============================================================================
# Protocol Return Type Models (for StructureAnalyzerProtocol)
# ============================================================================


class OrganizationAnalysis(AnalysisBaseModel):
    """Analysis of Memory Bank organization."""

    total_files: int = Field(..., ge=0, description="Total number of files")
    total_directories: int = Field(
        default=0, ge=0, description="Total number of directories"
    )
    max_depth: int = Field(..., ge=0, description="Maximum directory depth")
    avg_depth: float = Field(default=0.0, ge=0.0, description="Average directory depth")
    has_circular_deps: bool = Field(
        default=False, description="Whether circular dependencies exist"
    )
    orphaned_files: list[str] = Field(
        default_factory=list, description="Files with no dependencies"
    )


class AntiPatternInfo(AnalysisBaseModel):
    """Information about a detected anti-pattern."""

    type: str = Field(..., description="Anti-pattern type")
    file: str | None = Field(default=None, description="Affected file")
    files: list[str] = Field(default_factory=list, description="Affected files")
    severity: Literal["error", "warning", "info"] = Field(
        ..., description="Severity level"
    )
    description: str = Field(..., description="Description of the anti-pattern")
    recommendation: str | None = Field(
        default=None, description="Recommendation to fix"
    )


class ComplexityMetrics(AnalysisBaseModel):
    """Complexity metrics for Memory Bank structure."""

    max_dependency_depth: int = Field(
        default=0, ge=0, description="Maximum dependency depth"
    )
    cyclomatic_complexity: int = Field(
        default=0, ge=0, description="Cyclomatic complexity"
    )
    avg_dependencies_per_file: float = Field(
        default=0.0, ge=0.0, description="Average dependencies per file"
    )
    max_fan_in: int = Field(default=0, ge=0, description="Maximum fan-in")
    max_fan_out: int = Field(default=0, ge=0, description="Maximum fan-out")
    avg_fan_in: float = Field(default=0.0, ge=0.0, description="Average fan-in")
    avg_fan_out: float = Field(default=0.0, ge=0.0, description="Average fan-out")
    total_edges: int = Field(default=0, ge=0, description="Total edges in graph")
    total_nodes: int = Field(default=0, ge=0, description="Total nodes in graph")


class ComplexityAssessment(AnalysisBaseModel):
    """Assessment of structural complexity."""

    score: int = Field(default=100, ge=0, le=100, description="Complexity score 0-100")
    grade: str = Field(default="A", description="Letter grade")
    status: str = Field(default="healthy", description="Status description")
    issues: list[str] = Field(default_factory=list, description="Identified issues")
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )


class ComplexityHotspot(AnalysisBaseModel):
    """A complexity hotspot in the structure."""

    file: str = Field(..., description="File name")
    score: float = Field(default=0.0, ge=0.0, description="Hotspot score")
    depth: int = Field(default=0, ge=0, description="Dependency depth")
    fan_in: int = Field(default=0, ge=0, description="Fan-in count")
    fan_out: int = Field(default=0, ge=0, description="Fan-out count")


class ComplexityAnalysisResult(AnalysisBaseModel):
    """Result of complexity analysis."""

    status: Literal["analyzed", "no_files", "error"] = Field(
        ..., description="Analysis status"
    )
    metrics: ComplexityMetrics = Field(
        default_factory=ComplexityMetrics, description="Complexity metrics"
    )
    complexity_hotspots: list[ComplexityHotspot] = Field(
        default_factory=lambda: list[ComplexityHotspot](),
        description="Top complexity hotspots",
    )
    assessment: ComplexityAssessment = Field(
        default_factory=ComplexityAssessment, description="Complexity assessment"
    )


class DependencyChain(AnalysisBaseModel):
    """A dependency chain in the structure."""

    chain: list[str] = Field(default_factory=list, description="Files in chain")
    length: int = Field(default=0, ge=0, description="Chain length")
    start_file: str = Field(default="", description="Starting file")
    end_file: str = Field(default="", description="Ending file")


class InsightStatistics(AnalysisBaseModel):
    """Statistics about generated insights."""

    total_potential_savings: int = Field(
        default=0, ge=0, description="Total potential token savings"
    )
    high_impact: int = Field(default=0, ge=0, description="High impact insight count")
    medium_impact: int = Field(
        default=0, ge=0, description="Medium impact insight count"
    )
    low_impact: int = Field(default=0, ge=0, description="Low impact insight count")


# ============================================================================
# Additional Analysis Models (from migration plan)
# ============================================================================


class FileSizeInfo(AnalysisBaseModel):
    """Information about a file's size."""

    file: str = Field(..., description="File name")
    size_bytes: int = Field(..., ge=0, description="Size in bytes")
    tokens: int = Field(default=0, ge=0, description="Token count")


class DependencyChainResult(AnalysisBaseModel):
    """Result of dependency chain analysis."""

    chain: list[str] = Field(default_factory=list, description="Files in chain")
    length: int = Field(default=0, ge=0, description="Chain length")
    is_linear: bool = Field(default=True, description="Whether chain is linear")


# ============================================================================
# Composite Structure Analysis Data Model
# ============================================================================


class StructureAnalysisData(AnalysisBaseModel):
    """Aggregated structure analysis data from StructureAnalyzer.

    This model combines the results of:
    - analyze_file_organization() -> organization
    - detect_anti_patterns() -> anti_patterns
    - measure_complexity_metrics() -> complexity_metrics
    """

    organization: CoreFileOrganizationResult = Field(
        default_factory=lambda: CoreFileOrganizationResult(
            status="analyzed", file_count=0
        ),
        description="File organization analysis result",
    )
    anti_patterns: list[AntiPatternInfo] = Field(
        default_factory=lambda: list[AntiPatternInfo](),
        description="Detected anti-patterns",
    )
    complexity_metrics: ComplexityAnalysisResult = Field(
        default_factory=lambda: ComplexityAnalysisResult(status="no_files"),
        description="Complexity analysis result",
    )
