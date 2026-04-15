"""
Refactoring suggestion, consolidation, split, approval, and learning models.

Extracted from refactoring/models.py for Phase 9.1.2 file size compliance.
"""

from datetime import datetime

from pydantic import ConfigDict, Field

from cortex.core.models import RiskLevel
from cortex.core.pydantic_extra import EXTRA_FORBID

from ._base import (
    ActionDetails,
    RefactoringBaseModel,
    RefactoringImpactMetrics,
    RefactoringMetadata,
)
from ._enums import ApprovalStatus, RefactoringPriority, RefactoringType


class RefactoringActionModel(RefactoringBaseModel):
    """Represents a specific action in a refactoring."""

    action_type: str = Field(
        ..., description="Action type: move, create, delete, modify, rename"
    )
    target_file: str = Field(..., description="Target file path")
    description: str = Field(..., description="Action description")
    details: ActionDetails = Field(
        default_factory=ActionDetails, description="Additional details"
    )


class RefactoringSuggestionModel(RefactoringBaseModel):
    """Represents a refactoring suggestion."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
    )

    suggestion_id: str = Field(..., description="Unique suggestion identifier")
    refactoring_type: RefactoringType = Field(..., description="Type of refactoring")
    priority: RefactoringPriority = Field(..., description="Priority level")
    title: str = Field(..., description="Suggestion title")
    description: str = Field(..., description="Detailed description")
    reasoning: str = Field(..., description="Reasoning for suggestion")
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected"
    )
    actions: list[RefactoringActionModel] = Field(
        default_factory=lambda: list[RefactoringActionModel](),
        description="Actions to perform",
    )
    estimated_impact: RefactoringImpactMetrics = Field(
        default_factory=RefactoringImpactMetrics, description="Estimated impact metrics"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score 0-1"
    )
    metadata: RefactoringMetadata = Field(
        default_factory=RefactoringMetadata, description="Additional metadata"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp of creation",
    )


class ConsolidationOpportunityModel(RefactoringBaseModel):
    """Represents an opportunity to consolidate content."""

    opportunity_id: str = Field(..., description="Unique opportunity identifier")
    opportunity_type: str = Field(
        ..., description="Type: exact_duplicate, similar_content, shared_section"
    )
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected"
    )
    common_content: str = Field(..., description="Common content found")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score 0-1"
    )
    token_savings: int = Field(..., ge=0, description="Estimated token savings")
    suggested_action: str = Field(..., description="Suggested action")
    extraction_target: str = Field(..., description="Where to extract common content")
    transclusion_syntax: list[str] = Field(
        default_factory=list, description="Transclusion syntax for each file"
    )
    details: ActionDetails = Field(
        default_factory=ActionDetails, description="Additional details"
    )


class ConsolidationImpactModel(RefactoringBaseModel):
    """Impact analysis for applying a consolidation."""

    opportunity_id: str = Field(..., description="Opportunity identifier")
    token_savings: int = Field(..., ge=0, description="Token savings")
    files_affected: int = Field(..., ge=0, description="Number of files affected")
    extraction_required: bool = Field(
        default=True, description="Whether extraction is required"
    )
    transclusion_count: int = Field(..., ge=0, description="Number of transclusions")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    risk_level: RiskLevel = Field(..., description="Risk level")
    benefits: list[str] = Field(default_factory=list, description="List of benefits")
    risks: list[str] = Field(default_factory=list, description="List of risks")


class ParsedSectionModel(RefactoringBaseModel):
    """Represents a parsed markdown section."""

    heading: str = Field(..., description="Section heading text")
    level: int = Field(..., ge=1, le=6, description="Heading level (1-6)")
    start_line: int = Field(..., ge=1, description="Start line number")
    end_line: int | None = Field(default=None, description="End line number")
    content: str = Field(default="", description="Section content")


class SplitPointModel(RefactoringBaseModel):
    """Represents a potential point to split a file."""

    section_heading: str = Field(..., description="Section heading")
    start_line: int = Field(..., ge=1, description="Start line number")
    end_line: int = Field(..., ge=1, description="End line number")
    token_count: int = Field(..., ge=0, description="Token count")
    independence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Independence score 0-1"
    )
    suggested_filename: str = Field(..., description="Suggested filename")
    split_id: str | None = Field(default=None, description="Split point ID")
    section_title: str | None = Field(default=None, description="Section title (alias)")
    line_number: int | None = Field(
        default=None, ge=1, description="Line number (alias)"
    )


class SplitFileAnalysisResult(RefactoringBaseModel):
    """Result of analyzing a file for splitting opportunities."""

    file: str = Field(..., description="File path analyzed")
    size: int = Field(..., ge=0, description="File size in bytes")
    should_split: bool = Field(..., description="Whether file should be split")
    reason: str = Field(..., description="Reason for split recommendation")
    split_points: list[SplitPointModel] = Field(
        default_factory=lambda: list[SplitPointModel](),
        description="Suggested split points",
    )


class SplitStructure(RefactoringBaseModel):
    """Proposed structure after split."""

    new_files: list[str] = Field(
        default_factory=list, description="New files to be created"
    )
    sections_per_file: dict[str, list[str]] = Field(
        default_factory=dict, description="Sections assigned to each new file"
    )
    tokens_per_file: dict[str, int] = Field(
        default_factory=dict, description="Token count per new file"
    )


class SplitFileInfo(RefactoringBaseModel):
    """Information about a file to be created from a split."""

    filename: str = Field(..., description="Filename for the split file")
    heading: str = Field(..., description="Section heading")
    tokens: int = Field(..., ge=0, description="Token count")
    lines: str = Field(..., description="Line range (e.g., '10-50')")


class SplitIndexFile(RefactoringBaseModel):
    """Information about the index file after a split."""

    filename: str = Field(..., description="Index file path")
    purpose: str = Field(..., description="Purpose of the index file")
    tokens: int = Field(..., ge=0, description="Estimated token count")
    content_summary: str = Field(..., description="Summary of index content")


class NewSplitStructure(RefactoringBaseModel):
    """Proposed new file structure after split."""

    index_file: SplitIndexFile = Field(..., description="Index file information")
    split_files: list[SplitFileInfo] = Field(
        default_factory=lambda: list[SplitFileInfo](),
        description="Files to be created from split",
    )
    total_files: int = Field(..., ge=1, description="Total number of files")


class SplitImpactMetrics(RefactoringBaseModel):
    """Impact metrics for applying a file split."""

    original_file_tokens: int = Field(
        ..., ge=0, description="Original file token count"
    )
    new_file_count: int = Field(..., ge=1, description="Number of new files")
    average_file_size: int = Field(..., ge=0, description="Average file size in tokens")
    complexity_reduction: float = Field(
        ..., ge=0.0, le=1.0, description="Complexity reduction factor"
    )
    maintainability_improvement: float = Field(
        ..., ge=0.0, le=1.0, description="Maintainability improvement factor"
    )
    context_loading_improvement: float = Field(
        ..., ge=0.0, le=1.0, description="Context loading improvement factor"
    )
    benefits: list[str] = Field(default_factory=list, description="List of benefits")
    considerations: list[str] = Field(
        default_factory=list, description="Considerations/caveats"
    )


class SplitRecommendationModel(RefactoringBaseModel):
    """Represents a recommendation to split a file."""

    recommendation_id: str = Field(..., description="Unique recommendation identifier")
    file_path: str = Field(..., description="File path to split")
    reason: str = Field(..., description="Reason for split")
    split_strategy: str = Field(
        ..., description="Strategy: by_size, by_sections, by_topics, by_dependencies"
    )
    split_points: list[SplitPointModel] = Field(
        default_factory=lambda: list[SplitPointModel](), description="Split points"
    )
    estimated_impact: SplitImpactMetrics | RefactoringImpactMetrics = Field(
        default_factory=RefactoringImpactMetrics, description="Estimated impact"
    )
    new_structure: NewSplitStructure | SplitStructure = Field(
        default_factory=SplitStructure, description="Proposed new structure"
    )
    maintain_dependencies: bool = Field(
        default=True, description="Whether to maintain dependencies"
    )


class ApprovalModel(RefactoringBaseModel):
    """Approval record for a refactoring suggestion."""

    approval_id: str = Field(..., description="Unique approval identifier")
    suggestion_id: str = Field(..., description="Associated suggestion ID")
    suggestion_type: str = Field(..., description="Type of suggestion")
    status: ApprovalStatus = Field(..., description="Approval status")
    created_at: str = Field(..., description="ISO timestamp of creation")
    approved_at: str | None = Field(
        default=None, description="ISO timestamp of approval"
    )
    applied_at: str | None = Field(
        default=None, description="ISO timestamp of application"
    )
    user_comment: str | None = Field(default=None, description="User comment")
    auto_apply: bool = Field(default=False, description="Whether to auto-apply")
    execution_id: str | None = Field(
        default=None, description="Associated execution ID"
    )


class ApprovalConditions(RefactoringBaseModel):
    """Conditions for auto-approval."""

    min_confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Minimum confidence score"
    )
    max_files_affected: int | None = Field(
        default=None, ge=1, description="Maximum files affected"
    )
    max_token_impact: int | None = Field(
        default=None, ge=0, description="Maximum token impact"
    )
    allowed_types: list[str] = Field(
        default_factory=list, description="Allowed refactoring types"
    )


class ApprovalPreferenceModel(RefactoringBaseModel):
    """User preference for auto-approvals."""

    pattern_type: str = Field(
        ..., description="Pattern type: consolidation, split, reorganization"
    )
    conditions: ApprovalConditions = Field(
        default_factory=ApprovalConditions, description="Conditions for auto-approval"
    )
    auto_approve: bool = Field(..., description="Whether to auto-approve")
    created_at: str = Field(..., description="ISO timestamp of creation")


class FeedbackRecordModel(RefactoringBaseModel):
    """Record of user feedback on a suggestion."""

    feedback_id: str = Field(..., description="Unique feedback identifier")
    suggestion_id: str = Field(..., description="Associated suggestion ID")
    suggestion_type: str = Field(..., description="Type of suggestion")
    feedback_type: str = Field(
        ..., description="Feedback type: helpful, not_helpful, incorrect"
    )
    comment: str | None = Field(None, description="User comment")
    created_at: str = Field(..., description="ISO timestamp of creation")
    suggestion_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Original suggestion confidence"
    )
    was_approved: bool = Field(..., description="Whether suggestion was approved")
    was_applied: bool = Field(..., description="Whether suggestion was applied")


class PatternConditions(RefactoringBaseModel):
    """Conditions for a learned pattern."""

    similarity_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Similarity threshold"
    )
    min_token_savings: int | None = Field(
        default=None, ge=0, description="Minimum token savings"
    )
    file_patterns: list[str] = Field(
        default_factory=list, description="File name patterns"
    )
    section_patterns: list[str] = Field(
        default_factory=list, description="Section name patterns"
    )


class LearnedPatternModel(RefactoringBaseModel):
    """Pattern learned from user feedback."""

    model_config = ConfigDict(
        extra=EXTRA_FORBID,
        validate_assignment=True,
        use_enum_values=True,
    )

    pattern_id: str = Field(..., description="Unique pattern identifier")
    pattern_type: str = Field(
        ..., description="Pattern type: consolidation, split, reorganization"
    )
    conditions: PatternConditions = Field(
        default_factory=PatternConditions, description="Pattern conditions"
    )
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate 0-1")
    total_occurrences: int = Field(..., ge=0, description="Total occurrences")
    approved_count: int = Field(..., ge=0, description="Approved count")
    rejected_count: int = Field(..., ge=0, description="Rejected count")
    last_seen: str = Field(..., description="ISO timestamp of last occurrence")
    confidence_adjustment: float = Field(
        ..., description="Confidence adjustment factor"
    )
