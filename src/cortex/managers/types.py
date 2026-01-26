"""Type definitions for manager system.

This module contains Pydantic model definitions for manager dictionaries.
It is kept separate from implementation modules to avoid circular imports.

All manager types are imported directly - no forward string references needed
because none of these modules import from cortex.managers.
"""

from pydantic import BaseModel, ConfigDict, Field

# Import concrete classes that were previously forward references
from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer

# Import concrete classes for managers without protocols
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.migration import MigrationManager
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.linking.link_parser import LinkParser
from cortex.linking.link_validator import LinkValidator
from cortex.linking.transclusion_engine import TransclusionEngine

# Lazy manager wrapper for on-demand initialization
from cortex.managers.lazy_manager import LazyManager
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


class CoreManagersDict(BaseModel):
    """Pydantic model for core manager instances (eagerly loaded).

    These managers are initialized immediately and are always available.
    They form the foundation for all other managers.

    Usage:
        core_managers = CoreManagersDict.model_validate(await _init_core_managers(root))
        fs = core_managers.fs  # FileSystemProtocol
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    fs: FileSystemManager = Field(description="File system manager")
    index: MetadataIndex = Field(description="Metadata index")
    tokens: TokenCounter = Field(description="Token counter")
    graph: DependencyGraph = Field(description="Dependency graph")
    versions: VersionManager = Field(description="Version manager")
    migration: MigrationManager = Field(description="Migration manager")
    watcher: FileWatcherManager = Field(description="File watcher manager")


class ManagersDict(BaseModel):
    """Pydantic model for manager instances returned by get_managers().

    This provides type-safe access to manager instances. Core managers are
    required because they are eagerly loaded and always available. Other managers
    are optional because lazy managers may not be initialized yet.

    Usage:
        mgrs = ManagersDict.model_validate(await get_managers(root))
        fs = mgrs.fs  # FileSystemProtocol - always available
        index = mgrs.index  # MetadataIndexProtocol - always available
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    # Phase 1: Core managers (eagerly loaded - always available)
    fs: FileSystemManager = Field(description="File system manager")
    index: MetadataIndex = Field(description="Metadata index")
    tokens: TokenCounter = Field(description="Token counter")
    graph: DependencyGraph = Field(description="Dependency graph")
    versions: VersionManager = Field(description="Version manager")
    migration: MigrationManager = Field(description="Migration manager")
    watcher: FileWatcherManager = Field(description="File watcher manager")

    # Phase 2: DRY Linking managers (lazy)
    link_parser: LazyManager[LinkParser] | LinkParser | None = Field(
        default=None, description="Link parser"
    )
    transclusion: LazyManager[TransclusionEngine] | TransclusionEngine | None = Field(
        default=None, description="Transclusion engine"
    )
    link_validator: LazyManager[LinkValidator] | LinkValidator | None = Field(
        default=None, description="Link validator"
    )

    # Phase 3: Validation managers (lazy)
    validation_config: LazyManager[ValidationConfig] | ValidationConfig | None = Field(
        default=None, description="Validation config"
    )
    schema_validator: LazyManager[SchemaValidator] | SchemaValidator | None = Field(
        default=None, description="Schema validator"
    )
    duplication_detector: (
        LazyManager[DuplicationDetector] | DuplicationDetector | None
    ) = Field(default=None, description="Duplication detector")
    quality_metrics: LazyManager[QualityMetrics] | QualityMetrics | None = Field(
        default=None, description="Quality metrics"
    )

    # Phase 4: Optimization managers (lazy)
    optimization_config: LazyManager[OptimizationConfig] | OptimizationConfig | None = (
        Field(default=None, description="Optimization config")
    )
    relevance_scorer: LazyManager[RelevanceScorer] | RelevanceScorer | None = Field(
        default=None, description="Relevance scorer"
    )
    context_optimizer: LazyManager[ContextOptimizer] | ContextOptimizer | None = Field(
        default=None, description="Context optimizer"
    )
    progressive_loader: LazyManager[ProgressiveLoader] | ProgressiveLoader | None = (
        Field(default=None, description="Progressive loader")
    )
    summarization_engine: (
        LazyManager[SummarizationEngine] | SummarizationEngine | None
    ) = Field(default=None, description="Summarization engine")
    rules_manager: LazyManager[RulesManager] | RulesManager | None = Field(
        default=None, description="Rules manager"
    )
    synapse: LazyManager[SynapseManager] | SynapseManager | None = Field(
        default=None, description="Synapse manager"
    )

    # Phase 5.1: Analysis managers (lazy)
    pattern_analyzer: LazyManager[PatternAnalyzer] | PatternAnalyzer | None = Field(
        default=None, description="Pattern analyzer"
    )
    structure_analyzer: LazyManager[StructureAnalyzer] | StructureAnalyzer | None = (
        Field(default=None, description="Structure analyzer")
    )
    insight_engine: LazyManager[InsightEngine] | InsightEngine | None = Field(
        default=None, description="Insight engine"
    )

    # Phase 5.2: Refactoring managers (lazy)
    refactoring_engine: LazyManager[RefactoringEngine] | RefactoringEngine | None = (
        Field(default=None, description="Refactoring engine")
    )
    consolidation_detector: (
        LazyManager[ConsolidationDetector] | ConsolidationDetector | None
    ) = Field(default=None, description="Consolidation detector")
    split_recommender: LazyManager[SplitRecommender] | SplitRecommender | None = Field(
        default=None, description="Split recommender"
    )
    reorganization_planner: (
        LazyManager[ReorganizationPlanner] | ReorganizationPlanner | None
    ) = Field(default=None, description="Reorganization planner")

    # Phase 5.3-5.4: Execution managers (lazy)
    refactoring_executor: (
        LazyManager[RefactoringExecutor] | RefactoringExecutor | None
    ) = Field(default=None, description="Refactoring executor")
    approval_manager: LazyManager[ApprovalManager] | ApprovalManager | None = Field(
        default=None, description="Approval manager"
    )
    rollback_manager: LazyManager[RollbackManager] | RollbackManager | None = Field(
        default=None, description="Rollback manager"
    )
    learning_engine: LazyManager[LearningEngine] | LearningEngine | None = Field(
        default=None, description="Learning engine"
    )
    adaptation_config: LazyManager[AdaptationConfig] | AdaptationConfig | None = Field(
        default=None, description="Adaptation config"
    )
