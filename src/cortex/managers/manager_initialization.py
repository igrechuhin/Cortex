#!/usr/bin/env python3
"""Manager factory functions for creating and registering managers."""

import collections.abc
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.linking.link_parser import LinkParser
from cortex.linking.link_validator import LinkValidator
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import CoreManagersDict
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
from cortex.rules.synapse_manager import SynapseManager
from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator
from cortex.validation.validation_config import ValidationConfig

# Type alias for managers dict that can be mutated during initialization.
# This dict starts empty and is populated with manager instances.
#
# DESIGN NOTE: We use dict[str, object] here intentionally because:
# 1. During initialization, we add heterogeneous types: Protocol implementations,
#    concrete classes, and LazyManager[T] wrappers - there's no common base type
# 2. The final dict is cast to ManagersDict (TypedDict) for type-safe access
# 3. This is a polymorphic container at initialization boundary, not a domain model
# 4. Alternative (Union of all 30+ manager types) would be unmaintainable
#
# For type-safe access, consumers should use:
# - managers.types.ManagersDict (TypedDict with all manager types)
# - managers.manager_utils.get_manager() for safe extraction with type checking
ManagersBuilder = dict[str, object]


def _make_synapse_factory(
    proj_root: Path, mgrs: Mapping[str, object]
) -> collections.abc.Callable[[], collections.abc.Awaitable[SynapseManager]]:
    """Create factory function for SynapseManager.

    Args:
        proj_root: Project root directory
        mgrs: Managers dictionary

    Returns:
        Factory function that creates SynapseManager
    """

    async def factory() -> SynapseManager:
        return await _create_synapse_manager(proj_root, mgrs)

    return factory


def add_linking_managers(
    managers: ManagersBuilder, core_managers: CoreManagersDict
) -> None:
    """Add Phase 2 linking managers as lazy.

    Args:
        managers: Managers dictionary to update
        core_managers: Core managers dictionary
    """
    managers["link_parser"] = LazyManager(
        lambda: _create_link_parser(), name="link_parser"
    )
    managers["transclusion"] = LazyManager(
        lambda: _create_transclusion_engine(core_managers), name="transclusion"
    )
    managers["link_validator"] = LazyManager(
        lambda: _create_link_validator(core_managers), name="link_validator"
    )


def add_validation_managers(managers: ManagersBuilder, project_root: Path) -> None:
    """Add Phase 3 validation managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
    """
    managers["validation_config"] = LazyManager(
        lambda: _create_validation_config(project_root), name="validation_config"
    )
    managers["schema_validator"] = LazyManager(
        lambda: _create_schema_validator(project_root, managers),
        name="schema_validator",
    )
    managers["duplication_detector"] = LazyManager(
        lambda: _create_duplication_detector(), name="duplication_detector"
    )
    managers["quality_metrics"] = LazyManager(
        lambda: _create_quality_metrics(managers), name="quality_metrics"
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


def add_analysis_managers(
    managers: ManagersBuilder,
    project_root: Path,
    core_managers: CoreManagersDict,
) -> None:
    """Add Phase 5.1 analysis managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
        core_managers: Core managers dictionary
    """
    managers["pattern_analyzer"] = LazyManager(
        lambda: _create_pattern_analyzer(project_root), name="pattern_analyzer"
    )
    managers["structure_analyzer"] = LazyManager(
        lambda: _create_structure_analyzer(project_root, core_managers),
        name="structure_analyzer",
    )
    managers["insight_engine"] = LazyManager(
        lambda: _create_insight_engine(managers), name="insight_engine"
    )


def add_refactoring_managers(managers: ManagersBuilder, project_root: Path) -> None:
    """Add Phase 5.2 refactoring managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
    """
    managers["refactoring_engine"] = LazyManager(
        lambda: _create_refactoring_engine(project_root, managers),
        name="refactoring_engine",
    )
    managers["consolidation_detector"] = LazyManager(
        lambda: _create_consolidation_detector(project_root),
        name="consolidation_detector",
    )
    managers["split_recommender"] = LazyManager(
        lambda: _create_split_recommender(project_root), name="split_recommender"
    )
    managers["reorganization_planner"] = LazyManager(
        lambda: _create_reorganization_planner(project_root),
        name="reorganization_planner",
    )


def add_execution_managers(
    managers: ManagersBuilder,
    project_root: Path,
    core_managers: CoreManagersDict,
) -> None:
    """Add Phase 5.3-5.4 execution managers as lazy.

    Args:
        managers: Managers dictionary to update
        project_root: Project root directory
        core_managers: Core managers dictionary
    """
    managers["refactoring_executor"] = LazyManager(
        lambda: _create_refactoring_executor(project_root, core_managers, managers),
        name="refactoring_executor",
    )
    managers["approval_manager"] = LazyManager(
        lambda: _create_approval_manager(project_root, managers),
        name="approval_manager",
    )
    managers["rollback_manager"] = LazyManager(
        lambda: _create_rollback_manager(project_root, core_managers, managers),
        name="rollback_manager",
    )
    managers["learning_engine"] = LazyManager(
        lambda: _create_learning_engine(project_root, managers), name="learning_engine"
    )
    managers["adaptation_config"] = LazyManager(
        lambda: _create_adaptation_config(managers), name="adaptation_config"
    )


# Factory functions for lazy manager creation


async def _create_link_parser() -> LinkParser:
    """Create LinkParser instance."""
    return LinkParser()


async def _create_transclusion_engine(
    core_managers: CoreManagersDict,
) -> TransclusionEngine:
    """Create TransclusionEngine instance."""
    fs_manager = core_managers["fs"]
    link_parser = LinkParser()
    return TransclusionEngine(
        file_system=cast(FileSystemManager, fs_manager),
        link_parser=link_parser,
        max_depth=5,
        cache_enabled=True,
    )


async def _create_link_validator(core_managers: CoreManagersDict) -> LinkValidator:
    """Create LinkValidator instance."""
    fs_manager = core_managers["fs"]
    link_parser = LinkParser()
    return LinkValidator(
        file_system=cast(FileSystemManager, fs_manager), link_parser=link_parser
    )


async def _create_optimization_config(project_root: Path) -> OptimizationConfig:
    """Create OptimizationConfig instance."""
    return OptimizationConfig(project_root)


async def _create_relevance_scorer(
    core_managers: CoreManagersDict, managers: Mapping[str, object]
) -> RelevanceScorer:
    """Create RelevanceScorer instance."""
    from cortex.managers.manager_utils import get_manager

    dep_graph = cast(DependencyGraph, core_managers["graph"])
    metadata_index = cast(MetadataIndex, core_managers["index"])
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    return RelevanceScorer(
        dependency_graph=dep_graph,
        metadata_index=metadata_index,
        **optimization_config.get_relevance_weights(),
    )


async def _create_context_optimizer(
    core_managers: CoreManagersDict, managers: Mapping[str, object]
) -> ContextOptimizer:
    """Create ContextOptimizer instance."""
    from cortex.managers.manager_utils import get_manager

    token_counter = cast(TokenCounter, core_managers["tokens"])
    dep_graph = cast(DependencyGraph, core_managers["graph"])
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
    core_managers: CoreManagersDict, managers: Mapping[str, object]
) -> ProgressiveLoader:
    """Create ProgressiveLoader instance."""
    from cortex.managers.manager_utils import get_manager

    fs_manager = cast(FileSystemManager, core_managers["fs"])
    metadata_index = cast(MetadataIndex, core_managers["index"])
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
    token_counter = cast(TokenCounter, core_managers["tokens"])
    metadata_index = cast(MetadataIndex, core_managers["index"])

    return SummarizationEngine(
        token_counter=token_counter, metadata_index=metadata_index
    )


async def _create_rules_manager(
    project_root: Path, core_managers: CoreManagersDict, managers: Mapping[str, object]
) -> RulesManager:
    """Create RulesManager instance."""
    from cortex.managers.manager_utils import get_manager

    fs_manager = cast(FileSystemManager, core_managers["fs"])
    metadata_index = cast(MetadataIndex, core_managers["index"])
    token_counter = cast(TokenCounter, core_managers["tokens"])
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
    project_root: Path, managers: Mapping[str, object]
) -> SynapseManager:
    """Create SynapseManager instance."""
    from cortex.managers.manager_utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    synapse_folder = optimization_config.get_synapse_folder()

    return SynapseManager(
        project_root=project_root,
        synapse_folder=synapse_folder,
    )


async def _create_pattern_analyzer(project_root: Path) -> PatternAnalyzer:
    """Create PatternAnalyzer instance."""
    return PatternAnalyzer(project_root)


async def _create_structure_analyzer(
    project_root: Path, core_managers: CoreManagersDict
) -> StructureAnalyzer:
    """Create StructureAnalyzer instance."""
    dep_graph = cast(DependencyGraph, core_managers["graph"])
    fs_manager = cast(FileSystemManager, core_managers["fs"])
    metadata_index = cast(MetadataIndex, core_managers["index"])

    return StructureAnalyzer(
        project_root=project_root,
        dependency_graph=dep_graph,
        file_system=fs_manager,
        metadata_index=metadata_index,
    )


async def _create_insight_engine(managers: Mapping[str, object]) -> InsightEngine:
    """Create InsightEngine instance."""
    from cortex.managers.manager_utils import get_manager

    pattern_analyzer = await get_manager(managers, "pattern_analyzer", PatternAnalyzer)
    structure_analyzer = await get_manager(
        managers, "structure_analyzer", StructureAnalyzer
    )

    return InsightEngine(
        pattern_analyzer=pattern_analyzer, structure_analyzer=structure_analyzer
    )


async def _create_refactoring_engine(
    project_root: Path, managers: Mapping[str, object]
) -> RefactoringEngine:
    """Create RefactoringEngine instance."""
    from cortex.managers.manager_utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

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


async def _create_consolidation_detector(
    project_root: Path,
) -> ConsolidationDetector:
    """Create ConsolidationDetector instance."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return ConsolidationDetector(
        memory_bank_path=memory_bank_path,
        min_similarity=0.80,
        min_section_length=100,
        target_reduction=0.30,
    )


async def _create_split_recommender(project_root: Path) -> SplitRecommender:
    """Create SplitRecommender instance."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return SplitRecommender(
        memory_bank_path=memory_bank_path,
        max_file_size=5000,
        max_sections=10,
        min_section_independence=0.6,
    )


async def _create_reorganization_planner(
    project_root: Path,
) -> ReorganizationPlanner:
    """Create ReorganizationPlanner instance."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return ReorganizationPlanner(
        memory_bank_path=memory_bank_path,
        max_dependency_depth=5,
        enable_categories=True,
    )


async def _create_refactoring_executor(
    project_root: Path, core_managers: CoreManagersDict, managers: Mapping[str, object]
) -> RefactoringExecutor:
    """Create RefactoringExecutor instance."""
    from cortex.managers.manager_utils import get_manager

    fs_manager = cast(FileSystemManager, core_managers["fs"])
    metadata_index = cast(MetadataIndex, core_managers["index"])
    version_manager = cast(VersionManager, core_managers["versions"])
    link_validator = await get_manager(managers, "link_validator", LinkValidator)
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    # RefactoringExecutor expects its own config type, use defaults
    return RefactoringExecutor(
        memory_bank_dir=memory_bank_path,
        fs_manager=fs_manager,
        version_manager=version_manager,
        link_validator=link_validator,
        metadata_index=metadata_index,
        config=None,  # Use default RefactoringExecutorConfig
    )


async def _create_approval_manager(
    project_root: Path, managers: Mapping[str, object]
) -> ApprovalManager:
    """Create ApprovalManager instance."""
    _ = managers  # Not needed, kept for API compatibility
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    # ApprovalManager expects its own config type, use defaults
    return ApprovalManager(memory_bank_dir=memory_bank_path, config=None)


async def _create_rollback_manager(
    project_root: Path, core_managers: CoreManagersDict, managers: Mapping[str, object]
) -> RollbackManager:
    """Create RollbackManager instance."""
    _ = managers  # Not needed, kept for API compatibility
    fs_manager = cast(FileSystemManager, core_managers["fs"])
    version_manager = cast(VersionManager, core_managers["versions"])
    metadata_index = cast(MetadataIndex, core_managers["index"])
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    return RollbackManager(
        memory_bank_dir=memory_bank_path,
        fs_manager=fs_manager,
        version_manager=version_manager,
        metadata_index=metadata_index,
    )


async def _create_learning_engine(
    project_root: Path, managers: Mapping[str, object]
) -> LearningEngine:
    """Create LearningEngine instance."""
    from cortex.managers.manager_utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)

    # LearningEngine uses its own defaults when config is None
    _ = optimization_config  # Kept for API compatibility
    return LearningEngine(
        memory_bank_dir=memory_bank_path,
        config=None,
    )


async def _create_validation_config(project_root: Path) -> ValidationConfig:
    """Create ValidationConfig instance."""
    return ValidationConfig(project_root)


async def _create_schema_validator(
    project_root: Path, managers: Mapping[str, object]
) -> SchemaValidator:
    """Create SchemaValidator instance."""
    _ = managers  # Kept for API compatibility
    return SchemaValidator(config_path=project_root / ".cortex" / "validation.json")


async def _create_duplication_detector() -> DuplicationDetector:
    """Create DuplicationDetector instance."""
    return DuplicationDetector()


async def _create_quality_metrics(managers: Mapping[str, object]) -> QualityMetrics:
    """Create QualityMetrics instance."""
    from cortex.managers.manager_utils import get_manager

    schema_validator = await get_manager(managers, "schema_validator", SchemaValidator)
    metadata_index = cast(MetadataIndex, managers["index"])
    return QualityMetrics(
        schema_validator=schema_validator, metadata_index=metadata_index
    )


async def _create_adaptation_config(managers: Mapping[str, object]) -> AdaptationConfig:
    """Create AdaptationConfig instance.

    Note: AdaptationConfig now uses its own Pydantic models for defaults.
    The managers parameter is kept for API compatibility.
    """
    # AdaptationConfig now manages its own defaults via Pydantic models
    _ = managers  # Kept for API compatibility
    return AdaptationConfig()
