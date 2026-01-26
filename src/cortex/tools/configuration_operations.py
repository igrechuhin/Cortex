"""
Configuration Operations Tools

This module contains the consolidated configuration tool for Memory Bank.

Total: 1 tool
- configure: Configuration for validation/optimization/learning
"""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol, cast

from cortex.core.models import JsonValue, ModelDict
from cortex.core.responses import error_response
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.learning_engine import LearningEngine
from cortex.server import mcp
from cortex.tools.models import LearnedPatternsResult
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
        str,
        dict[str, JsonValue] | None,
        str | None,
        JsonValue | None,
    ],
    Awaitable[str],
]


async def get_managers(root: Path) -> ManagersDict:
    """Runtime indirection for test patching.

    Consolidated-tool tests patch `cortex.tools.file_operations.get_managers`.
    """
    from cortex.tools import file_operations

    return await file_operations.get_managers(root)


def get_project_root(project_root: str | None) -> Path:
    """Runtime indirection for test patching (see `get_managers`)."""
    from cortex.tools import file_operations

    return file_operations.get_project_root(project_root)


def _get_component_handler(component: str) -> ComponentHandler | None:
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


@mcp.tool()
async def configure(
    component: str,
    action: str = "view",
    settings: dict[str, JsonValue] | None = None,
    key: str | None = None,
    value: JsonValue | None = None,
    project_root: str | None = None,
) -> str:
    """Configure Memory Bank validation, optimization, and learning settings.

    This unified configuration tool manages three core Memory Bank components:
    - Validation: Control schema validation, duplication detection, quality metrics, and token budgets
    - Optimization: Configure context loading strategies, summarization, relevance scoring, and caching
    - Learning: Manage adaptive learning behavior, feedback collection, and pattern recognition

    Each component supports viewing current settings, updating specific values or bulk settings,
    and resetting to factory defaults. Configuration changes persist to disk and take effect
    immediately for subsequent operations.

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

        settings: Dictionary of settings for bulk updates. Use dot notation for nested keys.
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

        project_root: Path to project root directory. Defaults to current directory.
            Configuration files are stored in .cortex/ as:
            - .cortex/validation.json
            - .cortex/optimization.json
            - .cortex/learning.json
            Example: "/Users/name/project"

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
          "valid_components": ["validation", "optimization", "learning"],  // If invalid component
          "valid_actions": ["view", "update", "reset"]  // If invalid action
        }

    Examples:
        Example 1: View validation configuration
        >>> configure(component="validation", action="view")
        {"status": "success", "component": "validation", "configuration": {"...": "..."}}

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
        {"status": "success", "component": "optimization", "message": "Configuration updated", "...": "..."}

        Example 3: Update single learning setting
        >>> configure(
        ...     component="learning",
        ...     action="update",
        ...     key="self_evolution.learning.learning_rate",
        ...     value="moderate"
        ... )
        {"status": "success", "component": "learning", "message": "Configuration updated", "...": "..."}

    Note:
        - Use dot notation (e.g., "token_budget.max_total_tokens") for nested settings
        - Changes persist to `.cortex/{validation,optimization,learning}.json` and take effect immediately.
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        handler = _get_component_handler(component)
        if handler:
            return await handler(mgrs, action, settings, key, value)

        return _create_invalid_component_error(component)

    except Exception as e:
        return _create_configuration_exception_error(e, component, action)


def _create_invalid_component_error(component: str) -> str:
    """Create error response for invalid component."""
    return create_error_response(
        f"Unknown component: {component}",
        valid_components=["validation", "optimization", "learning"],
        action_required=(
            f"Use one of the valid components: 'validation', 'optimization', or 'learning'. "
            f"Received: '{component}'. "
            f"Example: {{'component': 'validation', 'action': 'view'}}"
        ),
        context={
            "invalid_component": component,
            "valid_components": ["validation", "optimization", "learning"],
        },
    )


def _create_configuration_exception_error(
    e: Exception, component: str, action: str
) -> str:
    """Create error response for configuration exception."""
    return error_response(
        e,
        action_required=(
            "Review the error details and verify your configuration parameters. "
            "Check that component, action, and settings are valid. "
            "Run with 'action=view' to see current configuration."
        ),
        context={"component": component, "action": action},
    )


async def configure_validation(
    mgrs: ManagersDict,
    action: str,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure validation settings."""
    validation_config = await get_manager(mgrs, "validation_config", ValidationConfig)

    if action == "view":
        validation_dict = cast(
            ModelDict, validation_config.config.model_dump(mode="json")
        )
        return create_success_response("validation", validation_dict, message=None)
    elif action == "update":
        return await handle_validation_update(validation_config, settings, key, value)
    elif action == "reset":
        return await handle_validation_reset(validation_config)
    else:
        return create_error_response(
            f"Unknown action: {action}",
            valid_actions=["view", "update", "reset"],
            action_required=(
                f"Use one of the valid actions: 'view', 'update', or 'reset'. "
                f"Received: '{action}'. "
                f"Example: {{'component': 'validation', 'action': 'view'}}"
            ),
            context={
                "invalid_action": action,
                "valid_actions": ["view", "update", "reset"],
            },
        )


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


def _create_invalid_action_error(action: str) -> str:
    """Create error response for invalid action."""
    return create_error_response(
        f"Unknown action: {action}",
        valid_actions=["view", "update", "reset"],
        action_required=(
            f"Use one of the valid actions: 'view', 'update', or 'reset'. "
            f"Received: '{action}'. "
            f"Example: {{'component': 'validation', 'action': 'view'}}"
        ),
        context={
            "invalid_action": action,
            "valid_actions": ["view", "update", "reset"],
        },
    )


async def configure_optimization(
    mgrs: ManagersDict,
    action: str,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure optimization settings."""
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )

    if action == "view":
        return create_success_response(
            "optimization", optimization_config.to_dict(), message=None
        )
    elif action == "update":
        return await handle_optimization_update(
            optimization_config, settings, key, value
        )
    elif action == "reset":
        return await handle_optimization_reset(optimization_config)
    else:
        return _create_invalid_action_error(action)


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
    action: str,
    settings: dict[str, JsonValue] | None,
    key: str | None,
    value: JsonValue | None,
) -> str:
    """Configure learning settings."""
    learning_engine, optimization_config, adaptation_config = (
        await _initialize_learning_components(mgrs)
    )

    if action == "view":
        return handle_learning_view(learning_engine, adaptation_config)
    elif action == "update":
        return await handle_learning_update(
            learning_engine,
            optimization_config,
            adaptation_config,
            settings,
            key,
            value,
        )
    elif action == "reset":
        return await handle_learning_reset(
            learning_engine, optimization_config, adaptation_config
        )
    else:
        return _create_invalid_action_error(action)


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
    """Apply configuration updates. Returns error message if invalid, None on success."""
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
        f"Example: {{'component': '{valid_components[0] if valid_components else 'validation'}'}}"
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


def create_error_response(error: str, **extra_fields: JsonValue) -> str:
    """Create an error response with optional extra fields and recovery suggestions.

    Args:
        error: Error message string
        **extra_fields: Additional fields to include in response (e.g., action_required, context)

    Returns:
        JSON string with standardized error response
    """
    import json

    # Extract action_required and context if provided
    action_required = extra_fields.pop("action_required", None)
    context = extra_fields.pop("context", None)

    # Generate default action_required if not provided
    if not action_required:
        action_required = _generate_action_required(error, extra_fields)

    # Build context from extra_fields if not explicitly provided
    if not context and extra_fields:
        context = extra_fields

    # Type assertions for error_response
    action_required_str = str(action_required)
    context_dict: ModelDict | None = (
        cast(ModelDict, context) if isinstance(context, dict) else None
    )

    # Create base error response
    base_response = json.loads(
        error_response(
            ValueError(error),
            action_required=action_required_str,
            context=context_dict,
        )
    )

    # Merge top-level fields from extra_fields (for backward compatibility with tests)
    # Fields like valid_components, valid_actions should be at top level
    top_level_fields = ["valid_components", "valid_actions", "valid_operations"]
    for field in top_level_fields:
        if field in extra_fields:
            base_response[field] = extra_fields[field]

    return json.dumps(base_response, indent=2)


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
