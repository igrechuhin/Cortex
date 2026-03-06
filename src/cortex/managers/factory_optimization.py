#!/usr/bin/env python3
"""Optimization-phase manager factory helpers (Phase 4)."""

import collections.abc
from pathlib import Path

from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import CoreManagersDict
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.progressive_loader import ProgressiveLoader
from cortex.optimization.relevance_scorer import RelevanceScorer
from cortex.optimization.rules_manager import RulesManager
from cortex.optimization.summarization_engine import SummarizationEngine
from cortex.rules.synapse_manager import SynapseManager


def _make_synapse_factory(
    proj_root: Path, mgrs: ManagersBuilder
) -> collections.abc.Callable[[], collections.abc.Awaitable[SynapseManager]]:
    """Create factory function for SynapseManager."""

    async def factory() -> SynapseManager:
        return await _create_synapse_manager(proj_root, mgrs)

    return factory


async def _create_optimization_config(project_root: Path) -> OptimizationConfig:
    """Create OptimizationConfig instance."""
    return OptimizationConfig(project_root)


async def _create_relevance_scorer(
    core_managers: CoreManagersDict, managers: ManagersBuilder
) -> RelevanceScorer:
    """Create RelevanceScorer instance."""
    from cortex.managers.utils import get_manager

    dep_graph = core_managers.graph
    metadata_index = core_managers.index
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    return RelevanceScorer(
        dependency_graph=dep_graph,
        metadata_index=metadata_index,
        **optimization_config.get_relevance_weights(),
    )


async def _create_context_optimizer(
    core_managers: CoreManagersDict, managers: ManagersBuilder
) -> ContextOptimizer:
    """Create ContextOptimizer instance."""
    from cortex.managers.utils import get_manager

    token_counter = core_managers.tokens
    dep_graph = core_managers.graph
    relevance_scorer = await get_manager(managers, "relevance_scorer", RelevanceScorer)
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    return ContextOptimizer(
        token_counter=token_counter,
        relevance_scorer=relevance_scorer,
        dependency_graph=dep_graph,
        mandatory_files=optimization_config.get_mandatory_files(),
    )


async def _create_progressive_loader(
    core_managers: CoreManagersDict, managers: ManagersBuilder
) -> ProgressiveLoader:
    """Create ProgressiveLoader instance."""
    from cortex.managers.utils import get_manager

    fs_manager = core_managers.fs
    metadata_index = core_managers.index
    context_optimizer = await get_manager(
        managers, "context_optimizer", ContextOptimizer
    )

    return ProgressiveLoader(
        file_system=fs_manager,
        context_optimizer=context_optimizer,
        metadata_index=metadata_index,
    )


async def _create_summarization_engine(
    core_managers: CoreManagersDict,
) -> SummarizationEngine:
    """Create SummarizationEngine instance."""
    token_counter = core_managers.tokens
    metadata_index = core_managers.index

    return SummarizationEngine(
        token_counter=token_counter, metadata_index=metadata_index
    )


async def _create_rules_manager(
    project_root: Path, core_managers: CoreManagersDict, managers: ManagersBuilder
) -> RulesManager:
    """Create RulesManager instance."""
    from cortex.managers.utils import get_manager

    fs_manager = core_managers.fs
    metadata_index = core_managers.index
    token_counter = core_managers.tokens
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    return RulesManager(
        project_root=project_root,
        file_system=fs_manager,
        metadata_index=metadata_index,
        token_counter=token_counter,
        rules_folder=(
            optimization_config.get_rules_folder()
            if optimization_config.is_rules_enabled()
            else None
        ),
        reindex_interval_minutes=optimization_config.get_rules_reindex_interval(),
    )


async def _create_synapse_manager(
    project_root: Path, managers: ManagersBuilder
) -> SynapseManager:
    """Create SynapseManager instance."""
    from cortex.managers.utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    synapse_folder = optimization_config.get_synapse_folder()
    language_keywords = optimization_config.get_language_keywords()
    synapse_repo = optimization_config.get_synapse_repo()
    auto_sync = optimization_config.is_synapse_auto_sync()
    sync_interval = optimization_config.get_synapse_sync_interval()

    return SynapseManager(
        project_root=project_root,
        synapse_folder=synapse_folder,
        language_keywords=language_keywords if language_keywords else None,
        synapse_repo=synapse_repo if synapse_repo else None,
        auto_sync=auto_sync,
        sync_interval_minutes=sync_interval,
    )


def add_optimization_managers(
    managers: ManagersBuilder,
    project_root: Path,
    core_managers: CoreManagersDict,
) -> None:
    """Add Phase 4 optimization managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
        core_managers: Core managers dictionary
    """
    managers["optimization_config"] = LazyManager(
        lambda: _create_optimization_config(project_root), name="optimization_config"
    )
    managers["relevance_scorer"] = LazyManager(
        lambda: _create_relevance_scorer(core_managers, managers),
        name="relevance_scorer",
    )
    managers["context_optimizer"] = LazyManager(
        lambda: _create_context_optimizer(core_managers, managers),
        name="context_optimizer",
    )
    managers["progressive_loader"] = LazyManager(
        lambda: _create_progressive_loader(core_managers, managers),
        name="progressive_loader",
    )
    managers["summarization_engine"] = LazyManager(
        lambda: _create_summarization_engine(core_managers), name="summarization_engine"
    )
    managers["rules_manager"] = LazyManager(
        lambda: _create_rules_manager(project_root, core_managers, managers),
        name="rules_manager",
    )
    managers["synapse"] = LazyManager(
        _make_synapse_factory(project_root, managers), name="synapse"
    )
