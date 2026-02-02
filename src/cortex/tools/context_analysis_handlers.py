"""
Context Analysis Tool Handlers

MCP tools for analyzing load_context effectiveness and managing statistics.
"""

import json

import cortex.tools.phase4_optimization as phase4_opt
from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.server import mcp
from cortex.tools.context_analysis_operations import (
    analyze_current_session,
    analyze_session_logs,
    get_context_statistics,
)


async def _analyze_context_effectiveness_impl(
    project_root: str | None, analyze_all_sessions: bool
) -> str:
    """Run analyze_context_effectiveness logic. Raises on error."""
    root = phase4_opt.get_project_root(project_root)
    if analyze_all_sessions:
        result = analyze_session_logs(root)
    else:
        result = analyze_current_session(root)
    return json.dumps(result.model_dump(mode="json"), indent=2)


@mcp.tool()
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def analyze_context_effectiveness(
    project_root: str | None = None,
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
        project_root: Project root path (default: current directory)
        analyze_all_sessions: If True, analyze all sessions; if False (default),
            analyze only the current session

    Returns:
        JSON with analysis results and statistics summary
    """
    await log_client(
        ctx, "info", "analyze_context_effectiveness: starting", logger_name=__name__
    )
    try:
        out = await _analyze_context_effectiveness_impl(
            project_root, analyze_all_sessions
        )
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


@mcp.tool()
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_context_usage_statistics(
    project_root: str | None = None,
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

    Args:
        project_root: Project root path (default: current directory)

    Returns:
        JSON with current statistics and recent entries
    """
    await log_client(
        ctx, "info", "get_context_usage_statistics: starting", logger_name=__name__
    )
    try:
        root = phase4_opt.get_project_root(project_root)
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
