"""
Context Analysis Tool Handlers

MCP tools for analyzing load_context effectiveness and managing statistics.
"""

import json

import cortex.tools.phase4_optimization as phase4_opt
from cortex.server import mcp
from cortex.tools.context_analysis_operations import (
    analyze_current_session,
    analyze_session_logs,
    get_context_statistics,
)


@mcp.tool()
async def analyze_context_effectiveness(
    project_root: str | None = None,
    analyze_all_sessions: bool = False,
) -> str:
    """Analyze load_context calls and update usage statistics.

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
    try:
        root = phase4_opt.get_project_root(project_root)
        if analyze_all_sessions:
            result = analyze_session_logs(root)
        else:
            result = analyze_current_session(root)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def get_context_usage_statistics(
    project_root: str | None = None,
) -> str:
    """Get current context usage statistics.

    Returns aggregated statistics from previous load_context analyses
    including average token utilization, file selection patterns,
    and common task types.

    Args:
        project_root: Project root path (default: current directory)

    Returns:
        JSON with current statistics and recent entries
    """
    try:
        root = phase4_opt.get_project_root(project_root)
        result = get_context_statistics(root)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )
