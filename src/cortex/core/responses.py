"""
Standardized response formatting for MCP Memory Bank tools.

This module provides consistent response formatting for all MCP tools,
ensuring uniform error handling and success responses across the server.
"""

import json

from cortex.core.models import ErrorContext, JsonDict, JsonValue, SuccessResponseData


def success_response(
    data: SuccessResponseData | JsonDict | dict[str, JsonValue],
) -> str:
    """
    Create a standardized success response.

    Args:
        data: SuccessResponseData or JsonDict containing response data.
              Will be merged with status="success" automatically.

    Returns:
        JSON string with status and data.

    Example:
        >>> success_response(SuccessResponseData(file_count=7, total_tokens=15000))
        '{"status": "success", "file_count": 7, "total_tokens": 15000}'
    """
    if isinstance(data, JsonDict):
        data_dict = data.to_dict()
    elif isinstance(data, dict):
        data_dict = data
    else:
        data_dict = data.to_dict()
    return json.dumps({"status": "success", **data_dict}, indent=2)


def error_response(
    error: Exception,
    action_required: str | None = None,
    context: ErrorContext | JsonDict | dict[str, JsonValue] | None = None,
) -> str:
    """
    Create a standardized error response.

    Args:
        error: The exception that occurred.
        action_required: Optional human-readable description of what the user
                        should do to resolve the error.
        context: Optional ErrorContext or JsonDict with additional context about the error
                (e.g., file paths, config values).

    Returns:
        JSON string with status, error details, and optional guidance.

    Example:
        >>> error_response(
        ...     ValueError("Invalid token budget"),
        ...     action_required="Set token_budget to a positive integer",
        ...     context=ErrorContext(provided_value=-1000)
        ... )
        '{
          "status": "error",
          "error": "Invalid token budget",
          "error_type": "ValueError",
          "action_required": "Set token_budget to a positive integer",
          "context": {"provided_value": -1000}
        }'
    """
    from cortex.core.models import ErrorResponseModel

    context_model: JsonDict | None = None
    if context:
        if isinstance(context, JsonDict):
            context_model = context
        elif isinstance(context, dict):
            context_model = JsonDict.from_dict(context)
        else:
            # Convert ErrorContext to JsonDict
            context_model = JsonDict.from_dict(context.to_dict())

    response_data = ErrorResponseModel(
        status="error",
        error=str(error),
        error_type=type(error).__name__,
        action_required=action_required,
        context=context_model,
    )

    return json.dumps(response_data.model_dump(exclude_none=True), indent=2)
