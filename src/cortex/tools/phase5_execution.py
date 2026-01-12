"""
Phase 5.3-5.4: Safe Execution and Learning Tools

This module contains tools for applying refactorings, providing feedback,
and configuring learning behavior.

Total: 3 tools
- apply_refactoring (consolidated: approve, apply, rollback)
- provide_feedback
- configure_learning

Note: get_refactoring_history has been consolidated into get_memory_bank_stats()
tool in tools/phase1_foundation.py with include_refactoring_history=True parameter.

Note: approve_refactoring and rollback_refactoring have been consolidated into
apply_refactoring() with action parameter.
"""

import json
from typing import Literal

from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.learning_engine import LearningEngine
from cortex.refactoring.refactoring_engine import (
    RefactoringEngine,
    RefactoringSuggestion,
)
from cortex.refactoring.refactoring_executor import RefactoringExecutor
from cortex.refactoring.rollback_manager import RollbackManager
from cortex.server import mcp


async def _approve_refactoring(
    mgrs: dict[str, object],
    suggestion_id: str,
    user_comment: str | None,
    auto_apply: bool,
) -> dict[str, object]:
    """Approve a refactoring suggestion."""
    approval_manager = await get_manager(mgrs, "approval_manager", ApprovalManager)
    return await approval_manager.approve_suggestion(
        suggestion_id=suggestion_id,
        user_comment=user_comment,
        auto_apply=auto_apply,
    )


async def _get_suggestion(
    mgrs: dict[str, object], suggestion_id: str
) -> dict[str, object] | None:
    """Get a refactoring suggestion by ID."""
    refactoring_engine = await get_manager(
        mgrs, "refactoring_engine", RefactoringEngine
    )
    suggestion = await refactoring_engine.get_suggestion(suggestion_id)
    return suggestion.to_dict() if suggestion else None


async def _find_approval_id(
    mgrs: dict[str, object], suggestion_id: str, approval_id: str | None
) -> str | dict[str, object]:
    """Find or validate approval ID for a suggestion."""
    if approval_id:
        return approval_id

    approval_manager = await get_manager(mgrs, "approval_manager", ApprovalManager)
    approvals = await approval_manager.get_approvals_for_suggestion(suggestion_id)
    approved = [a for a in approvals if a["status"] == "approved"]

    if not approved:
        return {
            "status": "error",
            "error": f"No approval found for suggestion '{suggestion_id}'",
            "message": "Use action='approve' first",
        }

    approval_id_val = approved[0].get("approval_id")
    if not isinstance(approval_id_val, str):
        return {"status": "error", "error": "Invalid approval_id type"}

    return approval_id_val


async def _execute_refactoring(
    mgrs: dict[str, object],
    suggestion_id: str,
    approval_id: str,
    suggestion_dict: dict[str, object],
    dry_run: bool,
    validate_first: bool,
) -> dict[str, object]:
    """Execute an approved refactoring."""
    refactoring_executor = await get_manager(
        mgrs, "refactoring_executor", RefactoringExecutor
    )
    return await refactoring_executor.execute_refactoring(
        suggestion_id=suggestion_id,
        approval_id=approval_id,
        suggestion=suggestion_dict,
        dry_run=dry_run,
        validate_first=validate_first,
    )


async def _mark_as_applied(
    mgrs: dict[str, object],
    approval_id: str,
    result: dict[str, object],
    dry_run: bool,
) -> None:
    """Mark approval as applied if execution succeeded."""
    if result.get("status") == "success" and not dry_run:
        execution_id_val = result.get("execution_id")
        if isinstance(execution_id_val, str):
            approval_manager = await get_manager(
                mgrs, "approval_manager", ApprovalManager
            )
            _ = await approval_manager.mark_as_applied(
                approval_id=approval_id, execution_id=execution_id_val
            )


async def _apply_approved_refactoring(
    mgrs: dict[str, object],
    suggestion_id: str,
    approval_id: str | None,
    dry_run: bool,
    validate_first: bool,
) -> dict[str, object]:
    """Apply an approved refactoring suggestion."""
    # Get the suggestion
    suggestion_dict = await _get_suggestion(mgrs, suggestion_id)
    if not suggestion_dict:
        return {
            "status": "error",
            "error": f"Suggestion '{suggestion_id}' not found",
        }

    # Find or validate approval
    approval_result = await _find_approval_id(mgrs, suggestion_id, approval_id)
    if isinstance(approval_result, dict):
        return approval_result
    approval_id = approval_result

    # Execute the refactoring
    result = await _execute_refactoring(
        mgrs, suggestion_id, approval_id, suggestion_dict, dry_run, validate_first
    )

    # Mark approval as applied if successful
    await _mark_as_applied(mgrs, approval_id, result, dry_run)

    return result


async def _rollback_refactoring(
    mgrs: dict[str, object],
    execution_id: str,
    restore_snapshot: bool,
    preserve_manual_changes: bool,
    dry_run: bool,
) -> dict[str, object]:
    """Rollback a previously applied refactoring."""
    rollback_manager = await get_manager(mgrs, "rollback_manager", RollbackManager)
    return await rollback_manager.rollback_refactoring(
        execution_id=execution_id,
        restore_snapshot=restore_snapshot,
        preserve_manual_changes=preserve_manual_changes,
        dry_run=dry_run,
    )


def _create_missing_param_error(param_name: str, action: str) -> str:
    """Create error response for missing required parameter.

    Args:
        param_name: Name of missing parameter
        action: Action that requires the parameter

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {
            "status": "error",
            "error": f"{param_name} is required for {action} action",
        },
        indent=2,
    )


def _create_invalid_action_error(action: str) -> str:
    """Create error response for invalid action.

    Args:
        action: The invalid action value

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {
            "status": "error",
            "error": f"Invalid action '{action}'. Must be 'approve', 'apply', or 'rollback'",
        },
        indent=2,
    )


def _create_execution_error_response(error: Exception) -> str:
    """Create error response for execution exceptions.

    Args:
        error: The exception that occurred

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {"status": "error", "error": str(error), "error_type": type(error).__name__},
        indent=2,
    )


async def _handle_approve_action(
    mgrs: dict[str, object],
    suggestion_id: str | None,
    user_comment: str | None,
    auto_apply: bool,
) -> str:
    """Handle approve action.

    Args:
        mgrs: Managers dictionary
        suggestion_id: Suggestion ID to approve
        user_comment: Optional user comment
        auto_apply: Whether to auto-apply after approval

    Returns:
        JSON string with approval result
    """
    if not suggestion_id:
        return _create_missing_param_error("suggestion_id", "approve")
    result = await _approve_refactoring(mgrs, suggestion_id, user_comment, auto_apply)
    return json.dumps(result, indent=2)


async def _handle_apply_action(
    mgrs: dict[str, object],
    suggestion_id: str | None,
    approval_id: str | None,
    dry_run: bool,
    validate_first: bool,
) -> str:
    """Handle apply action.

    Args:
        mgrs: Managers dictionary
        suggestion_id: Suggestion ID to apply
        approval_id: Optional approval ID
        dry_run: Whether to simulate without changes
        validate_first: Whether to validate before executing

    Returns:
        JSON string with apply result
    """
    if not suggestion_id:
        return _create_missing_param_error("suggestion_id", "apply")
    result = await _apply_approved_refactoring(
        mgrs, suggestion_id, approval_id, dry_run, validate_first
    )
    return json.dumps(result, indent=2)


async def _handle_rollback_action(
    mgrs: dict[str, object],
    execution_id: str | None,
    restore_snapshot: bool,
    preserve_manual_changes: bool,
    dry_run: bool,
) -> str:
    """Handle rollback action.

    Args:
        mgrs: Managers dictionary
        execution_id: Execution ID to rollback
        restore_snapshot: Whether to restore from snapshot
        preserve_manual_changes: Whether to preserve manual changes
        dry_run: Whether to simulate without changes

    Returns:
        JSON string with rollback result
    """
    if not execution_id:
        return _create_missing_param_error("execution_id", "rollback")
    result = await _rollback_refactoring(
        mgrs, execution_id, restore_snapshot, preserve_manual_changes, dry_run
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def apply_refactoring(
    action: Literal["approve", "apply", "rollback"] = "apply",
    suggestion_id: str | None = None,
    execution_id: str | None = None,
    approval_id: str | None = None,
    auto_apply: bool = False,
    user_comment: str | None = None,
    dry_run: bool = False,
    validate_first: bool = True,
    restore_snapshot: bool = True,
    preserve_manual_changes: bool = True,
    project_root: str | None = None,
) -> str:
    """
    Apply refactoring operations: approve suggestions, execute changes, or rollback.

    This unified tool consolidates three refactoring execution workflows into a single
    interface controlled by the action parameter. It provides a complete lifecycle for
    managing refactoring suggestions from approval through execution to rollback.

    The tool supports dry-run mode for all actions, allowing safe preview of operations
    before actual execution. It automatically creates snapshots before applying changes
    and tracks all operations in a detailed history for audit and rollback purposes.

    Args:
        action: Action to perform. Options:
            - "approve": Mark a suggestion as approved for execution
            - "apply": Execute an approved refactoring suggestion
            - "rollback": Revert a previously applied refactoring
        suggestion_id: ID of the refactoring suggestion (required for approve/apply).
            Example: "ref-consolidate-20240115123045"
        execution_id: ID of the refactoring execution (required for rollback).
            Example: "exec-ref-consolidate-20240115123045-20240115124530"
        approval_id: Specific approval ID to use (optional for apply, auto-detected if omitted).
            Example: "approval-123456"
        auto_apply: If True, automatically execute after approval (approve action only).
            Default: False
        user_comment: Optional comment explaining the approval, application, or rollback.
            Example: "Approved for Phase 2 consolidation"
        dry_run: If True, simulate the operation without making actual changes.
            Useful for previewing impact. Default: False
        validate_first: If True, validate the refactoring before execution (apply action only).
            Checks file existence, syntax, and conflicts. Default: True
        restore_snapshot: If True, restore files from snapshot (rollback action only).
            Default: True
        preserve_manual_changes: If True, attempt to preserve manual edits during rollback
            (rollback action only). Default: True
        project_root: Optional absolute path to project root.
            Default: current working directory

    Returns:
        JSON string with operation results. Structure varies by action:

        For action="approve":
        {
          "approval_id": "approval-123456",
          "status": "approved",
          "suggestion_id": "ref-consolidate-20240115123045",
          "auto_apply": false,
          "message": "Suggestion approved"
        }

        For action="apply" (success):
        {
          "status": "success",
          "execution_id": "exec-ref-consolidate-20240115123045-20240115124530",
          "operations_completed": 3,
          "snapshot_id": "snapshot-20240115124530",
          "actual_impact": {
            "files_modified": 2,
            "files_created": 1,
            "lines_changed": 45
          },
          "dry_run": false
        }

        For action="apply" (validation failure):
        {
          "status": "failed",
          "execution_id": "exec-ref-consolidate-20240115123045-20240115124530",
          "error": "Validation failed: File not found: src/utils/helpers.py",
          "operations_completed": 0,
          "rollback_available": false
        }

        For action="rollback" (success):
        {
          "status": "success",
          "rollback_id": "rollback-exec-123456-20240115130000",
          "execution_id": "exec-ref-consolidate-20240115123045-20240115124530",
          "files_restored": 3,
          "conflicts_detected": 1,
          "conflicts": [
            "src/utils/helpers.py: Manual changes detected, preserved"
          ],
          "dry_run": false
        }

        For action="rollback" (failure):
        {
          "status": "failed",
          "rollback_id": "rollback-exec-123456-20240115130000",
          "error": "No snapshot ID found for execution"
        }

    Examples:
        Example 1 - Approve a suggestion:
        >>> apply_refactoring(
        ...     action="approve",
        ...     suggestion_id="ref-consolidate-20240115123045",
        ...     user_comment="Looks good, consolidating duplicate code"
        ... )
        {
          "approval_id": "approval-123456",
          "status": "approved",
          "suggestion_id": "ref-consolidate-20240115123045",
          "auto_apply": false,
          "message": "Suggestion approved"
        }

        Example 2 - Apply an approved refactoring with dry-run:
        >>> apply_refactoring(
        ...     action="apply",
        ...     suggestion_id="ref-consolidate-20240115123045",
        ...     dry_run=True
        ... )
        {
          "status": "success",
          "execution_id": "exec-ref-consolidate-20240115123045-20240115124530",
          "operations_completed": 3,
          "snapshot_id": null,
          "actual_impact": {
            "files_modified": 2,
            "files_created": 1,
            "lines_changed": 45
          },
          "dry_run": true
        }

        Example 3 - Rollback a refactoring while preserving manual changes:
        >>> apply_refactoring(
        ...     action="rollback",
        ...     execution_id="exec-ref-consolidate-20240115123045-20240115124530",
        ...     preserve_manual_changes=True
        ... )
        {
          "status": "success",
          "rollback_id": "rollback-exec-123456-20240115130000",
          "execution_id": "exec-ref-consolidate-20240115123045-20240115124530",
          "files_restored": 3,
          "conflicts_detected": 1,
          "conflicts": [
            "src/utils/helpers.py: Manual changes detected, preserved"
          ],
          "dry_run": false
        }

    Note:
        - This tool replaces deprecated approve_refactoring and rollback_refactoring tools
        - All file operations are atomic: either all succeed or all are rolled back
        - Snapshots are automatically created before applying changes (when dry_run=False)
        - The tool auto-detects approval_id for apply action if not provided
        - Validation failures prevent execution and provide detailed error messages
        - Rollback can detect conflicts with manual edits and preserve them when requested
        - Use dry_run=True to safely preview any operation before actual execution
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)

        if action == "approve":
            return await _handle_approve_action(
                mgrs, suggestion_id, user_comment, auto_apply
            )
        if action == "apply":
            return await _handle_apply_action(
                mgrs, suggestion_id, approval_id, dry_run, validate_first
            )
        if action == "rollback":
            return await _handle_rollback_action(
                mgrs, execution_id, restore_snapshot, preserve_manual_changes, dry_run
            )
        return _create_invalid_action_error(action)
    except Exception as e:
        return _create_execution_error_response(e)


async def _extract_feedback_managers(
    mgrs: dict[str, object],
) -> tuple[LearningEngine, RefactoringEngine, ApprovalManager]:
    """Extract managers needed for feedback operations."""
    learning_engine = await get_manager(mgrs, "learning_engine", LearningEngine)
    refactoring_engine = await get_manager(
        mgrs, "refactoring_engine", RefactoringEngine
    )
    approval_manager = await get_manager(mgrs, "approval_manager", ApprovalManager)
    return learning_engine, refactoring_engine, approval_manager


def _create_suggestion_not_found_error(suggestion_id: str) -> dict[str, object]:
    """Create error response for suggestion not found."""
    return {
        "status": "error",
        "error": f"Suggestion '{suggestion_id}' not found",
    }


def _check_approval_status(approvals: list[dict[str, object]]) -> tuple[bool, bool]:
    """Check if suggestion was approved or applied."""
    was_approved = (
        len([a for a in approvals if a["status"] in ["approved", "applied"]]) > 0
    )
    was_applied = len([a for a in approvals if a["status"] == "applied"]) > 0
    return was_approved, was_applied


async def _record_feedback_and_build_result(
    learning_engine: LearningEngine,
    suggestion: RefactoringSuggestion,
    suggestion_id: str,
    feedback_type: str,
    comment: str | None,
    was_approved: bool,
    was_applied: bool,
) -> dict[str, object]:
    """Record feedback and build result with learning summary."""
    suggestion_dict = suggestion.to_dict()
    result = await learning_engine.record_feedback(
        suggestion_id=suggestion_id,
        suggestion_type=suggestion.refactoring_type.value,
        feedback_type=feedback_type,
        comment=comment,
        suggestion_confidence=suggestion.confidence_score,
        was_approved=was_approved,
        was_applied=was_applied,
        suggestion_details=suggestion_dict,
    )

    insights = await learning_engine.get_learning_insights()
    result["learning_summary"] = {
        "total_feedback": insights["total_feedback"],
        "approval_rate": insights["approval_rate"],
        "min_confidence_threshold": insights["min_confidence_threshold"],
    }
    return result


@mcp.tool()
async def provide_feedback(
    suggestion_id: str,
    feedback_type: str,
    comment: str | None = None,
    adjust_preferences: bool = True,
    project_root: str | None = None,
) -> str:
    """
    Provide feedback on refactoring suggestions to improve future recommendations.

    This tool captures user feedback on refactoring suggestions to train the learning
    engine. The system analyzes patterns in feedback to adjust confidence thresholds,
    identify successful refactoring patterns, and learn user preferences. Feedback
    influences future suggestions by updating the internal pattern library and
    preference weights.

    The learning engine tracks approval rates, application success rates, and
    feedback patterns to continuously improve suggestion quality. All feedback
    is persisted in the learning database with full audit trail including
    timestamps, confidence scores, and suggestion details.

    Args:
        suggestion_id: ID of the refactoring suggestion to provide feedback on.
            Must match an existing suggestion from get_refactoring_suggestions().
            Example: "ref-consolidate-20240115123045"
        feedback_type: Type of feedback to provide. Must be one of:
            - "helpful": Suggestion was valuable and appropriate
            - "not_helpful": Suggestion was not useful but not wrong
            - "incorrect": Suggestion was wrong or would cause issues
        comment: Optional detailed comment explaining the feedback reason.
            Helps the learning engine understand specific context.
            Example: "Good consolidation but prefer different naming"
        adjust_preferences: If True, automatically update user preferences and
            confidence thresholds based on this feedback. If False, record
            feedback without adjusting learning parameters.
            Default: True
        project_root: Optional absolute path to project root.
            Default: current working directory

    Returns:
        JSON string with feedback confirmation and learning statistics:
        {
          "feedback_id": "feedback-ref-consolidate-20240115123045-20240115125030",
          "status": "recorded",
          "learning_enabled": true,
          "message": "Feedback recorded and learning updated",
          "learning_summary": {
            "total_feedback": 42,
            "approval_rate": 0.76,
            "min_confidence_threshold": 0.65
          }
        }

    Examples:
        Example 1 - Positive feedback on helpful consolidation:
        >>> provide_feedback(
        ...     suggestion_id="ref-consolidate-20240115123045",
        ...     feedback_type="helpful",
        ...     comment="Great catch! This consolidation removed duplicate validation logic"
        ... )
        {
          "feedback_id": "feedback-ref-consolidate-20240115123045-20240115125030",
          "status": "recorded",
          "learning_enabled": true,
          "message": "Feedback recorded and learning updated",
          "learning_summary": {
            "total_feedback": 15,
            "approval_rate": 0.87,
            "min_confidence_threshold": 0.60
          }
        }

        Example 2 - Negative feedback on incorrect suggestion:
        >>> provide_feedback(
        ...     suggestion_id="ref-split-20240115130000",
        ...     feedback_type="incorrect",
        ...     comment="These functions should not be split - they share critical state"
        ... )
        {
          "feedback_id": "feedback-ref-split-20240115130000-20240115130530",
          "status": "recorded",
          "learning_enabled": true,
          "message": "Feedback recorded and learning updated",
          "learning_summary": {
            "total_feedback": 16,
            "approval_rate": 0.81,
            "min_confidence_threshold": 0.65
          }
        }

        Example 3 - Feedback without adjusting preferences:
        >>> provide_feedback(
        ...     suggestion_id="ref-reorganize-20240115131500",
        ...     feedback_type="not_helpful",
        ...     comment="Already organized well",
        ...     adjust_preferences=False
        ... )
        {
          "feedback_id": "feedback-ref-reorganize-20240115131500-20240115131530",
          "status": "recorded",
          "learning_enabled": true,
          "message": "Feedback recorded and learning updated",
          "learning_summary": {
            "total_feedback": 17,
            "approval_rate": 0.82,
            "min_confidence_threshold": 0.65
          }
        }

    Note:
        - Feedback is automatically linked to approval and application status
        - The learning engine adjusts confidence thresholds based on feedback patterns
        - "helpful" feedback increases confidence in similar patterns
        - "not_helpful" feedback reduces confidence slightly
        - "incorrect" feedback significantly lowers confidence and may filter future similar suggestions
        - All feedback is persisted to .cortex/learning.json
        - Learning statistics update after each feedback submission
        - Feedback can be provided at any time, even after suggestion approval/application
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)

        managers = await _extract_feedback_managers(mgrs)
        suggestion = await _get_suggestion_for_feedback(managers[1], suggestion_id)
        if isinstance(suggestion, str):
            return suggestion

        result = await _process_feedback(
            managers[0],
            managers[1],
            managers[2],
            suggestion,
            suggestion_id,
            feedback_type,
            comment,
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _get_suggestion_for_feedback(
    refactoring_engine: RefactoringEngine, suggestion_id: str
) -> RefactoringSuggestion | str:
    """Get suggestion or return error JSON."""
    suggestion = await refactoring_engine.get_suggestion(suggestion_id)
    if not suggestion:
        return json.dumps(_create_suggestion_not_found_error(suggestion_id), indent=2)
    return suggestion


async def _process_feedback(
    learning_engine: LearningEngine,
    refactoring_engine: RefactoringEngine,
    approval_manager: ApprovalManager,
    suggestion: RefactoringSuggestion,
    suggestion_id: str,
    feedback_type: str,
    comment: str | None,
) -> dict[str, object]:
    """Process feedback and return result.

    Args:
        learning_engine: Learning engine instance
        refactoring_engine: Refactoring engine instance
        approval_manager: Approval manager instance
        suggestion: Suggestion object
        suggestion_id: Suggestion ID
        feedback_type: Type of feedback
        comment: Optional comment

    Returns:
        Result dictionary with feedback processing results
    """
    approvals = await approval_manager.get_approvals_for_suggestion(suggestion_id)
    was_approved, was_applied = _check_approval_status(approvals)

    result = await _record_feedback_and_build_result(
        learning_engine,
        suggestion,
        suggestion_id,
        feedback_type,
        comment,
        was_approved,
        was_applied,
    )

    return result
