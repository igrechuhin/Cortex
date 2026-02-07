"""
Phase 4: Token Optimization Tool Handlers

This module contains the MCP tool decorators and handlers for context loading,
progressive loading, content summarization, and relevance scoring.

Total: 4 tools, 4 resources
- load_context / load_context_resource (cortex://optimization/load-context/{task_description})
- load_progressive_context / load_progressive_context_resource (cortex://optimization/load-progressive-context/{task_description})
- summarize_content / summarize_content_resource (cortex://optimization/summarize/{file_name})
- get_relevance_scores / get_relevance_scores_resource (cortex://optimization/relevance-scores/{task_description})
"""

import json
from urllib.parse import unquote

# Import via facade to allow test patching
import cortex.tools.phase4_optimization as phase4_opt
from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_COMPLEX,
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
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.server import mcp
from cortex.tools.phase4_context_operations import load_context_impl
from cortex.tools.phase4_progressive_operations import (
    load_progressive_context_impl,
)
from cortex.tools.phase4_relevance_operations import get_relevance_scores_impl
from cortex.tools.phase4_summarization_operations import summarize_content_impl


async def _check_optimization_enabled(
    mgrs: ManagersDict,
) -> str | None:
    """Check if optimization is enabled. Returns error JSON or None."""
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )
    if not optimization_config.is_optimization_enabled():
        return json.dumps(
            {
                "status": "error",
                "error": "Optimization features are disabled in configuration",
            },
            indent=2,
        )
    return None


@mcp.tool(annotations=read_only_annotations("Load Context"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_context(
    task_description: str,
    token_budget: int | None = None,
    strategy: str = "dependency_aware",
    ctx: MCPContext | None = None,
) -> str:
    """Load relevant context for a task within token budget.

    USE WHEN: User starts a task, user needs project context, user requests
    relevant files, user wants context for specific task, user needs memory
    bank content.

    EXAMPLES: 'load context for refactoring task', 'get relevant files for
    feature X', 'load context with 5000 token budget', 'get context for bug
    fix'.

    RETURNS: JSON with selected files, their content, relevance scores, and
    token usage.

    This tool should be called at the START of any task to:
    - Load memory bank files relevant to the task
    - Load applicable rules and patterns
    - Provide project context before making changes

    Args:
        task_description: Description of the task to perform
        token_budget: Maximum tokens to include (default from config)
        strategy: Loading strategy (dependency_aware, priority, hybrid)

    Returns:
        JSON with selected files, their content, and relevance scores
    """
    await log_client(ctx, "info", "load_context: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await phase4_opt.get_managers(root)

        enabled_error = await _check_optimization_enabled(mgrs)
        if enabled_error:
            return enabled_error

        out = await load_context_impl(
            mgrs, task_description, token_budget, strategy, project_root=root
        )
        await log_client(ctx, "info", "load_context: completed", logger_name=__name__)
        return out
    except Exception as e:
        await log_client(ctx, "error", f"load_context: {e!s}", logger_name=__name__)
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool(annotations=read_only_annotations("Load Progressive Context"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_progressive_context(
    task_description: str,
    token_budget: int | None = None,
    loading_strategy: str = "by_relevance",
    ctx: MCPContext | None = None,
) -> str:
    """Load context progressively based on relevance, loading files
    incrementally as needed.

    USE WHEN: User needs incremental context loading, user wants progressive
    file loading, user requests staged context, user needs context in
    batches.

    EXAMPLES: 'load progressive context for task', 'get context
    progressively', 'load context in stages'.

    RETURNS: JSON with progressive context batches, each with files and
    relevance scores.
    """
    await log_client(
        ctx, "info", "load_progressive_context: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await phase4_opt.get_managers(root)

        enabled_error = await _check_optimization_enabled(mgrs)
        if enabled_error:
            return enabled_error

        out = await load_progressive_context_impl(
            mgrs, task_description, token_budget, loading_strategy
        )
        await log_client(
            ctx, "info", "load_progressive_context: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx, "error", f"load_progressive_context: {e!s}", logger_name=__name__
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool(annotations=read_only_annotations("Summarize Content"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def summarize_content(
    file_name: str | None = None,
    target_reduction: float | None = None,
    strategy: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Summarize Memory Bank content to reduce token usage while preserving
    key information.

    USE WHEN: User needs to reduce token count, user wants content summary,
    user requests token optimization, user needs condensed content.

    EXAMPLES: 'summarize projectBrief.md', 'reduce token usage for
    activeContext.md', 'summarize content by 50%'.

    RETURNS: JSON with summarized content and token reduction metrics.
    """
    await log_client(ctx, "info", "summarize_content: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await phase4_opt.get_managers(root)

        enabled_error = await _check_optimization_enabled(mgrs)
        if enabled_error:
            return enabled_error

        out = await summarize_content_impl(mgrs, file_name, target_reduction, strategy)
        await log_client(
            ctx, "info", "summarize_content: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx, "error", f"summarize_content: {e!s}", logger_name=__name__
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool(annotations=read_only_annotations("Get Relevance Scores"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_relevance_scores(
    task_description: str,
    include_sections: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Get relevance scores for Memory Bank files based on task description.

    USE WHEN: User wants to know file relevance, user needs relevance
    ranking, user requests relevance scores, user wants to prioritize
    files.

    EXAMPLES: 'get relevance scores for refactoring task', 'score files for
    feature X', 'rank files by relevance'.

    RETURNS: JSON with files ranked by relevance scores and detailed scoring
    breakdown.
    """
    await log_client(
        ctx, "info", "get_relevance_scores: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await phase4_opt.get_managers(root)

        enabled_error = await _check_optimization_enabled(mgrs)
        if enabled_error:
            return enabled_error

        out = await get_relevance_scores_impl(mgrs, task_description, include_sections)
        await log_client(
            ctx, "info", "get_relevance_scores: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx, "error", f"get_relevance_scores: {e!s}", logger_name=__name__
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


# Phase 43: Optimization resources (read-only, default params)


@mcp.resource(uri="cortex://optimization/load-context/{task_description}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_context_resource(task_description: str) -> str:
    """Resource: Load context for task (default budget/strategy). Read via cortex://optimization/load-context/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await load_context(
        task_description=decoded,
        token_budget=None,
        strategy="dependency_aware",
    )


@mcp.resource(uri="cortex://optimization/load-progressive-context/{task_description}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_progressive_context_resource(task_description: str) -> str:
    """Resource: Load progressive context for task. Read via cortex://optimization/load-progressive-context/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await load_progressive_context(
        task_description=decoded,
        token_budget=None,
        loading_strategy="by_relevance",
    )


@mcp.resource(uri="cortex://optimization/relevance-scores/{task_description}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_relevance_scores_resource(task_description: str) -> str:
    """Resource: Relevance scores for task. Read via cortex://optimization/relevance-scores/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await get_relevance_scores(
        task_description=decoded,
        include_sections=False,
    )


@mcp.resource(uri="cortex://optimization/summarize/{file_name}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def summarize_content_resource(file_name: str) -> str:
    """Resource: Summarize file (default reduction/strategy from config). Read via cortex://optimization/summarize/{file_name}. Use file_name '_' for all files."""
    decoded = unquote(file_name)
    name_arg: str | None = None if decoded in ("_", "all", "") else decoded
    return await summarize_content(
        file_name=name_arg,
        target_reduction=None,  # Use config default
        strategy=None,  # Use config default
    )
