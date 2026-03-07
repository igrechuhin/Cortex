"""Factory methods for creating Phase 4 optimization manager instances."""

from pathlib import Path

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.progressive_loader import ProgressiveLoader
from cortex.optimization.relevance_scorer import RelevanceScorer
from cortex.optimization.rules_manager import RulesManager
from cortex.optimization.summarization_engine import SummarizationEngine

from .container_config import FoundationManagers, OptimizationManagers


def create_optimization_managers_from_deps(
    project_root: Path,
    foundation_managers: FoundationManagers,
) -> OptimizationManagers:
    """Create optimization managers from foundation dependencies."""
    file_system = foundation_managers[0]
    metadata_index = foundation_managers[1]
    token_counter = foundation_managers[2]
    dependency_graph = foundation_managers[3]
    return create_optimization_managers(
        project_root, file_system, metadata_index, token_counter, dependency_graph
    )


def create_optimization_managers(
    project_root: Path,
    file_system: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    dependency_graph: DependencyGraph,
) -> tuple[
    OptimizationConfig,
    RelevanceScorer,
    ContextOptimizer,
    ProgressiveLoader,
    SummarizationEngine,
    RulesManager,
]:
    """Create Phase 4 optimization managers."""
    core_managers = _create_core_optimization_managers(
        project_root, dependency_graph, metadata_index, token_counter
    )
    content_managers = _create_content_managers(
        file_system, core_managers[2], metadata_index, token_counter
    )
    rules_manager = _create_rules_manager(
        project_root, file_system, metadata_index, token_counter, core_managers[0]
    )

    return (
        core_managers[0],
        core_managers[1],
        core_managers[2],
        content_managers[0],
        content_managers[1],
        rules_manager,
    )


def _create_core_optimization_managers(
    project_root: Path,
    dependency_graph: DependencyGraph,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
) -> tuple[OptimizationConfig, RelevanceScorer, ContextOptimizer]:
    """Create core optimization managers (config, scorer, optimizer)."""
    optimization_config = OptimizationConfig(project_root)
    relevance_scorer = RelevanceScorer(
        dependency_graph=dependency_graph,
        metadata_index=metadata_index,
        **optimization_config.get_relevance_weights(),
    )
    context_optimizer = ContextOptimizer(
        token_counter=token_counter,
        relevance_scorer=relevance_scorer,
        dependency_graph=dependency_graph,
        mandatory_files=optimization_config.get_mandatory_files(),
    )
    return optimization_config, relevance_scorer, context_optimizer


def _create_content_managers(
    file_system: FileSystemManager,
    context_optimizer: ContextOptimizer,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
) -> tuple[ProgressiveLoader, SummarizationEngine]:
    """Create content management managers (loader, summarization)."""
    progressive_loader = ProgressiveLoader(
        file_system=file_system,
        context_optimizer=context_optimizer,
        metadata_index=metadata_index,
    )
    summarization_engine = SummarizationEngine(
        token_counter=token_counter, metadata_index=metadata_index
    )
    return progressive_loader, summarization_engine


def _create_rules_manager(
    project_root: Path,
    file_system: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    optimization_config: OptimizationConfig,
) -> RulesManager:
    """Create rules manager with configuration."""
    return RulesManager(
        project_root=project_root,
        file_system=file_system,
        metadata_index=metadata_index,
        token_counter=token_counter,
        rules_folder=(
            optimization_config.get_rules_folder()
            if optimization_config.is_rules_enabled()
            else None
        ),
        reindex_interval_minutes=optimization_config.get_rules_reindex_interval(),
    )
