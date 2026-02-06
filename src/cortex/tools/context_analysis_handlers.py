"""
Context Analysis Tool Handlers

MCP tools for analyzing load_context effectiveness and managing statistics.
"""

import json
from pathlib import Path

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.context_analysis_operations import (
    analyze_current_session,
    analyze_session_logs,
    get_context_statistics,
)


def _analyze_context_effectiveness_impl(root: Path, analyze_all_sessions: bool) -> str:
    """Run analyze_context_effectiveness logic. Raises on error."""
    if analyze_all_sessions:
        result = analyze_session_logs(root)
    else:
        result = analyze_current_session(root)
    return json.dumps(result.model_dump(mode="json"), indent=2)


@mcp.tool(annotations=read_only_annotations("Analyze Context Effectiveness"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def analyze_context_effectiveness(
    analyze_all_sessions: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Analyze load_context calls and update usage statistics.

    USE WHEN: User wants to optimize context loading, user needs usage
    statistics, user requests context analysis, user wants to improve
    context selection.

    EXAMPLES: 'analyze context effectiveness', 'get context usage stats',
    'analyze context loading patterns'.

    RETURNS: JSON with context usage statistics and optimization
    recommendations.

    By default, analyzes only the CURRENT session's load_context calls.
    Use analyze_all_sessions=True to analyze all historical sessions.

    Call this at the end of sessions to build a feedback dataset.

    Args:
        analyze_all_sessions: If True, analyze all sessions; if False (default),
            analyze only the current session

    Returns:
        JSON with analysis results and statistics summary
    """
    await log_client(
        ctx, "info", "analyze_context_effectiveness: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        out = _analyze_context_effectiveness_impl(root, analyze_all_sessions)
        await log_client(
            ctx,
            "info",
            "analyze_context_effectiveness: completed",
            logger_name=__name__,
        )
        return out
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"analyze_context_effectiveness: {e!s}",
            logger_name=__name__,
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool(annotations=read_only_annotations("Get Context Usage Statistics"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_context_usage_statistics(
    ctx: MCPContext | None = None,
) -> str:
    """Get current context usage statistics.

    USE WHEN: User wants usage statistics, user needs context metrics,
    user requests usage data, user wants to monitor context usage.

    EXAMPLES: 'get context usage statistics', 'show context metrics',
    'get context usage data'.

    RETURNS: JSON with context usage statistics and metrics.

    Returns aggregated statistics from previous load_context analyses
    including average token utilization, file selection patterns,
    and common task types.

    Returns:
        JSON with current statistics and recent entries
    """
    await log_client(
        ctx, "info", "get_context_usage_statistics: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        result = get_context_statistics(root)
        out = json.dumps(result.model_dump(mode="json"), indent=2)
        await log_client(
            ctx,
            "info",
            "get_context_usage_statistics: completed",
            logger_name=__name__,
        )
        return out
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"get_context_usage_statistics: {e!s}",
            logger_name=__name__,
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


# Phase 43: Context analysis resources (read-only, default params)


@mcp.resource(uri="cortex://optimization/context-effectiveness")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def analyze_context_effectiveness_resource() -> str:
    """Resource: Analyze context effectiveness (current session, default project). Read via cortex://optimization/context-effectiveness."""
    return await analyze_context_effectiveness(analyze_all_sessions=False)


@mcp.resource(uri="cortex://optimization/context-usage-statistics")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_context_usage_statistics_resource() -> str:
    """Resource: Context usage statistics (default project). Read via cortex://optimization/context-usage-statistics."""
    return await get_context_usage_statistics()
