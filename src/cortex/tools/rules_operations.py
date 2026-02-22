"""
Rules Operations Tools

This module contains the consolidated rules management tool for Memory Bank.

Total: 1 tool
- rules: Index/retrieve custom rules
"""

import json
from pathlib import Path
from urllib.parse import unquote

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ModelDict
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.initialization import get_managers
from cortex.managers.manager_utils import get_manager
from cortex.optimization.models import RulesManagerStatusModel
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.rules_manager import RulesManager
from cortex.server import mcp
from cortex.tools.rules_operation_helpers import (
    RulesOperation,
    build_get_relevant_response,
    build_invalid_operation_error,
    build_missing_rules_parameters_error,
    calculate_total_tokens,
    extract_all_rules,
    parse_rules_operation,
    resolve_config_defaults,
)

# Type alias for operation names (must match RulesOperation enum).
RulesOperationName = RulesOperation


async def check_rules_enabled(
    optimization_config: OptimizationConfig,
) -> str | None:
    """Check if rules indexing is enabled.

    Args:
        optimization_config: Optimization configuration

    Returns:
        JSON error message if disabled, None if enabled
    """
    if not optimization_config.is_rules_enabled():
        return json.dumps(
            {
                "status": "disabled",
                "message": (
                    "Rules indexing is disabled. "
                    "Enable it in .cortex/config/optimization.json"
                ),
            },
            indent=2,
        )
    return None


async def handle_index_operation(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    force: bool,
) -> str:
    """Handle index operation.

    Args:
        rules_manager: Rules manager instance
        optimization_config: Optimization configuration
        force: Force reindexing even if recently indexed

    Returns:
        JSON string with index result
    """
    # Validate rules folder configuration before proceeding
    rules_folder, config_error = _validate_rules_folder_config(optimization_config)
    if config_error:
        return config_error

    result = await rules_manager.index_rules(force=force)
    result_payload: ModelDict = result

    # Check if indexing returned an error
    if result_payload.get("status") == "error":
        from cortex.tools.tool_error_formatters import format_tool_error

        error_msg = result_payload.get("error", "Unknown error")
        return format_tool_error(
            FileNotFoundError(str(error_msg)),
            suggestion=(
                "Create the rules folder at the configured path or update "
                "rules.rules_folder in .cortex/config/optimization.json "
                "to point to an existing directory."
            ),
            example={"rules": {"enabled": True, "rules_folder": ".cortex/rules"}},
            context={
                "configured_path": rules_folder,
                "config_path": ".cortex/config/optimization.json",
            },
        )

    return json.dumps(
        {"status": "success", "operation": "index", "result": result_payload},
        indent=2,
    )


async def validate_get_relevant_params(task_description: str | None) -> str | None:
    """Validate parameters for get_relevant operation.

    Args:
        task_description: Description of the task

    Returns:
        JSON error message if validation fails, None if valid
    """
    if not task_description:
        return json.dumps(
            {
                "status": "error",
                "error": "task_description is required for get_relevant operation",
            },
            indent=2,
        )
    return None


def _validate_rules_folder_config(
    optimization_config: OptimizationConfig,
) -> tuple[str | None, str | None]:
    """Validate rules folder configuration.

    Args:
        optimization_config: Optimization configuration

    Returns:
        Tuple of (rules_folder, error_message). If error_message is not None,
        rules_folder is None and error_message contains the formatted error.
    """
    rules_folder = optimization_config.get_rules_folder()
    if not rules_folder:
        from cortex.tools.tool_error_formatters import format_tool_error

        error = format_tool_error(
            ValueError("Rules folder not configured"),
            suggestion=(
                "Configure rules_folder in .cortex/config/optimization.json "
                "under 'rules.rules_folder'. Example: '.cortex/rules'"
            ),
            example={"rules": {"enabled": True, "rules_folder": ".cortex/rules"}},
            context={"config_path": ".cortex/config/optimization.json"},
        )
        return None, error
    return rules_folder, None


def _validate_rules_folder_exists(
    rules_manager: RulesManager, rules_folder: str
) -> str | None:
    """Validate that rules folder exists on filesystem.

    Args:
        rules_manager: Rules manager instance
        rules_folder: Rules folder path from config

    Returns:
        Error message if folder doesn't exist, None if valid
    """
    project_root = rules_manager.project_root
    rules_path = project_root / rules_folder
    if not rules_path.exists():
        from cortex.tools.tool_error_formatters import format_tool_error

        return format_tool_error(
            FileNotFoundError(f"Rules folder not found: {rules_folder}"),
            suggestion=(
                f"Create the rules folder at '{rules_path}' or update "
                f"rules.rules_folder in .cortex/config/optimization.json "
                f"to point to an existing directory."
            ),
            example={"rules": {"enabled": True, "rules_folder": ".cortex/rules"}},
            context={
                "configured_path": rules_folder,
                "absolute_path": str(rules_path),
                "config_path": ".cortex/config/optimization.json",
            },
        )
    return None


async def _fetch_relevant_rules(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    task_description: str,
    resolved_max_tokens: int,
    resolved_min_score: float,
) -> ModelDict:
    """Fetch relevant rules from rules manager.

    Args:
        rules_manager: Rules manager instance
        optimization_config: Optimization configuration
        task_description: Description of the task
        resolved_max_tokens: Resolved max tokens
        resolved_min_score: Resolved min relevance score

    Returns:
        Relevant rules dictionary
    """
    rule_priority = optimization_config.get_rule_priority()
    context_aware = optimization_config.is_context_aware_loading()

    relevant_rules = await rules_manager.get_relevant_rules(
        task_description=task_description,
        max_tokens=resolved_max_tokens,
        min_relevance_score=resolved_min_score,
        rule_priority=rule_priority,
        context_aware=context_aware,
    )
    return relevant_rules


async def _execute_get_relevant(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    task_description: str,
    max_tokens: int | None,
    min_relevance_score: float | None,
    rules_folder: str,
) -> str:
    """Execute get_relevant operation after validation.

    Args:
        rules_manager: Rules manager instance
        optimization_config: Optimization configuration
        task_description: Description of the task
        max_tokens: Maximum tokens for rules (optional)
        min_relevance_score: Minimum relevance score (optional)
        rules_folder: Validated rules folder path

    Returns:
        JSON string with relevant rules result
    """
    resolved_max_tokens, resolved_min_score = resolve_config_defaults(
        optimization_config, max_tokens, min_relevance_score
    )
    relevant_rules_dict = await _fetch_relevant_rules(
        rules_manager,
        optimization_config,
        task_description,
        resolved_max_tokens,
        resolved_min_score,
    )
    all_rules = extract_all_rules(relevant_rules_dict)
    total_tokens = calculate_total_tokens(relevant_rules_dict, all_rules)
    status = _build_status_from_config(rules_manager, optimization_config, rules_folder)
    return build_get_relevant_response(
        task_description,
        resolved_max_tokens,
        resolved_min_score,
        all_rules,
        total_tokens,
        status,
        relevant_rules_dict,
    )


def _build_status_from_config(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    rules_folder: str | None,
) -> RulesManagerStatusModel:
    """Build status from current optimization config to ensure accuracy.

    Args:
        rules_manager: Rules manager instance (for indexer status)
        optimization_config: Current optimization configuration
        rules_folder: Current rules folder path from config (may be None)

    Returns:
        RulesManagerStatusModel with current status
    """
    indexer_status = rules_manager.indexer.get_status()

    return RulesManagerStatusModel(
        enabled=rules_folder is not None,
        rules_folder=rules_folder,  # Use current config value, not stale initialization
        indexed_files=indexer_status.indexed_files,
        last_indexed=indexer_status.last_indexed,
        auto_reindex_enabled=indexer_status.auto_reindex_enabled,
        reindex_interval_minutes=optimization_config.get_rules_reindex_interval(),
        total_tokens=indexer_status.total_tokens,
    )


async def handle_get_relevant_operation(
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    task_description: str,
    max_tokens: int | None,
    min_relevance_score: float | None,
) -> str:
    """Handle get_relevant operation.

    Args:
        rules_manager: Rules manager instance
        optimization_config: Optimization configuration
        task_description: Description of the task
        max_tokens: Maximum tokens for rules (optional)
        min_relevance_score: Minimum relevance score (optional)

    Returns:
        JSON string with relevant rules result
    """
    # Validate rules folder configuration before proceeding
    rules_folder, config_error = _validate_rules_folder_config(optimization_config)
    if config_error:
        return config_error
    assert rules_folder is not None  # Validated above

    # Check if rules folder exists
    folder_error = _validate_rules_folder_exists(rules_manager, rules_folder)
    if folder_error:
        return folder_error

    return await _execute_get_relevant(
        rules_manager,
        optimization_config,
        task_description,
        max_tokens,
        min_relevance_score,
        rules_folder,
    )


async def dispatch_operation(
    operation: RulesOperation,
    rules_manager: RulesManager,
    optimization_config: OptimizationConfig,
    force: bool,
    task_description: str | None,
    max_tokens: int | None,
    min_relevance_score: float | None,
) -> str:
    """Dispatch to appropriate operation handler.

    Args:
        operation: Operation to perform
        rules_manager: Rules manager instance
        optimization_config: Optimization configuration
        force: Force reindexing
        task_description: Task description
        max_tokens: Maximum tokens
        min_relevance_score: Minimum relevance score

    Returns:
        JSON string with operation result
    """
    if operation == RulesOperation.INDEX:
        return await handle_index_operation(rules_manager, optimization_config, force)
    if operation == RulesOperation.GET_RELEVANT:
        if error_msg := await validate_get_relevant_params(task_description):
            return error_msg
        assert task_description is not None
        return await handle_get_relevant_operation(
            rules_manager,
            optimization_config,
            task_description,
            max_tokens,
            min_relevance_score,
        )
    # Defensive: unknown enum member (e.g. after adding a new RulesOperation)
    return build_invalid_operation_error(operation.value)


@mcp.tool(annotations=safe_write_annotations("Rules"))
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
        JSON string containing operation result with structure depending on operation:

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
                },
                {
                    "file": "error-handling.mdc",
                    "category": "generic",
                    "relevance_score": 0.78,
                    "tokens": 620,
                    "title": "Error Handling Patterns",
                    "content": "Always validate inputs...",
                    "metadata": {
                        "tags": ["errors", "validation"]
                    }
                }
            ],
            "rules_manager_status": {
                "indexed_count": 42,
                "last_indexed": "2026-01-04T10:30:00Z",
                "rules_folder": ".cursor/rules"
            },
            "rules_context": {
                "filtered_count": 12,             # Rules filtered by min_relevance
                "truncated_count": 4              # Rules excluded due to token limit
            },
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

    Examples:
        Example 1 - Index custom rules from rules folder:
        >>> await rules(operation="index")
        {
            "status": "success",
            "operation": "index",
            "result": {
                "indexed": 42,
                "total_tokens": 15234,
                "cache_hit": false,
                "index_time_seconds": 2.5,
                "rules_folder": ".cursor/rules",
                "rules_by_category": {
                    "generic": 15,
                    "language_specific": 20,
                    "local": 7
                }
            }
        }

        Example 2 - Force reindex all rules (clear cache):
        >>> await rules(operation="index", force=True)
        {
            "status": "success",
            "operation": "index",
            "result": {
                "indexed": 42,
                "total_tokens": 15234,
                "cache_hit": false,
                "index_time_seconds": 3.1,
                "rules_folder": ".cursor/rules",
                "rules_by_category": {
                    "generic": 15,
                    "language_specific": 20,
                    "local": 7
                }
            }
        }

        Example 3 - Get relevant rules for async Python task:
        >>> await rules(
        ...     operation="get_relevant",
        ...     task_description=(
        ...         "Implementing async file operations with error handling"
        ...     ),
        ...     max_tokens=5000,
        ...     min_relevance_score=0.7
        ... )
        {
            "status": "success",
            "operation": "get_relevant",
            "task_description": (
                "Implementing async file operations with error handling"
            ),
            "max_tokens": 5000,
            "min_relevance_score": 0.7,
            "rules_count": 6,
            "total_tokens": 4123,
            "rules": [
                {
                    "file": "python-async.mdc",
                    "category": "language_specific",
                    "relevance_score": 0.92,
                    "tokens": 850,
                    "title": "Python Async Best Practices",
                    "content": "Use asyncio.timeout() instead of asyncio.wait_for()...",
                    "metadata": {"language": "python", "tags": ["async"]}
                },
                {
                    "file": "error-handling.mdc",
                    "category": "generic",
                    "relevance_score": 0.85,
                    "tokens": 620,
                    "title": "Error Handling Patterns",
                    "content": (
                        "Always validate inputs and use specific "
                        "exception types..."
                    ),
                    "metadata": {"tags": ["errors", "validation"]}
                },
                {
                    "file": "file-operations.mdc",
                    "category": "generic",
                    "relevance_score": 0.78,
                    "tokens": 540,
                    "title": "Safe File Operations",
                    "content": "Use context managers for file operations...",
                    "metadata": {"tags": ["files", "io"]}
                }
            ],
            "rules_manager_status": {
                "indexed_count": 42,
                "last_indexed": "2026-01-04T10:30:00Z",
                "rules_folder": ".cursor/rules"
            },
            "rules_context": {
                "filtered_count": 8,
                "truncated_count": 2
            },
            "rules_source": "indexed"
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
        - If rules disabled, returns status "disabled" with configuration instructions
        - Default max_tokens and min_relevance_score values loaded from optimization
          configuration if not explicitly provided
        - Index results include cache_hit flag indicating whether cached index used
          or fresh indexing performed
    """
    await log_client(ctx, "info", "rules: starting", logger_name=__name__)
    parsed = parse_rules_operation(operation)
    if parsed is None:
        await log_client(ctx, "warning", "rules: invalid or missing operation")
        if operation is None:
            return build_missing_rules_parameters_error()
        return build_invalid_operation_error(operation)
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
    # Deferred init: first rules use does indexing (avoids blocking first manage_file).
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
    from cortex.tools.tool_error_formatters import format_tool_error

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


@mcp.resource(uri="cortex://rules/relevant/{task_description}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def rules_get_relevant_resource(task_description: str) -> str:
    """Resource: Rules relevant to task (default params). Read via cortex://rules/relevant/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await rules(
        operation="get_relevant",
        force=False,
        task_description=decoded,
        max_tokens=None,
        min_relevance_score=None,
    )
