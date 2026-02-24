"""
Synapse Tools for MCP Memory Bank.

This module contains tools for syncing, updating, and retrieving
shared rules and prompts from a git submodule-based Synapse repository.

Total: 4 tools (update_synapse_rule + update_synapse_prompt consolidated into update_synapse)
- sync_synapse
- update_synapse (content_type=rule|prompt)
- get_synapse_rules
- get_synapse_prompts

Note: setup_synapse has been replaced by a prompt template in docs/prompts/
"""

import json
from collections.abc import Sequence
from typing import Literal, Protocol
from urllib.parse import unquote

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_EXTERNAL,
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations, safe_write_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import ModelDict
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.optimization.rules_manager import RulesManager
from cortex.rules.synapse_manager import SynapseManager
from cortex.server import mcp

RulePriorityLiteral = Literal["local_overrides_shared", "shared_overrides_local"]


class _ModelDumpable(Protocol):
    def model_dump(self, *, mode: str) -> ModelDict: ...


def format_prompts_list(
    prompts: Sequence[ModelDict] | Sequence[_ModelDumpable],
) -> list[ModelDict]:
    """Format a list of prompt objects into dictionaries."""
    result: list[ModelDict] = []
    for p in prompts:
        prompt_dict: ModelDict = p if isinstance(p, dict) else p.model_dump(mode="json")
        result.append(
            {
                "file": prompt_dict.get("file"),
                "name": prompt_dict.get("name"),
                "category": prompt_dict.get("category"),
                "description": prompt_dict.get("description"),
                "keywords": prompt_dict.get("keywords"),
            }
        )
    return result


async def _sync_synapse_impl(pull: bool, push: bool, ctx: MCPContext | None) -> str:
    """Run sync_synapse logic and return JSON result."""
    project_root = get_project_root()
    managers = await get_managers(project_root)
    if managers.synapse is None:
        await log_client(
            ctx,
            "warning",
            "sync_synapse: Synapse not initialized",
            logger_name=__name__,
        )
        return json.dumps(
            {
                "status": "error",
                "error": "Synapse not initialized. Run setup_synapse first.",
            },
            indent=2,
        )
    synapse_manager = await get_manager(managers, "synapse", SynapseManager)
    result = await synapse_manager.sync_synapse(pull=pull, push=push)
    if result.reindex_triggered and managers.rules_manager is not None:
        rules_manager = await get_manager(managers, "rules_manager", RulesManager)
        _ = await rules_manager.index_rules(force=True)
    out = json.dumps(result.model_dump(mode="json"), indent=2)
    await log_client(ctx, "info", "sync_synapse: completed", logger_name=__name__)
    return out


@mcp.tool(annotations=safe_write_annotations("Sync Synapse"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_EXTERNAL)
async def sync_synapse(
    pull: bool = True,
    push: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Sync Synapse repository with remote using git operations.

    USE WHEN: User wants to sync shared rules, user needs to update Synapse,
    user requests Synapse sync, user wants to pull/push changes.

    EXAMPLES: 'sync Synapse repository', 'pull Synapse updates', 'push
    Synapse changes', 'sync shared rules'.

    RETURNS: JSON with sync status, changes pulled/pushed, and operation
    results.

    This tool synchronizes the local Synapse git submodule with the remote
    repository. When pulling, it fetches the latest rules and prompts from
    other projects that share the same Synapse repository. When pushing, it
    shares local modifications with all other projects. After pulling changes,
    the rules index is automatically rebuilt to incorporate new or modified rules.

    Args:
        pull: Pull latest changes from remote repository.
              Set to True to fetch updates from other projects.
              Triggers automatic rules reindexing if changes are detected.
              Default: True

        push: Push local changes to remote repository.
              Set to True to share your local modifications with other projects.
              Requires commit access to the Synapse repository.
              Default: False

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - pulled: Boolean indicating if pull was performed
        - pushed: Boolean indicating if push was performed
        - changes: Dictionary with lists of added/modified/deleted files
        - reindex_triggered: Boolean indicating if rules reindex occurred
        - last_sync: ISO timestamp of sync operation
        - error: Error message (only present if status is "error")

    Examples:
        Example 1: Pull latest changes from remote
        >>> await sync_synapse(pull=True, push=False)
        {
          "status": "success",
          "pulled": true,
          "pushed": false,
          "changes": {
            "added": ["python/async-patterns.mdc"],
            "modified": ["general/code-style.mdc"],
            "deleted": []
          },
          "reindex_triggered": true,
          "last_sync": "2026-01-13T10:30:00Z"
        }

        Example 2: Push local changes to remote
        >>> await sync_synapse(pull=False, push=True)
        {
          "status": "success",
          "pulled": false,
          "pushed": true,
          "changes": {
            "added": [],
            "modified": ["python/type-hints.mdc"],
            "deleted": []
          },
          "reindex_triggered": false,
          "last_sync": "2026-01-13T10:35:00Z"
        }

        Example 3: Error - Synapse not initialized
        >>> await sync_synapse()
        {
          "status": "error",
          "error": "Synapse not initialized. Run setup_synapse first."
        }
    """
    await log_client(ctx, "info", "sync_synapse: starting", logger_name=__name__)
    try:
        return await _sync_synapse_impl(pull, push, ctx)
    except Exception as e:
        await log_client(ctx, "error", f"sync_synapse: {e!s}", logger_name=__name__)
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _update_synapse_rule_impl(
    category: str, file: str, content: str, commit_message: str, ctx: MCPContext | None
) -> str:
    """Run update_synapse_rule logic and return JSON result."""
    project_root = get_project_root()
    managers = await get_managers(project_root)
    if managers.synapse is None:
        await log_client(
            ctx,
            "warning",
            "update_synapse_rule: Synapse not initialized",
            logger_name=__name__,
        )
        return json.dumps(
            {
                "status": "error",
                "error": "Synapse not initialized. Run setup_synapse first.",
            },
            indent=2,
        )
    synapse_manager = await get_manager(managers, "synapse", SynapseManager)
    result = await synapse_manager.update_synapse_rule(
        category=category, file=file, content=content, commit_message=commit_message
    )
    out = json.dumps(result, indent=2)
    await log_client(
        ctx, "info", "update_synapse_rule: completed", logger_name=__name__
    )
    return out


@mcp.tool(annotations=safe_write_annotations("Update Synapse (rule or prompt)"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_EXTERNAL)
async def update_synapse(
    content_type: Literal["rule", "prompt"],
    category: str,
    file: str,
    content: str,
    commit_message: str,
    ctx: MCPContext | None = None,
) -> str:
    """Update a Synapse rule or prompt file and push changes to all projects.

    USE WHEN: User wants to update a shared rule or prompt, user needs to
    modify rule/prompt, user requests rule/prompt update.

    EXAMPLES: update_synapse(content_type="rule", category="python", ...),
    update_synapse(content_type="prompt", category="general", ...).

    RETURNS: JSON with update status, changes made, and push results.

    Args:
        content_type: "rule" to update a rule file, "prompt" to update a prompt file.
        category: Category name (e.g. "python", "general").
        file: Filename within the category.
        content: Complete new content for the file.
        commit_message: Git commit message describing the change.
        ctx: MCP context (automatically provided).
    """
    await log_client(
        ctx, "info", f"update_synapse({content_type}): starting", logger_name=__name__
    )
    try:
        if content_type == "rule":
            return await _update_synapse_rule_impl(
                category, file, content, commit_message, ctx
            )
        return await _update_synapse_prompt_impl(
            category, file, content, commit_message, ctx
        )
    except Exception as e:
        await log_client(ctx, "error", f"update_synapse: {e!s}", logger_name=__name__)
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def update_synapse_rule(
    category: str,
    file: str,
    content: str,
    commit_message: str,
    ctx: MCPContext | None = None,
) -> str:
    """Update a Synapse rule file (wrapper; use update_synapse(content_type=\"rule\", ...) as MCP tool)."""
    return await update_synapse(
        content_type="rule",
        category=category,
        file=file,
        content=content,
        commit_message=commit_message,
        ctx=ctx,
    )


async def _get_synapse_handle_rules(
    task_description: str | None,
    max_tokens: int,
    min_relevance_score: float,
    project_files: str | None,
    rule_priority: RulePriorityLiteral,
    context_aware: bool,
    ctx: MCPContext | None,
) -> str:
    """Handle get_synapse(content_type='rules') branch."""
    if not (task_description or "").strip():
        return json.dumps(
            {
                "status": "error",
                "error": "task_description required when content_type is rules",
            },
            indent=2,
        )
    desc = (task_description or "").strip()
    return await _get_synapse_rules_impl(
        desc,
        max_tokens,
        min_relevance_score,
        project_files,
        rule_priority,
        context_aware,
        ctx,
    )


async def _get_synapse_handle_prompts(
    category: str | None, ctx: MCPContext | None
) -> str:
    """Handle get_synapse(content_type='prompts') branch."""
    try:
        return await _get_synapse_prompts_impl(category, ctx)
    except Exception as e:
        await log_client(
            ctx, "error", f"get_synapse(prompts): {e!s}", logger_name=__name__
        )
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


@mcp.tool(annotations=read_only_annotations("Get Synapse (rules or prompts)"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_synapse(
    content_type: str,
    task_description: str | None = None,
    category: str | None = None,
    max_tokens: int = 10000,
    min_relevance_score: float = 0.3,
    project_files: str | None = None,
    rule_priority: RulePriorityLiteral = "local_overrides_shared",
    context_aware: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Get Synapse rules (by task) or prompts (optionally by category).

    USE WHEN: content_type=\"rules\" — user needs relevant rules. content_type=\"prompts\" — user needs prompts.
    EXAMPLES: get_synapse(content_type=\"rules\", task_description=\"Python async\"), get_synapse(content_type=\"prompts\", category=\"general\").
    """
    ct = (content_type or "").strip().lower()
    if ct == "rules":
        return await _get_synapse_handle_rules(
            task_description,
            max_tokens,
            min_relevance_score,
            project_files,
            rule_priority,
            context_aware,
            ctx,
        )
    if ct == "prompts":
        return await _get_synapse_handle_prompts(category, ctx)
    return json.dumps(
        {
            "status": "error",
            "error": f"Unknown content_type: {content_type!r}. Use rules or prompts.",
        },
        indent=2,
    )


async def get_synapse_rules(
    task_description: str,
    max_tokens: int = 10000,
    min_relevance_score: float = 0.3,
    project_files: str | None = None,
    rule_priority: RulePriorityLiteral = "local_overrides_shared",
    context_aware: bool = True,
    ctx: MCPContext | None = None,
) -> str:
    """Get intelligently selected rules from task context and project.

    USE WHEN: User needs relevant rules, user wants Synapse rules, user
    requests rule retrieval, user needs coding standards.

    EXAMPLES: 'get Synapse rules for Python', 'get relevant rules for task',
    'get coding standards', 'get rules for refactoring'.

    RETURNS: JSON with relevant rules, relevance scores, and rule content.

    This tool analyzes your task description and project files to automatically
    select the most relevant coding rules from both Synapse and local sources.
    It detects programming languages, frameworks, and task types to load
    appropriate rules while respecting token budget constraints.

    Args:
        task_description: Natural language description of your current task.
                         Used for keyword extraction and semantic matching.

        max_tokens: Maximum total tokens to include in response.
                   Default: 10000

        min_relevance_score: Minimum relevance score (0.0-1.0) for rule inclusion.
                            Default: 0.3

        project_files: Comma-separated list of file paths for context detection.
                      Optional - if not provided, uses task_description only.

        rule_priority: Conflict resolution strategy when Synapse and local
                      rules overlap.
                      "local_overrides_shared": Prefer project-specific
                      rules (default)
                      "shared_overrides_local": Prefer team-wide Synapse
                      rules

        context_aware: Enable intelligent context detection and rule selection.
                      Default: True

    Returns:
        JSON string containing:
        - status: "success" or "error"
        - task_description: Echo of input task description
        - context: Detected context information
        - rules_loaded: Categorized rules (generic, language, local)
        - total_tokens: Actual token count of returned rules
        - token_budget: Maximum token limit specified
        - source: Rules source ("mixed", "shared_only", "local_only")

    Examples:
        Example 1: Get rules for Python async task
        >>> await get_synapse_rules(
        ...     task_description=(
        ...         "Implement async file operations with proper error "
        ...         "handling"
        ...     ),
        ...     max_tokens=8000,
        ...     min_relevance_score=0.4
        ... )
        {
          "status": "success",
          "task_description": (
              "Implement async file operations with proper error handling"
          ),
          "context": {
            "languages": ["python"],
            "frameworks": [],
            "task_type": "implementation"
          },
          "rules_loaded": {
            "generic": [
              {
                "file": "general/error-handling.mdc",
                "tokens": 450,
                "priority": "high",
                "relevance_score": 0.92
              }
            ],
            "language": [
              {
                "file": "python/async-patterns.mdc",
                "category": "python",
                "tokens": 680,
                "priority": "high",
                "relevance_score": 0.88
              }
            ],
            "local": []
          },
          "total_tokens": 1130,
          "token_budget": 8000,
          "source": "mixed"
        }

        Example 2: Get rules with project file context
        >>> await get_synapse_rules(
        ...     task_description="Refactor authentication module",
        ...     project_files="src/auth.py, tests/test_auth.py",
        ...     max_tokens=10000
        ... )
        {
          "status": "success",
          "task_description": "Refactor authentication module",
          "context": {
            "languages": ["python"],
            "frameworks": [],
            "task_type": "refactoring"
          },
          "rules_loaded": {
            "generic": [
              {
                "file": "general/refactoring-patterns.mdc",
                "tokens": 520,
                "priority": "medium",
                "relevance_score": 0.75
              }
            ],
            "language": [
              {
                "file": "python/code-organization.mdc",
                "category": "python",
                "tokens": 420,
                "priority": "medium",
                "relevance_score": 0.68
              }
            ],
            "local": []
          },
          "total_tokens": 940,
          "token_budget": 10000,
          "source": "mixed"
        }
    """
    return await _get_synapse_rules_impl(
        task_description,
        max_tokens,
        min_relevance_score,
        project_files,
        rule_priority,
        context_aware,
        ctx,
    )


def _get_synapse_rules_error_json(exc: Exception) -> str:
    """Build JSON error response for get_synapse_rules failures."""
    return json.dumps(
        {"status": "error", "error": str(exc), "error_type": type(exc).__name__},
        indent=2,
    )


async def _get_synapse_rules_impl(
    task_description: str,
    max_tokens: int,
    min_relevance_score: float,
    project_files: str | None,
    rule_priority: RulePriorityLiteral,
    context_aware: bool,
    ctx: MCPContext | None,
) -> str:
    """Run get_synapse_rules logic and return JSON result."""
    await log_client(ctx, "info", "get_synapse_rules: starting", logger_name=__name__)
    try:
        from cortex.tools.synapse_tools_helpers import execute_rules_with_context

        result = await execute_rules_with_context(
            task_description,
            max_tokens,
            min_relevance_score,
            project_files,
            rule_priority,
            context_aware,
        )
        out = json.dumps(result.model_dump(mode="json"), indent=2)
        await log_client(
            ctx, "info", "get_synapse_rules: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx, "error", f"get_synapse_rules: {e!s}", logger_name=__name__
        )
        return _get_synapse_rules_error_json(e)


def _build_category_prompts_response(
    category: str, prompts: Sequence[ModelDict] | Sequence[_ModelDumpable]
) -> str:
    """Build JSON response for category-specific prompts."""
    return json.dumps(
        {
            "status": "success",
            "category": category,
            "prompts": format_prompts_list(prompts),
            "total_count": len(prompts),
        },
        indent=2,
    )


def _build_all_prompts_response(
    prompts: Sequence[ModelDict] | Sequence[_ModelDumpable], categories: list[str]
) -> str:
    """Build JSON response for all prompts."""
    return json.dumps(
        {
            "status": "success",
            "categories": categories,
            "prompts": format_prompts_list(prompts),
            "total_count": len(prompts),
        },
        indent=2,
    )


def _synapse_not_initialized_json() -> str:
    """Build JSON error when Synapse is not initialized."""
    return json.dumps(
        {
            "status": "error",
            "error": "Synapse not initialized. Run setup_synapse first.",
        },
        indent=2,
    )


async def _get_synapse_prompts_impl(
    category: str | None, ctx: MCPContext | None
) -> str:
    """Run get_synapse_prompts logic and return JSON result."""
    project_root = get_project_root()
    managers = await get_managers(project_root)
    if managers.synapse is None:
        await log_client(
            ctx,
            "warning",
            "get_synapse_prompts: Synapse not initialized",
            logger_name=__name__,
        )
        return _synapse_not_initialized_json()
    synapse_manager = await get_manager(managers, "synapse", SynapseManager)
    _ = await synapse_manager.load_prompts_manifest()
    if category:
        prompts = await synapse_manager.load_prompts_category(category)
        out = _build_category_prompts_response(category, prompts)
    else:
        prompts = await synapse_manager.get_all_prompts()
        categories = synapse_manager.get_prompt_categories()
        out = _build_all_prompts_response(prompts, categories)
    await log_client(
        ctx, "info", "get_synapse_prompts: completed", logger_name=__name__
    )
    return out


async def get_synapse_prompts(
    category: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Get Synapse prompts (wrapper; use get_synapse(content_type=\"prompts\", category=...) as MCP tool)."""
    return await get_synapse(
        content_type="prompts",
        category=category,
        ctx=ctx,
    )


async def _update_synapse_prompt_impl(
    category: str, file: str, content: str, commit_message: str, ctx: MCPContext | None
) -> str:
    """Run update_synapse_prompt logic and return JSON result."""
    project_root = get_project_root()
    managers = await get_managers(project_root)
    if managers.synapse is None:
        await log_client(
            ctx,
            "warning",
            "update_synapse_prompt: Synapse not initialized",
            logger_name=__name__,
        )
        return json.dumps(
            {
                "status": "error",
                "error": "Synapse not initialized. Run setup_synapse first.",
            },
            indent=2,
        )
    synapse_manager = await get_manager(managers, "synapse", SynapseManager)
    result = await synapse_manager.update_synapse_prompt(
        category=category, file=file, content=content, commit_message=commit_message
    )
    out = json.dumps(result, indent=2)
    await log_client(
        ctx, "info", "update_synapse_prompt: completed", logger_name=__name__
    )
    return out


async def update_synapse_prompt(
    category: str,
    file: str,
    content: str,
    commit_message: str,
    ctx: MCPContext | None = None,
) -> str:
    """Update a Synapse prompt file (wrapper; use update_synapse(content_type=\"prompt\", ...) as MCP tool)."""
    return await update_synapse(
        content_type="prompt",
        category=category,
        file=file,
        content=content,
        commit_message=commit_message,
        ctx=ctx,
    )


@mcp.resource(uri="cortex://synapse/rules/{task_description}")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_synapse_rules_resource(task_description: str) -> str:
    """Resource: Synapse rules for task (default params). Read via cortex://synapse/rules/{task_description}. Task description may be URL-encoded."""
    decoded = unquote(task_description)
    return await get_synapse_rules(
        task_description=decoded,
        max_tokens=10000,
        min_relevance_score=0.3,
        project_files=None,
        rule_priority="local_overrides_shared",
        context_aware=True,
    )


@mcp.resource(uri="cortex://synapse/prompts")
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_synapse_prompts_resource() -> str:
    """Resource: All Synapse prompts (no category filter). Read via cortex://synapse/prompts."""
    return await get_synapse_prompts(category=None)
