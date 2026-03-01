"""
Phase 4: Optimization Handlers - Load Context Execution Helpers

Load context execution flow: initialization, strategy dispatch, progressive loading,
and error handling.
"""

import json
from pathlib import Path

# Import via facade to allow test patching
import cortex.tools.optimization as opt
from cortex.core.context_logging import MCPContext
from cortex.core.models import ContextDepth, ResponseFormat
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.optimization.agent_roles import (
    AgentRole,
    detect_agent_role,
    normalize_role_name,
)
from cortex.optimization.config import OptimizationConfig
from cortex.tools.context.load_operations import load_context_impl
from cortex.tools.optimization_handlers_format import (
    format_and_add_warnings_if_needed,
    format_load_context_error,
)
from cortex.tools.optimization_handlers_validation import (
    validate_explicit_budget_for_non_trivial,
)


def determine_agent_role(role: str | None, task_description: str) -> AgentRole:
    """Determine effective agent role from explicit parameter or task description."""
    explicit_role = normalize_role_name(role) if role is not None else None
    return explicit_role or detect_agent_role(task_description)


def determine_depth_from_budget(
    depth: ContextDepth | None,
    token_budget: int | None,
) -> ContextDepth:
    """Determine depth level from budget if not explicitly specified."""
    if depth is not None:
        return depth

    if token_budget is None:
        return ContextDepth.FULL

    if token_budget < 5000:
        return ContextDepth.METADATA_ONLY
    if token_budget <= 15000:
        return ContextDepth.SUMMARY
    return ContextDepth.FULL


async def check_optimization_enabled(mgrs: ManagersDict) -> str | None:
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


async def load_context_progressive(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    loading_strategy: str | None,
) -> str:
    """Load context using progressive strategy."""
    from cortex.tools.optimization.progressive_operations import (
        load_progressive_context_impl,
    )

    effective_loading_strategy = loading_strategy or "by_relevance"
    return await load_progressive_context_impl(
        mgrs, task_description, token_budget, effective_loading_strategy
    )


async def load_context_execute(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    effective_depth: str,
    root: Path,
    agent_role: AgentRole | None = None,
) -> str:
    """Execute context loading with appropriate strategy."""
    if strategy == "progressive":
        return await load_context_progressive(
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


async def load_context_with_error_handling(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    effective_depth: str,
    root: Path,
    agent_role: AgentRole | None = None,
) -> str:
    """Execute context loading with error handling."""
    try:
        return await load_context_execute(
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


async def initialize_context_loading(
    ctx: MCPContext | None,
) -> tuple[Path, ManagersDict, str | None]:
    """Initialize context loading with managers and check enabled status."""
    root = await resolve_project_root_async(None, ctx)
    mgrs = await opt.get_managers(root)
    enabled_error = await check_optimization_enabled(mgrs)
    return root, mgrs, enabled_error


async def validate_and_initialize_context_loading(
    task_description: str, token_budget: int | None, ctx: MCPContext | None
) -> tuple[Path | None, ManagersDict | None, str | None]:
    """Validate budget and initialize context loading."""
    validation_error = validate_explicit_budget_for_non_trivial(
        task_description, token_budget
    )
    if validation_error:
        return None, None, validation_error
    root, mgrs, enabled_error = await initialize_context_loading(ctx)
    if enabled_error:
        return None, None, enabled_error
    return root, mgrs, None


async def execute_load_context(
    task_description: str,
    token_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    depth: ContextDepth | None,
    response_format: ResponseFormat,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    """Execute load_context with initialization and error handling."""
    root, mgrs, error = await validate_and_initialize_context_loading(
        task_description, token_budget, ctx
    )
    if error or root is None or mgrs is None:
        return error or json.dumps({"status": "error", "error": "Failed to initialize"})

    agent_role = determine_agent_role(role, task_description)
    effective_depth = determine_depth_from_budget(depth, token_budget)
    out = await load_context_with_error_handling(
        mgrs,
        task_description,
        token_budget,
        strategy,
        loading_strategy,
        effective_depth.value,
        root,
        agent_role,
    )
    return format_and_add_warnings_if_needed(
        out, response_format, agent_role.value, task_description, token_budget
    )


async def execute_load_context_with_logging(
    task_description: str,
    effective_budget: int | None,
    strategy: str,
    loading_strategy: str | None,
    depth: ContextDepth | None,
    response_format: ResponseFormat,
    role: str | None,
    ctx: MCPContext | None,
) -> str:
    """Run execute_load_context with success/error logging. Returns result JSON or error string."""
    from cortex.core.context_logging import log_client

    try:
        result = await execute_load_context(
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
        return format_load_context_error(e)
