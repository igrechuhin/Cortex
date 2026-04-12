"""
Phase 4: Optimization Handlers - Validation Helpers

Validation logic for load_context: task description length, budget requirements,
and non-trivial task detection.
"""

import json

from cortex.core.constants import MAX_TASK_DESCRIPTION_CHARS
from cortex.core.models import OperationStatus


def is_non_trivial_task(task_description: str) -> bool:
    """Detect if a task is non-trivial based on keywords."""
    task_lower = task_description.lower()
    keywords = (
        "implement add create build develop fix debug resolve correct repair "
        "refactor refactoring restructure restructuring reorganize test testing "
        "verify validate optimize optimization improve improving enhance "
        "update modify change edit plan planning analyze analysis"
    ).split()
    return any(kw in task_lower for kw in keywords)


def validate_explicit_budget_for_non_trivial(
    task_description: str, token_budget: int | None
) -> str | None:
    """Require explicit non-zero token_budget for non-trivial tasks.

    For implement/refactor/fix/debug and similar flows, token_budget must be
    explicitly provided (not omitted and not 0). Returns a validation error
    when the task is non-trivial and token_budget is None or 0.

    Args:
        task_description: Task description
        token_budget: Token budget (None = omitted)

    Returns:
        Error JSON string if validation fails, None otherwise
    """
    if not is_non_trivial_task(task_description):
        return None
    if token_budget is not None and token_budget != 0:
        return None
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": (
                "Explicit non-zero token_budget is required for non-trivial tasks "
                "(implement/add, fix/debug, refactor, test, optimize). "
                "Omitted or zero token_budget is not allowed. "
                "Use e.g. token_budget=10000 for implement/add, 15000 for fix/debug."
            ),
            "error_type": "ValueError",
            "task_description": task_description,
            "action_required": "Pass an explicit positive token_budget (e.g. 10000 or 15000).",
            "suggestion": (
                "For non-trivial tasks, use appropriate token budgets: "
                "10000 for implement/add/update/modify, "
                "15000 for fix/debug/other, "
                "20000-30000 for small features, "
                "15000 for optimization, "
                "7000-8000 for narrow review/documentation."
            ),
        },
        indent=2,
    )


def resolve_load_context_budget(
    task_description: str, token_budget: int | None
) -> tuple[int | None, str | None]:
    """Validate explicit budget for non-trivial tasks and resolve effective budget.

    Returns:
        (effective_budget, error_json_or_none). If error is non-None, caller should return it.
    """
    validation_error = validate_explicit_budget_for_non_trivial(
        task_description, token_budget
    )
    if validation_error:
        return None, validation_error
    effective_budget = None if token_budget == 0 else token_budget
    return effective_budget, None


def validate_task_description_length(task_description: str) -> str | None:
    """Return error JSON if task_description exceeds max length, else None."""
    if len(task_description) <= MAX_TASK_DESCRIPTION_CHARS:
        return None
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": (
                f"task_description too long: {len(task_description)} chars "
                f"exceeds limit of {MAX_TASK_DESCRIPTION_CHARS}"
            ),
            "error_type": "ValueError",
        },
        indent=2,
    )
