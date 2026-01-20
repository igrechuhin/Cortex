"""
Phase 4: Token Optimization Tool Handlers

This module contains the MCP tool decorators and handlers for context loading,
progressive loading, content summarization, and relevance scoring.

Total: 4 tools
- load_context
- load_progressive_context
- summarize_content
- get_relevance_scores
"""

import json

# Import via facade to allow test patching
import cortex.tools.phase4_optimization as phase4_opt
from cortex.server import mcp
from cortex.tools.phase4_context_operations import load_context_impl
from cortex.tools.phase4_progressive_operations import (
    load_progressive_context_impl,
)
from cortex.tools.phase4_relevance_operations import get_relevance_scores_impl
from cortex.tools.phase4_summarization_operations import summarize_content_impl


@mcp.tool()
async def load_context(
    task_description: str,
    token_budget: int | None = None,
    strategy: str = "dependency_aware",
    project_root: str | None = None,
) -> str:
    """Load relevant context for a task within token budget.

    This tool should be called at the START of any task to:
    - Load memory bank files relevant to the task
    - Load applicable rules and patterns
    - Provide project context before making changes

    Args:
        task_description: Description of the task to perform
        token_budget: Maximum tokens to include (default from config)
        strategy: Loading strategy (dependency_aware, priority, hybrid)
        project_root: Project root path (default: current directory)

    Returns:
        JSON with selected files, their content, and relevance scores
    """
    try:
        root = phase4_opt.get_project_root(project_root)
        mgrs = await phase4_opt.get_managers(root)
        return await load_context_impl(mgrs, task_description, token_budget, strategy)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def load_progressive_context(
    task_description: str,
    token_budget: int | None = None,
    loading_strategy: str = "by_relevance",
    project_root: str | None = None,
) -> str:
    """Load context progressively based on strategy."""
    try:
        root = phase4_opt.get_project_root(project_root)
        mgrs = await phase4_opt.get_managers(root)
        return await load_progressive_context_impl(
            mgrs, task_description, token_budget, loading_strategy
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def summarize_content(
    file_name: str | None = None,
    target_reduction: float = 0.5,
    strategy: str = "extract_key_sections",
    project_root: str | None = None,
) -> str:
    """Summarize Memory Bank content to reduce token usage."""
    try:
        root = phase4_opt.get_project_root(project_root)
        mgrs = await phase4_opt.get_managers(root)
        return await summarize_content_impl(mgrs, file_name, target_reduction, strategy)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool()
async def get_relevance_scores(
    task_description: str,
    project_root: str | None = None,
    include_sections: bool = False,
) -> str:
    """Get relevance scores for all Memory Bank files."""
    try:
        root = phase4_opt.get_project_root(project_root)
        mgrs = await phase4_opt.get_managers(root)
        return await get_relevance_scores_impl(mgrs, task_description, include_sections)
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )
