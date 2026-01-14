"""
Configuration Operations Tools

This module contains the consolidated configuration tool for Memory Bank.

Total: 1 tool
- configure: Configuration for validation/optimization/learning
"""

import json
from collections.abc import Awaitable, Callable
from typing import Literal, Protocol

from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.learning_engine import LearningEngine
from cortex.server import mcp
from cortex.validation.validation_config import ValidationConfig


class ConfigProtocol(Protocol):
    """Protocol for configuration objects with set method.

    Supports both ValidationConfig/AdaptationConfig (set(key, value) -> None)
    and OptimizationConfig (set(key_path, value) -> bool) patterns.
    """

    def set(self, __key_or_path: str, __value: object) -> None | bool:
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
        dict[str, object],
        str,
        dict[str, object] | None,
        str | None,
        object | None,
    ],
    Awaitable[str],
]


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
    component: Literal["validation", "optimization", "learning"],
    action: Literal["view", "update", "reset"] = "view",
    settings: dict[str, object] | None = None,
    key: str | None = None,
    value: object | None = None,
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
        {
          "status": "success",
          "component": "validation",
          "configuration": {
            "enabled": true,
            "auto_validate_on_write": true,
            "strict_mode": false,
            "token_budget": {
              "max_total_tokens": 100000,
              "warn_at_percentage": 80,
              "per_file_max": 15000,
              "per_file_warn": 12000
            },
            "duplication": {
              "enabled": true,
              "threshold": 0.85,
              "min_length": 100,
              "suggest_transclusion": true
            },
            "schemas": {
              "enforce_required_sections": true,
              "enforce_section_order": false,
              "custom_schemas": {}
            },
            "quality": {
              "minimum_score": 70,
              "fail_below": 50,
              "weights": {
                "completeness": 0.3,
                "consistency": 0.25,
                "freshness": 0.15,
                "structure": 0.15,
                "token_efficiency": 0.15
              }
            }
          }
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
          "configuration": {
            "enabled": true,
            "token_budget": {
              "default_budget": 90000,
              "max_budget": 100000,
              "reserve_for_response": 10000
            },
            "loading_strategy": {
              "default": "dependency_aware",
              "mandatory_files": ["memorybankinstructions.md"],
              "priority_order": ["memorybankinstructions.md", "projectBrief.md", "activeContext.md"]
            },
            "summarization": {
              "enabled": true,
              "auto_summarize_old_files": false,
              "age_threshold_days": 90,
              "target_reduction": 0.5
            },
            "relevance": {
              "keyword_weight": 0.5,
              "dependency_weight": 0.3,
              "recency_weight": 0.15,
              "quality_weight": 0.05
            }
          }
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
          "configuration": {
            "learning": {
              "enabled": true,
              "learning_rate": "moderate",
              "remember_rejections": true,
              "adapt_suggestions": true,
              "min_feedback_count": 5,
              "confidence_adjustment_limit": 0.2
            },
            "feedback": {
              "collect_feedback": true,
              "prompt_for_feedback": false,
              "feedback_types": ["helpful", "not_helpful", "incorrect"],
              "allow_comments": true
            },
            "pattern_recognition": {
              "enabled": true,
              "min_pattern_occurrences": 3,
              "pattern_confidence_threshold": 0.7,
              "forget_old_patterns_days": 90
            }
          }
        }

    Note:
        - Configuration changes persist to JSON files in project root and take effect immediately
        - Validation component controls quality thresholds, token limits, and duplication detection
        - Optimization component affects context loading, caching, and summarization behavior
        - Learning component manages adaptive behavior based on user feedback and usage patterns
        - Use dot notation (e.g., "token_budget.max_total_tokens") for nested settings
        - Settings parameter allows bulk updates; key/value allows single setting updates
        - Reset action restores factory defaults and clears any custom configuration
        - Learning component includes learned_patterns in view output showing adaptation history
        - Export patterns by setting key="export_patterns" in learning component updates
        - Configuration validation occurs automatically; invalid values return error status
        - Component-specific configuration files: .cortex/validation.json, .cortex/optimization.json
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        handler = _get_component_handler(component)
        if handler:
            return await handler(mgrs, action, settings, key, value)

        return create_error_response(
            f"Unknown component: {component}",
            valid_components=["validation", "optimization", "learning"],
        )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": e.__class__.__name__},
            indent=2,
        )


async def configure_validation(
    mgrs: dict[str, object],
    action: str,
    settings: dict[str, object] | None,
    key: str | None,
    value: object | None,
) -> str:
    """Configure validation settings."""
    validation_config = await get_manager(mgrs, "validation_config", ValidationConfig)

    if action == "view":
        return create_success_response(
            "validation", validation_config.to_dict(), message=None
        )
    elif action == "update":
        return await handle_validation_update(validation_config, settings, key, value)
    elif action == "reset":
        return await handle_validation_reset(validation_config)
    else:
        return create_error_response(
            f"Unknown action: {action}", valid_actions=["view", "update", "reset"]
        )


async def handle_validation_update(
    validation_config: ValidationConfig,
    settings: dict[str, object] | None,
    key: str | None,
    value: object | None,
) -> str:
    """Handle validation configuration update."""
    error = apply_config_updates(validation_config, settings, key, value)
    if error:
        return error
    await validation_config.save()
    return create_success_response(
        "validation", validation_config.to_dict(), "Configuration updated"
    )


async def handle_validation_reset(validation_config: ValidationConfig) -> str:
    """Handle validation configuration reset."""
    validation_config.reset_to_defaults()
    await validation_config.save()
    return create_success_response(
        "validation", validation_config.to_dict(), "Configuration reset to defaults"
    )


async def configure_optimization(
    mgrs: dict[str, object],
    action: str,
    settings: dict[str, object] | None,
    key: str | None,
    value: object | None,
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
        return create_error_response(
            f"Unknown action: {action}", valid_actions=["view", "update", "reset"]
        )


async def handle_optimization_update(
    optimization_config: OptimizationConfig,
    settings: dict[str, object] | None,
    key: str | None,
    value: object | None,
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


async def configure_learning(
    mgrs: dict[str, object],
    action: str,
    settings: dict[str, object] | None,
    key: str | None,
    value: object | None,
) -> str:
    """Configure learning settings."""
    learning_engine = await get_manager(mgrs, "learning_engine", LearningEngine)
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )

    adaptation_config = AdaptationConfig(base_config=optimization_config.config)

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
        return create_error_response(
            f"Unknown action: {action}", valid_actions=["view", "update", "reset"]
        )


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
            "learned_patterns": patterns,
        },
        indent=2,
    )


async def handle_learning_update(
    learning_engine: LearningEngine,
    optimization_config: OptimizationConfig,
    adaptation_config: AdaptationConfig,
    settings: dict[str, object] | None,
    key: str | None,
    value: object | None,
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
    settings: dict[str, object] | None,
    key: str | None,
    value: object | None,
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
    component: str, configuration: dict[str, object], message: str | None
) -> str:
    """Create a success response with configuration."""
    response: dict[str, object] = {
        "status": "success",
        "component": component,
        "configuration": configuration,
    }
    if message:
        response["message"] = message
    return json.dumps(response, indent=2)


def create_error_response(error: str, **extra_fields: object) -> str:
    """Create an error response with optional extra fields."""
    response: dict[str, object] = {"status": "error", "error": error}
    response.update(extra_fields)
    return json.dumps(response, indent=2)


def get_learned_patterns(learning_engine: LearningEngine) -> dict[str, object]:
    """Get all learned patterns as dict."""
    patterns_dict = learning_engine.data_manager.get_all_patterns()
    return {
        pattern_id: pattern.to_dict() for pattern_id, pattern in patterns_dict.items()
    }


def export_learned_patterns(learning_engine: LearningEngine) -> str:
    """Export learned patterns as JSON response."""
    patterns = get_learned_patterns(learning_engine)
    return json.dumps(
        {
            "status": "success",
            "component": "learning",
            "action": "export_patterns",
            "patterns": patterns,
        },
        indent=2,
    )
