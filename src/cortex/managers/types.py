"""Type definitions for manager system.

This module contains TypedDict definitions for manager dictionaries.
It is kept separate from implementation modules to avoid circular imports.

All manager types are imported directly - no forward string references needed
because none of these modules import from cortex.managers.
"""

from typing import Required, TypedDict

# Import concrete classes that were previously forward references
from cortex.analysis.insight_engine import InsightEngine

# Import concrete classes for managers without protocols
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.migration import MigrationManager

# Import protocols for type-safe manager access
from cortex.core.protocols import (
    ApprovalManagerProtocol,
    ConsolidationDetectorProtocol,
    ContextOptimizerProtocol,
    DependencyGraphProtocol,
    FileSystemProtocol,
    LearningEngineProtocol,
    LinkParserProtocol,
    LinkValidatorProtocol,
    MetadataIndexProtocol,
    PatternAnalyzerProtocol,
    ProgressiveLoaderProtocol,
    RefactoringEngineProtocol,
    RelevanceScorerProtocol,
    ReorganizationPlannerProtocol,
    RollbackManagerProtocol,
    RulesManagerProtocol,
    SplitRecommenderProtocol,
    StructureAnalyzerProtocol,
    SummarizationEngineProtocol,
    TokenCounterProtocol,
    TransclusionEngineProtocol,
    VersionManagerProtocol,
)
from cortex.optimization.optimization_config import OptimizationConfig
from cortex.refactoring.adaptation_config import AdaptationConfig
from cortex.refactoring.refactoring_executor import RefactoringExecutor
from cortex.rules.synapse_manager import SynapseManager
from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.quality_metrics import QualityMetrics
from cortex.validation.schema_validator import SchemaValidator
from cortex.validation.validation_config import ValidationConfig


class CoreManagersDict(TypedDict):
    """TypedDict for core manager instances (eagerly loaded).

    These managers are initialized immediately and are always available.
    They form the foundation for all other managers.

    Usage:
        core_managers: CoreManagersDict = await _init_core_managers(root)
        fs = core_managers["fs"]  # FileSystemProtocol
    """

    fs: FileSystemProtocol
    index: MetadataIndexProtocol
    tokens: TokenCounterProtocol
    graph: DependencyGraphProtocol
    versions: VersionManagerProtocol
    migration: MigrationManager
    watcher: FileWatcherManager


class ManagersDict(TypedDict, total=False):
    """TypedDict for manager instances returned by get_managers().

    This provides type-safe access to manager instances without changing
    the underlying dictionary structure. Core managers are marked as Required
    because they are eagerly loaded and always available. Other managers are
    optional (total=False) because lazy managers may not be initialized yet.

    Usage:
        mgrs: ManagersDict = await get_managers(root)
        fs = mgrs["fs"]  # FileSystemProtocol - always available
        index = mgrs["index"]  # MetadataIndexProtocol - always available
    """

    # Phase 1: Core managers (eagerly loaded - always available)
    fs: Required[FileSystemProtocol]
    index: Required[MetadataIndexProtocol]
    tokens: Required[TokenCounterProtocol]
    graph: Required[DependencyGraphProtocol]
    versions: Required[VersionManagerProtocol]
    migration: Required[MigrationManager]
    watcher: Required[FileWatcherManager]

    # Phase 2: DRY Linking managers (lazy)
    link_parser: LinkParserProtocol
    transclusion: TransclusionEngineProtocol
    link_validator: LinkValidatorProtocol

    # Phase 3: Validation managers (lazy)
    validation_config: ValidationConfig
    schema_validator: SchemaValidator
    duplication_detector: DuplicationDetector
    quality_metrics: QualityMetrics

    # Phase 4: Optimization managers (lazy)
    optimization_config: OptimizationConfig
    relevance_scorer: RelevanceScorerProtocol
    context_optimizer: ContextOptimizerProtocol
    progressive_loader: ProgressiveLoaderProtocol
    summarization_engine: SummarizationEngineProtocol
    rules_manager: RulesManagerProtocol
    synapse: SynapseManager

    # Phase 5.1: Analysis managers (lazy)
    pattern_analyzer: PatternAnalyzerProtocol
    structure_analyzer: StructureAnalyzerProtocol
    insight_engine: InsightEngine

    # Phase 5.2: Refactoring managers (lazy)
    refactoring_engine: RefactoringEngineProtocol
    consolidation_detector: ConsolidationDetectorProtocol
    split_recommender: SplitRecommenderProtocol
    reorganization_planner: ReorganizationPlannerProtocol

    # Phase 5.3-5.4: Execution managers (lazy)
    refactoring_executor: RefactoringExecutor
    approval_manager: ApprovalManagerProtocol
    rollback_manager: RollbackManagerProtocol
    learning_engine: LearningEngineProtocol
    adaptation_config: AdaptationConfig
