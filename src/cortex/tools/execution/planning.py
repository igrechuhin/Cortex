"""Orchestration and execution flow for Phase 5 execution tools.

Extracted to keep execution module under 400 lines.
"""

import json

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import OperationStatus
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.types import ManagersDict
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.learning_engine import LearningEngine
from cortex.refactoring.models import (
    FeedbackRecordResult,
    RefactoringAction,
    RefactoringSuggestionModel,
)
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.tools.execution.errors import create_invalid_action_error
from cortex.tools.execution.handlers import (
    handle_apply_action,
    handle_approve_action,
    handle_rollback_action,
)
from cortex.tools.execution.helpers import (
    check_approval_status,
    extract_feedback_managers,
    record_feedback_and_build_result,
)
from cortex.tools.execution.monitoring import (
    log_apply_result,
    warn_suggestion_not_found_and_return,
)
from cortex.tools.execution.validation import validate_apply_refactoring_params


async def execute_with_error_handling(
    action: RefactoringAction,
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
    ctx: MCPContext | None = None,
) -> str:
    """Execute with validation and error handling."""
    try:
        out = await execute_validated_refactoring(
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
        )
        return await log_apply_result(ctx, out, None)
    except Exception as e:
        return await log_apply_result(ctx, None, e)


async def execute_validated_refactoring(
    action: RefactoringAction,
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
) -> str:
    """Execute validated refactoring action."""
    validation_error = validate_apply_refactoring_params(
        action, suggestion_id, execution_id
    )
    if validation_error is not None:
        return validation_error
    return await call_execute_refactoring_action(
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
    )


async def call_execute_refactoring_action(
    action: RefactoringAction,
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
) -> str:
    """Call execute refactoring action with all parameters."""
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    return await dispatch_refactoring_action(
        action,
        mgrs,
        suggestion_id,
        approval_id,
        execution_id,
        user_comment,
        auto_apply,
        dry_run,
        validate_first,
        restore_snapshot,
        preserve_manual_changes,
    )


async def dispatch_refactoring_action(
    action: RefactoringAction,
    mgrs: ManagersDict,
    suggestion_id: str | None,
    approval_id: str | None,
    execution_id: str | None,
    user_comment: str | None,
    auto_apply: bool,
    dry_run: bool,
    validate_first: bool,
    restore_snapshot: bool,
    preserve_manual_changes: bool,
) -> str:
    """Dispatch refactoring action to appropriate handler."""
    if action == RefactoringAction.APPROVE:
        return await handle_approve_action(
            mgrs, suggestion_id, user_comment, auto_apply
        )
    if action == RefactoringAction.APPLY:
        return await handle_apply_action(
            mgrs, suggestion_id, approval_id, dry_run, validate_first
        )
    if action == RefactoringAction.ROLLBACK:
        return await handle_rollback_action(
            mgrs, execution_id, restore_snapshot, preserve_manual_changes, dry_run
        )
    return create_invalid_action_error(action.value)


async def get_suggestion_for_feedback(
    refactoring_engine: RefactoringEngine, suggestion_id: str
) -> RefactoringSuggestionModel | str:
    """Get suggestion or return error JSON."""
    suggestion = await refactoring_engine.get_suggestion(suggestion_id)
    if not suggestion:
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": f"Suggestion '{suggestion_id}' not found",
            },
            indent=2,
        )
    return suggestion


async def process_feedback(
    learning_engine: LearningEngine,
    refactoring_engine: RefactoringEngine,
    approval_manager: ApprovalManager,
    suggestion: RefactoringSuggestionModel,
    suggestion_id: str,
    feedback_type: str,
    comment: str | None,
) -> FeedbackRecordResult:
    """Process feedback and return result."""
    approvals = await approval_manager.get_approvals_for_suggestion(suggestion_id)
    was_approved, was_applied = check_approval_status(approvals)
    return await record_feedback_and_build_result(
        learning_engine,
        suggestion,
        suggestion_id,
        feedback_type,
        comment,
        was_approved,
        was_applied,
    )


async def provide_feedback_impl(
    suggestion_id: str,
    feedback_type: str,
    comment: str | None,
    adjust_preferences: bool,
    project_root: str | None,
    ctx: MCPContext | None,
) -> str:
    """Run provide_feedback logic and return JSON result."""
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    (
        learning_engine,
        refactoring_engine,
        approval_manager,
    ) = await extract_feedback_managers(mgrs)
    suggestion = await get_suggestion_for_feedback(refactoring_engine, suggestion_id)
    if isinstance(suggestion, str):
        return await warn_suggestion_not_found_and_return(ctx, suggestion)
    result = await process_feedback(
        learning_engine,
        refactoring_engine,
        approval_manager,
        suggestion,
        suggestion_id,
        feedback_type,
        comment,
    )
    out = result.model_dump_json(indent=2)
    await log_client(ctx, "info", "provide_feedback: completed", logger_name=__name__)
    return out
