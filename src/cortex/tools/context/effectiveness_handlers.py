"""
Context Analysis Tool Handlers

MCP tools for analyzing load_context effectiveness and managing statistics.
"""

import json

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.context.effectiveness_operations import (
    analyze_current_session,
    get_context_statistics,
)

# Phase 43: Context analysis resources (read-only, default params)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def analyze_context_effectiveness_resource() -> str:
    """Resource: Analyze context effectiveness (current session, default project). Read via cortex://optimization/context-effectiveness."""
    # Current-session analysis only; full-session analysis is available via
    # the consolidated `analyze` tool with target="context_all_sessions".
    root = await resolve_project_root_async(None, None)
    result = analyze_current_session(root)
    return json.dumps(result.model_dump(mode="json"), indent=2)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_context_usage_statistics_resource() -> str:
    """Resource: Context usage statistics (default project). Read via cortex://optimization/context-usage-statistics."""
    root = await resolve_project_root_async(None, None)
    stats = get_context_statistics(root)
    return json.dumps(stats.model_dump(mode="json"), indent=2)
