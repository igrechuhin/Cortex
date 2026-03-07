"""Type aliases for manager groups produced by the container factory."""

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
from cortex.linking.parser import LinkParser
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.linking.validator import LinkValidator
from cortex.optimization.config import OptimizationConfig
from cortex.optimization.context_optimizer import ContextOptimizer
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
