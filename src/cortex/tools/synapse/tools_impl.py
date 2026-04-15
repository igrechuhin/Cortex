"""Implementation logic for synapse_tools module.

Extracted from synapse_tools.py to reduce main module size.
"""

import json
from collections.abc import Sequence
from typing import Literal, Protocol

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import ModelDict, OperationStatus
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.utils import get_manager
from cortex.optimization.rules_manager import RulesManager
from cortex.rules.synapse_manager import SynapseManager
from cortex.tools.synapse.synapse_models import SynapseCategory

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


def _synapse_not_initialized_json() -> str:
    """Build JSON error when Synapse is not initialized."""
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": "Synapse not initialized. Run setup_synapse first.",
        },
        indent=2,
    )


async def sync_synapse_impl(pull: bool, push: bool, ctx: MCPContext | None) -> str:
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
        return _synapse_not_initialized_json()
    synapse_manager = await get_manager(managers, "synapse", SynapseManager)
    result = await synapse_manager.sync_synapse(pull=pull, push=push)
    if result.reindex_triggered and managers.rules_manager is not None:
        rules_manager = await get_manager(managers, "rules_manager", RulesManager)
        _ = await rules_manager.index_rules(force=True)
    out = json.dumps(result.model_dump(mode="json"), indent=2)
    await log_client(ctx, "info", "sync_synapse: completed", logger_name=__name__)
    return out


async def update_synapse_rule_impl(
    category: SynapseCategory,
    file: str,
    content: str,
    commit_message: str,
    ctx: MCPContext | None,
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
        return _synapse_not_initialized_json()
    synapse_manager = await get_manager(managers, "synapse", SynapseManager)
    result = await synapse_manager.update_synapse_rule(
        category=category.value,
        file=file,
        content=content,
        commit_message=commit_message,
    )
    out = json.dumps(result, indent=2)
    await log_client(
        ctx, "info", "update_synapse_rule: completed", logger_name=__name__
    )
    return out


async def update_synapse_prompt_impl(
    category: SynapseCategory,
    file: str,
    content: str,
    commit_message: str,
    ctx: MCPContext | None,
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
        return _synapse_not_initialized_json()
    synapse_manager = await get_manager(managers, "synapse", SynapseManager)
    result = await synapse_manager.update_synapse_prompt(
        category=category.value,
        file=file,
        content=content,
        commit_message=commit_message,
    )
    out = json.dumps(result, indent=2)
    await log_client(
        ctx, "info", "update_synapse_prompt: completed", logger_name=__name__
    )
    return out


def _build_category_prompts_response(
    category: SynapseCategory, prompts: Sequence[ModelDict] | Sequence[_ModelDumpable]
) -> str:
    """Build JSON response for category-specific prompts."""
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "category": category.value,
            "prompts": format_prompts_list(prompts),
            "total_count": len(prompts),
        },
        indent=2,
    )


def _build_all_prompts_response(
    prompts: Sequence[ModelDict] | Sequence[_ModelDumpable],
    categories: list[str],
) -> str:
    """Build JSON response for all prompts."""
    return json.dumps(
        {
            "status": OperationStatus.SUCCESS.value,
            "categories": categories,
            "prompts": format_prompts_list(prompts),
            "total_count": len(prompts),
        },
        indent=2,
    )


def _get_synapse_rules_error_json(exc: Exception) -> str:
    """Build JSON error response for get_synapse_rules failures."""
    return json.dumps(
        {
            "status": OperationStatus.ERROR.value,
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
        indent=2,
    )


async def get_synapse_rules_impl(
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
        from cortex.tools.synapse.tools_helpers import execute_rules_with_context

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


async def get_synapse_handle_rules(
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
                "status": OperationStatus.ERROR.value,
                "error": "task_description required when content_type is rules",
            },
            indent=2,
        )
    desc = (task_description or "").strip()
    return await get_synapse_rules_impl(
        desc,
        max_tokens,
        min_relevance_score,
        project_files,
        rule_priority,
        context_aware,
        ctx,
    )


async def get_synapse_prompts_impl(
    category: SynapseCategory | None, ctx: MCPContext | None
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
        prompts = await synapse_manager.load_prompts_category(category.value)
        out = _build_category_prompts_response(category, prompts)
    else:
        prompts = await synapse_manager.get_all_prompts()
        categories = synapse_manager.get_prompt_categories()
        out = _build_all_prompts_response(prompts, categories)
    await log_client(
        ctx, "info", "get_synapse_prompts: completed", logger_name=__name__
    )
    return out


async def get_synapse_handle_prompts(
    category: SynapseCategory | None, ctx: MCPContext | None
) -> str:
    """Handle get_synapse(content_type='prompts') branch."""
    try:
        return await get_synapse_prompts_impl(category, ctx)
    except Exception as e:
        await log_client(
            ctx, "error", f"get_synapse(prompts): {e!s}", logger_name=__name__
        )
        return json.dumps(
            {
                "status": OperationStatus.ERROR.value,
                "error": str(e),
                "error_type": type(e).__name__,
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

    RETURNS: JSON with relevant rules, relevance scores, and rule content.

    This tool analyzes your task description and project files to automatically
    select the most relevant coding rules from both Synapse and local sources.

    Args:
        task_description: Natural language description of your current task.
        max_tokens: Maximum total tokens to include in response (default 10000).
        min_relevance_score: Min relevance 0.0-1.0 for rule inclusion (default 0.3).
        project_files: Comma-separated file paths for context (optional).
        rule_priority: "local_overrides_shared" (default) or "shared_overrides_local".
        context_aware: Enable context detection (default True).
    """
    return await get_synapse_rules_impl(
        task_description,
        max_tokens,
        min_relevance_score,
        project_files,
        rule_priority,
        context_aware,
        ctx,
    )
