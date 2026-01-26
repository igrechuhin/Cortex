"""Handler functions for phase5_execution module."""

from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.models import (
    ApproveResult,
    ExecutionResult,
    RefactoringSuggestionModel,
    RollbackRefactoringResult,
)
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.refactoring.refactoring_executor import RefactoringExecutor
from cortex.refactoring.rollback_manager import RollbackManager


async def _approve_refactoring(
    mgrs: ManagersDict,
    suggestion_id: str,
    user_comment: str | None,
    auto_apply: bool,
) -> ApproveResult:
    """Approve a refactoring suggestion."""
    approval_manager = await get_manager(mgrs, "approval_manager", ApprovalManager)
    return await approval_manager.approve_suggestion(
        suggestion_id=suggestion_id,
        user_comment=user_comment,
        auto_apply=auto_apply,
    )


async def _get_suggestion(
    mgrs: ManagersDict, suggestion_id: str
) -> RefactoringSuggestionModel | None:
    """Get suggestion by ID."""
    refactoring_engine = await get_manager(
        mgrs, "refactoring_engine", RefactoringEngine
    )
    return await refactoring_engine.get_suggestion(suggestion_id)


async def _find_approval_id(
    mgrs: ManagersDict, suggestion_id: str, approval_id: str | None
) -> str | ExecutionResult:
    """Find or validate approval ID for a suggestion."""
    if approval_id:
        return approval_id
    approval_manager = await get_manager(mgrs, "approval_manager", ApprovalManager)
    approvals = await approval_manager.get_approvals_for_suggestion(suggestion_id)
    from cortex.refactoring.models import ApprovalStatus as ApprovalStatusEnum

    approved = [a for a in approvals if a.status == ApprovalStatusEnum.APPROVED]
    if not approved:
        return _create_no_approval_error(suggestion_id)
    return _extract_approval_id_from_list(approved, suggestion_id)


def _create_no_approval_error(suggestion_id: str) -> ExecutionResult:
    """Create error for no approval found."""
    return ExecutionResult(
        status="validation_failed",
        execution_id="",
        suggestion_id=suggestion_id,
        error=(
            f"No approval found for suggestion '{suggestion_id}'. "
            "Use action='approve' first."
        ),
    )


def _extract_approval_id_from_list(
    approved: list, suggestion_id: str
) -> str | ExecutionResult:
    """Extract approval ID from approved list."""
    first = approved[0]
    approval_value = first.approval_id
    if not approval_value:
        return ExecutionResult(
            status="validation_failed",
            execution_id="",
            suggestion_id=suggestion_id,
            error="Invalid approval_id; expected non-empty string",
        )
    return approval_value


async def _execute_refactoring(
    mgrs: ManagersDict,
    suggestion_id: str,
    approval_id: str,
    suggestion: RefactoringSuggestionModel,
    dry_run: bool,
    validate_first: bool,
) -> ExecutionResult:
    """Execute an approved refactoring."""
    executor = await get_manager(mgrs, "refactoring_executor", RefactoringExecutor)
    return await executor.execute_refactoring(
        suggestion_id=suggestion_id,
        approval_id=approval_id,
        suggestion=suggestion,
        dry_run=dry_run,
        validate_first=validate_first,
    )


async def _mark_as_applied(
    mgrs: ManagersDict,
    approval_id: str,
    result: ExecutionResult,
    dry_run: bool,
) -> None:
    """Mark approval as applied if execution succeeded."""
    if result.status == "success" and not dry_run and result.execution_id:
        approval_manager = await get_manager(mgrs, "approval_manager", ApprovalManager)
        _ = await approval_manager.mark_as_applied(
            approval_id=approval_id, execution_id=result.execution_id
        )


async def _apply_approved_refactoring(
    mgrs: ManagersDict,
    suggestion_id: str,
    approval_id: str,
    dry_run: bool,
    validate_first: bool,
) -> ExecutionResult:
    """Apply an approved refactoring suggestion."""
    result = await _execute_refactoring(
        mgrs, suggestion_id, approval_id, dry_run, validate_first
    )
    if result.status == "success" and not dry_run:
        await _mark_as_applied(mgrs, approval_id)
    return result


async def _rollback_refactoring(
    mgrs: ManagersDict,
    execution_id: str,
    restore_snapshot: bool,
    preserve_manual_changes: bool,
    dry_run: bool,
) -> RollbackRefactoringResult:
    """Rollback a refactoring execution."""
    rollback_manager = await get_manager(mgrs, "rollback_manager", RollbackManager)
    return await rollback_manager.rollback_refactoring(
        execution_id=execution_id,
        restore_snapshot=restore_snapshot,
        preserve_manual_changes=preserve_manual_changes,
        dry_run=dry_run,
    )


async def _handle_approve_action(
    mgrs: ManagersDict,
    suggestion_id: str | None,
    user_comment: str | None,
    auto_apply: bool,
) -> str:
    """Handle approve action."""
    if not suggestion_id:
        from cortex.tools.phase5_execution_errors import create_missing_param_error

        return create_missing_param_error("suggestion_id", "approve")
    result = await _approve_refactoring(mgrs, suggestion_id, user_comment, auto_apply)
    return result.model_dump_json(indent=2)


async def _handle_apply_action(
    mgrs: ManagersDict,
    suggestion_id: str | None,
    approval_id: str | None,
    dry_run: bool,
    validate_first: bool,
) -> str:
    """Handle apply action."""
    if not suggestion_id:
        from cortex.tools.phase5_execution_errors import create_missing_param_error

        return create_missing_param_error("suggestion_id", "apply")
    result = await _apply_approved_refactoring(
        mgrs, suggestion_id, approval_id, dry_run, validate_first
    )
    return result.model_dump_json(indent=2)


async def _handle_rollback_action(
    mgrs: ManagersDict,
    execution_id: str | None,
    restore_snapshot: bool,
    preserve_manual_changes: bool,
    dry_run: bool,
) -> str:
    """Handle rollback action."""
    if not execution_id:
        from cortex.tools.phase5_execution_errors import create_missing_param_error

        return create_missing_param_error("execution_id", "rollback")
    result = await _rollback_refactoring(
        mgrs, execution_id, restore_snapshot, preserve_manual_changes, dry_run
    )
    return result.model_dump_json(indent=2)
