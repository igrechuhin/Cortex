"""Context loading, summarization, and relevance-score handlers."""

from __future__ import annotations

import json

# Import via facade to allow test patching
import cortex.tools.optimization as opt
from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.context_logging import MCPContext
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import ContextDepth, OperationStatus, ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.optimization.relevance_operations import get_relevance_scores_impl
from cortex.tools.optimization.summarization_operations import summarize_content_impl

from .handlers_load import (
    check_optimization_enabled,
    execute_load_context_with_logging,
)
from .handlers_validation import (
    resolve_load_context_budget,
    validate_task_description_length,
)


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


async def _log_client(
    ctx: MCPContext | None,
    level: str,
    message: str,
) -> None:
    """Route logging through handlers facade so tests can patch one symbol."""
    from cortex.tools.optimization import handlers as handlers_mod

    await handlers_mod.log_client(ctx, level, message, logger_name=__name__)


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
    """Load relevant context for a task within token budget."""
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
    await _log_client(ctx, "info", "load_context: starting")
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


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def summarize_content(
    file_name: str | None = None,
    target_reduction: float | None = None,
    strategy: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Summarize Memory Bank content to reduce token usage."""
    return await _summarize_content_body(file_name, target_reduction, strategy, ctx)


async def _summarize_content_body(
    file_name: str | None,
    target_reduction: float | None,
    strategy: str | None,
    ctx: MCPContext | None,
) -> str:
    """Execute summarize_content with error handling."""
    await _log_client(ctx, "info", "summarize_content: starting")
    try:
        root = await resolve_project_root_async(None, ctx)
        mgrs = await opt.get_managers(root)
        enabled_error = await check_optimization_enabled(mgrs)
        if enabled_error:
            return enabled_error
        out = await summarize_content_impl(mgrs, file_name, target_reduction, strategy)
        await _log_client(ctx, "info", "summarize_content: completed")
        return out
    except Exception as e:
        await _log_client(ctx, "error", f"summarize_content: {e!s}")
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            indent=2,
        )


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_relevance_scores(
    task_description: str | None = None,
    include_sections: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Get relevance scores for Memory Bank files based on task description."""
    return await _get_relevance_scores_body(task_description, include_sections, ctx)


def _resolve_relevance_task(task_description: str | None) -> str:
    """Resolve task_description with zero-arg fallback from session config."""
    if task_description:
        return task_description
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    return str(cfg.get("task_description", "session context"))


async def _execute_relevance_scores_core(
    resolved_task: str,
    include_sections: bool,
    ctx: MCPContext | None,
) -> str:
    root = await resolve_project_root_async(None, ctx)
    mgrs = await opt.get_managers(root)
    enabled_error = await check_optimization_enabled(mgrs)
    if enabled_error:
        return enabled_error
    out = await get_relevance_scores_impl(mgrs, resolved_task, include_sections)
    await _log_client(ctx, "info", "get_relevance_scores: completed")
    return out


async def _get_relevance_scores_body(
    task_description: str | None,
    include_sections: bool,
    ctx: MCPContext | None,
) -> str:
    """Execute get_relevance_scores with error handling."""
    await _log_client(ctx, "info", "get_relevance_scores: starting")
    resolved_task = _resolve_relevance_task(task_description)
    try:
        return await _execute_relevance_scores_core(
            resolved_task, include_sections, ctx
        )
    except Exception as e:
        await _log_client(ctx, "error", f"get_relevance_scores: {e!s}")
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            indent=2,
        )
