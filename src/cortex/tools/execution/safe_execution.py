"""Phase 5.3-5.4: Safe Execution and Learning Tools.

Tools: apply_refactoring, provide_feedback, configure_learning.

Notes:
- get_refactoring_history is consolidated into get_memory_bank_stats(...,
  include_refactoring_history=True).
- approve_refactoring/rollback_refactoring are consolidated into
  apply_refactoring(action=...).
"""

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_COMPLEX,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.refactoring.models import RefactoringAction
from cortex.server import mcp
from cortex.tools.execution.helpers import parse_refactoring_action
from cortex.tools.execution.monitoring import log_invalid_action_and_return
from cortex.tools.execution.planning import execute_with_error_handling
from cortex.tools.tool_categories import ALLOWED_CALLERS_CODE_EXECUTION


async def _apply_refactoring_validate_and_run(
    action: str,
    root: str,
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
        root,
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


@mcp.tool(
    annotations=safe_write_annotations("Apply Refactoring"),
    meta={"allowed_callers": list(ALLOWED_CALLERS_CODE_EXECUTION)},
)
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def apply_refactoring(
    action: RefactoringAction | str = RefactoringAction.APPLY,
    suggestion_id: str | None = None,
    execution_id: str | None = None,
    approval_id: str | None = None,
    auto_apply: bool = False,
    user_comment: str | None = None,
    dry_run: bool = False,
    validate_first: bool = True,
    restore_snapshot: bool = True,
    preserve_manual_changes: bool = True,
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

        Example (Error - invalid action or missing suggestion_id):
        {
          "status": "error",
          "error": "suggestion_id is required for action 'apply'",
          "error_type": "ValueError"
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
        - Project root is resolved by the server (MCP roots or cwd).
    """
    await log_client(ctx, "info", "apply_refactoring: starting", logger_name=__name__)
    action_str = action.value if isinstance(action, RefactoringAction) else action
    root = await resolve_project_root_async(None, ctx)
    return await _apply_refactoring_validate_and_run(
        action_str,
        str(root),
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
