"""Domain-specific error formatters for MCP tools.

Provides format_file_not_found_error, format_invalid_parameter_error,
format_missing_parameter_error, format_validation_error, format_configuration_error,
format_external_tool_error.
"""

from typing import cast

from cortex.core.models import JsonValue
from cortex.tools.error_formatters_core import format_tool_error, fuzzy_match


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
    suggestions = fuzzy_match(file_name, available_files, threshold=0.6)

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
    suggestions = fuzzy_match(invalid_value, valid_options, threshold=0.6)

    suggestion_parts: list[str] = []
    if suggestions:
        did_you_mean = ", ".join(f"'{s}'" for s in suggestions[:3])
        suggestion_parts.append(f"Did you mean {did_you_mean}?")
    suggestion_parts.append(
        f"Valid {parameter_name} values: {', '.join(valid_options)}"
    )

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
        example = {param: "value" for param in missing_parameters}

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
