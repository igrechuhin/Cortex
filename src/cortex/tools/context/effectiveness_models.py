"""
Models for context analysis operations (usage statistics, insights, cleanup report,
session analysis, rules execution, learned patterns).
"""

from __future__ import annotations

from enum import Enum

from pydantic import ConfigDict, Field, field_validator

from cortex.core.models import JsonDict, OperationStatus
from cortex.tools.models_base import StrictBaseModel
from cortex.tools.structure_models import CleanupActionResult


class ContextAnalysisStatus(str, Enum):
    """Status for context analysis results."""

    SUCCESS = "success"
    NO_DATA = "no_data"


class ContextUsageEntry(StrictBaseModel):
    """Structure for a single context usage analysis entry."""

    session_id: str = Field(..., description="Session identifier")
    timestamp: str = Field(..., description="Timestamp of the load_context call")
    task_description: str = Field(..., description="Task description")
    token_budget: int = Field(..., ge=0, description="Token budget allocated")
    total_tokens: int = Field(..., ge=0, description="Total tokens used")
    utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Token utilization ratio"
    )
    files_selected: int = Field(..., ge=0, description="Number of files selected")
    files_excluded: int = Field(..., ge=0, description="Number of files excluded")
    avg_relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    files_with_high_relevance: int = Field(
        ..., ge=0, description="Number of files with relevance score > 0.7"
    )
    files_with_low_relevance: int = Field(
        ..., ge=0, description="Number of files with relevance score < 0.3"
    )
    selected_file_names: list[str] | None = Field(
        None, description="List of selected file names for tracking"
    )
    relevance_by_file: dict[str, float] | None = Field(
        None, description="Relevance scores by file name"
    )
    role: str | None = Field(
        default=None,
        description="Agent role (feature/quality/testing/docs/planning/debugging/review)",
    )


class TaskTypeInsight(StrictBaseModel):
    """Insights for a specific task type."""

    calls_count: int = Field(
        ..., ge=0, description="Number of calls for this task type"
    )
    recommended_budget: int = Field(..., ge=0, description="Recommended token budget")
    essential_files: list[str] = Field(
        default_factory=list, description="Essential files for this task type"
    )
    avg_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Average utilization"
    )
    avg_relevance: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    notes: str = Field(..., description="Notes and recommendations")


class FileEffectiveness(StrictBaseModel):
    """Effectiveness tracking for a specific file."""

    times_selected: int = Field(
        ..., ge=0, description="Number of times file was selected"
    )
    avg_relevance: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    task_types_used: list[str] = Field(
        default_factory=list, description="Task types that used this file"
    )
    recommendation: str = Field(..., description="Recommendation for this file")


class ContextInsights(StrictBaseModel):
    """Actionable insights derived from statistics."""

    task_type_recommendations: dict[str, TaskTypeInsight] = Field(
        default_factory=dict, description="Recommendations by task type"
    )
    file_effectiveness: dict[str, FileEffectiveness] = Field(
        default_factory=dict, description="Effectiveness by file"
    )
    learned_patterns: list[str] = Field(
        default_factory=list, description="Learned usage patterns"
    )
    budget_recommendations: dict[str, int] = Field(
        default_factory=dict, description="Budget recommendations by task type"
    )
    role_recommendations: dict[str, TaskTypeInsight] = Field(
        default_factory=dict,
        description="Recommendations by agent role (feature/quality/testing/docs/planning/debugging/review)",
    )
    role_budget_recommendations: dict[str, int] = Field(
        default_factory=dict, description="Budget recommendations by agent role"
    )


class ContextUsageStatistics(StrictBaseModel):
    """Structure for aggregated context usage statistics."""

    last_updated: str = Field(..., description="Last update timestamp")
    total_sessions_analyzed: int = Field(
        ..., ge=0, description="Total sessions analyzed"
    )
    total_load_context_calls: int = Field(
        ..., ge=0, description="Total load_context calls"
    )
    avg_token_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Average token utilization"
    )
    avg_files_selected: float = Field(..., ge=0.0, description="Average files selected")
    avg_relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    common_task_patterns: dict[str, int] = Field(
        default_factory=dict, description="Common task patterns and their counts"
    )
    insights: ContextInsights | None = Field(
        None, description="Actionable insights derived from statistics"
    )
    entries: list[ContextUsageEntry] = Field(
        default_factory=lambda: list[ContextUsageEntry](),
        description="Individual context usage entries",
    )


class SessionStats(StrictBaseModel):
    """Statistics for a single session's context usage."""

    calls_count: int = Field(..., ge=0, description="Number of load_context calls")
    avg_token_utilization: float = Field(
        ..., ge=0.0, le=1.0, description="Average token utilization"
    )
    avg_files_selected: float = Field(..., ge=0.0, description="Average files selected")
    avg_relevance_score: float = Field(
        ..., ge=0.0, le=1.0, description="Average relevance score"
    )
    task_patterns: dict[str, int] = Field(
        default_factory=dict, description="Task patterns and their counts"
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

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def _coerce_context_analysis_status(
    v: ContextAnalysisStatus | str,
) -> ContextAnalysisStatus:
    """Coerce str to ContextAnalysisStatus for validation from JSON/dict (strict mode)."""
    if isinstance(v, ContextAnalysisStatus):
        return v
    return ContextAnalysisStatus(v)


class CurrentSessionAnalysisResult(StrictBaseModel):
    """Result of analyzing current session's context usage."""

    status: ContextAnalysisStatus = Field(description="Analysis status")

    @field_validator("status", mode="before")
    @classmethod
    def _status_enum(cls, v: ContextAnalysisStatus | str) -> ContextAnalysisStatus:
        return _coerce_context_analysis_status(v)

    session_id: str | None = Field(None, description="Current session ID")
    current_session: JsonDict | None = Field(
        None, description="Current session data (calls, statistics, entries)"
    )
    global_statistics_updated: bool | None = Field(
        None, description="Whether global statistics were updated"
    )
    new_entries_added: int | None = Field(
        None, ge=0, description="Number of new entries added"
    )
    total_sessions: int | None = Field(
        None, ge=0, description="Total sessions analyzed"
    )
    total_entries: int | None = Field(None, ge=0, description="Total entries")
    insights: JsonDict | None = Field(None, description="Context insights")
    message: str | None = Field(None, description="Status message for no_data case")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SessionLogsAnalysisResult(StrictBaseModel):
    """Result of analyzing session logs."""

    status: ContextAnalysisStatus = Field(description="Analysis status")

    @field_validator("status", mode="before")
    @classmethod
    def _status_enum(cls, v: ContextAnalysisStatus | str) -> ContextAnalysisStatus:
        return _coerce_context_analysis_status(v)

    new_sessions_analyzed: int | None = Field(
        None, ge=0, description="Number of new sessions analyzed"
    )
    new_entries_added: int | None = Field(
        None, ge=0, description="Number of new entries added"
    )
    total_sessions: int | None = Field(
        None, ge=0, description="Total sessions analyzed"
    )
    total_entries: int | None = Field(None, ge=0, description="Total entries")
    statistics: JsonDict | None = Field(
        None, description="Aggregated statistics (avg_token_utilization, etc.)"
    )
    insights: JsonDict | None = Field(None, description="Context insights")
    message: str | None = Field(None, description="Status message for no_data case")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ContextStatisticsResult(StrictBaseModel):
    """Result of getting context usage statistics."""

    status: ContextAnalysisStatus = Field(description="Status")

    @field_validator("status", mode="before")
    @classmethod
    def _status_enum(cls, v: ContextAnalysisStatus | str) -> ContextAnalysisStatus:
        return _coerce_context_analysis_status(v)

    last_updated: str | None = Field(None, description="Last update timestamp")
    total_sessions: int | None = Field(None, ge=0, description="Total sessions")
    total_calls: int | None = Field(None, ge=0, description="Total load_context calls")
    statistics: JsonDict | None = Field(
        None, description="Aggregated statistics (avg_token_utilization, etc.)"
    )
    insights: JsonDict | None = Field(None, description="Context insights")
    recent_entries: list[JsonDict] | None = Field(
        None, description="Last 10 context usage entries"
    )
    message: str | None = Field(None, description="Status message for no_data case")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RulesExecutionResult(StrictBaseModel):
    """Result of executing rules with context."""

    status: OperationStatus = Field(description="Execution status")
    task_description: str | None = Field(None, description="Task description")
    context: JsonDict | None = Field(None, description="Context information")
    rules_loaded: JsonDict | None = Field(
        None, description="Rules loaded (generic, language, local)"
    )
    total_tokens: int | None = Field(None, ge=0, description="Total tokens used")
    token_budget: int | None = Field(None, ge=0, description="Token budget")
    source: str | None = Field(None, description="Rules source")
    error: str | None = Field(None, description="Error message if status is error")

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class LearnedPatternsResult(StrictBaseModel):
    """Result containing learned patterns dictionary."""

    patterns: dict[str, JsonDict] = Field(
        default_factory=dict, description="Dictionary of pattern_id -> pattern data"
    )

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
