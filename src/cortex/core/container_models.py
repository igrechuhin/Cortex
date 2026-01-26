#!/usr/bin/env python3
"""Pydantic models used by the dependency injection container.

These models are separated from `cortex.core.models` to avoid circular imports:
- Container models depend on protocol types (`cortex.core.protocols`)
- Several protocol modules reference core models for return types
"""

from pydantic import BaseModel, ConfigDict, Field

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
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


class UnpackedManagers(BaseModel):
    """Unpacked managers for container initialization."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    # Phase 1: Foundation
    file_system: FileSystemManager = Field(description="File I/O operations")
    metadata_index: MetadataIndex = Field(description="Metadata tracking")
    token_counter: TokenCounter = Field(description="Token counting")
    dependency_graph: DependencyGraph = Field(description="Dependency management")
    version_manager: VersionManager = Field(description="Version control")
    migration_manager: MigrationManager = Field(description="Format migration")
    file_watcher: FileWatcherManager = Field(description="External change detection")

    # Phase 2: DRY Linking
    link_parser: LinkParser = Field(description="Link parsing")
    transclusion_engine: TransclusionEngine = Field(description="Content transclusion")
    link_validator: LinkValidator = Field(description="Link validation")

    # Phase 4: Optimization
    optimization_config: OptimizationConfig = Field(
        description="Configuration management"
    )
    relevance_scorer: RelevanceScorer = Field(description="Relevance scoring")
    context_optimizer: ContextOptimizer = Field(description="Context optimization")
    progressive_loader: ProgressiveLoader = Field(description="Progressive loading")
    summarization_engine: SummarizationEngine = Field(
        description="Content summarization"
    )
    rules_manager: RulesManager = Field(description="Rules indexing")

    # Phase 5.1: Pattern Analysis
    pattern_analyzer: PatternAnalyzer = Field(description="Usage pattern analysis")
    structure_analyzer: StructureAnalyzer = Field(description="Structure analysis")
    insight_engine: InsightEngine = Field(description="AI insights")

    # Phase 5.2: Refactoring Suggestions
    refactoring_engine: RefactoringEngine = Field(description="Refactoring suggestions")
    consolidation_detector: ConsolidationDetector = Field(
        description="Consolidation detection"
    )
    split_recommender: SplitRecommender = Field(description="File splitting")
    reorganization_planner: ReorganizationPlanner = Field(
        description="Structure reorganization"
    )

    # Phase 5.3-5.4: Execution & Learning
    refactoring_executor: RefactoringExecutor = Field(
        description="Safe refactoring execution"
    )
    approval_manager: ApprovalManager = Field(description="User approval workflow")
    rollback_manager: RollbackManager = Field(description="Rollback support")
    learning_engine: LearningEngine = Field(description="Learning from feedback")
    adaptation_config: AdaptationConfig = Field(description="Adaptation configuration")


class FoundationKwargs(BaseModel):
    """Keyword arguments for Phase 1 foundation managers."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    file_system: FileSystemManager = Field(description="File I/O operations")
    metadata_index: MetadataIndex = Field(description="Metadata tracking")
    token_counter: TokenCounter = Field(description="Token counting")
    dependency_graph: DependencyGraph = Field(description="Dependency management")
    version_manager: VersionManager = Field(description="Version control")
    migration_manager: MigrationManager = Field(description="Format migration")
    file_watcher: FileWatcherManager = Field(description="External change detection")


class LinkingKwargs(BaseModel):
    """Keyword arguments for Phase 2 linking managers."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    link_parser: LinkParser = Field(description="Link parsing")
    transclusion_engine: TransclusionEngine = Field(description="Content transclusion")
    link_validator: LinkValidator = Field(description="Link validation")


class OptimizationKwargs(BaseModel):
    """Keyword arguments for Phase 4 optimization managers."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    optimization_config: OptimizationConfig = Field(
        description="Configuration management"
    )
    relevance_scorer: RelevanceScorer = Field(description="Relevance scoring")
    context_optimizer: ContextOptimizer = Field(description="Context optimization")
    progressive_loader: ProgressiveLoader = Field(description="Progressive loading")
    summarization_engine: SummarizationEngine = Field(
        description="Content summarization"
    )
    rules_manager: RulesManager = Field(description="Rules indexing")


class AnalysisKwargs(BaseModel):
    """Keyword arguments for Phase 5.1 analysis managers."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    pattern_analyzer: PatternAnalyzer = Field(description="Usage pattern analysis")
    structure_analyzer: StructureAnalyzer = Field(description="Structure analysis")
    insight_engine: InsightEngine = Field(description="AI insights")


class RefactoringKwargs(BaseModel):
    """Keyword arguments for Phase 5.2 refactoring managers."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    refactoring_engine: RefactoringEngine = Field(description="Refactoring suggestions")
    consolidation_detector: ConsolidationDetector = Field(
        description="Consolidation detection"
    )
    split_recommender: SplitRecommender = Field(description="File splitting")
    reorganization_planner: ReorganizationPlanner = Field(
        description="Structure reorganization"
    )


class ExecutionKwargs(BaseModel):
    """Keyword arguments for Phase 5.3-5.4 execution managers."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    refactoring_executor: RefactoringExecutor = Field(
        description="Safe refactoring execution"
    )
    approval_manager: ApprovalManager = Field(description="User approval workflow")
    rollback_manager: RollbackManager = Field(description="Rollback support")
    learning_engine: LearningEngine = Field(description="Learning from feedback")
    adaptation_config: AdaptationConfig = Field(description="Adaptation configuration")


class ContainerKwargs(BaseModel):
    """Combined keyword arguments for container instantiation."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")
