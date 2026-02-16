"""Shared error-response helpers for Phase 5 execution tools."""

from cortex.tools.tool_error_formatters import (
    format_invalid_parameter_error,
    format_missing_parameter_error,
    format_tool_error,
)


def create_missing_param_error(param_name: str, action: str) -> str:
    """Create error response for missing required parameter."""
    return format_missing_parameter_error(
        missing_parameters=[param_name],
        tool_name="apply_refactoring",
        example={param_name: "your-value", "action": action},
    )


def create_invalid_action_error(action: str) -> str:
    """Create error response for invalid action."""
    valid_actions = ["approve", "apply", "rollback"]
    return format_invalid_parameter_error(
        parameter_name="action",
        invalid_value=action,
        valid_options=valid_actions,
        tool_name="apply_refactoring",
    )


def _get_execution_error_suggestion(error_type: str, error_message: str) -> str:
    """Get suggestion based on error type and message."""
    if "ValidationError" in error_type or "validation" in error_message:
        return (
            "Review the refactoring suggestion for issues. "
            "Check that all required files exist and parameters are valid. "
            "Try running with 'validate_first=true' to identify issues before execution."
        )
    elif "PermissionError" in error_type or "permission" in error_message:
        return (
            "Check file system permissions. Ensure the process has read/write access "
            "to the memory bank directory. Verify no other process is locking the files."
        )
    elif "FileNotFoundError" in error_type or "not found" in error_message:
        return (
            "Verify that all referenced files exist. Check file paths and ensure "
            "the memory bank is properly initialized. Run "
            "'get_memory_bank_stats()' to verify setup."
        )
    else:
        return (
            "Review the error details and retry the operation. "
            "If the issue persists, check system logs for additional context. "
            "Consider running with 'dry_run=true' to test without making changes."
        )


def create_execution_error_response(error: Exception) -> str:
    """Create error response for execution exceptions."""
    error_type = type(error).__name__
    error_message = str(error).lower()
    suggestion = _get_execution_error_suggestion(error_type, error_message)

    return format_tool_error(
        error,
        suggestion=suggestion,
        example={"action": "apply", "suggestion_id": "suggestion-123", "dry_run": True},
        context={"error_type": error_type},
    )
