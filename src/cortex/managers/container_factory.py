#!/usr/bin/env python3
"""Factory methods for creating manager instances.

This module contains all factory methods for creating manager instances
organized by implementation phase. These methods are separated from the
container class to keep the container focused on its core responsibility.
"""

from pathlib import Path
from typing import cast

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.migration import MigrationManager
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.linking.link_parser import LinkParser
from cortex.linking.link_validator import LinkValidator
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.optimization.context_optimizer import ContextOptimizer
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.optimization.progressive_loader import ProgressiveLoader
from cortex.optimization.relevance_scorer import RelevanceScorer
from cortex.optimization.rules_manager import RulesManager
from cortex.optimization.summarization_engine import SummarizationEngine
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.approval_manager import ApprovalManager
from cortex.refactoring.consolidation_detector import ConsolidationDetector
from cortex.refactoring.learning_engine import LearningEngine
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.refactoring.refactoring_executor import RefactoringExecutor
from cortex.refactoring.reorganization_planner import ReorganizationPlanner
from cortex.refactoring.rollback_manager import RollbackManager
from cortex.refactoring.split_recommender import SplitRecommender

# Type aliases for manager groups
FoundationManagers = tuple[
    FileSystemManager,
    MetadataIndex,
    TokenCounter,
    DependencyGraph,
    VersionManager,
    MigrationManager,
    FileWatcherManager,
]
LinkingManagers = tuple[LinkParser, TransclusionEngine, LinkValidator]
OptimizationManagers = tuple[
    OptimizationConfig,
    RelevanceScorer,
    ContextOptimizer,
    ProgressiveLoader,
    SummarizationEngine,
    RulesManager,
]
AnalysisManagers = tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine]
RefactoringManagers = tuple[
    RefactoringEngine,
    ConsolidationDetector,
    SplitRecommender,
    ReorganizationPlanner,
]
ExecutionManagers = tuple[
    RefactoringExecutor,
    ApprovalManager,
    RollbackManager,
    LearningEngine,
    AdaptationConfig,
]
AllManagers = tuple[
    FoundationManagers,
    LinkingManagers,
    OptimizationManagers,
    AnalysisManagers,
    RefactoringManagers,
    ExecutionManagers,
]


def create_all_managers(
    project_root: Path,
) -> AllManagers:
    """Create all managers grouped by phase.

    Args:
        project_root: Project root directory

    Returns:
        Tuple of manager groups: (foundation, linking, optimization, analysis, refactoring, execution)
    """
    foundation_managers = create_foundation_managers(project_root)
    linking_managers = create_linking_managers_from_foundation(foundation_managers)
    optimization_managers = create_optimization_managers_from_deps(
        project_root, foundation_managers
    )
    analysis_managers = create_analysis_managers_from_deps(
        project_root, foundation_managers
    )
    refactoring_managers = create_refactoring_managers_from_optimization(
        project_root, optimization_managers
    )
    execution_managers = create_execution_managers_from_deps(
        project_root, foundation_managers, linking_managers, optimization_managers
    )

    return (
        foundation_managers,
        linking_managers,
        optimization_managers,
        analysis_managers,
        refactoring_managers,
        execution_managers,
    )


def create_linking_managers_from_foundation(
    foundation_managers: FoundationManagers,
) -> LinkingManagers:
    """Create linking managers from foundation managers."""
    file_system = foundation_managers[0]
    return create_linking_managers(file_system)


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


def create_analysis_managers_from_deps(
    project_root: Path,
    foundation_managers: FoundationManagers,
) -> AnalysisManagers:
    """Create analysis managers from foundation dependencies."""
    dependency_graph = foundation_managers[3]
    file_system = foundation_managers[0]
    metadata_index = foundation_managers[1]
    return create_analysis_managers(
        project_root, dependency_graph, file_system, metadata_index
    )


def create_refactoring_managers_from_optimization(
    project_root: Path,
    optimization_managers: OptimizationManagers,
) -> RefactoringManagers:
    """Create refactoring managers from optimization dependencies."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    optimization_config = optimization_managers[0]
    return create_refactoring_managers(memory_bank_path, optimization_config)


def create_execution_managers_from_deps(
    project_root: Path,
    foundation_managers: FoundationManagers,
    linking_managers: LinkingManagers,
    optimization_managers: OptimizationManagers,
) -> ExecutionManagers:
    """Create execution managers from all dependencies."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    file_system = foundation_managers[0]
    version_manager = foundation_managers[4]
    metadata_index = foundation_managers[1]
    link_validator = linking_managers[2]
    optimization_config = optimization_managers[0]
    return create_execution_managers(
        memory_bank_path,
        file_system,
        version_manager,
        link_validator,
        metadata_index,
        optimization_config,
    )


def create_foundation_managers(
    project_root: Path,
) -> tuple[
    FileSystemManager,
    MetadataIndex,
    TokenCounter,
    DependencyGraph,
    VersionManager,
    MigrationManager,
    FileWatcherManager,
]:
    """Create Phase 1 foundation managers."""
    file_system = FileSystemManager(project_root)
    metadata_index = MetadataIndex(project_root)
    token_counter = TokenCounter()
    dependency_graph = DependencyGraph()
    version_manager = VersionManager(project_root)
    migration_manager = MigrationManager(project_root)
    file_watcher = FileWatcherManager()

    return (
        file_system,
        metadata_index,
        token_counter,
        dependency_graph,
        version_manager,
        migration_manager,
        file_watcher,
    )


def create_linking_managers(
    file_system: FileSystemManager,
) -> tuple[LinkParser, TransclusionEngine, LinkValidator]:
    """Create Phase 2 linking managers."""
    link_parser = LinkParser()
    transclusion_engine = TransclusionEngine(
        file_system=file_system,
        link_parser=link_parser,
        max_depth=5,
        cache_enabled=True,
    )
    link_validator = LinkValidator(file_system=file_system, link_parser=link_parser)

    return link_parser, transclusion_engine, link_validator


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


def create_analysis_managers(
    project_root: Path,
    dependency_graph: DependencyGraph,
    file_system: FileSystemManager,
    metadata_index: MetadataIndex,
) -> tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine]:
    """Create Phase 5.1 pattern analysis managers."""
    pattern_analyzer = PatternAnalyzer(project_root)
    structure_analyzer = StructureAnalyzer(
        project_root=project_root,
        dependency_graph=dependency_graph,
        file_system=file_system,
        metadata_index=metadata_index,
    )
    insight_engine = InsightEngine(
        pattern_analyzer=pattern_analyzer, structure_analyzer=structure_analyzer
    )

    return pattern_analyzer, structure_analyzer, insight_engine


def create_refactoring_managers(
    memory_bank_path: Path, optimization_config: OptimizationConfig
) -> tuple[
    RefactoringEngine,
    ConsolidationDetector,
    SplitRecommender,
    ReorganizationPlanner,
]:
    """Create Phase 5.2 refactoring suggestion managers."""
    refactoring_engine = _create_refactoring_engine(
        memory_bank_path, optimization_config
    )
    consolidation_detector = _create_consolidation_detector(memory_bank_path)
    split_recommender = _create_split_recommender(memory_bank_path)
    reorganization_planner = _create_reorganization_planner(memory_bank_path)

    return (
        refactoring_engine,
        consolidation_detector,
        split_recommender,
        reorganization_planner,
    )


def create_execution_managers(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    link_validator: LinkValidator,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> tuple[
    RefactoringExecutor,
    ApprovalManager,
    RollbackManager,
    LearningEngine,
    AdaptationConfig,
]:
    """Create Phase 5.3-5.4 execution and learning managers."""
    managers = _create_all_execution_managers(
        memory_bank_path,
        file_system,
        version_manager,
        link_validator,
        metadata_index,
        optimization_config,
    )
    return _build_execution_managers_tuple(*managers)


def _create_all_execution_managers(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    link_validator: LinkValidator,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> tuple[
    RefactoringExecutor,
    ApprovalManager,
    RollbackManager,
    LearningEngine,
    AdaptationConfig,
]:
    """Create all execution managers."""
    core_managers = _create_core_execution_managers(
        memory_bank_path,
        file_system,
        version_manager,
        link_validator,
        metadata_index,
        optimization_config,
    )
    learning_components = _create_learning_components(
        memory_bank_path, optimization_config
    )
    return _build_execution_managers_tuple(*core_managers, *learning_components)


def _create_core_execution_managers(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    link_validator: LinkValidator,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> tuple[RefactoringExecutor, ApprovalManager, RollbackManager]:
    """Create core execution managers."""
    refactoring_executor = _create_refactoring_executor(
        memory_bank_path,
        file_system,
        version_manager,
        link_validator,
        metadata_index,
        optimization_config,
    )
    approval_manager = _create_approval_manager(memory_bank_path, optimization_config)
    rollback_manager = _create_rollback_manager(
        memory_bank_path,
        file_system,
        version_manager,
        metadata_index,
        optimization_config,
    )
    return refactoring_executor, approval_manager, rollback_manager


def _create_learning_components(
    memory_bank_path: Path, optimization_config: OptimizationConfig
) -> tuple[LearningEngine, AdaptationConfig]:
    """Create learning engine and adaptation config."""
    learning_engine = _create_learning_engine(memory_bank_path, optimization_config)
    adaptation_config = _create_adaptation_config(optimization_config)
    return learning_engine, adaptation_config


def _build_execution_managers_tuple(
    refactoring_executor: RefactoringExecutor,
    approval_manager: ApprovalManager,
    rollback_manager: RollbackManager,
    learning_engine: LearningEngine,
    adaptation_config: AdaptationConfig,
) -> tuple[
    RefactoringExecutor,
    ApprovalManager,
    RollbackManager,
    LearningEngine,
    AdaptationConfig,
]:
    """Build tuple of execution managers."""
    return (
        refactoring_executor,
        approval_manager,
        rollback_manager,
        learning_engine,
        adaptation_config,
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


def _create_refactoring_executor(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    link_validator: LinkValidator,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> RefactoringExecutor:
    """Create refactoring executor manager."""
    return RefactoringExecutor(
        memory_bank_dir=memory_bank_path,
        fs_manager=file_system,
        version_manager=version_manager,
        link_validator=link_validator,
        metadata_index=metadata_index,
        config=None,
    )


def _create_approval_manager(
    memory_bank_path: Path,
    optimization_config: OptimizationConfig,
) -> ApprovalManager:
    """Create approval manager."""
    return ApprovalManager(memory_bank_dir=memory_bank_path, config=None)


def _create_rollback_manager(
    memory_bank_path: Path,
    file_system: FileSystemManager,
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
    optimization_config: OptimizationConfig,
) -> RollbackManager:
    """Create rollback manager."""
    return RollbackManager(
        memory_bank_dir=memory_bank_path,
        fs_manager=file_system,
        version_manager=version_manager,
        metadata_index=metadata_index,
        config=None,
    )


def _create_learning_engine(
    memory_bank_path: Path,
    optimization_config: OptimizationConfig,
) -> LearningEngine:
    """Create learning engine."""
    return LearningEngine(
        memory_bank_dir=memory_bank_path,
        config=cast(
            ModelDict | None,
            optimization_config.get("self_evolution.learning", {}),
        ),
    )


def _create_adaptation_config(
    optimization_config: OptimizationConfig,
) -> AdaptationConfig:
    """Create adaptation config."""
    # AdaptationConfig expects its own self-evolution schema (learning/feedback/etc.),
    # which is distinct from OptimizationConfig's `self_evolution` section.
    # Use defaults unless a dedicated adaptation config source is introduced.
    return AdaptationConfig(base_config=None)


def _create_refactoring_engine(
    memory_bank_path: Path, optimization_config: OptimizationConfig
) -> RefactoringEngine:
    """Create refactoring engine."""
    return RefactoringEngine(
        memory_bank_path=memory_bank_path,
        min_confidence=cast(
            float,
            optimization_config.get("self_evolution.suggestions.min_confidence", 0.7),
        ),
        max_suggestions_per_run=cast(
            int,
            optimization_config.get(
                "self_evolution.suggestions.max_suggestions_per_run", 10
            ),
        ),
    )


def _create_consolidation_detector(
    memory_bank_path: Path,
) -> ConsolidationDetector:
    """Create consolidation detector."""
    return ConsolidationDetector(
        memory_bank_path=memory_bank_path,
        min_similarity=0.80,
        min_section_length=100,
        target_reduction=0.30,
    )


def _create_split_recommender(
    memory_bank_path: Path,
) -> SplitRecommender:
    """Create split recommender."""
    return SplitRecommender(
        memory_bank_path=memory_bank_path,
        max_file_size=5000,
        max_sections=10,
        min_section_independence=0.6,
    )


def _create_reorganization_planner(
    memory_bank_path: Path,
) -> ReorganizationPlanner:
    """Create reorganization planner."""
    return ReorganizationPlanner(
        memory_bank_path=memory_bank_path,
        max_dependency_depth=5,
        enable_categories=True,
    )
