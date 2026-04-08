"""
Rules Operations Tools

This module contains the consolidated rules management tool for Memory Bank.

Total: 1 tool
- rules: Index/retrieve custom rules
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.cache import TTLCache
from cortex.core.constants import (
    CORTEX_RULES_RESOURCE_READ_META,
    MCP_STATIC_RESOURCE_CACHE_TTL_SECONDS,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.initialization import get_managers
from cortex.managers.utils import get_manager
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.rules_manager import RulesManager
from cortex.server import mcp
from cortex.tools.reflection_constants import REFLECTION_CHECKLIST_MARKDOWN
from cortex.tools.synapse.rules_operation_helpers import (
    RulesOperation,
    build_invalid_operation_error,
    parse_rules_operation,
)
from cortex.tools.synapse.rules_operations_handlers import (
    check_rules_enabled,
    dispatch_operation,
)

# Type alias for operation names (must match RulesOperation enum).
RulesOperationName = RulesOperation

_rules_resource_cache: TTLCache[str] = TTLCache(MCP_STATIC_RESOURCE_CACHE_TTL_SECONDS)


def invalidate_rules_resource_cache(key: str | None = None) -> None:
    """Invalidate cached cortex://rules payload by session key, or clear all."""
    if key is None:
        _rules_resource_cache.clear()
    else:
        _rules_resource_cache.invalidate(key)


# MCP tool removed — exposed as resource cortex://rules/{task_description}
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def rules(
    operation: RulesOperationName | None = None,
    force: bool = False,
    task_description: str | None = None,
    max_tokens: int | None = None,
    min_relevance_score: float | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Manage custom rules for Memory Bank with indexing and intelligent retrieval.

    Valid values for operation: "index", "get_relevant" (get_relevant requires
    task_description). Invalid or missing operation returns structured error
    with details.missing or valid_operations.

    USE WHEN: User wants to index rules, user needs relevant rules,
    user requests rule retrieval, user wants rule indexing.

    EXAMPLES: 'index rules', 'get relevant rules for task', 'get rules
    for Python', 'index project rules'.

    RETURNS: JSON with indexed rules or relevant rules with scores.

    This consolidated tool provides two key operations for custom rules management:

    1. **index**: Discovers and indexes custom rules from configured rules folders
       (e.g., .cursor/rules/, .idea/rules/). Parses rule files, extracts metadata,
       calculates token counts, and builds a searchable index for fast retrieval.
       Supports incremental updates and caching to avoid redundant reindexing.

    2. **get_relevant**: Retrieves rules relevant to a specific task using semantic
       matching. Scores rules based on relevance to task description, filters by
       minimum score, and enforces token budget constraints. Returns categorized
       rules (generic, language-specific, local) with relevance scores and token
       counts.

    Rules indexing must be enabled in .cortex/config/optimization.json configuration
    file with rules_enabled: true and rules_folder path specified.

    Args:
        operation: Operation to perform:
            - "index": Index/reindex custom rules from rules folder
            - "get_relevant": Retrieve rules relevant to task description
            Example: "index", "get_relevant"

        force: Force complete reindexing even if index is recent (index operation only).
            When False, uses cached index if available and recent. When True, clears
            cache and reindexes all rules from scratch.
            Default: False
            Example: True

        task_description: Description of current task for rule matching (get_relevant
            operation only, REQUIRED). Should describe the development task, feature,
            or problem to get relevant coding rules and guidelines.
            Example: "Implementing async file operations with error handling"

        max_tokens: Maximum total tokens allowed for returned rules (get_relevant
            operation only). Rules are ranked by relevance and included until token
            budget exhausted. Defaults to rules_max_tokens from optimization config.
            Example: 5000

        min_relevance_score: Minimum relevance score (0.0-1.0) for rules to include
            (get_relevant operation only). Rules below threshold excluded even if
            tokens available. Defaults to rules_min_relevance from optimization config.
            Example: 0.6

    Returns:
        JSON string containing operation result with structure depending on operation.

        For "index" operation:
        {
            "status": "success",
            "operation": "index",
            "result": {
                "indexed": 42,                    # Number of rules indexed
                "total_tokens": 15234,            # Total tokens across all rules
                "cache_hit": false,               # Whether cache was used
                "index_time_seconds": 2.5,        # Time taken to index
                "rules_folder": ".cursor/rules",  # Source folder path
                "rules_by_category": {            # Breakdown by category
                    "generic": 15,
                    "language_specific": 20,
                    "local": 7
                }
            }
        }

        For "get_relevant" operation:
        {
            "status": "success",
            "operation": "get_relevant",
            "task_description": "Implementing async file operations",
            "max_tokens": 5000,
            "min_relevance_score": 0.6,
            "rules_count": 8,                     # Number of rules returned
            "total_tokens": 4523,                 # Total tokens in returned rules
            "rules": [
                {
                    "file": "python-async.mdc",
                    "category": "language_specific",
                    "relevance_score": 0.92,
                    "tokens": 850,
                    "title": "Python Async Best Practices",
                    "content": "Use asyncio.timeout()...",
                    "metadata": {
                        "language": "python",
                        "tags": ["async", "concurrency"]
                    }
                }
            ],
            "rules_manager_status": {...},
            "rules_context": {...},
            "rules_source": "indexed"
        }

        For disabled rules:
        {
            "status": "disabled",
            "message": (
                "Rules indexing is disabled. "
                "Enable it in .cortex/config/optimization.json"
            )
        }

        For errors:
        {
            "status": "error",
            "error": "task_description is required for get_relevant operation",
            "error_type": "ValueError"
        }

    Note:
        - Rules indexing must be enabled in .cortex/config/optimization.json with
          rules_enabled: true and rules_folder path configured
        - Index operation uses incremental caching by default; use force=True to
          rebuild entire index from scratch
        - get_relevant operation requires task_description parameter; returns error
          if missing
        - Rules are categorized as generic (cross-language), language_specific
          (Python, JavaScript, etc.), or local (project-specific)
        - Relevance scoring uses semantic similarity between task description and
          rule content/metadata; higher scores indicate better matches
        - Token budgets enforced strictly; rules ranked by relevance and added until
          max_tokens reached, even if more relevant rules available
        - Rules with relevance_score below min_relevance_score excluded regardless
          of available token budget
    """
    return await _rules_body(
        operation,
        force,
        task_description,
        max_tokens,
        min_relevance_score,
        ctx,
    )


def _resolve_rules_zero_arg(
    operation: RulesOperationName | None,
    task_description: str | None,
) -> tuple[RulesOperationName | None, str | None]:
    """Apply zero-arg defaults from session config when operation is None."""
    if operation is not None:
        return operation, task_description
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    resolved_op: RulesOperationName | None = RulesOperation("get_relevant")
    if task_description is None:
        task_description = str(cfg.get("task_description", "general coding standards"))
    return resolved_op, task_description


async def _rules_body(
    operation: RulesOperationName | None,
    force: bool,
    task_description: str | None,
    max_tokens: int | None,
    min_relevance_score: float | None,
    ctx: MCPContext | None,
) -> str:
    """Resolve zero-arg defaults, validate, and dispatch."""
    await log_client(ctx, "info", "rules: starting", logger_name=__name__)
    operation, task_description = _resolve_rules_zero_arg(operation, task_description)
    parsed = parse_rules_operation(operation)
    if parsed is None:
        await log_client(ctx, "warning", "rules: invalid or missing operation")
        operation_text = (
            operation.value if isinstance(operation, RulesOperation) else str(operation)
        )
        return build_invalid_operation_error(operation_text)
    root = await resolve_project_root_async(None, ctx)
    return await _execute_rules_operation(
        parsed,
        root,
        force,
        task_description,
        max_tokens,
        min_relevance_score,
        ctx,
    )


async def _run_rules_operation_impl(
    operation: RulesOperation,
    root: Path,
    force: bool,
    task_description: str | None,
    max_tokens: int | None,
    min_relevance_score: float | None,
) -> str:
    """Run rules operation: resolve managers, check enabled, dispatch."""
    mgrs = await get_managers(root)
    rules_manager = await get_manager(mgrs, "rules_manager", RulesManager)
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )
    if error_msg := await check_rules_enabled(optimization_config):
        return error_msg
    _ = await rules_manager.initialize()
    return await dispatch_operation(
        operation,
        rules_manager,
        optimization_config,
        force,
        task_description,
        max_tokens,
        min_relevance_score,
    )


def _format_rules_error(error: Exception) -> str:
    """Format error response for rules operation failures."""
    from cortex.tools.execution.error_formatters import format_tool_error

    return format_tool_error(
        error,
        suggestion=(
            "Review the error details. Ensure operation is 'index' or 'get_relevant'. "
            "For 'get_relevant', provide task_description. "
            "Check that rules folder is configured in optimization config."
        ),
        example={"operation": "index"},
        available_options=["index", "get_relevant"],
    )


async def _execute_rules_operation(
    operation: RulesOperation,
    root: Path,
    force: bool,
    task_description: str | None,
    max_tokens: int | None,
    min_relevance_score: float | None,
    ctx: MCPContext | None,
) -> str:
    """Execute rules operation with error handling."""
    try:
        result = await _run_rules_operation_impl(
            operation, root, force, task_description, max_tokens, min_relevance_score
        )
        await log_client(ctx, "info", "rules: completed", logger_name=__name__)
        return result
    except Exception as e:
        await log_client(ctx, "error", f"rules: failed: {e}", logger_name=__name__)
        return _format_rules_error(e)


async def _read_ai_code_comments_rule(root: Path) -> str:
    ai_path = (
        get_cortex_path(root, CortexResourceType.SYNAPSE)
        / "rules"
        / "general"
        / "ai-code-comments.mdc"
    )
    try:
        if ai_path.is_file():
            async with open_async_text_file(ai_path, "r", "utf-8") as f:
                return await f.read()
    except OSError:
        pass
    return ""


async def _read_agent_internal_communication_rule(root: Path) -> str:
    path = (
        get_cortex_path(root, CortexResourceType.SYNAPSE)
        / "rules"
        / "general"
        / "agent-internal-communication.mdc"
    )
    try:
        if path.is_file():
            async with open_async_text_file(path, "r", "utf-8") as f:
                return await f.read()
    except OSError:
        pass
    return ""


async def _merge_rules_payload(payload: str) -> str:
    """Inject reflection checklist and AI comment rule into a rules JSON payload."""
    try:
        data: object = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    if not isinstance(data, dict):
        return payload
    merged: ModelDict = cast(ModelDict, data)
    merged["reflection_checklist"] = REFLECTION_CHECKLIST_MARKDOWN
    root = await resolve_project_root_async(None, None)
    merged["ai_code_comments_rule"] = await _read_ai_code_comments_rule(root)
    merged["agent_internal_communication_rule"] = (
        await _read_agent_internal_communication_rule(root)
    )
    return json.dumps(merged, indent=2)


@mcp.resource(uri="cortex://rules", meta=CORTEX_RULES_RESOURCE_READ_META)
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_relevant_rules() -> str:
    """Resource: Rules relevant to current task. Zero-arg — reads task from session config.

    Falls back to "general coding standards" if no session config exists.
    """
    from cortex.core.session_config import read_session_config

    cfg = read_session_config()
    task = str(cfg.get("task_description", "general coding standards"))
    cache_key = f"rules:{task}"
    cached = _rules_resource_cache.get(cache_key)
    if cached is not None:
        return cached
    payload = await rules(
        operation="get_relevant",
        force=False,
        task_description=task,
        max_tokens=None,
        min_relevance_score=None,
    )
    merged = await _merge_rules_payload(payload)
    _rules_resource_cache.set(cache_key, merged)
    return merged
