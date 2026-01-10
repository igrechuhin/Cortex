"""
Standardized response formatting for MCP Memory Bank tools.

This module provides consistent response formatting for all MCP tools,
ensuring uniform error handling and success responses across the server.
"""

import json


def success_response(data: dict[str, object]) -> str:
    """
    Create a standardized success response.

    Args:
        data: Dictionary containing response data. Will be merged with
              status="success" automatically.

    Returns:
        JSON string with status and data.

    Example:
        >>> success_response({"file_count": 7, "total_tokens": 15000})
        '{"status": "success", "file_count": 7, "total_tokens": 15000}'
    """
    return json.dumps({"status": "success", **data}, indent=2)


def error_response(
    error: Exception,
    action_required: str | None = None,
    context: dict[str, object] | None = None,
) -> str:
    """
    Create a standardized error response.

    Args:
        error: The exception that occurred.
        action_required: Optional human-readable description of what the user
                        should do to resolve the error.
        context: Optional dictionary with additional context about the error
                (e.g., file paths, config values).

    Returns:
        JSON string with status, error details, and optional guidance.

    Example:
        >>> error_response(
        ...     ValueError("Invalid token budget"),
        ...     action_required="Set token_budget to a positive integer",
        ...     context={"provided_value": -1000}
        ... )
        '{
          "status": "error",
          "error": "Invalid token budget",
          "error_type": "ValueError",
          "action_required": "Set token_budget to a positive integer",
          "context": {"provided_value": -1000}
        }'
    """
    response: dict[str, object] = {
        "status": "error",
        "error": str(error),
        "error_type": type(error).__name__,
    }

    if action_required:
        response["action_required"] = action_required

    if context:
        response["context"] = context

    return json.dumps(response, indent=2)
