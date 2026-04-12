"""
Synapse Tools for MCP Memory Bank.

This module contains tools for syncing, updating, and retrieving
shared rules and prompts from a git submodule-based Synapse repository.

Tools: synapse (dispatcher), get_synapse_rules, get_synapse_prompts.
synapse consolidates sync_synapse and update_synapse (operation=sync|update_rule|update_prompt).

Note: setup_synapse has been replaced by a prompt template in docs/prompts/
"""

__all__ = [
    "RulePriorityLiteral",
    "get_synapse",
    "get_synapse_prompts",
    "get_synapse_prompts_resource",
    "get_synapse_rules",
    "get_synapse_rules_resource",
    "synapse",
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
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import OperationStatus
from cortex.tools.synapse.tools_impl import (
    RulePriorityLiteral,
    get_synapse_handle_prompts,
    get_synapse_handle_rules,
    get_synapse_rules,
    sync_synapse_impl,
    update_synapse_prompt_impl,
    update_synapse_rule_impl,
)


def _synapse_error_invalid_operation(operation: str) -> str:
    """Build error JSON for invalid synapse operation."""
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": f"Invalid operation '{operation}'. Use sync, update_rule, or update_prompt.",
        },
        indent=2,
    )


def _synapse_error_update_missing_params(operation: str) -> str:
    """Build error JSON when update_rule/update_prompt params are missing."""
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": f"category, file, content, and commit_message are required when operation is '{operation}'",
        },
        indent=2,
    )


async def _synapse_handle_sync(pull: bool, push: bool, ctx: MCPContext | None) -> str:
    """Handle synapse(operation='sync').

    MCP boundary: catches all exceptions and serialises them as JSON error
    responses so the MCP client always receives a structured payload rather
    than an unhandled exception.  Internal helpers (``sync_synapse_impl``,
    ``update_synapse_*_impl``) raise on all error conditions; narrowing here
    is intentional — see ``prompts_paths.py`` for narrowed catches at lower
    layers where specific failure modes are known.
    """
    await log_client(ctx, "info", "synapse(sync): starting", logger_name=__name__)
    try:
        return await sync_synapse_impl(pull, push, ctx)
    except Exception as e:
        await log_client(ctx, "error", f"synapse(sync): {e!s}", logger_name=__name__)
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            indent=2,
        )


async def _synapse_handle_update(
    op: str,
    category: str,
    file: str,
    content: str,
    commit_message: str,
    ctx: MCPContext | None,
) -> str:
    """Handle synapse(operation='update_rule'|'update_prompt')."""
    impl = (
        update_synapse_rule_impl if op == "update_rule" else update_synapse_prompt_impl
    )
    await log_client(ctx, "info", f"synapse({op}): starting", logger_name=__name__)
    try:
        return await impl(category, file, content, commit_message, ctx)
    except Exception as e:
        await log_client(ctx, "error", f"synapse({op}): {e!s}", logger_name=__name__)
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            indent=2,
        )


# MCP registration removed — admin tool, use git directly
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_EXTERNAL)
async def synapse(
    operation: str = "sync",
    # sync params
    pull: bool = True,
    push: bool = False,
    # update_rule / update_prompt params
    category: str | None = None,
    file: str | None = None,
    content: str | None = None,
    commit_message: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Sync Synapse repository with remote or update a rule/prompt file (single tool).

    USE WHEN: User wants to sync shared rules (operation=sync), pull/push
    Synapse changes, or update a shared rule/prompt file
    (operation=update_rule|update_prompt).

    EXAMPLES:
    - synapse(operation="sync", pull=True, push=False) — pull latest from remote
    - synapse(operation="sync", pull=False, push=True) — push local changes
    - synapse(operation="update_rule", category="python", file="type-hints.mdc",
      content="...", commit_message="Update type hints")
    - synapse(operation="update_prompt", category="general", file="implement.md",
      content="...", commit_message="Update implement prompt")

    RETURNS: JSON. For sync: status, pulled, pushed, changes (added/modified/deleted),
    reindex_triggered, last_sync. For update_rule/update_prompt: status, category,
    file, commit_hash, committed, pushed. On error: status "error", error message.

    Args:
        operation: "sync" (default) — git pull/push; "update_rule" or
            "update_prompt" — modify file, commit, push.
        pull: For sync. Pull latest from remote (default True).
        push: For sync. Push local changes (default False).
        category: For update_rule/update_prompt. Category (e.g. "python", "general").
        file: For update_rule/update_prompt. Filename (e.g. "type-hints.mdc").
        content: For update_rule/update_prompt. Complete new file content.
        commit_message: For update_rule/update_prompt. Git commit message.
    """
    op = (operation or "sync").strip().lower()
    if op not in ("sync", "update_rule", "update_prompt"):
        return _synapse_error_invalid_operation(operation or "")

    if op == "sync":
        return await _synapse_handle_sync(pull, push, ctx)

    if not all([category, file, content, commit_message]):
        return _synapse_error_update_missing_params(op)
    assert category is not None and file is not None
    assert content is not None and commit_message is not None
    return await _synapse_handle_update(
        op, category, file, content, commit_message, ctx
    )


async def sync_synapse(
    pull: bool = True,
    push: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Sync Synapse with remote (internal; use synapse(operation=\"sync\", ...) as MCP tool)."""
    return await synapse(operation="sync", pull=pull, push=push, ctx=ctx)


async def update_synapse(
    content_type: Literal["rule", "prompt"],
    category: str,
    file: str,
    content: str,
    commit_message: str,
    ctx: MCPContext | None = None,
) -> str:
    """Update Synapse rule or prompt (internal; use synapse(operation=\"update_rule\"|\"update_prompt\", ...) as MCP tool)."""
    op = "update_rule" if content_type == "rule" else "update_prompt"
    return await synapse(
        operation=op,
        category=category,
        file=file,
        content=content,
        commit_message=commit_message,
        ctx=ctx,
    )


async def update_synapse_rule(
    category: str,
    file: str,
    content: str,
    commit_message: str,
    ctx: MCPContext | None = None,
) -> str:
    """Update a Synapse rule file (wrapper; use synapse(operation=\"update_rule\", ...) as MCP tool)."""
    return await update_synapse(
        content_type="rule",
        category=category,
        file=file,
        content=content,
        commit_message=commit_message,
        ctx=ctx,
    )


# Internalized for tool budget reduction (2026-02-26). Use cortex://synapse/rules/{task}
# and cortex://synapse/prompts resources or rules(operation="get_relevant") instead.
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
            "status": OperationStatus.ERROR.value,
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
    """Update a Synapse prompt file (wrapper; use synapse(operation=\"update_prompt\", ...) as MCP tool)."""
    return await update_synapse(
        content_type="prompt",
        category=category,
        file=file,
        content=content,
        commit_message=commit_message,
        ctx=ctx,
    )


# MCP resource registration removed
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


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def get_synapse_prompts_resource() -> str:
    """Resource: All Synapse prompts (no category filter). Read via cortex://synapse/prompts."""
    return await get_synapse_prompts(category=None)
