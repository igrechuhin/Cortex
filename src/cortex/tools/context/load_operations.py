"""
Phase 4: Context Loading Operations

This module contains the implementation logic for the load_context tool.
"""

from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import ContextDepth
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.optimization.agent_roles import AgentRole
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.tools.context.load_operations_content import handle_full_or_summary_depth
from cortex.tools.context.load_operations_metadata import load_context_metadata_only


def calculate_effective_budget(
    token_budget: int | None, optimization_config: OptimizationConfig
) -> int:
    """Calculate effective token budget with max and reserve applied."""
    if token_budget is None or token_budget == 0:
        token_budget = optimization_config.get_token_budget()
    max_budget = optimization_config.get_max_token_budget()
    token_budget = min(token_budget, max_budget)
    # AI: the response reserve must never consume the whole budget. A request at
    # or below the reserve used to resolve to 0, which excluded every file and
    # returned an empty context with no error (telemetry: token_budget=0,
    # files_selected=0, files_excluded=7). Cap the reserve at half the budget.
    reserve = min(optimization_config.get_reserve_for_response(), token_budget // 2)
    return max(token_budget - reserve, 0)


async def _prepare_context_loading(
    mgrs: ManagersDict, token_budget: int | None
) -> tuple[int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager]:
    """Prepare managers and calculate effective budget."""
    (
        optimization_config,
        context_optimizer,
        metadata_index,
        fs_manager,
    ) = await _setup_optimization_managers(mgrs)
    effective_budget = calculate_effective_budget(token_budget, optimization_config)
    return (
        effective_budget,
        optimization_config,
        context_optimizer,
        metadata_index,
        fs_manager,
    )


async def _handle_metadata_only_depth(
    metadata_index: MetadataIndex,
    task_description: str,
    effective_budget: int,
    strategy: str,
    project_root: Path | None,
    optimization_config: OptimizationConfig,
    fs_manager: FileSystemManager,
    agent_role: AgentRole | None = None,
) -> str:
    """Handle metadata_only depth with hybrid retrieval strategy."""
    return await load_context_metadata_only(
        metadata_index,
        task_description,
        effective_budget,
        strategy,
        project_root,
        optimization_config,
        fs_manager,
        agent_role,
    )


async def load_context_impl(
    mgrs: ManagersDict,
    task_description: str,
    token_budget: int | None,
    strategy: str,
    depth: ContextDepth | str = ContextDepth.FULL,
    project_root: Path | None = None,
    agent_role: AgentRole | None = None,
) -> str:
    """Implementation logic for load_context tool."""
    if not isinstance(depth, ContextDepth):
        try:
            depth = ContextDepth(depth)
        except ValueError:
            depth = ContextDepth.FULL

    loading_data = await _prepare_context_loading(mgrs, token_budget)
    return await _dispatch_by_depth(
        loading_data, task_description, strategy, depth, project_root, agent_role
    )


def _unpack_loading_data(
    loading_data: tuple[
        int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager
    ],
) -> tuple[int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager]:
    """Unpack loading data tuple."""
    return loading_data


async def _dispatch_metadata_only(
    components: tuple[
        int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager
    ],
    task_description: str,
    strategy: str,
    project_root: Path | None,
    agent_role: AgentRole | None,
) -> str:
    """Dispatch metadata_only depth loading."""
    effective_budget, optimization_config, _, metadata_index, fs_manager = components
    return await _handle_metadata_only_depth(
        metadata_index,
        task_description,
        effective_budget,
        strategy,
        project_root,
        optimization_config,
        fs_manager,
        agent_role,
    )


async def _dispatch_full_or_summary(
    components: tuple[
        int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager
    ],
    task_description: str,
    strategy: str,
    depth: ContextDepth,
    project_root: Path | None,
    agent_role: AgentRole | None,
) -> str:
    """Dispatch full or summary depth loading."""
    effective_budget, _, context_optimizer, metadata_index, fs_manager = components
    return await handle_full_or_summary_depth(
        context_optimizer,
        metadata_index,
        fs_manager,
        task_description,
        effective_budget,
        strategy,
        depth,
        project_root,
        agent_role,
    )


async def _dispatch_by_depth(
    loading_data: tuple[
        int, OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager
    ],
    task_description: str,
    strategy: str,
    depth: ContextDepth,
    project_root: Path | None,
    agent_role: AgentRole | None,
) -> str:
    """Dispatch context loading based on depth parameter."""
    components = _unpack_loading_data(loading_data)
    if depth == ContextDepth.METADATA_ONLY:
        return await _dispatch_metadata_only(
            components, task_description, strategy, project_root, agent_role
        )
    return await _dispatch_full_or_summary(
        components, task_description, strategy, depth, project_root, agent_role
    )


async def _setup_optimization_managers(
    mgrs: ManagersDict,
) -> tuple[OptimizationConfig, ContextOptimizer, MetadataIndex, FileSystemManager]:
    """Setup managers for context optimization."""
    optimization_config = await get_manager(
        mgrs, "optimization_config", OptimizationConfig
    )
    context_optimizer = await get_manager(mgrs, "context_optimizer", ContextOptimizer)
    metadata_index = mgrs.index
    fs_manager = mgrs.fs
    return optimization_config, context_optimizer, metadata_index, fs_manager
