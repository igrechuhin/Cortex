"""
Refactoring suggest and apply_refactoring result models.

Used by suggest_refactoring, apply_refactoring.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, ConfigDict, Field

from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.refactoring.models import RefactoringImpactMetrics
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


class SuggestRefactoringType(str, Enum):
    """suggest_refactoring result type."""

    CONSOLIDATION = "consolidation"
    SPLITS = "splits"
    REORGANIZATION = "reorganization"


class ApplyRefactoringStatus(str, Enum):
    """apply_refactoring action status."""

    APPROVED = "approved"
    SUCCESS = "success"
    FAILED = "failed"


_StatusField = Annotated[
    ToolResultStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, ToolResultStatus)),
]
_SuggestTypeField = Annotated[
    SuggestRefactoringType,
    BeforeValidator(lambda x: _coerce_str_enum(x, SuggestRefactoringType)),
]
_ApplyStatusField = Annotated[
    ApplyRefactoringStatus,
    BeforeValidator(lambda x: _coerce_str_enum(x, ApplyRefactoringStatus)),
]


# ============================================================================
# suggest_refactoring
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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    type: _SuggestTypeField = Field(default=SuggestRefactoringType.CONSOLIDATION)
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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    type: _SuggestTypeField = Field(default=SuggestRefactoringType.SPLITS)
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
        populate_by_name=True,
        extra=EXTRA_FORBID,
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

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    type: _SuggestTypeField = Field(default=SuggestRefactoringType.REORGANIZATION)
    goal: str
    plan: ReorganizationPlan


class SuggestRefactoringPreviewResult(ToolResultBase):
    """Result of suggest_refactoring preview mode."""

    status: _StatusField = Field(default=ToolResultStatus.SUCCESS)
    preview_mode: bool = True
    suggestion_id: str
    message: str
    note: str | None = None


class SuggestRefactoringErrorResult(ErrorResultBase):
    """Error result for suggest_refactoring operations."""

    type: str | None = None


class ConciseRefactoringSuggestionEntry(StrictBaseModel):
    """Single suggestion entry in concise suggest_refactoring response."""

    id: str | None = None
    type: str = Field(..., description="consolidation | splits | reorganization")
    confidence: str | None = None
    recommendation: str | None = None


def _empty_suggestion_list() -> list[ConciseRefactoringSuggestionEntry]:
    """Return empty list for SuggestRefactoringConcisePayload.suggestions default."""
    return []


class SuggestRefactoringConcisePayload(StrictBaseModel):
    """Concise suggest_refactoring JSON payload (response_format=concise)."""

    status: str = Field(default="success")
    type: str | None = Field(
        None, description="consolidation | splits | reorganization"
    )
    suggestions: list[ConciseRefactoringSuggestionEntry] = Field(
        default_factory=_empty_suggestion_list
    )


SuggestRefactoringResult = (
    SuggestRefactoringConsolidationResult
    | SuggestRefactoringSplitsResult
    | SuggestRefactoringReorganizationResult
    | SuggestRefactoringPreviewResult
    | SuggestRefactoringErrorResult
)


# ============================================================================
# apply_refactoring
# ============================================================================


class ApplyRefactoringApproveResult(ToolResultBase):
    """Result of apply_refactoring approve action (success)."""

    status: _ApplyStatusField = Field(default=ApplyRefactoringStatus.APPROVED)
    approval_id: str
    suggestion_id: str
    auto_apply: bool
    message: str = "Suggestion approved"


class ApplyRefactoringApplySuccessResult(ToolResultBase):
    """Result of apply_refactoring apply action (success)."""

    status: _ApplyStatusField = Field(default=ApplyRefactoringStatus.SUCCESS)
    execution_id: str
    operations_completed: int
    snapshot_id: str | None = None
    actual_impact: RefactoringImpactMetrics | None = None
    dry_run: bool


class ApplyRefactoringApplyFailureResult(ToolResultBase):
    """Result of apply_refactoring apply action (validation/execution failure)."""

    status: _ApplyStatusField = Field(default=ApplyRefactoringStatus.FAILED)
    execution_id: str
    error: str
    operations_completed: int
    rollback_available: bool


class ApplyRefactoringRollbackSuccessResult(ToolResultBase):
    """Result of apply_refactoring rollback action (success)."""

    status: _ApplyStatusField = Field(default=ApplyRefactoringStatus.SUCCESS)
    rollback_id: str
    execution_id: str
    files_restored: int
    conflicts_detected: int
    conflicts: list[str] = Field(default_factory=list)
    dry_run: bool


class ApplyRefactoringRollbackFailureResult(ToolResultBase):
    """Result of apply_refactoring rollback action (failure)."""

    status: _ApplyStatusField = Field(default=ApplyRefactoringStatus.FAILED)
    rollback_id: str
    error: str


class ApplyRefactoringErrorResult(ErrorResultBase):
    """Error result for apply_refactoring operations (general errors)."""

    action: str | None = None
    suggestion_id: str | None = None
    execution_id: str | None = None


ApplyRefactoringResultUnion = (
    ApplyRefactoringApproveResult
    | ApplyRefactoringApplySuccessResult
    | ApplyRefactoringApplyFailureResult
    | ApplyRefactoringRollbackSuccessResult
    | ApplyRefactoringRollbackFailureResult
    | ApplyRefactoringErrorResult
)
