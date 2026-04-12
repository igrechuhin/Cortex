"""
Analysis Operations Tools

This module contains analysis tools for Memory Bank.

Total: 1 tool, 1 resource
- analyze (resource: cortex://analysis)
"""

import json
from pathlib import Path

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import OperationStatus
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers import initialization
from cortex.managers.types import ManagersDict
from cortex.server import mcp
from cortex.tools.analysis.token_budget import (
    compute_token_budget,
    format_token_budget_report,
)
from cortex.tools.context.analysis_helpers import (
    AnalysisTarget,
    normalize_analysis_target,
    parse_analysis_target,
)
from cortex.tools.context.analysis_run_helpers import (
    analysis_invalid_target_response,
    dispatch_analysis_target,
    get_analysis_managers,
    run_context_analysis,
    run_health_analysis,
)


async def get_managers(root: Path) -> ManagersDict:
    """Runtime indirection for test patching.

    Some tests patch `cortex.tools.context.analysis_operations.get_managers`.
    """
    return await initialization.get_managers(root)


# MCP tool registration removed — exposed as resource below
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def analyze_impl(
    target: str = "context",
    time_window_days: int | None = None,
    export_format: str = "json",
    categories: list[str] | None = None,
    max_sessions: int | None = None,
    max_calls_per_session: int | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Analyze Memory Bank, context effectiveness, or health-check data.

    USE WHEN: User wants pattern analysis, context effectiveness statistics,
    health-check consolidation, or optimization insights.

    EXAMPLES: 'analyze memory bank patterns', 'analyze project structure',
    'analyze context effectiveness', 'get context usage stats',
    'analyze health check'.

    RETURNS: JSON with analysis results, patterns found, and insights.

    This consolidated tool provides multiple types of analysis:

    1. **usage_patterns**: Analyzes file access frequency, co-access
       patterns, task patterns, and identifies unused files within a time
       window.

    2. **structure**: Analyzes file organization, detects anti-patterns
       (deeply nested directories, oversized files, naming inconsistencies),
       and measures complexity metrics.

    3. **insights**: Generates AI-driven optimization insights with impact
       scoring.

    4. **context / context_all_sessions / context_stats**: Runs
       load_context effectiveness analysis for current session, all sessions,
       or returns aggregated usage statistics.

    5. **health**: Runs prompts/rules/tools health-check analysis and
       returns the consolidated report.

    Args:
        target: Analysis target to perform. Defaults to "context".
            - "usage_patterns": Analyze file access and usage patterns
            - "structure": Analyze file organization and detect issues
            - "insights": Generate actionable optimization recommendations
            - "context": Analyze current-session load_context effectiveness (default)
            - "context_all_sessions": Analyze all-session effectiveness logs
            - "context_stats": Return aggregated context usage statistics
            - "health": Run health-check analysis for prompts/rules/tools

        time_window_days: Number of days to analyze for usage_patterns.
            Example: 30 (analyzes last 30 days). Only applies to
            target="usage_patterns".

        export_format: Output format for insights.
            - "json": Structured JSON data (default)
            - "markdown": Human-readable Markdown format
            - "text": Plain text format
            Only applies to target="insights".

        categories: Specific insight categories to analyze for
            target="insights".
        max_sessions: Optional cap for multi-session context analysis (reserved for
            context_all_sessions style outputs; None = no cap).
        max_calls_per_session: When set, caps load_context call rows in the current-session
            context effectiveness payload (None = full detail). Used by cortex://analysis.

    Returns:
        JSON string. Success: status, target, and type-specific fields
        (patterns, analysis, insights). Error: status "error", error, error_type.

    Note:
        - Usage patterns analysis requires file access history. If no history exists,
          access_frequency and co_access_patterns will be empty.
        - Structure analysis always runs on the current state of the Memory Bank.
        - Insights generation may take longer as it performs comprehensive analysis
          and uses pattern matching algorithms.
        - The time_window_days parameter only affects usage_patterns analysis. For
          structure and insights, this parameter is ignored.
        - Insight categories include: "duplication", "complexity", "organization",
          "dependencies", "naming", "size". If categories is None, all are analyzed.
        - Export formats for insights: "json" provides structured data, "markdown"
          provides formatted documentation, "text" provides plain text summary.
    """
    return await _analyze_dispatch(
        target,
        time_window_days,
        export_format,
        categories,
        ctx,
        max_sessions=max_sessions,
        max_calls_per_session=max_calls_per_session,
    )


async def _analyze_dispatch(
    target: str,
    time_window_days: int | None,
    export_format: str,
    categories: list[str] | None,
    ctx: MCPContext | None,
    *,
    max_sessions: int | None = None,
    max_calls_per_session: int | None = None,
) -> str:
    """Dispatch analysis to the appropriate handler."""
    await log_client(ctx, "info", "analyze: starting", logger_name=__name__)
    normalized_target = normalize_analysis_target(target)
    target_value = normalized_target if normalized_target is not None else target
    root = await resolve_project_root_async(None, ctx)
    parsed_target = parse_analysis_target(target_value)
    if parsed_target is not None:
        return await _analyze_run_or_error(
            ctx, parsed_target, root, time_window_days, export_format, categories
        )
    return await _analyze_consolidated_target(
        target_value,
        root,
        ctx,
        max_sessions=max_sessions,
        max_calls_per_session=max_calls_per_session,
    )


async def _analyze_consolidated_target(
    target_value: str,
    root: Path,
    ctx: MCPContext | None,
    *,
    max_sessions: int | None = None,
    max_calls_per_session: int | None = None,
) -> str:
    """Handle consolidated analytics targets: context* and health."""
    if target_value.startswith("context"):
        return await run_context_analysis(
            target_value,
            root,
            max_sessions=max_sessions,
            max_calls_per_session=max_calls_per_session,
        )
    if target_value in ("health", "health_check", "prompts", "rules", "tools", "all"):
        health_type = (
            "all" if target_value in ("health", "health_check") else target_value
        )
        return await run_health_analysis(root, analysis_type=health_type)
    await log_client(ctx, "warning", "analyze: invalid target")
    return analysis_invalid_target_response(target_value)


async def _analyze_run_or_error(
    ctx: MCPContext | None,
    parsed_target: AnalysisTarget,
    root: Path,
    time_window_days: int | None,
    export_format: str,
    categories: list[str] | None,
) -> str:
    """Run analysis and handle exceptions with context logging."""
    try:
        mgrs = await get_managers(root)
        analyzers = await get_analysis_managers(mgrs)
        result = await dispatch_analysis_target(
            parsed_target, analyzers, time_window_days, export_format, categories
        )
        await log_client(ctx, "info", "analyze: completed", logger_name=__name__)
        return result
    except Exception as e:
        await log_client(ctx, "error", f"analyze: failed: {e}", logger_name=__name__)
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            indent=2,
        )


@mcp.resource(uri="cortex://analysis")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def analyze() -> str:
    """Resource: Run analysis. Zero-arg — reads target from session config.

    Falls back to "context" if no session config exists. Target must be one of:
    usage_patterns, structure, insights, context.
    """
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    target = str(cfg.get("analysis_target", "context"))
    # AI: Bound default resource payload size for high-frequency cortex://analysis reads.
    base = await analyze_impl(
        target=target,
        time_window_days=None,
        export_format="json",
        categories=None,
        max_sessions=3,
        max_calls_per_session=10,
    )
    root = await resolve_project_root_async(None, None)
    entries = compute_token_budget(root)
    report_md = format_token_budget_report(entries)
    token_payload = {
        "markdown": "## Token Budget\n\n" + report_md,
        "entries": [e.model_dump(mode="json") for e in entries],
    }
    try:
        parsed: object = json.loads(base)
    except json.JSONDecodeError:
        return f"{base}\n\n## Token Budget\n\n{report_md}"
    if isinstance(parsed, dict):
        parsed["token_budget"] = token_payload
        return json.dumps(parsed, indent=2)
    return f"{base}\n\n## Token Budget\n\n{report_md}"
