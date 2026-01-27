"""Shared error-response helpers for Phase 5 execution tools."""

from cortex.core.responses import error_response


def create_missing_param_error(param_name: str, action: str) -> str:
    """Create error response for missing required parameter."""
    return error_response(
        ValueError(f"{param_name} is required for {action} action"),
        action_required=(
            f"Provide the {param_name} parameter when calling the {action} action. "
            f"Example: {{'{param_name}': 'your-value', 'action': '{action}'}}"
        ),
        context={"missing_parameter": param_name, "action": action},
    )


def create_invalid_action_error(action: str) -> str:
    """Create error response for invalid action."""
    return error_response(
        ValueError(
            f"Invalid action '{action}'. Must be 'approve', 'apply', or 'rollback'"
        ),
        action_required=(
            "Set the 'action' parameter to one of: 'approve', 'apply', or 'rollback'. "
            f"Received: '{action}'. "
            "Example: {'action': 'approve', 'suggestion_id': 'suggestion-123'}"
        ),
        context={
            "invalid_action": action,
            "valid_actions": ["approve", "apply", "rollback"],
        },
    )


def create_execution_error_response(error: Exception) -> str:
    """Create error response for execution exceptions."""
    error_type = type(error).__name__
    if "ValidationError" in error_type or "validation" in str(error).lower():
        action_required = (
            "Review the refactoring suggestion for issues. "
            "Check that all required files exist and parameters are valid. "
            "Try running with 'validate_first=true' to identify issues "
            "before execution."
        )
    elif "PermissionError" in error_type or "permission" in str(error).lower():
        action_required = (
            "Check file system permissions. Ensure the process has read/write access "
            "to the memory bank directory. Verify no other process is "
            "locking the files."
        )
    elif "FileNotFoundError" in error_type or "not found" in str(error).lower():
        action_required = (
            "Verify that all referenced files exist. Check file paths and ensure "
            "the memory bank is properly initialized. Run "
            "'get_memory_bank_stats()' to verify setup."
        )
    else:
        action_required = (
            "Review the error details and retry the operation. "
            "If the issue persists, check system logs for additional context. "
            "Consider running with 'dry_run=true' to test without making changes."
        )

    return error_response(
        error, action_required=action_required, context={"error_type": error_type}
    )
