"""
Phase 4: Token Optimization Tool Handlers

This module contains the MCP tool decorators and handlers for context loading,
content summarization, and relevance scoring.

Total: 3 tools, 3 resources
- load_context / load_context_resource (cortex://optimization/load-context/{task_description})
- summarize_content / summarize_content_resource (cortex://optimization/summarize/{file_name})
- get_relevance_scores / get_relevance_scores_resource (cortex://optimization/relevance-scores/{task_description})

Note: load_progressive_context has been merged into load_context with strategy="progressive"
"""

import json
from pathlib import Path
from typing import cast
from urllib.parse import unquote

# Import via facade to allow test patching
import cortex.tools.phase4_optimization as phase4_opt
from cortex.core.constants import (
    MAX_TASK_DESCRIPTION_CHARS,
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
from cortex.core.models import ContextDepth, ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.agent_roles import (
    AgentRole,
    detect_agent_role,
    normalize_role_name,
)
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.server import mcp
from cortex.tools.phase4_context_operations import load_context_impl
from cortex.tools.phase4_relevance_operations import get_relevance_scores_impl
from cortex.tools.phase4_summarization_operations import summarize_content_impl


def _determine_agent_role(role: str | None, task_description: str) -> AgentRole:
    """Determine effective agent role from explicit parameter or task description.

    Args:
        role: Explicit role parameter
        task_description: Task description for keyword-based detection

    Returns:
        Determined agent role
    """
    explicit_role = normalize_role_name(role) if role is not None else None
    return explicit_role or detect_agent_role(task_description)


def _validate_explicit_budget_for_non_trivial(
    task_description: str, token_budget: int | None
) -> str | None:
    """Require explicit non-zero token_budget for non-trivial tasks.

    For implement/refactor/fix/debug and similar flows, token_budget must be
    explicitly provided (not omitted and not 0). Returns a validation error
    when the task is non-trivial and token_budget is None or 0.

    Args:
        task_description: Task description
        token_budget: Token budget (None = omitted)

    Returns:
        Error JSON string if validation fails, None otherwise
    """
    if not is_non_trivial_task(task_description):
        return None
    if token_budget is not None and token_budget != 0:
        return None
    return json.dumps(
        {
            "status": "error",
            "error": (
                "Explicit non-zero token_budget is required for non-trivial tasks "
                "(implement/add, fix/debug, refactor, test, optimize). "
                "Omitted or zero token_budget is not allowed. "
                "Use e.g. token_budget=10000 for implement/add, 15000 for fix/debug."
            ),
            "error_type": "ValueError",
            "task_description": task_description,
            "action_required": "Pass an explicit positive token_budget (e.g. 10000 or 15000).",
            "suggestion": (
                "For non-trivial tasks, use appropriate token budgets: "
                "10000 for implement/add/update/modify, "
                "15000 for fix/debug/other, "
                "20000-30000 for small features, "
                "15000 for optimization, "
                "7000-8000 for narrow review/documentation."
            ),
        },
        indent=2,
    )


def _resolve_load_context_budget(
    task_description: str, token_budget: int | None
) -> tuple[int | None, str | None]:
    """Validate explicit budget for non-trivial tasks and resolve effective budget.

    Returns:
        (effective_budget, error_json_or_none). If error is non-None, caller should return it.
    """
    validation_error = _validate_explicit_budget_for_non_trivial(
        task_description, token_budget
    )
    if validation_error:
        return None, validation_error
    effective_budget = None if token_budget == 0 else token_budget
    return effective_budget, None


async def _execute_load_context_with_logging(
    task_description: str,
    effective_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    depth: ContextDepth | None,
    response_format: ResponseFormat,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    """Run _execute_load_context with success/error logging. Returns result JSON or error string."""
    try:
        result = await _execute_load_context(
            task_description,
            effective_budget,
            strategy,
            loading_strategy,
            depth,
            response_format,
            role,
            ctx,
        )
        await log_client(ctx, "info", "load_context: completed", logger_name=__name__)
        return result
    except Exception as e:
        await log_client(ctx, "error", f"load_context: {e!s}", logger_name=__name__)
        return _format_load_context_error(e)


def is_non_trivial_task(task_description: str) -> bool:
    """Detect if a task is non-trivial based on keywords."""
    task_lower = task_description.lower()
    keywords = (
        "implement add create build develop fix debug resolve correct repair "
        "refactor refactoring restructure restructuring reorganize test testing "
        "verify validate optimize optimization improve improving enhance "
        "update modify change edit"
    ).split()
    return any(kw in task_lower for kw in keywords)


def _format_load_context_error(error: Exception) -> str:
    """Format error response for load_context failures."""
    from cortex.tools.tool_error_formatters import format_tool_error

    return format_tool_error(
        error,
        suggestion=(
            "Verify task_description is clear and token_budget is appropriate. "
            "Try reducing token_budget or using depth='metadata_only' for large contexts."
        ),
        example={
            "task_description": "Example task description",
            "token_budget": 10000,
            "strategy": "dependency_aware",
        },
    )


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


async def _load_context_execute(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    effective_depth: str,
    root: Path,
    agent_role: AgentRole | None = None,
) -> str:
    """Execute context loading with appropriate strategy.

    Args:
        mgrs: Managers dictionary
        task_description: Task description
        token_budget: Token budget
        strategy: Loading strategy
        loading_strategy: Progressive loading strategy
        effective_depth: Effective depth level
        root: Project root path
        agent_role: Optional agent role for role-based context selection

    Returns:
        JSON string with loaded context
    """
    if strategy == "progressive":
        return await _load_context_progressive(
            mgrs, task_description, token_budget, loading_strategy
        )

    return await load_context_impl(
        mgrs,
        task_description,
        token_budget,
        strategy,
        depth=effective_depth,
        project_root=root,
        agent_role=agent_role,
    )


async def _load_context_with_error_handling(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    effective_depth: str,
    root: Path,
    agent_role: AgentRole | None = None,
) -> str:
    """Execute context loading with error handling.

    Args:
        mgrs: Managers dictionary
        task_description: Task description
        token_budget: Token budget
        strategy: Loading strategy
        loading_strategy: Progressive loading strategy
        effective_depth: Effective depth level
        root: Project root path
        agent_role: Optional agent role for role-based context selection

    Returns:
        JSON string with loaded context or error
    """
    try:
        return await _load_context_execute(
            mgrs,
            task_description,
            token_budget,
            strategy,
            loading_strategy,
            effective_depth,
            root,
            agent_role,
        )
    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _initialize_context_loading(
    ctx: MCPContext | None,
) -> tuple[Path, ManagersDict, str | None]:
    """Initialize context loading with managers and check enabled status.

    Args:
        ctx: MCP context

    Returns:
        Tuple of (root, mgrs, enabled_error). enabled_error is None if enabled.
    """
    root = await resolve_project_root_async(None, ctx)
    mgrs = await phase4_opt.get_managers(root)
    enabled_error = await _check_optimization_enabled(mgrs)
    return root, mgrs, enabled_error


async def _validate_and_initialize_context_loading(
    task_description: str, token_budget: int | None, ctx: MCPContext | None
) -> tuple[Path | None, ManagersDict | None, str | None]:
    """Validate budget and initialize context loading.

    Returns:
        Tuple of (root, managers, error) where error is None if successful
    """
    validation_error = _validate_explicit_budget_for_non_trivial(
        task_description, token_budget
    )
    if validation_error:
        return None, None, validation_error
    root, mgrs, enabled_error = await _initialize_context_loading(ctx)
    if enabled_error:
        return None, None, enabled_error
    return root, mgrs, None


async def _execute_load_context(
    task_description: str,
    token_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    depth: ContextDepth | None,
    response_format: ResponseFormat,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    """Execute load_context with initialization and error handling.

    Args:
        task_description: Task description
        token_budget: Token budget
        strategy: Loading strategy
        loading_strategy: Progressive loading strategy
        depth: Content depth level
        response_format: Response format
        ctx: MCP context

    Returns:
        JSON string with loaded context or error
    """
    root, mgrs, error = await _validate_and_initialize_context_loading(
        task_description, token_budget, ctx
    )
    if error or root is None or mgrs is None:
        return error or json.dumps({"status": "error", "error": "Failed to initialize"})

    agent_role = _determine_agent_role(role, task_description)
    effective_depth = _determine_depth_from_budget(depth, token_budget)
    out = await _load_context_with_error_handling(
        mgrs,
        task_description,
        token_budget,
        strategy,
        loading_strategy,
        effective_depth.value,
        root,
        agent_role,
    )
    return _format_and_add_warnings_if_needed(
        out, response_format, agent_role.value, task_description, token_budget
    )


def _format_and_add_warnings_if_needed(
    out: str,
    response_format: ResponseFormat,
    role: str,
    task_description: str,
    token_budget: int | None,
) -> str:
    """Format response and add zero-file warnings if needed."""
    result_str = _format_load_context_response(out, response_format, role)
    if is_non_trivial_task(task_description):
        result_str = _add_zero_file_warning_if_needed(
            result_str, task_description, token_budget
        )
    return result_str


def _count_files_from_result(result_data: dict[str, object]) -> int:
    """Count files from load_context result data.

    Args:
        result_data: Parsed JSON result data

    Returns:
        Number of files selected
    """
    files_count = 0
    if "files" in result_data:
        # metadata_only format
        files_list = result_data.get("files")
        if isinstance(files_list, list):
            files_count = len(files_list)  # type: ignore[arg-type]
        elif "total_files" in result_data:
            total_files = result_data.get("total_files")
            if isinstance(total_files, int):
                files_count = total_files
    elif "selected_files" in result_data:
        # full/summary format
        selected_files = result_data.get("selected_files")
        if isinstance(selected_files, list):
            files_count = len(selected_files)  # type: ignore[arg-type]
    return files_count


def _add_zero_file_warning_if_needed(
    result_str: str, task_description: str, token_budget: int | None
) -> str:
    """Add zero-file warning to result if non-trivial task has zero files.

    Args:
        result_str: JSON string result from load_context
        task_description: Task description
        token_budget: Token budget used

    Returns:
        Updated result string with warning if needed, original otherwise
    """
    try:
        result_data: dict[str, object] = json.loads(result_str)
        if result_data.get("status") != "success":
            return result_str

        files_count = _count_files_from_result(result_data)
        if files_count == 0:
            warnings_raw = result_data.get("warnings")
            warnings: list[dict[str, object]] = (
                list(warnings_raw) if isinstance(warnings_raw, list) else []  # type: ignore[arg-type]
            )
            warnings.append(
                {
                    "type": "zero_files_selected",
                    "message": (
                        "Non-trivial task resulted in zero selected files. "
                        "This may indicate insufficient context or a configuration issue. "
                        "Consider increasing token_budget or reviewing task_description."
                    ),
                    "task_description": task_description,
                    "token_budget": token_budget,
                }
            )
            result_data["warnings"] = warnings
            return json.dumps(result_data, indent=2)
    except (json.JSONDecodeError, KeyError, TypeError):
        # If parsing fails, return original response
        pass

    return result_str


def _validate_task_description_length(task_description: str) -> str | None:
    """Return error JSON if task_description exceeds max length, else None."""
    if len(task_description) <= MAX_TASK_DESCRIPTION_CHARS:
        return None
    return json.dumps(
        {
            "status": "error",
            "error": (
                f"task_description too long: {len(task_description)} chars "
                f"exceeds limit of {MAX_TASK_DESCRIPTION_CHARS}"
            ),
            "error_type": "ValueError",
        },
        indent=2,
    )


@mcp.tool(annotations=read_only_annotations("Load Context"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_context(
    task_description: str,
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
    await log_client(ctx, "info", "load_context: starting", logger_name=__name__)
    length_error = _validate_task_description_length(task_description)
    if length_error:
        return length_error
    effective_budget, budget_error = _resolve_load_context_budget(
        task_description, token_budget
    )
    if budget_error:
        return budget_error
    return await _execute_load_context_with_logging(
        task_description,
        effective_budget,
        strategy,
        loading_strategy,
        depth,
        response_format,
        role,
        ctx,
    )


def _determine_depth_from_budget(
    depth: ContextDepth | None,
    token_budget: int | None,
) -> ContextDepth:
    """Determine depth level from budget if not explicitly specified.

    Args:
        depth: Explicit depth level or None
        token_budget: Token budget or None

    Returns:
        Effective depth level
    """
    if depth is not None:
        return depth

    if token_budget is None:
        return ContextDepth.FULL

    if token_budget < 5000:
        return ContextDepth.METADATA_ONLY
    if token_budget <= 15000:
        return ContextDepth.SUMMARY
    return ContextDepth.FULL


async def _load_context_progressive(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    loading_strategy: str | None,
) -> str:
    """Load context using progressive strategy."""
    from cortex.tools.phase4_progressive_operations import (
        load_progressive_context_impl,
    )

    effective_loading_strategy = loading_strategy or "by_relevance"
    return await load_progressive_context_impl(
        mgrs, task_description, token_budget, effective_loading_strategy
    )


def _format_detailed_load_context_response(out: str, role: str | None) -> str:
    """Return detailed response JSON, injecting role when available."""
    if role is None:
        return out
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return out
    if not isinstance(data, dict):
        return out
    typed = cast(dict[str, object], data)
    if "role" not in typed:
        typed["role"] = role
    return json.dumps(typed, indent=2)


def _build_concise_payload(data: dict[str, object], role: str | None) -> str:
    """Build concise response payload from detailed JSON data."""
    selected_files_raw = data.get("selected_files")
    file_names: list[str] = []
    if isinstance(selected_files_raw, dict):
        selected_files_typed = cast(dict[str, object], selected_files_raw)
        file_names = sorted(selected_files_typed.keys())

    concise_payload: dict[str, object] = {
        "status": data.get("status", "success"),
        "task_description": data.get("task_description"),
        "strategy": data.get("strategy"),
        "file_names": file_names,
        "total_tokens": data.get("total_tokens"),
        "utilization": data.get("utilization"),
    }
    if role is not None:
        concise_payload["role"] = role
    return json.dumps(concise_payload, indent=2)


def _format_load_context_response(
    out: str,
    response_format: ResponseFormat,
    role: str | None = None,
) -> str:
    """Format load_context response payload based on response_format."""
    if response_format != ResponseFormat.CONCISE:
        return _format_detailed_load_context_response(out, role)

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return out
    if not isinstance(data, dict):
        return out
    typed = cast(dict[str, object], data)
    return _build_concise_payload(typed, role)


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


# Default token budget for load_context_resource (no param in URI); ensures explicit budget for validation.
_LOAD_CONTEXT_RESOURCE_DEFAULT_BUDGET = 10000


@mcp.resource(uri="cortex://optimization/load-context/{task_description}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def load_context_resource(task_description: str) -> str:
    """Resource: Load context for task (default budget/strategy). Read via cortex://optimization/load-context/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await load_context(
        task_description=decoded,
        token_budget=_LOAD_CONTEXT_RESOURCE_DEFAULT_BUDGET,
        strategy="dependency_aware",
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
