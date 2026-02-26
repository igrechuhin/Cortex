"""
Configuration Operations Tools

This module contains the consolidated configuration tool for Memory Bank.
Phase 43 hybrid split (get_config_resource, update_config) lives in
configuration_hybrid.py.

Total: 1 tool
- configure: Configuration for validation/optimization/learning
"""

from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Protocol

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import JsonValue
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.types import ManagersDict
from cortex.server import mcp
from cortex.tools.configuration_helpers import ConfigAction, parse_config_action
from cortex.tools.configuration_operations_errors import (
    create_configuration_exception_error,
    create_error_response,
    create_invalid_action_error,
    create_invalid_component_error,
)
from cortex.tools.configuration_operations_handlers import (
    configure_learning,
    configure_optimization,
    configure_validation,
    handle_learning_reset,
    handle_learning_update,
    handle_learning_view,
    handle_optimization_reset,
    handle_optimization_update,
    handle_validation_reset,
    handle_validation_update,
)
from cortex.tools.configuration_operations_response import (
    apply_config_updates,
    create_success_response,
    export_learned_patterns,
    get_learned_patterns,
)


class ConfigProtocol(Protocol):
    """Protocol for configuration objects with set method.

    Supports both ValidationConfig/AdaptationConfig (set(key, value) -> None)
    and OptimizationConfig (set(key_path, value) -> bool) patterns.
    """

    def set(self, __key_or_path: str, __value: JsonValue) -> None | bool:
        """Set configuration value."""
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
    """Get component handler function."""
    component_handlers: dict[str, ComponentHandler] = {
        "validation": configure_validation,
        "optimization": configure_optimization,
        "learning": configure_learning,
    }
    return component_handlers.get(component)


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
        component: Component to configure (validation, optimization, learning).
        action: Action to perform (view, update, reset). Default: view.
        settings: Dictionary of settings for bulk updates. Mutually exclusive
            with key/value parameters.
        key: Single setting key to update. Requires value. Mutually exclusive
            with settings.
        value: Value to set for the specified key.

    Returns:
        JSON string with operation result.
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


# Re-export for backward compatibility (tests and configuration_hybrid import these)
__all__ = [
    "ConfigProtocol",
    "ComponentHandler",
    "ConfigureActionName",
    "ConfigureComponentName",
    "apply_config_updates",
    "configure",
    "configure_learning",
    "configure_optimization",
    "configure_validation",
    "create_configuration_exception_error",
    "create_error_response",
    "create_invalid_component_error",
    "create_success_response",
    "export_learned_patterns",
    "get_component_handler",
    "get_learned_patterns",
    "handle_learning_reset",
    "handle_learning_update",
    "handle_learning_view",
    "handle_optimization_reset",
    "handle_optimization_update",
    "handle_validation_reset",
    "handle_validation_update",
]
