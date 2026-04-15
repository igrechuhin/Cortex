"""
Refactoring configuration and protocol parameter models.

Extracted from refactoring/models.py for Phase 9.1.2 file size compliance.
"""

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel
from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID

from ._base import RefactoringBaseModel
from ._enums import LearningRate
from ._execution import RollbackRecordModel
from ._suggestions import ApprovalModel, ApprovalPreferenceModel


class ApprovalManagerConfig(RefactoringBaseModel):
    """Configuration for ApprovalManager."""

    auto_approve_enabled: bool = Field(
        default=True, description="Whether auto-approval is enabled"
    )
    default_expiry_days: int = Field(
        default=30, ge=1, description="Default expiry days for pending approvals"
    )
    max_pending_approvals: int = Field(
        default=100, ge=1, description="Maximum pending approvals to keep"
    )


class ApprovalFileData(RefactoringBaseModel):
    """Structure of approval history file."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    last_updated: str = Field(..., description="ISO timestamp of last update")
    approvals: dict[str, ApprovalModel] = Field(
        default_factory=dict, description="Approval records by ID"
    )
    preferences: list[ApprovalPreferenceModel] = Field(
        default_factory=lambda: list[ApprovalPreferenceModel](),
        description="User preferences",
    )


class RollbackManagerConfig(RefactoringBaseModel):
    """Configuration for RollbackManager."""

    preserve_manual_edits: bool = Field(
        default=True, description="Whether to preserve manual edits during rollback"
    )
    max_rollback_history: int = Field(
        default=50, ge=1, description="Maximum rollback history entries to keep"
    )


class RollbackFileData(RefactoringBaseModel):
    """Structure of rollback history file."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    last_updated: str = Field(..., description="ISO timestamp of last update")
    rollbacks: dict[str, RollbackRecordModel] = Field(
        default_factory=dict, description="Rollback records by ID"
    )


class LearningEngineConfig(RefactoringBaseModel):
    """Configuration for LearningEngine."""

    learning_enabled: bool = Field(
        default=True, description="Whether learning is enabled"
    )
    min_feedback_for_pattern: int = Field(
        default=3, ge=1, description="Minimum feedback count to create pattern"
    )
    confidence_decay_rate: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Rate at which confidence decays"
    )


class RefactoringExecutorConfig(RefactoringBaseModel):
    """Configuration for RefactoringExecutor."""

    dry_run_by_default: bool = Field(
        default=False, description="Whether to run in dry-run mode by default"
    )
    validate_before_execute: bool = Field(
        default=True, description="Whether to validate before execution"
    )
    create_snapshots: bool = Field(
        default=True, description="Whether to create snapshots before execution"
    )


class ApprovalRequestDetails(RefactoringBaseModel):
    """Details for an approval request."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    suggestion_type: str = Field(description="Type of refactoring suggestion")
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected by the refactoring"
    )
    estimated_impact: str = Field(
        default="", description="Estimated impact description"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score"
    )
    description: str = Field(default="", description="Refactoring description")


class SuggestionData(RefactoringBaseModel):
    """Data for a refactoring suggestion used in learning."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    suggestion_id: str = Field(description="Unique suggestion identifier")
    suggestion_type: str = Field(description="Type of suggestion")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence score"
    )
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected"
    )
    pattern_type: str | None = Field(
        default=None, description="Pattern type for learning"
    )


class FeedbackData(RefactoringBaseModel):
    """Additional data for feedback recording."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    user_comment: str | None = Field(default=None, description="User comment")
    execution_time_ms: int | None = Field(
        default=None, ge=0, description="Execution time in milliseconds"
    )
    files_modified: list[str] = Field(
        default_factory=list, description="Files that were modified"
    )


class SuggestionTypePreference(RefactoringBaseModel):
    """User preference for a suggestion type (e.g., consolidation, split)."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    total: int = Field(default=0, ge=0, description="Total feedback count")
    approved: int = Field(default=0, ge=0, description="Approved count")
    rejected: int = Field(default=0, ge=0, description="Rejected count")
    preference_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Preference score 0-1"
    )


class PreferenceSummary(RefactoringBaseModel):
    """Summary of user preference for a suggestion type."""

    preference_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Preference score 0-1"
    )
    total_feedback: int = Field(default=0, ge=0, description="Total feedback count")
    recommendation: str = Field(
        default="Not enough data yet", description="Recommendation text"
    )


class LearningPreferences(RefactoringBaseModel):
    """User preferences for learning engine."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    min_confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )
    suggestion_type_consolidation: SuggestionTypePreference | None = Field(
        default=None, description="Preferences for consolidation suggestions"
    )
    suggestion_type_split: SuggestionTypePreference | None = Field(
        default=None, description="Preferences for split suggestions"
    )
    suggestion_type_reorganization: SuggestionTypePreference | None = Field(
        default=None, description="Preferences for reorganization suggestions"
    )
    suggestion_type_transclusion: SuggestionTypePreference | None = Field(
        default=None, description="Preferences for transclusion suggestions"
    )
    suggestion_type_rename: SuggestionTypePreference | None = Field(
        default=None, description="Preferences for rename suggestions"
    )
    suggestion_type_merge: SuggestionTypePreference | None = Field(
        default=None, description="Preferences for merge suggestions"
    )

    def get_suggestion_preference(
        self, suggestion_type: str
    ) -> SuggestionTypePreference | None:
        """Get preference for a suggestion type."""
        attr_name = f"suggestion_type_{suggestion_type}"
        return getattr(self, attr_name, None)

    def set_suggestion_preference(
        self, suggestion_type: str, pref: SuggestionTypePreference
    ) -> None:
        """Set preference for a suggestion type."""
        attr_name = f"suggestion_type_{suggestion_type}"
        if hasattr(self, attr_name):
            setattr(self, attr_name, pref)


class ConfidenceAdjustmentDetails(RefactoringBaseModel):
    """Details of confidence adjustment calculation."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    adjustments: list[str] = Field(
        default_factory=list, description="List of adjustment descriptions"
    )
    reason: str = Field(
        default="Adjusted based on learned patterns", description="Overall reason"
    )
    pattern_match: bool = Field(default=False, description="Whether a pattern matched")
    pattern_id: str | None = Field(default=None, description="Matched pattern ID")


class SuggestionInput(RefactoringBaseModel):
    """Input suggestion for confidence adjustment and filtering."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    suggestion_id: str | None = Field(default=None, description="Suggestion identifier")
    type: str | None = Field(default=None, description="Suggestion type")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence score"
    )
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected"
    )


class SuggestionDetails(RefactoringBaseModel):
    """Details about a suggestion for pattern extraction."""

    model_config = ConfigDict(extra=EXTRA_ALLOW)

    type: str | None = Field(default=None, description="Suggestion type")
    similarity_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for consolidation",
    )
    min_token_savings: int | None = Field(
        default=None, ge=0, description="Minimum token savings"
    )
    file_tokens: int | None = Field(
        default=None, ge=0, description="File token count for split suggestions"
    )
    optimization_goal: str | None = Field(
        default=None, description="Optimization goal for reorganization suggestions"
    )
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected"
    )
    sections: list[str] = Field(default_factory=list, description="Sections affected")
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Suggestion confidence score"
    )


class InsightDataModel(RefactoringBaseModel):
    """Insight data for refactoring suggestion generation."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    duplicated_content: list[dict[str, str]] = Field(
        default_factory=lambda: list[dict[str, str]](),
        description="List of duplicated content entries",
    )
    large_files: list[dict[str, str | int]] = Field(
        default_factory=lambda: list[dict[str, str | int]](),
        description="List of large files with metadata",
    )
    unused_files: list[str] = Field(
        default_factory=lambda: list[str](),
        description="List of unused file paths",
    )
    complexity_hotspots: list[dict[str, str | float]] = Field(
        default_factory=lambda: list[dict[str, str | float]](),
        description="List of complexity hotspots",
    )
    dependency_issues: list[dict[str, str]] = Field(
        default_factory=lambda: list[dict[str, str]](),
        description="List of dependency issues",
    )


class AnalysisDataModel(RefactoringBaseModel):
    """Analysis data for refactoring suggestion generation."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    file_sizes: dict[str, int] = Field(
        default_factory=dict, description="File sizes in bytes"
    )
    file_tokens: dict[str, int] = Field(
        default_factory=dict, description="File token counts"
    )
    dependency_graph: dict[str, list[str]] = Field(
        default_factory=dict, description="Dependency graph structure"
    )
    access_patterns: dict[str, int] = Field(
        default_factory=dict, description="File access frequency patterns"
    )
    structure_metrics: dict[str, int | float] = Field(
        default_factory=dict, description="Structure complexity metrics"
    )


class LearningConfigModel(RefactoringBaseModel):
    """Learning configuration settings."""

    enabled: bool = Field(default=True, description="Whether learning is enabled")
    learning_rate: LearningRate = Field(
        default=LearningRate.CONSERVATIVE, description="Learning rate setting"
    )
    remember_rejections: bool = Field(
        default=True, description="Remember rejected suggestions"
    )
    adapt_suggestions: bool = Field(
        default=True, description="Adapt suggestions based on learning"
    )
    export_patterns: bool = Field(default=False, description="Export learned patterns")
    min_feedback_count: int = Field(
        default=5, ge=1, description="Minimum feedback before adapting"
    )
    confidence_adjustment_limit: float = Field(
        default=0.2, ge=0.0, le=1.0, description="Maximum confidence adjustment"
    )


class FeedbackConfigModel(RefactoringBaseModel):
    """Feedback collection configuration."""

    collect_feedback: bool = Field(
        default=True, description="Whether to collect feedback"
    )
    prompt_for_feedback: bool = Field(
        default=False, description="Prompt user for feedback"
    )
    feedback_types: list[str] = Field(
        default_factory=lambda: ["helpful", "not_helpful", "incorrect"],
        description="Available feedback types",
    )
    allow_comments: bool = Field(
        default=True, description="Allow comments with feedback"
    )


class PatternRecognitionConfigModel(RefactoringBaseModel):
    """Pattern recognition configuration."""

    enabled: bool = Field(
        default=True, description="Whether pattern recognition is enabled"
    )
    min_pattern_occurrences: int = Field(
        default=3, ge=1, description="Minimum pattern occurrences"
    )
    pattern_confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Pattern confidence threshold"
    )
    forget_old_patterns_days: int = Field(
        default=90, ge=1, description="Days before forgetting old patterns"
    )


class AdaptationBehaviorConfigModel(RefactoringBaseModel):
    """Adaptation behavior configuration."""

    auto_adjust_thresholds: bool = Field(
        default=True, description="Auto-adjust thresholds"
    )
    min_confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )
    max_confidence_threshold: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Maximum confidence threshold"
    )
    threshold_adjustment_step: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Threshold adjustment step size"
    )
    adapt_to_user_style: bool = Field(default=True, description="Adapt to user style")


class SuggestionFilteringConfigModel(RefactoringBaseModel):
    """Suggestion filtering configuration."""

    filter_by_learned_patterns: bool = Field(
        default=True, description="Filter by learned patterns"
    )
    filter_by_user_preferences: bool = Field(
        default=True, description="Filter by user preferences"
    )
    show_filtered_count: bool = Field(
        default=True, description="Show count of filtered suggestions"
    )
    allow_override: bool = Field(
        default=True, description="Allow users to override filtering"
    )


class SelfEvolutionAdaptationConfigModel(RefactoringBaseModel):
    """Self-evolution configuration for adaptation."""

    learning: LearningConfigModel = Field(
        default_factory=LearningConfigModel, description="Learning configuration"
    )
    feedback: FeedbackConfigModel = Field(
        default_factory=FeedbackConfigModel, description="Feedback configuration"
    )
    pattern_recognition: PatternRecognitionConfigModel = Field(
        default_factory=PatternRecognitionConfigModel,
        description="Pattern recognition configuration",
    )
    adaptation: AdaptationBehaviorConfigModel = Field(
        default_factory=AdaptationBehaviorConfigModel,
        description="Adaptation behavior configuration",
    )
    suggestion_filtering: SuggestionFilteringConfigModel = Field(
        default_factory=SuggestionFilteringConfigModel,
        description="Suggestion filtering configuration",
    )


class AdaptationConfigModel(RefactoringBaseModel):
    """Complete adaptation configuration model."""

    self_evolution: SelfEvolutionAdaptationConfigModel = Field(
        default_factory=SelfEvolutionAdaptationConfigModel,
        description="Self-evolution configuration",
    )


class AdaptationValidationResult(DictLikeModel):
    """Result of adaptation configuration validation."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )

    valid: bool = Field(..., description="Whether configuration is valid")
    issues: list[str] = Field(default_factory=list, description="Validation issues")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class AdaptationSummary(DictLikeModel):
    """Summary of adaptation configuration settings."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )

    learning_enabled: bool = Field(..., description="Whether learning is enabled")
    learning_rate: str = Field(..., description="Learning rate setting")
    min_confidence_threshold: float = Field(
        ..., description="Minimum confidence threshold"
    )
    max_confidence_threshold: float = Field(
        ..., description="Maximum confidence threshold"
    )
    pattern_recognition_enabled: bool = Field(
        ..., description="Whether pattern recognition is enabled"
    )
    feedback_collection_enabled: bool = Field(
        ..., description="Whether feedback collection is enabled"
    )
    auto_adjust_thresholds: bool = Field(
        ..., description="Whether thresholds are auto-adjusted"
    )
    adapt_to_user_style: bool = Field(
        ..., description="Whether system adapts to user style"
    )
    filter_by_learned_patterns: bool = Field(
        ..., description="Whether suggestions are filtered by learned patterns"
    )
    filter_by_user_preferences: bool = Field(
        ..., description="Whether suggestions are filtered by user preferences"
    )
