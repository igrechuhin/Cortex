"""
Rules Operations Tools

This module contains the consolidated rules management tool for Memory Bank.

Total: 1 tool
- rules: Index/retrieve custom rules
"""

import json
from typing import Literal, cast

from cortex.managers.initialization import get_managers, get_project_root
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.rules_manager import RulesManager
from cortex.server import mcp


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
                "message": "Rules indexing is disabled. Enable it in .cortex/optimization.json",
            },
            indent=2,
        )
    return None


async def handle_index_operation(rules_manager: RulesManager, force: bool) -> str:
    """Handle index operation.

    Args:
        rules_manager: Rules manager instance
        force: Force reindexing even if recently indexed

    Returns:
        JSON string with index result
    """
    result = await rules_manager.index_rules(force=force)
    return json.dumps(
        {"status": "success", "operation": "index", "result": result}, indent=2
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


def resolve_config_defaults(
    optimization_config: OptimizationConfig,
    max_tokens: int | None,
    min_relevance_score: float | None,
) -> tuple[int, float]:
    """Resolve configuration defaults for get_relevant operation.

    Args:
        optimization_config: Optimization configuration
        max_tokens: Maximum tokens for rules (optional)
        min_relevance_score: Minimum relevance score (optional)

    Returns:
        Tuple of (max_tokens, min_relevance_score) with defaults applied
    """
    resolved_max_tokens = (
        max_tokens
        if max_tokens is not None
        else optimization_config.get_rules_max_tokens()
    )
    resolved_min_score = (
        min_relevance_score
        if min_relevance_score is not None
        else optimization_config.get_rules_min_relevance()
    )
    return resolved_max_tokens, resolved_min_score


def extract_all_rules(
    relevant_rules_dict: dict[str, object],
) -> list[dict[str, object]]:
    """Extract all rules from the relevant rules dictionary.

    Args:
        relevant_rules_dict: Dictionary containing rules by category

    Returns:
        List of all rules combined from all categories
    """
    all_rules: list[dict[str, object]] = []
    generic_rules = relevant_rules_dict.get("generic_rules", [])
    language_rules = relevant_rules_dict.get("language_rules", [])
    local_rules = relevant_rules_dict.get("local_rules", [])

    if isinstance(generic_rules, list):
        all_rules.extend(cast(list[dict[str, object]], generic_rules))
    if isinstance(language_rules, list):
        all_rules.extend(cast(list[dict[str, object]], language_rules))
    if isinstance(local_rules, list):
        all_rules.extend(cast(list[dict[str, object]], local_rules))

    return all_rules


def calculate_total_tokens(
    relevant_rules_dict: dict[str, object], all_rules: list[dict[str, object]]
) -> int:
    """Calculate total tokens from rules.

    Args:
        relevant_rules_dict: Dictionary containing total_tokens key
        all_rules: List of all rules

    Returns:
        Total tokens count
    """
    total_tokens_value = relevant_rules_dict.get("total_tokens", 0)
    if isinstance(total_tokens_value, (int, float)):
        return int(total_tokens_value)

    return sum(
        (
            int(token_val)
            if isinstance(token_val := r.get("tokens"), (int, float))
            else 0
        )
        for r in all_rules
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
    resolved_max_tokens, resolved_min_score = resolve_config_defaults(
        optimization_config, max_tokens, min_relevance_score
    )

    relevant_rules_dict = await rules_manager.get_relevant_rules(
        task_description=task_description,
        max_tokens=resolved_max_tokens,
        min_relevance_score=resolved_min_score,
    )

    all_rules = extract_all_rules(relevant_rules_dict)
    total_tokens = calculate_total_tokens(relevant_rules_dict, all_rules)

    return build_get_relevant_response(
        task_description,
        resolved_max_tokens,
        resolved_min_score,
        all_rules,
        total_tokens,
        rules_manager.get_status(),
        relevant_rules_dict,
    )


def build_get_relevant_response(
    task_description: str,
    max_tokens: int,
    min_score: float,
    all_rules: list[dict[str, object]],
    total_tokens: int,
    status: dict[str, object],
    relevant_rules_dict: dict[str, object],
) -> str:
    """Build response for get_relevant operation."""
    return json.dumps(
        {
            "status": "success",
            "operation": "get_relevant",
            "task_description": task_description,
            "max_tokens": max_tokens,
            "min_relevance_score": min_score,
            "rules_count": len(all_rules),
            "total_tokens": total_tokens,
            "rules": all_rules,
            "rules_manager_status": status,
            "rules_context": relevant_rules_dict.get("context", {}),
            "rules_source": relevant_rules_dict.get("source", "unknown"),
        },
        indent=2,
    )


async def dispatch_operation(
    operation: Literal["index", "get_relevant"],
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
    if operation == "index":
        return await handle_index_operation(rules_manager, force)
    elif operation == "get_relevant":
        # Validate parameters
        if error_msg := await validate_get_relevant_params(task_description):
            return error_msg
        # Handle operation
        return await handle_get_relevant_operation(
            rules_manager,
            optimization_config,
            task_description,  # type: ignore[arg-type]
            max_tokens,
            min_relevance_score,
        )
    else:
        return json.dumps(
            {
                "status": "error",
                "error": f"Invalid operation: {operation}",
                "valid_operations": ["index", "get_relevant"],
            },
            indent=2,
        )


@mcp.tool()
async def rules(
    operation: Literal["index", "get_relevant"],
    project_root: str | None = None,
    force: bool = False,
    task_description: str | None = None,
    max_tokens: int | None = None,
    min_relevance_score: float | None = None,
) -> str:
    """Manage custom rules for Memory Bank with indexing and intelligent retrieval.

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

    Rules indexing must be enabled in .cortex/optimization.json configuration
    file with rules_enabled: true and rules_folder path specified.

    Args:
        operation: Operation to perform:
            - "index": Index/reindex custom rules from rules folder
            - "get_relevant": Retrieve rules relevant to task description
            Example: "index", "get_relevant"

        project_root: Absolute path to project root directory containing Memory Bank.
            Defaults to current working directory if not specified.
            Example: "/Users/username/projects/my-app"

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
            "message": "Rules indexing is disabled. Enable it in .cortex/optimization.json"
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
        ...     task_description="Implementing async file operations with error handling",
        ...     max_tokens=5000,
        ...     min_relevance_score=0.7
        ... )
        {
            "status": "success",
            "operation": "get_relevant",
            "task_description": "Implementing async file operations with error handling",
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
                    "content": "Always validate inputs and use specific exception types...",
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
        - Rules indexing must be enabled in .cortex/optimization.json with
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
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)

        rules_manager = cast(RulesManager, mgrs["rules_manager"])
        optimization_config = cast(OptimizationConfig, mgrs["optimization_config"])

        # Check if rules are enabled
        if error_msg := await check_rules_enabled(optimization_config):
            return error_msg

        # Dispatch to operation handler
        return await dispatch_operation(
            operation,
            rules_manager,
            optimization_config,
            force,
            task_description,
            max_tokens,
            min_relevance_score,
        )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )
