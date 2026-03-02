"""Phase 43 hybrid split: get_config resource.

Read config via get_config_resource (cortex://config/{component}).
Unified configure() tool remains in configuration_operations.
"""

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.config.helpers import ConfigAction
from cortex.tools.config.operations import (
    create_invalid_component_error,
    get_component_handler,
    get_managers,
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
