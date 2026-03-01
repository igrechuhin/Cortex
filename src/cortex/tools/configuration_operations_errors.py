"""Error response helpers for configuration operations.

Extracted from configuration_operations to keep main module under 400 lines.
"""

from cortex.core.models import JsonValue
from cortex.tools.configuration_helpers import ConfigAction
from cortex.tools.error_formatters import (
    format_invalid_parameter_error,
    format_tool_error,
)


def create_invalid_component_error(component: str) -> str:
    """Create error response for invalid component."""
    valid_components = ["validation", "optimization", "learning"]
    return format_invalid_parameter_error(
        parameter_name="component",
        invalid_value=component,
        valid_options=valid_components,
        tool_name="configure",
    )


def create_configuration_exception_error(
    e: Exception, component: str, action: str
) -> str:
    """Create error response for configuration exception."""
    return format_tool_error(
        e,
        suggestion=(
            "Review the error details and verify your configuration parameters. "
            "Check that component, action, and settings are valid. "
            "Run with 'action=view' to see current configuration."
        ),
        example={
            "component": component,
            "action": "view",
        },
        context={"component": component, "action": action},
    )


def create_invalid_action_error(action: str) -> str:
    """Create error response for invalid action."""
    valid_actions = [a.value for a in ConfigAction]
    return format_invalid_parameter_error(
        parameter_name="action",
        invalid_value=action,
        valid_options=valid_actions,
        tool_name="configure",
    )


def _format_component_error(valid_components: list[str]) -> str:
    """Format component error message."""
    return (
        f"Use one of the valid components: {', '.join(valid_components)}. "
        f"Example: {{'component': "
        f"'{valid_components[0] if valid_components else 'validation'}'}}"
    )


def _format_action_error(valid_actions: list[str]) -> str:
    """Format action error message."""
    return (
        f"Use one of the valid actions: {', '.join(valid_actions)}. "
        f"Example: {{'action': '{valid_actions[0] if valid_actions else 'view'}'}}"
    )


def _generate_action_required(error: str, extra_fields: dict[str, JsonValue]) -> str:
    """Generate action_required message from error and extra_fields."""
    if "Unknown component" in error:
        valid_components_raw: JsonValue = extra_fields.get("valid_components", [])
        valid_components: list[str] = (
            [str(c) for c in valid_components_raw]
            if isinstance(valid_components_raw, list)
            else []
        )
        return _format_component_error(valid_components)
    elif "Unknown action" in error:
        valid_actions_raw: JsonValue = extra_fields.get("valid_actions", [])
        valid_actions: list[str] = (
            [
                str(item)
                for item in valid_actions_raw
                if isinstance(item, (str, int, float, bool))
            ]
            if isinstance(valid_actions_raw, list)
            else []
        )
        return _format_action_error(valid_actions)
    else:
        return (
            "Review the error message and correct the configuration parameters. "
            "Check the tool documentation for valid parameter values."
        )


def _extract_available_options(extra_fields: dict[str, JsonValue]) -> list[str] | None:
    """Extract available_options from extra_fields."""
    for field in ["valid_components", "valid_actions", "valid_operations"]:
        if field in extra_fields:
            value = extra_fields[field]
            if isinstance(value, list):
                return [str(v) for v in value]
    return None


def _build_error_example(
    error: str, available_options: list[str] | None
) -> dict[str, JsonValue] | None:
    """Build example dict from error message and available options."""
    if not available_options:
        return None
    error_lower = error.lower()
    if "component" in error_lower:
        return {"component": available_options[0], "action": "view"}
    elif "action" in error_lower:
        return {"action": available_options[0]}
    return None


def create_error_response(error: str, **extra_fields: JsonValue) -> str:
    """Create an error response with optional extra fields and recovery suggestions.

    Args:
        error: Error message string
        **extra_fields: Additional fields to include in response
            (e.g., action_required, context, valid_components, valid_actions)

    Returns:
        JSON string with standardized error response
    """
    action_required = extra_fields.pop("action_required", None)
    context = extra_fields.pop("context", None)

    if not action_required:
        action_required = _generate_action_required(error, extra_fields)

    if not context and extra_fields:
        context = extra_fields

    available_options = _extract_available_options(extra_fields)
    context_dict: dict[str, JsonValue] | None = (
        context
        if isinstance(context, dict)
        else {"context": context} if context else None
    )
    example = _build_error_example(error, available_options)

    return format_tool_error(
        ValueError(error),
        suggestion=str(action_required) if action_required else None,
        example=example,
        available_options=available_options,
        context=context_dict,
        action_required=str(action_required) if action_required else None,
    )
