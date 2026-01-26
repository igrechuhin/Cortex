"""
Pydantic models for refactoring module.

This module contains Pydantic models for refactoring operations,
migrated from dataclass definitions for better validation and IDE support.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import ModelDict

# ============================================================================
# Base Model
# ============================================================================


class RefactoringBaseModel(BaseModel):
    """Base model for refactoring types with strict validation."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        validate_default=True,
    )


# ============================================================================
# Enums (kept from original modules)
# ============================================================================


class RefactoringType(str, Enum):
    """Types of refactoring suggestions."""

    CONSOLIDATION = "consolidation"
    SPLIT = "split"
    REORGANIZATION = "reorganization"
    TRANSCLUSION = "transclusion"
    RENAME = "rename"
    MERGE = "merge"


class RefactoringPriority(str, Enum):
    """Priority levels for refactoring suggestions."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class ApprovalStatus(str, Enum):
    """Status of an approval."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    APPLIED = "applied"


class RefactoringStatus(str, Enum):
    """Status of a refactoring operation."""

    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


# ============================================================================
# Common Metric Models
# ============================================================================


class RefactoringImpactMetrics(RefactoringBaseModel):
    """Estimated impact metrics for refactoring operations."""

    # token_savings may be negative when a refactoring increases token usage.
    token_savings: int = Field(
        default=0,
        description="Estimated token savings (positive) or increase (negative)",
    )
    files_affected: int = Field(default=0, ge=0, description="Number of files affected")
    operations_completed: int = Field(
        default=0, ge=0, description="Number of operations completed"
    )
    # complexity_reduction may be negative when complexity increases.
    complexity_reduction: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Complexity reduction factor (negative means increase)",
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        default="low", description="Risk level"
    )
    maintainability_improvement: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Maintainability improvement factor",
    )


class RefactoringMetadata(RefactoringBaseModel):
    """Metadata for refactoring suggestions."""

    source: str | None = Field(default=None, description="Source of suggestion")
    analyzer_version: str | None = Field(default=None, description="Analyzer version")
    confidence_factors: list[str] = Field(
        default_factory=list, description="Factors affecting confidence"
    )
    related_suggestions: list[str] = Field(
        default_factory=list, description="Related suggestion IDs"
    )
    insight_category: str | None = Field(
        default=None, description="Insight category if from insight"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations from insight"
    )


class ActionDetails(RefactoringBaseModel):
    """Details for a refactoring action."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    source_file: str | None = Field(default=None, description="Source file path")
    source_files: list[str] | None = Field(
        default=None, description="List of source files for consolidation"
    )
    destination_file: str | None = Field(
        default=None, description="Destination file path"
    )
    content: str | None = Field(default=None, description="Content to add/modify")
    section: str | None = Field(default=None, description="Target section")
    sections: list[str] | None = Field(
        default=None, description="List of sections to operate on"
    )
    line_start: int | None = Field(default=None, ge=1, description="Start line number")
    line_end: int | None = Field(default=None, ge=1, description="End line number")
    heading1: str | None = Field(
        default=None, description="First heading for consolidation"
    )
    heading2: str | None = Field(
        default=None, description="Second heading for consolidation"
    )
    differences: list[str] | None = Field(
        default=None, description="Content differences"
    )
    size: int | None = Field(default=None, ge=0, description="Size in bytes")
    token_count: int | None = Field(default=None, ge=0, description="Token count")
    # Consolidation-specific fields
    extraction_method: str | None = Field(
        default=None, description="Method used for extraction"
    )
    transclusion_target: str | None = Field(
        default=None, description="Target file for transclusion"
    )
    replace_duplicates: bool | None = Field(
        default=None, description="Whether to replace duplicates"
    )
    # Split-specific fields
    split_strategy: str | None = Field(
        default=None, description="Strategy for splitting files"
    )
    add_links: bool | None = Field(
        default=None, description="Whether to add links to split files"
    )
    create_index: bool | None = Field(
        default=None, description="Whether to create an index file"
    )
    # Reorganization-specific fields
    affected_files: list[str] | None = Field(
        default=None, description="Files affected by reorganization"
    )
    new_structure: str | None = Field(
        default=None, description="New directory structure"
    )
    preserve_links: bool | None = Field(
        default=None, description="Whether to preserve existing links"
    )
    add_dependencies: bool | None = Field(
        default=None, description="Whether to add dependencies"
    )


# ============================================================================
# Refactoring Engine Models (from refactoring_engine.py)
# ============================================================================


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
        extra="forbid",
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


# ============================================================================
# Consolidation Models (from consolidation_detector.py)
# ============================================================================


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
    risk_level: Literal["low", "medium", "high"] = Field(..., description="Risk level")
    benefits: list[str] = Field(default_factory=list, description="List of benefits")
    risks: list[str] = Field(default_factory=list, description="List of risks")


# ============================================================================
# Split Models (from split_recommender.py)
# ============================================================================


class ParsedSectionModel(RefactoringBaseModel):
    """Represents a parsed markdown section.

    Used by SplitAnalyzer and SplitRecommender for file structure analysis.
    Replaces `ModelDict` for type-safe section handling.
    """

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
    # Protocol compatibility fields
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


# ============================================================================
# Approval Models (from approval_manager.py)
# ============================================================================


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


# ============================================================================
# Learning Models (from learning_data_manager.py)
# ============================================================================


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
        extra="forbid",
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


# ============================================================================
# Execution Models (from execution_validator.py, refactoring_executor.py)
# ============================================================================


class OperationParameters(RefactoringBaseModel):
    """Parameters for a refactoring operation."""

    source_file: str | None = Field(default=None, description="Source file path")
    source_files: list[str] | None = Field(
        default=None, description="Source files for multi-file operations"
    )
    destination_file: str | None = Field(
        default=None, description="Destination file path"
    )
    content: str | None = Field(default=None, description="Content to add/modify")
    new_name: str | None = Field(default=None, description="New name for rename")
    section: str | None = Field(default=None, description="Target section")
    sections: list[str] | None = Field(
        default=None, description="List of sections to operate on"
    )
    line_start: int | None = Field(default=None, ge=1, description="Start line number")
    line_end: int | None = Field(default=None, ge=1, description="End line number")
    preserve_history: bool = Field(default=True, description="Preserve version history")
    is_directory: bool = Field(
        default=False, description="Whether to create a directory"
    )


class RefactoringOperationModel(RefactoringBaseModel):
    """Single refactoring operation."""

    operation_id: str = Field(..., description="Unique operation identifier")
    operation_type: str = Field(
        ...,
        description="Type: move, rename, create, delete, modify, consolidate, split",
    )
    target_file: str = Field(..., description="Target file path")
    parameters: OperationParameters = Field(
        default_factory=OperationParameters, description="Operation parameters"
    )
    status: RefactoringStatus = Field(
        default=RefactoringStatus.PENDING, description="Operation status"
    )
    error: str | None = Field(default=None, description="Error message if failed")
    created_at: str | None = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO timestamp of creation",
    )
    completed_at: str | None = Field(
        default=None, description="ISO timestamp of completion"
    )


class RefactoringExecutionModel(RefactoringBaseModel):
    """Record of a refactoring execution."""

    execution_id: str = Field(..., description="Unique execution identifier")
    suggestion_id: str = Field(..., description="Associated suggestion ID")
    approval_id: str = Field(..., description="Associated approval ID")
    operations: list[RefactoringOperationModel] = Field(
        default_factory=lambda: list[RefactoringOperationModel](),
        description="Operations performed",
    )
    status: RefactoringStatus = Field(..., description="Execution status")
    created_at: str = Field(..., description="ISO timestamp of creation")
    completed_at: str | None = Field(
        default=None, description="ISO timestamp of completion"
    )
    snapshot_id: str | None = Field(
        default=None, description="Snapshot ID for rollback"
    )
    validation_results: RefactoringImpactMetrics | None = Field(
        default=None, description="Validation results"
    )
    actual_impact: RefactoringImpactMetrics | None = Field(
        default=None, description="Actual impact"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class RefactoringValidationResult(RefactoringBaseModel):
    """Result of validating a refactoring suggestion."""

    valid: bool = Field(..., description="Whether the suggestion is valid")
    issues: list[str] = Field(default_factory=list, description="Validation issues")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    operations_count: int = Field(default=0, ge=0, description="Number of operations")
    dry_run: bool = Field(default=True, description="Whether this was a dry run")


# ============================================================================
# Rollback Models (from rollback_manager.py)
# ============================================================================


class RollbackRecordModel(RefactoringBaseModel):
    """Record of a rollback operation."""

    rollback_id: str = Field(..., description="Unique rollback identifier")
    execution_id: str = Field(..., description="Associated execution ID")
    created_at: str = Field(..., description="ISO timestamp of creation")
    completed_at: str | None = Field(
        default=None, description="ISO timestamp of completion"
    )
    status: RefactoringStatus = Field(
        default=RefactoringStatus.PENDING, description="Rollback status"
    )
    files_restored: list[str] = Field(
        default_factory=list, description="Files restored"
    )
    conflicts_detected: list[str] = Field(
        default_factory=list, description="Conflicts detected"
    )
    preserve_manual_edits: bool = Field(
        default=True, description="Whether to preserve manual edits"
    )
    error: str | None = Field(default=None, description="Error message if failed")


# ============================================================================
# Reorganization Models (from reorganization_planner.py, reorganization/executor.py)
# ============================================================================


class ReorganizationActionModel(RefactoringBaseModel):
    """Represents a single reorganization action."""

    action_type: str = Field(
        ..., description="Type: move, rename, reorder, create_category"
    )
    source: str = Field(..., description="Source path")
    target: str = Field(..., description="Target path")
    reason: str = Field(..., description="Reason for action")
    dependencies_affected: list[str] = Field(
        default_factory=list, description="Dependencies affected"
    )


class ReorganizationStructure(RefactoringBaseModel):
    """Structure representation for reorganization."""

    files: list[str] = Field(default_factory=list, description="List of files")
    directories: list[str] = Field(
        default_factory=list, description="List of directories"
    )
    files_by_category: dict[str, list[str]] = Field(
        default_factory=dict, description="Files grouped by category"
    )
    max_depth: int = Field(default=0, ge=0, description="Maximum directory depth")


class MemoryBankStructureData(RefactoringBaseModel):
    """Analyzed structure data for Memory Bank reorganization.

    This model replaces `ModelDict` in reorganization modules,
    providing type-safe access to structure analysis results.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    # Core file info
    total_files: int = Field(default=0, ge=0, description="Total number of files")
    files: list[str] = Field(default_factory=list, description="List of file paths")

    # Organization structure
    organization: str = Field(
        default="flat",
        description="Organization type: flat, category_based, dependency_optimized, simplified",
    )
    categories: dict[str, list[str]] = Field(
        default_factory=dict, description="Files grouped by category"
    )

    # Dependency info
    dependency_depth: int = Field(
        default=0, ge=0, description="Maximum dependency depth"
    )
    dependency_order: list[str] = Field(
        default_factory=list, description="Optimized dependency order"
    )
    hub_files: list[str] = Field(
        default_factory=list, description="Files with many dependents (hubs)"
    )

    # Structural issues
    orphaned_files: list[str] = Field(
        default_factory=list, description="Files with no dependencies"
    )
    complexity_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall structural complexity 0-1"
    )


class DependencyInfo(RefactoringBaseModel):
    """Dependency information for a single file."""

    depends_on: list[str] = Field(
        default_factory=list, description="Files this file depends on"
    )
    dependents: list[str] = Field(
        default_factory=list, description="Files that depend on this file"
    )


class DependencyGraphInput(RefactoringBaseModel):
    """Dependency graph input for reorganization.

    This model provides type-safe access to dependency graph data
    used in reorganization planning.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    dependencies: dict[str, DependencyInfo] = Field(
        default_factory=dict, description="File dependency information"
    )


class ReorganizationImpactModel(RefactoringBaseModel):
    """Impact metrics for reorganization operations."""

    files_moved: int = Field(..., ge=0, description="Number of files moved")
    categories_created: int = Field(
        ..., ge=0, description="Number of categories created"
    )
    dependency_depth_reduction: float = Field(
        ..., ge=0.0, le=1.0, description="Dependency depth reduction factor"
    )
    complexity_reduction: float = Field(
        ..., ge=0.0, le=1.0, description="Complexity reduction factor"
    )
    maintainability_improvement: float = Field(
        ..., ge=0.0, le=1.0, description="Maintainability improvement factor"
    )
    navigation_improvement: float = Field(
        ..., ge=0.0, le=1.0, description="Navigation improvement factor"
    )
    estimated_effort: Literal["low", "medium", "high"] = Field(
        ..., description="Estimated effort level"
    )


class ReorganizationPlanModel(RefactoringBaseModel):
    """Represents a complete reorganization plan."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    plan_id: str = Field(..., description="Unique plan identifier")
    optimization_goal: str = Field(
        ..., description="Goal: dependency_depth, category_based, complexity"
    )
    current_structure: MemoryBankStructureData = Field(
        default_factory=MemoryBankStructureData, description="Current structure"
    )
    proposed_structure: MemoryBankStructureData = Field(
        default_factory=MemoryBankStructureData, description="Proposed structure"
    )
    actions: list[ReorganizationActionModel] = Field(
        default_factory=lambda: list[ReorganizationActionModel](),
        description="Actions to perform",
    )
    estimated_impact: ReorganizationImpactModel = Field(
        ...,
        description="Estimated impact",
    )
    risks: list[str] = Field(default_factory=list, description="Identified risks")
    benefits: list[str] = Field(default_factory=list, description="Expected benefits")
    preserve_history: bool = Field(
        default=True, description="Whether to preserve history"
    )


class ReorganizationPreviewResult(RefactoringBaseModel):
    """Result of previewing a reorganization plan."""

    files_to_move: int = Field(..., ge=0, description="Number of files to move")
    estimated_improvement: float = Field(
        ..., ge=0.0, le=1.0, description="Estimated improvement factor"
    )
    risks: list[str] = Field(default_factory=list, description="Identified risks")


# ============================================================================
# Protocol Return Type Models (for ApprovalManagerProtocol)
# ============================================================================


class CleanupExpiredApprovalsResult(RefactoringBaseModel):
    """Result of cleaning up expired approvals."""

    status: str = Field(..., description="Operation status")
    expired_count: int = Field(..., ge=0, description="Number of expired approvals")
    expiry_days: int = Field(..., ge=0, description="Expiry threshold in days")
    message: str = Field(..., description="Human-readable message")


class ApprovalRequestResult(RefactoringBaseModel):
    """Result of an approval request operation."""

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
    approved_at: str | None = Field(
        default=None, description="ISO timestamp of approval"
    )


class ApproveResult(RefactoringBaseModel):
    """Result of approving a refactoring."""

    approval_id: str = Field(..., description="Approval ID")
    status: str = Field(..., description="Approval result status")
    suggestion_id: str = Field(..., description="Suggestion ID")
    auto_apply: bool = Field(default=False, description="Whether to auto-apply")
    message: str = Field(..., description="Result message")


# ============================================================================
# Protocol Return Type Models (for RollbackManagerProtocol)
# ============================================================================


class RollbackResult(RefactoringBaseModel):
    """Result of a rollback operation."""

    status: Literal["rolled_back", "error", "not_found"] = Field(
        ..., description="Rollback status"
    )
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
    status: Literal["completed", "failed", "partial"] = Field(
        ..., description="Rollback status"
    )


# ============================================================================
# Protocol Return Type Models (for LearningEngineProtocol)
# ============================================================================


class FeedbackRecordResult(RefactoringBaseModel):
    """Result of recording feedback."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    status: Literal["recorded", "error"] = Field(..., description="Record status")
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

    model_config = ConfigDict(extra="allow", validate_assignment=True)

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


# ============================================================================
# Additional Approval Manager Models
# ============================================================================


class RejectResult(RefactoringBaseModel):
    """Result of rejecting a refactoring suggestion."""

    status: Literal["rejected", "error"] = Field(..., description="Rejection status")
    approval_id: str | None = Field(default=None, description="Approval ID")
    suggestion_id: str = Field(..., description="Suggestion ID")
    message: str = Field(..., description="Status message")


class MarkAppliedResult(RefactoringBaseModel):
    """Result of marking an approval as applied."""

    status: Literal["applied", "error"] = Field(..., description="Mark status")
    approval_id: str = Field(..., description="Approval ID")
    execution_id: str | None = Field(default=None, description="Execution ID")
    message: str = Field(..., description="Status message")


class PreferenceResult(RefactoringBaseModel):
    """Result of adding/removing a preference."""

    status: Literal["success", "not_found", "error"] = Field(
        ..., description="Operation status"
    )
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

    status: Literal["success", "error"] = Field(..., description="Cleanup status")
    expired_count: int = Field(default=0, ge=0, description="Number expired")
    expiry_days: int = Field(..., ge=0, description="Expiry threshold in days")
    message: str = Field(..., description="Status message")


# ============================================================================
# Additional Rollback Manager Models
# ============================================================================


class RollbackRefactoringResult(RefactoringBaseModel):
    """Result of rolling back a refactoring execution."""

    status: Literal["success", "failed"] = Field(..., description="Rollback status")
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

    status: Literal["success", "error"] = Field(..., description="Analysis status")
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


# ============================================================================
# Additional Learning Engine Models
# ============================================================================


class ResetLearningResult(RefactoringBaseModel):
    """Result of resetting learning data."""

    status: Literal["success", "error"] = Field(..., description="Reset status")
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

    status: Literal["success", "error"] = Field(..., description="Export status")
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


# ============================================================================
# Refactoring Executor Models
# ============================================================================


# ============================================================================
# Preview Models (for RefactoringEngine.preview_refactoring)
# ============================================================================


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

    status: Literal["success", "failed", "validation_failed"] = Field(
        ..., description="Execution status"
    )
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


# ============================================================================
# Configuration Models
# ============================================================================


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

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

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

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

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


# ============================================================================
# Protocol Parameter Models
# ============================================================================


class ApprovalRequestDetails(RefactoringBaseModel):
    """Details for an approval request."""

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

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

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

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

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    user_comment: str | None = Field(default=None, description="User comment")
    execution_time_ms: int | None = Field(
        default=None, ge=0, description="Execution time in milliseconds"
    )
    files_modified: list[str] = Field(
        default_factory=list, description="Files that were modified"
    )


# ============================================================================
# Learning Preference Models
# ============================================================================


class SuggestionTypePreference(RefactoringBaseModel):
    """User preference for a suggestion type (e.g., consolidation, split)."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

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
    """User preferences for learning engine.

    This model stores typed user preferences for the learning system.
    Uses explicit fields for known preference types rather than a generic dict.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

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
        """Get preference for a suggestion type.

        Args:
            suggestion_type: Type of suggestion (consolidation, split, etc.)

        Returns:
            SuggestionTypePreference if found, None otherwise
        """
        attr_name = f"suggestion_type_{suggestion_type}"
        return getattr(self, attr_name, None)

    def set_suggestion_preference(
        self, suggestion_type: str, pref: SuggestionTypePreference
    ) -> None:
        """Set preference for a suggestion type.

        Args:
            suggestion_type: Type of suggestion (consolidation, split, etc.)
            pref: Preference to set
        """
        attr_name = f"suggestion_type_{suggestion_type}"
        if hasattr(self, attr_name):
            setattr(self, attr_name, pref)


class ConfidenceAdjustmentDetails(RefactoringBaseModel):
    """Details of confidence adjustment calculation."""

    model_config = ConfigDict(extra="allow")

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

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    suggestion_id: str | None = Field(default=None, description="Suggestion identifier")
    type: str | None = Field(default=None, description="Suggestion type")
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence score"
    )
    affected_files: list[str] = Field(
        default_factory=list, description="Files affected"
    )


class SuggestionDetails(RefactoringBaseModel):
    """Details about a suggestion for pattern extraction.

    Used by LearningEngine and PatternManager to extract patterns from suggestions.
    """

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

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


# ============================================================================
# Protocol Parameter Models (for RefactoringEngineProtocol)
# ============================================================================


class InsightDataModel(RefactoringBaseModel):
    """Insight data for refactoring suggestion generation.

    This model replaces `ModelDict` for insight_data parameter
    in RefactoringEngineProtocol.generate_suggestions().
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

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
    """Analysis data for refactoring suggestion generation.

    This model replaces `ModelDict` for analysis_data parameter
    in RefactoringEngineProtocol.generate_suggestions().
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

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


# ============================================================================
# Adaptation Configuration Models
# ============================================================================


class LearningConfigModel(RefactoringBaseModel):
    """Learning configuration settings."""

    enabled: bool = Field(default=True, description="Whether learning is enabled")
    learning_rate: Literal["aggressive", "moderate", "conservative"] = Field(
        default="conservative", description="Learning rate setting"
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
    """Complete adaptation configuration model.

    This replaces the `ModelDict`-based AdaptationConfig with a
    fully typed Pydantic model for better validation and IDE support.
    """

    self_evolution: SelfEvolutionAdaptationConfigModel = Field(
        default_factory=SelfEvolutionAdaptationConfigModel,
        description="Self-evolution configuration",
    )


class AdaptationValidationResult(RefactoringBaseModel):
    """Result of adaptation configuration validation."""

    valid: bool = Field(..., description="Whether configuration is valid")
    issues: list[str] = Field(default_factory=list, description="Validation issues")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class AdaptationSummary(RefactoringBaseModel):
    """Summary of adaptation configuration settings."""

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
