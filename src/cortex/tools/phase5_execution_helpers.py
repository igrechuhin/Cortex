"""Helper functions for phase5_execution module."""

from typing import cast

from cortex.core.models import ModelDict
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.learning_engine import LearningEngine
from cortex.refactoring.models import (
    ApprovalModel,
    FeedbackRecordResult,
    RefactoringSuggestionModel,
)
from cortex.refactoring.models import (
    ApprovalStatus as ApprovalStatusEnum,
)
from cortex.refactoring.refactoring_engine import RefactoringEngine


async def _extract_feedback_managers(
    mgrs: ManagersDict,
) -> tuple[LearningEngine, RefactoringEngine, ApprovalManager]:
    """Extract managers needed for feedback operations."""
    learning_engine = await get_manager(mgrs, "learning_engine", LearningEngine)
    refactoring_engine = await get_manager(
        mgrs, "refactoring_engine", RefactoringEngine
    )
    approval_manager = await get_manager(mgrs, "approval_manager", ApprovalManager)
    return learning_engine, refactoring_engine, approval_manager


def _check_approval_status(approvals: list[ApprovalModel]) -> tuple[bool, bool]:
    """Check if suggestion was approved or applied."""
    was_approved = False
    was_applied = False
    for a in approvals:
        status = a.status
        if status in {ApprovalStatusEnum.APPROVED, ApprovalStatusEnum.APPLIED}:
            was_approved = True
        if status == ApprovalStatusEnum.APPLIED:
            was_applied = True
    return was_approved, was_applied


async def _record_feedback_and_build_result(
    learning_engine: LearningEngine,
    suggestion: RefactoringSuggestionModel,
    suggestion_id: str,
    feedback_type: str,
    comment: str | None,
    was_approved: bool,
    was_applied: bool,
) -> FeedbackRecordResult:
    """Record feedback and build result with learning summary."""
    suggestion_details = cast(ModelDict, suggestion.model_dump(mode="json"))
    suggestion_type = suggestion.refactoring_type.value
    suggestion_confidence = suggestion.confidence_score
    result = await learning_engine.record_feedback(
        suggestion_id=suggestion_id,
        suggestion_type=suggestion_type,
        feedback_type=feedback_type,
        comment=comment,
        suggestion_confidence=suggestion_confidence,
        was_approved=was_approved,
        was_applied=was_applied,
        suggestion_details=suggestion_details,
    )

    insights = await learning_engine.get_learning_insights()
    insights_dict = cast(ModelDict, insights.model_dump(mode="json"))
    result.learning_summary = {
        "total_feedback": insights_dict.get("total_feedback"),
        "approval_rate": insights_dict.get("approval_rate"),
        "min_confidence_threshold": insights_dict.get("min_confidence_threshold"),
    }
    return result
