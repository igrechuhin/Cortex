"""
Phase 4: Token Optimization Tool Handlers

This module contains the MCP tool decorators and handlers for context loading,
content summarization, and relevance scoring.

Total: 3 tools, 3 resources
- load_context (resource: cortex://context)
- summarize_content / summarize_content_resource (cortex://optimization/summarize/{file_name})
- get_relevance_scores / get_relevance_scores_resource (cortex://optimization/relevance-scores/{task_description})

Note: load_progressive_context has been merged into load_context with strategy="progressive"
"""

import json
from typing import cast
from urllib.parse import unquote

# Import via facade to allow test patching
import cortex.tools.optimization as opt
from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ContextDepth, ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.optimization.relevance_operations import get_relevance_scores_impl
from cortex.tools.optimization.summarization_operations import summarize_content_impl
from cortex.tools.session.models import SESSION_SCOPE_PROMPT

from .handlers_load import (
    check_optimization_enabled,
    execute_load_context_with_logging,
)
from .handlers_validation import (
    is_non_trivial_task,
    resolve_load_context_budget,
    validate_task_description_length,
)

# Re-export for backward compatibility (tests import from this module)
__all__ = ["is_non_trivial_task"]


def _resolve_load_context_inputs(
    task_description: str | None,
    token_budget: int | None,
) -> tuple[str, int | None]:
    """Resolve zero-arg defaults from session config."""
    if task_description:
        return task_description, token_budget
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    resolved_task = str(cfg.get("task_description", "session context"))
    if token_budget is None:
        raw_budget = cfg.get("token_budget")
        if isinstance(raw_budget, int):
            token_budget = raw_budget
    return resolved_task, token_budget


async def _execute_load_context(
    resolved_task: str,
    effective_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    depth: ContextDepth | None,
    response_format: ResponseFormat,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    """Call execute_load_context_with_logging with the resolved args."""
    return await execute_load_context_with_logging(
        resolved_task,
        effective_budget,
        strategy,
        loading_strategy,
        depth,
        response_format,
        role,
        ctx,
    )


# MCP tool removed — exposed as resource cortex://context/{task_description}
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_context_impl(
    task_description: str | None = None,
    token_budget: int | None = None,
    strategy: str = "dependency_aware",
    loading_strategy: str | None = None,
    depth: ContextDepth | None = None,
    response_format: ResponseFormat = ResponseFormat.CONCISE,
    role: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Load relevant context for a task within token budget.

    USE WHEN: User starts a task, needs project context, requests relevant files.
    EXAMPLES: 'load context for refactoring task', 'get relevant files for feature X'.
    RETURNS: JSON with selected files, content, relevance scores, token usage.

    Args:
        task_description: Description of the task to perform
        token_budget: Maximum tokens (default from config)
        strategy: Loading strategy (dependency_aware, priority, hybrid, section_level, progressive)
        loading_strategy: Required when strategy="progressive" (by_relevance, by_priority, by_dependencies)
        depth: Content depth (metadata_only, summary, full). Auto-selected if None based on budget.
        response_format: Response format (concise or detailed)

    Returns:
        JSON with selected files, their content, and relevance scores
    """
    return await _load_context_body(
        task_description,
        token_budget,
        strategy,
        loading_strategy,
        depth,
        response_format,
        role,
        ctx,
    )


async def _load_context_body(
    task_description: str | None,
    token_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    depth: ContextDepth | None,
    response_format: ResponseFormat,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    """Resolve inputs, validate, and execute load_context."""
    await log_client(ctx, "info", "load_context: starting", logger_name=__name__)
    resolved_task, resolved_budget = _resolve_load_context_inputs(
        task_description, token_budget
    )
    if (length_error := validate_task_description_length(resolved_task)) is not None:
        return length_error
    effective_budget, budget_error = resolve_load_context_budget(
        resolved_task, resolved_budget
    )
    if budget_error is not None:
        return budget_error
    return await _execute_load_context(
        resolved_task,
        effective_budget,
        strategy,
        loading_strategy,
        depth,
        response_format,
        role,
        ctx,
    )


# MCP registration removed — unused tool
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

    Args:
        file_name: Optional Memory Bank file to summarize (e.g. "activeContext.md").
            If None, summarization scope is configuration-dependent.
        target_reduction: Optional target reduction ratio (0.0–1.0). If None,
            uses configured default.
        strategy: Optional strategy name (e.g. "progressive", "tiered"). If None,
            uses configured default.
        ctx: MCP context (automatically provided).

    Example (Success):
        ```json
        {
          "status": "success",
          "file_name": "activeContext.md",
          "original_tokens": 1200,
          "summarized_tokens": 600,
          "reduction_ratio": 0.5,
          "strategy": "progressive"
        }
        ```

    Example (Error - optimization disabled):
        ```json
        {
          "status": "error",
          "error": "Context optimization is disabled",
          "error_type": "ValueError"
        }
        ```
    """
    return await _summarize_content_body(file_name, target_reduction, strategy, ctx)


async def _summarize_content_body(
    file_name: str | None,
    target_reduction: float | None,
    strategy: str | None,
    ctx: MCPContext | None,
) -> str:
    """Execute summarize_content with error handling."""
    await log_client(ctx, "info", "summarize_content: starting", logger_name=__name__)
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await opt.get_managers(root)
        enabled_error = await check_optimization_enabled(mgrs)
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


# MCP registration removed — internal to load_context
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_relevance_scores(
    task_description: str | None = None,
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
    breakdown. When include_sections is True, includes section-level
    scores per file.

    Args:
        task_description: Natural language description of the task; used
            for semantic matching against memory bank content.
        include_sections: If True, include per-section relevance scores
            within each file. Default: False (file-level only).

    Example (Success):
        ```json
        {
          "status": "success",
          "task_description": "refactoring memory bank",
          "files": [
            { "file_name": "activeContext.md", "relevance_score": 0.92, "tokens": 1200 },
            { "file_name": "systemPatterns.md", "relevance_score": 0.78, "tokens": 800 }
          ],
          "include_sections": false
        }
        ```

    Example (Error - optimization disabled):
        ```json
        {
          "status": "error",
          "error": "Context optimization is disabled",
          "error_type": "ValueError"
        }
        ```
    """
    return await _get_relevance_scores_body(task_description, include_sections, ctx)


def _resolve_relevance_task(task_description: str | None) -> str:
    """Resolve task_description with zero-arg fallback from session config."""
    if task_description:
        return task_description
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    return str(cfg.get("task_description", "session context"))


async def _get_relevance_scores_body(
    task_description: str | None,
    include_sections: bool,
    ctx: MCPContext | None,
) -> str:
    """Execute get_relevance_scores with error handling."""
    await log_client(
        ctx, "info", "get_relevance_scores: starting", logger_name=__name__
    )
    resolved_task = _resolve_relevance_task(task_description)
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await opt.get_managers(root)
        enabled_error = await check_optimization_enabled(mgrs)
        if enabled_error:
            return enabled_error
        out = await get_relevance_scores_impl(mgrs, resolved_task, include_sections)
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

_LOAD_CONTEXT_DEFAULT_BUDGET = 10000


def _append_session_scope_to_context_payload(payload: str) -> str:
    """Add session scope guidance to successful context payloads."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload

    if not isinstance(parsed, dict):
        return payload
    payload_data = cast(dict[str, object], parsed)
    if payload_data.get("status") != "success":
        return payload

    payload_data["session_scope"] = SESSION_SCOPE_PROMPT
    return json.dumps(payload_data, indent=2)


@mcp.resource(uri="cortex://context")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_context() -> str:
    """Resource: Load context for current task. Zero-arg — reads task from session config.

    Falls back to "general session context" if no session config exists.
    """
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    task = str(cfg.get("task_description", "general session context"))
    raw_budget = cfg.get("token_budget", _LOAD_CONTEXT_DEFAULT_BUDGET)
    budget = raw_budget if isinstance(raw_budget, int) else _LOAD_CONTEXT_DEFAULT_BUDGET
    result = await load_context_impl(
        task_description=task,
        token_budget=budget,
        strategy="dependency_aware",
    )
    return _append_session_scope_to_context_payload(result)


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_relevance_scores_resource(task_description: str) -> str:
    """Resource: Relevance scores for task. Read via cortex://optimization/relevance-scores/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await get_relevance_scores(
        task_description=decoded,
        include_sections=False,
    )


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def summarize_content_resource(file_name: str) -> str:
    """Resource: Summarize file (default reduction/strategy from config). Read via cortex://optimization/summarize/{file_name}. Use file_name '_' for all files."""
    decoded = unquote(file_name)
    name_arg: str | None = None if decoded in ("_", "all", "") else decoded
    return await summarize_content(
        file_name=name_arg,
        target_reduction=None,
        strategy=None,
    )
