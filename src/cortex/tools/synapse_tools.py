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

__all__ = [
    "RulePriorityLiteral",
    "get_synapse",
    "get_synapse_prompts",
    "get_synapse_prompts_resource",
    "get_synapse_rules",
    "get_synapse_rules_resource",
    "sync_synapse",
    "update_synapse",
    "update_synapse_prompt",
    "update_synapse_rule",
]

import json
from typing import Literal
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
from cortex.server import mcp
from cortex.tools.synapse_tools_impl import (
    RulePriorityLiteral,
    get_synapse_handle_prompts,
    get_synapse_handle_rules,
    get_synapse_rules,
    sync_synapse_impl,
    update_synapse_prompt_impl,
    update_synapse_rule_impl,
)


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
        return await sync_synapse_impl(pull, push, ctx)
    except Exception as e:
        await log_client(ctx, "error", f"sync_synapse: {e!s}", logger_name=__name__)
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


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

    EXAMPLES: update_synapse(content_type="rule", category="python", file="type-hints.mdc", content="...", commit_message="Update type hints"),
    update_synapse(content_type="prompt", category="general", file="implement.md", content="...", commit_message="Update implement prompt").

    RETURNS: JSON with status, updated path, commit hash, and push result.
    On error: status \"error\" and error message.

    Args:
        content_type: "rule" to update a rule file, "prompt" to update a prompt file.
        category: Category name (e.g. "python", "general").
        file: Filename within the category (e.g. "type-hints.mdc", "implement.md").
        content: Complete new content for the file.
        commit_message: Git commit message describing the change.
        ctx: MCP context (automatically provided).
    """
    await log_client(
        ctx, "info", f"update_synapse({content_type}): starting", logger_name=__name__
    )
    try:
        if content_type == "rule":
            return await update_synapse_rule_impl(
                category, file, content, commit_message, ctx
            )
        return await update_synapse_prompt_impl(
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

    USE WHEN: content_type=\"rules\" — agent needs relevant coding rules for a task.
    content_type=\"prompts\" — agent needs Synapse prompts (optionally filtered by category).

    EXAMPLES: get_synapse(content_type=\"rules\", task_description=\"Python async\"),
    get_synapse(content_type=\"prompts\", category=\"general\"),
    get_synapse(content_type=\"rules\", task_description=\"commit pipeline\", max_tokens=8000).

    RETURNS: JSON with status; for rules: rules_loaded, total_tokens, context; for prompts:
    prompts list (name, category, path). Errors include status \"error\" and error message.

    Args:
        content_type: \"rules\" to get task-relevant rules; \"prompts\" to list/get prompts.
        task_description: Required for content_type=\"rules\". Natural language task for
            rule relevance (e.g. \"Python async\", \"commit pipeline\").
        category: For prompts only. Filter by category (e.g. \"general\", \"python\").
        max_tokens: Max tokens for rules response (default 10000). Ignored for prompts.
        min_relevance_score: Min relevance 0.0–1.0 for rules (default 0.3).
        project_files: Optional comma-separated file paths for context. Rules only.
        rule_priority: \"local_overrides_shared\" (default) or \"shared_overrides_local\".
        context_aware: Use context detection for rule selection (default True). Rules only.
    """
    ct = (content_type or "").strip().lower()
    if ct == "rules":
        return await get_synapse_handle_rules(
            task_description,
            max_tokens,
            min_relevance_score,
            project_files,
            rule_priority,
            context_aware,
            ctx,
        )
    if ct == "prompts":
        return await get_synapse_handle_prompts(category, ctx)
    return json.dumps(
        {
            "status": "error",
            "error": f"Unknown content_type: {content_type!r}. Use rules or prompts.",
        },
        indent=2,
    )


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
