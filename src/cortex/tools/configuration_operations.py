"""
Configuration Operations Tools

This module contains the consolidated configuration tool for Memory Bank.
Phase 43 hybrid split (get_config_resource, update_config) lives in
configuration_hybrid.py.

Total: 1 tool
- configure: Configuration for validation/optimization/learning
"""

import json
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Protocol, cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import JsonValue, ModelDict
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.learning_engine import LearningEngine
from cortex.server import mcp
from cortex.tools.configuration_helpers import ConfigAction, parse_config_action
from cortex.tools.models import LearnedPatternsResult
from cortex.tools.tool_error_formatters import (
    format_invalid_parameter_error,
    format_tool_error,
)
from cortex.validation.validation_config import ValidationConfig


class ConfigProtocol(Protocol):
    """Protocol for configuration objects with set method.

    Supports both ValidationConfig/AdaptationConfig (set(key, value) -> None)
    and OptimizationConfig (set(key_path, value) -> bool) patterns.
    """

    def set(self, __key_or_path: str, __value: JsonValue) -> None | bool:
        """Set configuration value.

        Args:
            __key_or_path: Configuration key or key path (positional only)
            __value: Value to set (positional only)

        Returns:
            None for ValidationConfig/AdaptationConfig, bool for OptimizationConfig
        """
        ...


ComponentHandler = Callable[
    [
        ManagersDict,
        ConfigAction,
        dict[str, JsonValue] | None,
        str | None,
        JsonValue | None,
    ],
    Awaitable[str],
]


async def get_managers(root: Path) -> ManagersDict:
    """Resolve managers for project root.

    Consolidated-tool tests patch `cortex.managers.initialization.get_managers`.
    """
    from cortex.managers.initialization import get_managers as _get_managers_impl

    return await _get_managers_impl(root)


def get_component_handler(component: str) -> ComponentHandler | None:
    """Get component handler function.

    Args:
        component: Component name (validation, optimization, learning)

    Returns:
        Handler function or None if component not found
    """
    component_handlers: dict[str, ComponentHandler] = {
        "validation": configure_validation,
        "optimization": configure_optimization,
        "learning": configure_learning,
    }
    return component_handlers.get(component)


# Valid component/action values for configure() (component handlers; ConfigAction).
class ConfigureComponentName(str, Enum):
    """Configuration component name."""

    VALIDATION = "validation"
    OPTIMIZATION = "optimization"
    LEARNING = "learning"


class ConfigureActionName(str, Enum):
    """Configuration action name."""

    VIEW = "view"
    UPDATE = "update"
    RESET = "reset"


@mcp.tool(annotations=safe_write_annotations("Configure Memory Bank"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def configure(
    component: ConfigureComponentName | str,
    action: ConfigureActionName | str = ConfigureActionName.VIEW,
    settings: dict[str, JsonValue] | None = None,
    key: str | None = None,
    value: JsonValue | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Configure Memory Bank validation, optimization, and learning settings.

    USE WHEN: User wants to configure settings, user needs to change
    configuration, user requests configuration update, user wants to
    customize behavior.

    EXAMPLES: 'configure validation settings', 'set optimization
    parameters', 'update refactoring config', 'view current
    configuration'.

    RETURNS: JSON with configuration status and updated settings.

    This unified configuration tool manages three core Memory Bank components:
    - Validation: Control schema validation, duplication detection, quality
      metrics, and token budgets
    - Optimization: Configure context loading strategies, summarization,
      relevance scoring, and caching
    - Learning: Manage adaptive learning behavior, feedback collection, and
      pattern recognition

    Each component supports viewing current settings, updating specific values
    or bulk settings, and resetting to factory defaults. Configuration changes
    persist to disk and take effect immediately for subsequent operations.

    Args:
        component: Component to configure. Valid options:
            - "validation": Validation rules and quality thresholds
            - "optimization": Context optimization and token management
            - "learning": Adaptive learning and feedback processing
            Example: "validation"

        action: Action to perform on the configuration. Options:
            - "view": Display current configuration (default)
            - "update": Modify one or more settings
            - "reset": Restore factory defaults
            Example: "update"

        settings: Dictionary of settings for bulk updates. Use dot notation
            for nested keys.
            Mutually exclusive with key/value parameters.
            Example: {"strict_mode": true, "quality.minimum_score": 75}

        key: Single setting key to update. Supports dot notation for nested settings.
            Requires value parameter. Mutually exclusive with settings parameter.
            Examples:
            - "enabled" (top-level boolean)
            - "token_budget.max_total_tokens" (nested integer)
            - "duplication.threshold" (nested float)
            - "relevance.keyword_weight" (nested weight value)

        value: Value to set for the specified key. Type depends on the setting.
            Required when key is provided.
            Examples: true, 100000, 0.85, "conservative"

    Returns:
        JSON string with operation result. Structure varies by action:

        View action returns:
        {
          "status": "success",
          "component": "validation|optimization|learning",
          "configuration": {
            // Current configuration dictionary
          },
          "learned_patterns": {
            // Only for learning component
          }
        }

        Update action returns:
        {
          "status": "success",
          "component": "validation|optimization|learning",
          "message": "Configuration updated",
          "configuration": {
            // Updated configuration dictionary
          }
        }

        Reset action returns:
        {
          "status": "success",
          "message": "Configuration reset to defaults",
          "component": "validation|optimization|learning",
          "configuration": {
            // Default configuration dictionary
          }
        }

        Error response:
        {
          "status": "error",
          "error": "Error message description",
          "error_type": "ExceptionClassName",
          "valid_components": ["validation", "optimization", "learning"],
          // If invalid component
          "valid_actions": ["view", "update", "reset"]  // If invalid action
        }

    Examples:
        Example 1: View validation configuration
        >>> configure(component="validation", action="view")
        {
            "status": "success",
            "component": "validation",
            "configuration": {"...": "..."}
        }

        Example 2: Update optimization settings with bulk changes
        >>> configure(
        ...     component="optimization",
        ...     action="update",
        ...     settings={
        ...         "token_budget.default_budget": 90000,
        ...         "summarization.enabled": True,
        ...         "relevance.keyword_weight": 0.5
        ...     }
        ... )
        {
            "status": "success",
            "component": "optimization",
            "message": "Configuration updated",
            "...": "..."
        }

        Example 3: Update single learning setting
        >>> configure(
        ...     component="learning",
        ...     action="update",
        ...     key="self_evolution.learning.learning_rate",
        ...     value="moderate"
        ... )
        {
            "status": "success",
            "component": "learning",
            "message": "Configuration updated",
            "...": "..."
        }

        Example 4 (error — invalid component):
        >>> configure(component="invalid", action="view")
        {"status": "error", "error": "Invalid component: 'invalid'",
         "valid_components": ["validation", "optimization", "learning"]}

    Note:
        - Use dot notation (e.g., "token_budget.max_total_tokens") for nested settings
        - Changes persist to `.cortex/{validation,optimization,learning}.json`
          and take effect immediately.
    """
    await log_client(ctx, "info", "configure: starting", logger_name=__name__)
    component_str = (
        component.value if isinstance(component, ConfigureComponentName) else component
    )
    action_str = action.value if isinstance(action, ConfigureActionName) else action
    parsed_action = parse_config_action(action_str)
    if parsed_action is None:
        await log_client(ctx, "warning", "configure: invalid action")
        return create_invalid_action_error(action_str or "null")
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await get_managers(root)
        handler = get_component_handler(component_str)
        if not handler:
            await log_client(ctx, "warning", "configure: invalid component")
            return create_invalid_component_error(component_str)
        result = await handler(mgrs, parsed_action, settings, key, value)
        await log_client(ctx, "info", "configure: completed", logger_name=__name__)
        return result
    except Exception as e:
        await log_client(ctx, "error", f"configure: failed: {e}", logger_name=__name__)
        return create_configuration_exception_error(e, component_str, action_str)


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


async def configure_validation(
    mgrs: ManagersDict,
    action: ConfigAction,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure validation settings."""
    validation_config = await get_manager(mgrs, "validation_config", ValidationConfig)

    if action == ConfigAction.VIEW:
        validation_dict = cast(
            ModelDict, validation_config.config.model_dump(mode="json")
        )
        return create_success_response("validation", validation_dict, message=None)
    elif action == ConfigAction.UPDATE:
        return await handle_validation_update(validation_config, settings, key, value)
    elif action == ConfigAction.RESET:
        return await handle_validation_reset(validation_config)
    else:
        return create_invalid_action_error(action.value)


async def handle_validation_update(
    validation_config: ValidationConfig,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Handle validation configuration update."""
    error = apply_config_updates(validation_config, settings, key, value)
    if error:
        return error
    await validation_config.save()
    validation_dict = cast(ModelDict, validation_config.config.model_dump(mode="json"))
    return create_success_response(
        "validation", validation_dict, "Configuration updated"
    )


async def handle_validation_reset(validation_config: ValidationConfig) -> str:
    """Handle validation configuration reset."""
    validation_config.reset_to_defaults()
    await validation_config.save()
    validation_dict = cast(ModelDict, validation_config.config.model_dump(mode="json"))
    return create_success_response(
        "validation", validation_dict, "Configuration reset to defaults"
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


async def configure_optimization(
    mgrs: ManagersDict,
    action: ConfigAction,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure optimization settings."""
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )

    if action == ConfigAction.VIEW:
        return create_success_response(
            "optimization", optimization_config.to_dict(), message=None
        )
    elif action == ConfigAction.UPDATE:
        return await handle_optimization_update(
            optimization_config, settings, key, value
        )
    elif action == ConfigAction.RESET:
        return await handle_optimization_reset(optimization_config)
    else:
        return create_invalid_action_error(action.value)


async def handle_optimization_update(
    optimization_config: OptimizationConfig,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Handle optimization configuration update."""
    error = apply_config_updates(optimization_config, settings, key, value)
    if error:
        return error
    _ = await optimization_config.save_config()
    return create_success_response(
        "optimization", optimization_config.to_dict(), "Configuration updated"
    )


async def handle_optimization_reset(
    optimization_config: OptimizationConfig,
) -> str:
    """Handle optimization configuration reset."""
    await optimization_config.reset()
    return create_success_response(
        "optimization",
        optimization_config.to_dict(),
        "Configuration reset to defaults",
    )


async def _initialize_learning_components(
    mgrs: ManagersDict,
) -> tuple[LearningEngine, OptimizationConfig, AdaptationConfig]:
    """Initialize learning-related components."""
    learning_engine = await get_manager(mgrs, "learning_engine", LearningEngine)
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )
    adaptation_config = AdaptationConfig(base_config=optimization_config.config)
    return learning_engine, optimization_config, adaptation_config


async def configure_learning(
    mgrs: ManagersDict,
    action: ConfigAction,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure learning settings."""
    (
        learning_engine,
        optimization_config,
        adaptation_config,
    ) = await _initialize_learning_components(mgrs)

    if action == ConfigAction.VIEW:
        return handle_learning_view(learning_engine, adaptation_config)
    elif action == ConfigAction.UPDATE:
        return await handle_learning_update(
            learning_engine,
            optimization_config,
            adaptation_config,
            settings,
            key,
            value,
        )
    elif action == ConfigAction.RESET:
        return await handle_learning_reset(
            learning_engine, optimization_config, adaptation_config
        )
    else:
        return create_invalid_action_error(action.value)


def handle_learning_view(
    learning_engine: LearningEngine, adaptation_config: AdaptationConfig
) -> str:
    """Handle learning configuration view."""
    patterns = get_learned_patterns(learning_engine)
    return json.dumps(
        {
            "status": "success",
            "component": "learning",
            "configuration": adaptation_config.to_dict(),
            "learned_patterns": {
                k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
                for k, v in patterns.patterns.items()
            },
        },
        indent=2,
    )


async def handle_learning_update(
    learning_engine: LearningEngine,
    optimization_config: OptimizationConfig,
    adaptation_config: AdaptationConfig,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Handle learning configuration update."""
    if key == "export_patterns":
        return export_learned_patterns(learning_engine)

    error = apply_config_updates(adaptation_config, settings, key, value)
    if error:
        return error
    _ = await optimization_config.save_config()
    return create_success_response(
        "learning", adaptation_config.to_dict(), "Configuration updated"
    )


async def handle_learning_reset(
    learning_engine: LearningEngine,
    optimization_config: OptimizationConfig,
    adaptation_config: AdaptationConfig,
) -> str:
    """Handle learning configuration reset."""
    _ = await learning_engine.reset_learning_data()
    adaptation_config.reset_to_defaults()
    _ = await optimization_config.save_config()
    return json.dumps(
        {
            "status": "success",
            "message": "Learning data and configuration reset to defaults",
            "configuration": adaptation_config.to_dict(),
        },
        indent=2,
    )


def apply_config_updates(
    config: ConfigProtocol,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str | None:
    """Apply configuration updates. Returns error message if invalid,
    None on success."""
    if settings:
        for k, v in settings.items():
            _ = config.set(k, v)
        return None
    elif key and value is not None:
        _ = config.set(key, value)
        return None
    else:
        return json.dumps(
            {
                "status": "error",
                "error": "Either settings or key+value required for update",
            },
            indent=2,
        )


def create_success_response(
    component: str, configuration: ModelDict, message: str | None
) -> str:
    """Create a success response with configuration."""
    response: ModelDict = {
        "status": "success",
        "component": component,
        "configuration": configuration,
    }
    if message:
        response["message"] = message
    return json.dumps(response, indent=2)


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


def get_learned_patterns(learning_engine: LearningEngine) -> LearnedPatternsResult:
    """Get all learned patterns as model."""
    from cortex.core.models import JsonDict

    patterns_dict = learning_engine.data_manager.get_all_patterns()
    return LearnedPatternsResult(
        patterns={
            pattern_id: JsonDict.from_dict(pattern.to_dict())
            for pattern_id, pattern in patterns_dict.items()
        }
    )


def export_learned_patterns(learning_engine: LearningEngine) -> str:
    """Export learned patterns as JSON response."""
    patterns = get_learned_patterns(learning_engine)
    return json.dumps(
        {
            "status": "success",
            "component": "learning",
            "action": "export_patterns",
            "patterns": {
                k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
                for k, v in patterns.patterns.items()
            },
        },
        indent=2,
    )
