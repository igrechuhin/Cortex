"""Phase 5.3-5.4: Safe Execution and Learning Tools.

Tools: apply_refactoring, provide_feedback, configure_learning.

Notes:
- get_refactoring_history is consolidated into get_memory_bank_stats(...,
  include_refactoring_history=True).
- approve_refactoring/rollback_refactoring are consolidated into
  apply_refactoring(action=...).
"""

import json
from typing import Literal

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import mcp_tool_wrapper
from cortex.server import mcp
from cortex.tools.phase5_execution_helpers import parse_refactoring_action
from cortex.tools.phase5_execution_monitoring import log_invalid_action_and_return
from cortex.tools.phase5_execution_planning import (
    execute_with_error_handling,
    provide_feedback_impl,
)


async def _apply_refactoring_validate_and_run(
    action: str,
    project_root: str | None,
    suggestion_id: str | None,
    approval_id: str | None,
    execution_id: str | None,
    user_comment: str | None,
    auto_apply: bool,
    dry_run: bool,
    validate_first: bool,
    restore_snapshot: bool,
    preserve_manual_changes: bool,
    ctx: MCPContext | None,
) -> str:
    """Validate action and run apply refactoring."""
    parsed_action = parse_refactoring_action(action)
    if parsed_action is None:
        return await log_invalid_action_and_return(ctx, action)
    return await execute_with_error_handling(
        parsed_action,
        project_root,
        suggestion_id,
        approval_id,
        execution_id,
        user_comment,
        auto_apply,
        dry_run,
        validate_first,
        restore_snapshot,
        preserve_manual_changes,
        ctx,
    )


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
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
    ctx: MCPContext | None = None,
) -> str:
    """Apply refactoring operations: approve suggestions, execute changes, or rollback.

    USE WHEN: User wants to apply refactoring, user needs to approve
    changes, user requests rollback, user wants to execute refactoring.

    EXAMPLES: 'apply refactoring suggestion X', 'approve refactoring Y',
    'rollback refactoring Z'.

    RETURNS: JSON with execution status, changes applied, and rollback
    information.

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
        approval_id: Specific approval ID to use (optional for apply,
            auto-detected if omitted).
            Example: "approval-123456"
        auto_apply: If True, automatically execute after approval (approve action only).
            Default: False
        user_comment: Optional comment explaining the approval, application,
            or rollback.
            Example: "Approved for Phase 2 consolidation"
        dry_run: If True, simulate the operation without making actual changes.
            Useful for previewing impact. Default: False
        validate_first: If True, validate the refactoring before execution
            (apply action only).
            Checks file existence, syntax, and conflicts. Default: True
        restore_snapshot: If True, restore files from snapshot (rollback action only).
            Default: True
        preserve_manual_changes: If True, attempt to preserve manual edits
            during rollback (rollback action only). Default: True
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
        - This tool replaces deprecated approve_refactoring and
          rollback_refactoring tools
        - All file operations are atomic: either all succeed or all are
          rolled back
        - Snapshots are automatically created before applying changes
          (when dry_run=False)
        - The tool auto-detects approval_id for apply action if not provided
        - Validation failures prevent execution and provide detailed error
          messages
        - Rollback can detect conflicts with manual edits and preserve them
          when requested
        - Use dry_run=True to safely preview any operation before actual execution
    """
    await log_client(ctx, "info", "apply_refactoring: starting", logger_name=__name__)
    return await _apply_refactoring_validate_and_run(
        action,
        project_root,
        suggestion_id,
        approval_id,
        execution_id,
        user_comment,
        auto_apply,
        dry_run,
        validate_first,
        restore_snapshot,
        preserve_manual_changes,
        ctx,
    )


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def provide_feedback(
    suggestion_id: str,
    feedback_type: str,
    comment: str | None = None,
    adjust_preferences: bool = True,
    project_root: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Provide feedback on refactoring suggestions to improve future recommendations.

    USE WHEN: User wants to give feedback, user needs to rate suggestions,
    user requests feedback submission, user wants to improve learning.

    EXAMPLES: 'provide feedback on suggestion X', 'rate refactoring Y',
    'submit feedback for improvement'.

    RETURNS: JSON with feedback submission status and learning updates.

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
        ...     comment=(
        ...         "Great catch! This consolidation removed duplicate "
        ...         "validation logic"
        ...     )
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
        ...     comment=(
        ...         "These functions should not be split - they share "
        ...         "critical state"
        ...     )
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
        - "incorrect" feedback significantly lowers confidence and may filter
          future similar suggestions
        - All feedback is persisted to .cortex/learning.json
        - Learning statistics update after each feedback submission
        - Feedback can be provided at any time, even after suggestion
          approval/application
    """
    await log_client(ctx, "info", "provide_feedback: starting", logger_name=__name__)
    try:
        return await provide_feedback_impl(
            suggestion_id, feedback_type, comment, adjust_preferences, project_root, ctx
        )
    except Exception as e:
        await log_client(ctx, "error", f"provide_feedback: {e!s}", logger_name=__name__)
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )
