"""Parameter validation for Phase 5 execution tools.

Extracted to keep phase5_execution.py under 400 lines.
"""

from cortex.refactoring.models import RefactoringAction
from cortex.tools.phase5_execution_errors import create_missing_param_error


def validate_apply_refactoring_params(
    action: RefactoringAction,
    suggestion_id: str | None,
    execution_id: str | None,
) -> str | None:
    """Validate apply_refactoring parameters. Return error JSON or None."""
    if action == RefactoringAction.APPROVE and not suggestion_id:
        return create_missing_param_error("suggestion_id", action.value)
    if action == RefactoringAction.APPLY and not suggestion_id:
        return create_missing_param_error("suggestion_id", action.value)
    if action == RefactoringAction.ROLLBACK and not execution_id:
        return create_missing_param_error("execution_id", action.value)
    return None
