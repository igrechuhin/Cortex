"""
Refactoring result and protocol return type models.

Extracted from refactoring/models.py for Phase 9.1.2 file size compliance.
"""

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel, ModelDict, OperationStatus
from cortex.core.pydantic_extra import EXTRA_ALLOW, EXTRA_FORBID

from ._base import RefactoringBaseModel, RefactoringImpactMetrics
from ._enums import (
    ExecutionStatus,
    FeedbackRecordStatus,
    MarkAppliedStatus,
    PreferenceStatus,
    RejectStatus,
    RollbackHistoryStatus,
    RollbackRefactoringStatus,
    RollbackStatus,
)
from ._execution import RefactoringExecutionModel, RollbackRecordModel
from ._suggestions import ApprovalModel, ApprovalPreferenceModel, LearnedPatternModel


class CleanupExpiredApprovalsResult(RefactoringBaseModel):
    """Result of cleaning up expired approvals."""

    status: str = Field(..., description="Operation status")
    expired_count: int = Field(..., ge=0, description="Number of expired approvals")
    expiry_days: int = Field(..., ge=0, description="Expiry threshold in days")
    message: str = Field(..., description="Human-readable message")


class ApprovalRequestResult(DictLikeModel):
    """Result of an approval request operation."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        validate_default=True,
    )

    approval_id: str = Field(..., description="Approval ID")
    status: str = Field(..., description="Request status")
    auto_approved: bool = Field(default=False, description="Whether auto-approved")
    auto_apply: bool = Field(default=False, description="Whether to auto-apply")
    message: str = Field(..., description="Status message")


class ApprovalStatusResult(RefactoringBaseModel):
    """Result of getting approval status."""

    approval_id: str = Field(..., description="Approval ID")
    status: str = Field(..., description="Approval status")
    suggestion_id: str = Field(..., description="Suggestion ID")
    suggestion_type: str = Field(..., description="Suggestion type")
    created_at: str = Field(..., description="Creation timestamp")
    approved_at: str | None = Field(default=None, description="Approval timestamp")
    user_comment: str | None = Field(default=None, description="User comment")
    requested_at: str | None = Field(
        default=None, description="ISO timestamp of request"
    )


class ApproveResult(RefactoringBaseModel):
    """Result of approving a refactoring."""

    approval_id: str = Field(..., description="Approval ID")
    status: str = Field(..., description="Approval result status")
    suggestion_id: str = Field(..., description="Suggestion ID")
    auto_apply: bool = Field(default=False, description="Whether to auto-apply")
    message: str = Field(..., description="Result message")


class RollbackResult(RefactoringBaseModel):
    """Result of a rollback operation."""

    status: RollbackStatus = Field(..., description="Rollback status")
    execution_id: str = Field(..., description="Execution ID that was rolled back")
    files_restored: int = Field(default=0, ge=0, description="Number of files restored")
    files_list: list[str] = Field(
        default_factory=list, description="List of restored files"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    timestamp: str | None = Field(default=None, description="ISO timestamp of rollback")


class RollbackHistoryEntry(RefactoringBaseModel):
    """Entry in rollback history."""

    rollback_id: str = Field(..., description="Unique rollback identifier")
    execution_id: str = Field(..., description="Associated execution ID")
    files: list[str] = Field(default_factory=list, description="Files restored")
    timestamp: str = Field(..., description="ISO timestamp of rollback")
    status: RollbackHistoryStatus = Field(..., description="Rollback status")


class FeedbackRecordResult(RefactoringBaseModel):
    """Result of recording feedback."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    status: FeedbackRecordStatus = Field(..., description="Record status")
    feedback_id: str | None = Field(default=None, description="Feedback ID if recorded")
    learning_enabled: bool = Field(
        default=True, description="Whether learning is enabled"
    )
    message: str = Field(default="Feedback recorded", description="Status message")
    learning_summary: ModelDict | None = Field(
        default=None, description="Learning insights summary"
    )


class ConfidenceAdjustmentResult(RefactoringBaseModel):
    """Result of adjusting suggestion confidence."""

    original_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Original confidence"
    )
    adjusted_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Adjusted confidence"
    )
    adjustment_factors: list[str] = Field(
        default_factory=list, description="Factors that influenced adjustment"
    )
    reason: str = Field(..., description="Reason for adjustment")


class LearningInsights(RefactoringBaseModel):
    """Learning insights and statistics."""

    model_config = ConfigDict(extra=EXTRA_ALLOW, validate_assignment=True)

    learning_enabled: bool = Field(
        default=True, description="Whether learning is enabled"
    )
    total_feedback: int = Field(default=0, ge=0, description="Total feedback count")
    approved: int = Field(default=0, ge=0, description="Number of approved suggestions")
    rejected: int = Field(default=0, ge=0, description="Number of rejected suggestions")
    approval_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Approval rate"
    )
    min_confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )
    learned_patterns: int = Field(
        default=0, ge=0, description="Number of learned patterns"
    )
    pattern_statistics: ModelDict = Field(
        default_factory=dict, description="Pattern statistics"
    )
    user_preferences: ModelDict = Field(
        default_factory=dict, description="User preference summary"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Learning recommendations"
    )
    top_patterns: list[str] = Field(
        default_factory=list, description="Top learned patterns"
    )


class RejectResult(RefactoringBaseModel):
    """Result of rejecting a refactoring suggestion."""

    status: RejectStatus = Field(..., description="Rejection status")
    approval_id: str | None = Field(default=None, description="Approval ID")
    suggestion_id: str = Field(..., description="Suggestion ID")
    message: str = Field(..., description="Status message")


class MarkAppliedResult(RefactoringBaseModel):
    """Result of marking an approval as applied."""

    status: MarkAppliedStatus = Field(..., description="Mark status")
    approval_id: str = Field(..., description="Approval ID")
    execution_id: str | None = Field(default=None, description="Execution ID")
    message: str = Field(..., description="Status message")


class PreferenceResult(RefactoringBaseModel):
    """Result of adding/removing a preference."""

    status: PreferenceStatus = Field(..., description="Operation status")
    pattern_type: str = Field(..., description="Pattern type")
    auto_approve: bool | None = Field(default=None, description="Auto-approve setting")
    message: str = Field(..., description="Status message")


class PreferencesListResult(RefactoringBaseModel):
    """Result of listing preferences."""

    preferences: list[ApprovalPreferenceModel] = Field(
        default_factory=lambda: list[ApprovalPreferenceModel](),
        description="List of preferences",
    )
    count: int = Field(default=0, ge=0, description="Number of preferences")


class PendingApprovalsResult(RefactoringBaseModel):
    """Result of listing pending approvals."""

    pending_approvals: list[ApprovalModel] = Field(
        default_factory=lambda: list[ApprovalModel](),
        description="List of pending approvals",
    )
    count: int = Field(default=0, ge=0, description="Number of pending approvals")


class ApprovalHistoryResult(RefactoringBaseModel):
    """Result of getting approval history."""

    time_range_days: int = Field(..., ge=0, description="Time range in days")
    total_approvals: int = Field(default=0, ge=0, description="Total approvals")
    approved: int = Field(default=0, ge=0, description="Approved count")
    rejected: int = Field(default=0, ge=0, description="Rejected count")
    pending: int = Field(default=0, ge=0, description="Pending count")
    applied: int = Field(default=0, ge=0, description="Applied count")
    approval_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Approval rate"
    )
    approvals: list[ApprovalModel] = Field(
        default_factory=lambda: list[ApprovalModel](), description="List of approvals"
    )


class CleanupExpiredResult(RefactoringBaseModel):
    """Result of cleaning up expired approvals."""

    status: OperationStatus = Field(..., description="Cleanup status")
    expired_count: int = Field(default=0, ge=0, description="Number expired")
    expiry_days: int = Field(..., ge=0, description="Expiry threshold in days")
    message: str = Field(..., description="Status message")


class RollbackRefactoringResult(RefactoringBaseModel):
    """Result of rolling back a refactoring execution."""

    status: RollbackRefactoringStatus = Field(..., description="Rollback status")
    rollback_id: str = Field(..., description="Rollback ID")
    execution_id: str | None = Field(default=None, description="Execution ID")
    files_restored: int = Field(default=0, ge=0, description="Number of files restored")
    conflicts_detected: int = Field(
        default=0, ge=0, description="Number of conflicts detected"
    )
    conflicts: list[str] = Field(
        default_factory=list, description="List of conflicting files"
    )
    dry_run: bool = Field(default=False, description="Whether it was a dry run")
    error: str | None = Field(default=None, description="Error message if failed")


class RollbackHistoryResult(RefactoringBaseModel):
    """Result of getting rollback history."""

    time_range_days: int = Field(..., ge=0, description="Time range in days")
    total_rollbacks: int = Field(default=0, ge=0, description="Total rollbacks")
    successful: int = Field(default=0, ge=0, description="Successful rollbacks")
    failed: int = Field(default=0, ge=0, description="Failed rollbacks")
    rollbacks: list[RollbackRecordModel] = Field(
        default_factory=lambda: list[RollbackRecordModel](),
        description="List of rollbacks",
    )


class RollbackImpactResult(RefactoringBaseModel):
    """Result of analyzing rollback impact."""

    status: OperationStatus = Field(..., description="Analysis status")
    execution_id: str = Field(..., description="Execution ID")
    total_files: int = Field(default=0, ge=0, description="Total files affected")
    conflicts_count: int = Field(default=0, ge=0, description="Number of conflicts")
    can_rollback_all: bool = Field(
        default=True, description="Whether all files can be rolled back"
    )
    affected_files: list[str] = Field(
        default_factory=list, description="Files that would be affected"
    )
    conflicts: list[str] = Field(
        default_factory=list, description="Potential conflicts"
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings")
    message: str | None = Field(default=None, description="Status message")
    error: str | None = Field(
        default=None, description="Error message if analysis failed"
    )


class ResetLearningResult(RefactoringBaseModel):
    """Result of resetting learning data."""

    status: OperationStatus = Field(..., description="Reset status")
    message: str = Field(..., description="Status message")
    feedback_reset: int = Field(default=0, ge=0, description="Feedback records reset")
    patterns_reset: int = Field(default=0, ge=0, description="Patterns reset")
    preferences_reset: int = Field(default=0, ge=0, description="Preferences reset")


class ExportedPatterns(RefactoringBaseModel):
    """Exported patterns structure."""

    consolidation: list[LearnedPatternModel] = Field(
        default_factory=lambda: list[LearnedPatternModel](),
        description="Consolidation patterns",
    )
    split: list[LearnedPatternModel] = Field(
        default_factory=lambda: list[LearnedPatternModel](),
        description="Split patterns",
    )
    reorganization: list[LearnedPatternModel] = Field(
        default_factory=lambda: list[LearnedPatternModel](),
        description="Reorganization patterns",
    )


class ExportPatternsResult(RefactoringBaseModel):
    """Result of exporting learned patterns."""

    status: OperationStatus = Field(..., description="Export status")
    format: str = Field(..., description="Export format")
    patterns_count: int = Field(
        default=0, ge=0, description="Number of patterns exported"
    )
    content: str | None = Field(
        default=None, description="Exported content (for text format)"
    )
    patterns: ExportedPatterns = Field(
        default_factory=ExportedPatterns,
        description="Exported patterns (for json format)",
    )


class ActionPreviewModel(RefactoringBaseModel):
    """Preview information for a single refactoring action."""

    action_type: str = Field(..., description="Type of action")
    target_file: str = Field(..., description="Target file path")
    description: str = Field(..., description="Action description")
    preview: str | None = Field(default=None, description="Preview of changes")


class RefactoringPreviewModel(RefactoringBaseModel):
    """Preview information for a refactoring suggestion."""

    suggestion_id: str = Field(..., description="Suggestion ID")
    title: str = Field(..., description="Suggestion title")
    refactoring_type: str = Field(..., description="Type of refactoring")
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected"
    )
    actions_count: int = Field(default=0, ge=0, description="Number of actions")
    estimated_impact: RefactoringImpactMetrics | None = Field(
        default=None, description="Estimated impact metrics"
    )
    actions: list[ActionPreviewModel] = Field(
        default_factory=lambda: list[ActionPreviewModel](),
        description="Action previews",
    )


class RefactoringPreviewErrorModel(RefactoringBaseModel):
    """Error result when preview fails."""

    error: str = Field(..., description="Error message")


class ExtractedInsightData(RefactoringBaseModel):
    """Data extracted from an insight for refactoring suggestions."""

    title: str = Field(default="", description="Insight title")
    description: str = Field(default="", description="Insight description")
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Impact score")
    severity: str = Field(default="medium", description="Severity level")
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )
    affected_files: list[str] = Field(
        default_factory=list, description="Affected files"
    )
    valid: bool = Field(default=False, description="Whether data is valid")


class ExecutionResult(RefactoringBaseModel):
    """Result of executing a refactoring."""

    status: ExecutionStatus = Field(..., description="Execution status")
    execution_id: str = Field(..., description="Execution ID")
    suggestion_id: str | None = Field(default=None, description="Suggestion ID")
    approval_id: str | None = Field(default=None, description="Approval ID")
    operations_completed: int = Field(
        default=0, ge=0, description="Number of operations completed"
    )
    snapshot_id: str | None = Field(
        default=None, description="Snapshot ID for rollback"
    )
    actual_impact: RefactoringImpactMetrics = Field(
        default_factory=RefactoringImpactMetrics, description="Actual impact metrics"
    )
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation errors"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    dry_run: bool = Field(default=False, description="Whether it was a dry run")
    rollback_available: bool = Field(
        default=False, description="Whether rollback is available"
    )


class ExecutionHistoryResult(RefactoringBaseModel):
    """Result of getting execution history."""

    time_range_days: int = Field(..., ge=0, description="Time range in days")
    total_executions: int = Field(default=0, ge=0, description="Total executions")
    successful: int = Field(default=0, ge=0, description="Successful executions")
    failed: int = Field(default=0, ge=0, description="Failed executions")
    rolled_back: int = Field(default=0, ge=0, description="Rolled back executions")
    executions: list[RefactoringExecutionModel] = Field(
        default_factory=lambda: list[RefactoringExecutionModel](),
        description="List of executions",
    )


class ExecutionStatsResult(RefactoringBaseModel):
    """Result of getting execution statistics."""

    total_executions: int = Field(default=0, ge=0, description="Total executions")
    successful: int = Field(default=0, ge=0, description="Successful executions")
    failed: int = Field(default=0, ge=0, description="Failed executions")
    rolled_back: int = Field(default=0, ge=0, description="Rolled back executions")
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Success rate")
    files_modified: int = Field(default=0, ge=0, description="Total files modified")
    token_savings: int = Field(default=0, ge=0, description="Total token savings")
