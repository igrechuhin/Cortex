"""Phase 43 hybrid split: get_config resource and update_config tool.

Read config via get_config_resource (cortex://config/{component}).
Update/reset config via update_config tool. Unified configure() remains in
configuration_operations.
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import JsonValue
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.configuration_helpers import ConfigAction, parse_config_action
from cortex.tools.configuration_operations import (
    create_configuration_exception_error,
    create_invalid_action_error,
    create_invalid_component_error,
    get_component_handler,
    get_managers,
)

_VALID_UPDATE_ACTIONS: frozenset[ConfigAction] = frozenset(
    {ConfigAction.UPDATE, ConfigAction.RESET}
)


@mcp.resource(uri="cortex://config/{component}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_config_resource(component: str) -> str:
    """Resource: Read configuration for a component. URI: cortex://config/{component}."""
    root = await resolve_project_root_async(None, None)
    mgrs = await get_managers(root)
    handler = get_component_handler(component)
    if not handler:
        return create_invalid_component_error(component)
    return await handler(mgrs, ConfigAction.VIEW, None, None, None)


@mcp.tool(annotations=safe_write_annotations("Update Memory Bank Configuration"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def update_config(
    component: str,
    action: str,
    settings: dict[str, JsonValue] | None = None,
    key: str | None = None,
    value: JsonValue | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Update or reset Memory Bank configuration (write-only). View via get_config_resource or configure.

    USE WHEN: User wants to change validation/optimization/learning settings or reset to defaults.

    Args:
        component: validation, optimization, or learning.
        action: update or reset.
        settings: Optional bulk settings dict (for update).
        key: Optional single key (for update).
        value: Optional value for key (for update).
    """
    await log_client(ctx, "info", "update_config: starting", logger_name=__name__)
    parsed_action = parse_config_action(action)
    if parsed_action is None or parsed_action not in _VALID_UPDATE_ACTIONS:
        await log_client(ctx, "warning", "update_config: invalid action")
        return create_invalid_action_error(action or "null")
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await get_managers(root)
        handler = get_component_handler(component)
        if not handler:
            await log_client(ctx, "warning", "update_config: invalid component")
            return create_invalid_component_error(component)
        result = await handler(mgrs, parsed_action, settings, key, value)
        await log_client(ctx, "info", "update_config: completed", logger_name=__name__)
        return result
    except Exception as e:
        await log_client(
            ctx, "error", f"update_config: failed: {e}", logger_name=__name__
        )
        return create_configuration_exception_error(e, component, action)
