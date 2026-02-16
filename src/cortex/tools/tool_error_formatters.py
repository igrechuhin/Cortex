"""Standardized tool error response formatting.

This module provides consistent error response formatting for all MCP tools,
following Anthropic's guidance: "error responses should clearly communicate
specific and actionable improvements, rather than opaque error codes or tracebacks."
"""

import json
from difflib import SequenceMatcher
from typing import Literal, cast

from pydantic import BaseModel, Field

from cortex.core.models import JsonDict, JsonValue


class ToolErrorResponse(BaseModel):
    """Standardized error response model for all MCP tools.

    Extends ErrorResponseModel with additional fields for actionable guidance:
    - suggestion: What to do differently
    - example: Example of correct usage
    - available_options: Valid values if applicable

    All fields from ErrorResponseModel are preserved for backward compatibility.
    """

    model_config = {"extra": "forbid", "validate_assignment": True}

    status: Literal["error"] = Field(default="error", description="Response status")
    error: str = Field(description="Human-readable error message")
    error_type: str = Field(description="Exception class name")
    action_required: str | None = Field(
        default=None, description="Action required to resolve (legacy field)"
    )
    suggestion: str | None = Field(default=None, description="What to do differently")
    example: dict[str, JsonValue] | None = Field(
        default=None, description="Example of correct usage"
    )
    available_options: list[str] | None = Field(
        default=None, description="Valid values if applicable"
    )
    context: JsonDict | None = Field(default=None, description="Error context")

    def to_json(self) -> str:
        """Convert to JSON string with proper formatting.

        Returns:
            JSON string with indentation
        """
        return json.dumps(self.model_dump(exclude_none=True), indent=2)


def _fuzzy_match(
    value: str, candidates: list[str], threshold: float = 0.6, max_results: int = 3
) -> list[str]:
    """Find fuzzy matches for a value among candidates.

    Args:
        value: Value to match
        candidates: List of candidate strings
        threshold: Minimum similarity ratio (0.0-1.0)
        max_results: Maximum number of results to return

    Returns:
        List of candidate strings sorted by similarity (best first)
    """
    matches: list[tuple[float, str]] = []
    for candidate in candidates:
        ratio = SequenceMatcher(None, value.lower(), candidate.lower()).ratio()
        if ratio >= threshold:
            matches.append((ratio, candidate))

    # Sort by ratio (descending) and return top matches
    matches.sort(reverse=True, key=lambda x: x[0])
    return [candidate for _, candidate in matches[:max_results]]


def format_tool_error(
    error: Exception,
    suggestion: str | None = None,
    example: dict[str, JsonValue] | None = None,
    available_options: list[str] | None = None,
    context: dict[str, JsonValue] | None = None,
    action_required: str | None = None,
) -> str:
    """Format a tool error into standardized ToolErrorResponse.

    This is the main entry point for creating consistent error responses
    across all MCP tools.

    Args:
        error: The exception that occurred
        suggestion: What to do differently (auto-generated if None)
        example: Example of correct usage (auto-generated if None)
        available_options: Valid values if applicable
        context: Additional error context
        action_required: Legacy field for backward compatibility

    Returns:
        JSON string with standardized error response

    Example:
        >>> format_tool_error(
        ...     ValueError("Invalid check_type: 'invalid'"),
        ...     suggestion="Use one of: schema, duplications, quality",
        ...     available_options=["schema", "duplications", "quality"],
        ...     example={"check_type": "schema", "file_name": "activeContext.md"}
        ... )
    """
    error_type = type(error).__name__
    error_message = str(error)

    # Auto-generate suggestion if not provided
    if suggestion is None:
        suggestion = _generate_default_suggestion(error_type, error_message)

    # Convert context to JsonDict if provided
    context_model: JsonDict | None = None
    if context:
        context_model = JsonDict.from_dict(context)

    # Use action_required as suggestion if suggestion is still None
    if suggestion is None and action_required:
        suggestion = action_required

    response = ToolErrorResponse(
        status="error",
        error=error_message,
        error_type=error_type,
        action_required=action_required,
        suggestion=suggestion,
        example=example,
        available_options=available_options,
        context=context_model,
    )

    return response.to_json()


def _generate_default_suggestion(error_type: str, error_message: str) -> str | None:
    """Generate default suggestion based on error type and message.

    Args:
        error_type: Exception class name
        error_message: Error message string

    Returns:
        Default suggestion string or None
    """
    error_lower = error_message.lower()

    if "file" in error_lower and "not found" in error_lower:
        return (
            "Verify the file name is correct. Use manage_file(operation='metadata') "
            "to list available files."
        )

    if "invalid" in error_lower or "not valid" in error_lower:
        return "Check the parameter values and ensure they match the expected format."

    if "required" in error_lower or "missing" in error_lower:
        return "Provide all required parameters. Check the tool documentation for required fields."

    if "permission" in error_lower or "access" in error_lower:
        return (
            "Check file system permissions. Ensure the process has read/write access "
            "to the required directories."
        )

    if "timeout" in error_lower or "lock" in error_lower:
        return (
            "The operation timed out or a lock could not be acquired. "
            "Wait and retry, or check for stale lock files."
        )

    if "validation" in error_lower:
        return (
            "The input does not meet validation requirements. "
            "Review the error details and fix the issues before retrying."
        )

    return None


# ============================================================================
# Domain-specific error formatters
# ============================================================================


def format_file_not_found_error(
    file_name: str,
    available_files: list[str],
    tool_name: str = "manage_file",
) -> str:
    """Format error response for file not found.

    Args:
        file_name: The file name that was not found
        available_files: List of available file names
        tool_name: Name of the tool that produced the error

    Returns:
        JSON string with error response including fuzzy match suggestions
    """
    # Find fuzzy matches
    suggestions = _fuzzy_match(file_name, available_files, threshold=0.6)

    suggestion_parts: list[str] = []
    if suggestions:
        did_you_mean = ", ".join(f"'{s}'" for s in suggestions[:3])
        suggestion_parts.append(f"Did you mean {did_you_mean}?")
    suggestion_parts.append(f"Available files: {', '.join(sorted(available_files))}")

    example: dict[str, JsonValue] = {
        "file_name": available_files[0] if available_files else "example.md",
        "operation": "read",
    }

    return format_tool_error(
        FileNotFoundError(f"File {file_name} does not exist"),
        suggestion=". ".join(suggestion_parts),
        example=example,
        available_options=available_files,
        context={"file_name": file_name, "tool_name": tool_name},
    )


def format_invalid_parameter_error(
    parameter_name: str,
    invalid_value: str,
    valid_options: list[str],
    tool_name: str,
) -> str:
    """Format error response for invalid parameter value.

    Args:
        parameter_name: Name of the invalid parameter
        invalid_value: The invalid value that was provided
        valid_options: List of valid values
        tool_name: Name of the tool that produced the error

    Returns:
        JSON string with error response including fuzzy match suggestions
    """
    # Find fuzzy matches
    suggestions = _fuzzy_match(invalid_value, valid_options, threshold=0.6)

    suggestion_parts: list[str] = []
    if suggestions:
        did_you_mean = ", ".join(f"'{s}'" for s in suggestions[:3])
        suggestion_parts.append(f"Did you mean {did_you_mean}?")
    suggestion_parts.append(
        f"Valid {parameter_name} values: {', '.join(valid_options)}"
    )

    # Generate example with first valid option
    example: dict[str, JsonValue] = {
        parameter_name: valid_options[0] if valid_options else "valid_value",
    }

    return format_tool_error(
        ValueError(f"Invalid {parameter_name}: '{invalid_value}'"),
        suggestion=". ".join(suggestion_parts),
        example=example,
        available_options=valid_options,
        context={
            "parameter_name": parameter_name,
            "invalid_value": invalid_value,
            "tool_name": tool_name,
        },
    )


def format_missing_parameter_error(
    missing_parameters: list[str],
    tool_name: str,
    example: dict[str, JsonValue] | None = None,
) -> str:
    """Format error response for missing required parameters.

    Args:
        missing_parameters: List of missing parameter names
        tool_name: Name of the tool that produced the error
        example: Optional example of correct usage

    Returns:
        JSON string with error response
    """
    params_str = ", ".join(f"'{p}'" for p in missing_parameters)
    error_msg = f"Missing required parameters: {params_str}"

    suggestion = (
        f"Provide all required parameters: {', '.join(missing_parameters)}. "
        f"See docs/api/tools.md#{tool_name} for parameter details."
    )

    if example is None:
        # Generate minimal example
        example = {param: "value" for param in missing_parameters}

    # Convert list[str] to list[JsonValue] for type compatibility
    # str is a JsonValue, so this cast is safe
    missing_params_json = cast(list[JsonValue], missing_parameters)
    context_dict: dict[str, JsonValue] = {
        "missing_parameters": missing_params_json,
        "tool_name": tool_name,
    }

    return format_tool_error(
        ValueError(error_msg),
        suggestion=suggestion,
        example=example,
        context=context_dict,
    )


def format_validation_error(
    error: Exception,
    violations: list[dict[str, str]] | None = None,
    fix_suggestions: list[str] | None = None,
) -> str:
    """Format error response for validation failures.

    Args:
        error: The validation exception
        violations: List of specific violations (optional)
        fix_suggestions: List of fix suggestions (optional)

    Returns:
        JSON string with error response
    """
    suggestion_parts: list[str] = []
    if violations:
        suggestion_parts.append(
            f"Found {len(violations)} validation issue(s). Review and fix each issue."
        )
    if fix_suggestions:
        suggestion_parts.extend(fix_suggestions)
    if not suggestion_parts:
        suggestion_parts.append(
            "Review the validation errors and fix the issues before retrying."
        )

    context: dict[str, JsonValue] = {}
    if violations:
        # Convert violations to JsonValue-compatible format
        violations_json: list[JsonValue] = [
            {k: v for k, v in v_dict.items()} for v_dict in violations
        ]
        context["violations"] = violations_json

    return format_tool_error(
        error,
        suggestion=" ".join(suggestion_parts),
        context=context if context else None,
    )


def format_configuration_error(
    error: Exception,
    component: str | None = None,
    current_config: dict[str, JsonValue] | None = None,
    expected_format: str | None = None,
) -> str:
    """Format error response for configuration errors.

    Args:
        error: The configuration exception
        component: Configuration component name (optional)
        current_config: Current configuration values (optional)
        expected_format: Expected configuration format description (optional)

    Returns:
        JSON string with error response
    """
    suggestion_parts: list[str] = []
    if component:
        suggestion_parts.append(f"Check the {component} configuration.")
    if expected_format:
        suggestion_parts.append(f"Expected format: {expected_format}")
    if not suggestion_parts:
        suggestion_parts.append(
            "Review the configuration and ensure it matches the expected format."
        )

    context: dict[str, JsonValue] = {}
    if component:
        context["component"] = component
    if current_config:
        context["current_config"] = current_config

    return format_tool_error(
        error,
        suggestion=" ".join(suggestion_parts),
        context=context if context else None,
    )


def format_external_tool_error(
    error: Exception,
    tool_name: str,
    troubleshooting_steps: list[str] | None = None,
) -> str:
    """Format error response for external tool failures.

    Args:
        error: The external tool exception
        tool_name: Name of the external tool that failed
        troubleshooting_steps: List of troubleshooting steps (optional)

    Returns:
        JSON string with error response
    """
    suggestion_parts: list[str] = []
    if troubleshooting_steps:
        suggestion_parts.extend(troubleshooting_steps)
    else:
        suggestion_parts.append(
            f"Check that {tool_name} is installed and available in PATH. "
            + "Verify the tool can run independently."
        )

    context_dict: dict[str, JsonValue] = {"external_tool": tool_name}
    return format_tool_error(
        error,
        suggestion=" ".join(suggestion_parts),
        context=context_dict,
    )
