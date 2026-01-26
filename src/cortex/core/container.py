#!/usr/bin/env python3
"""Dependency injection container for MCP Memory Bank managers.

This module provides a centralized container for all manager instances,
enabling better testability and dependency management.
"""

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

# Runtime imports - only protocols and core layer dependencies
from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.container_models import (
    AnalysisKwargs,
    ContainerKwargs,
    ExecutionKwargs,
    FoundationKwargs,
    LinkingKwargs,
    OptimizationKwargs,
    RefactoringKwargs,
    UnpackedManagers,
)
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
from cortex.managers.container_factory import (
    AnalysisManagers,
    ExecutionManagers,
    FoundationManagers,
    LinkingManagers,
    OptimizationManagers,
    RefactoringManagers,
)
from cortex.managers.types import ManagersDict
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


class ManagerContainer(BaseModel):
    """Container for all manager instances.

    This container holds all initialized managers for a project,
    organized by implementation phase. It provides type-safe access
    to manager instances and supports dependency injection patterns.

    Attributes:
        Phase 1 - Foundation:
            file_system: File I/O operations
            metadata_index: Metadata tracking
            token_counter: Token counting
            dependency_graph: Dependency management
            version_manager: Version control
            migration_manager: Format migration
            file_watcher: External change detection

        Phase 2 - DRY Linking:
            link_parser: Link parsing
            transclusion_engine: Content transclusion
            link_validator: Link validation

        Phase 4 - Optimization:
            optimization_config: Configuration management
            relevance_scorer: Relevance scoring
            context_optimizer: Context optimization
            progressive_loader: Progressive loading
            summarization_engine: Content summarization
            rules_manager: Rules indexing

        Phase 5.1 - Pattern Analysis:
            pattern_analyzer: Usage pattern analysis
            structure_analyzer: Structure analysis
            insight_engine: AI insights

        Phase 5.2 - Refactoring Suggestions:
            refactoring_engine: Refactoring suggestions
            consolidation_detector: Consolidation detection
            split_recommender: File splitting
            reorganization_planner: Structure reorganization

        Phase 5.3-5.4 - Execution & Learning:
            refactoring_executor: Safe refactoring execution
            approval_manager: User approval workflow
            rollback_manager: Rollback support
            learning_engine: Learning from feedback
            adaptation_config: Adaptation configuration
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        validate_assignment=False,
    )

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

    @classmethod
    async def create(cls, project_root: Path) -> Self:
        """Factory method to create fully initialized container.

        This method initializes all managers in the correct dependency order,
        ensuring that each manager has access to its required dependencies.

        Args:
            project_root: Project root directory

        Returns:
            Fully initialized ManagerContainer

        Raises:
            MemoryBankError: If initialization fails
        """
        # Import factory at runtime to avoid circular dependency
        from cortex.managers.container_factory import create_all_managers

        # Create all managers grouped by phase
        (
            foundation_managers,
            linking_managers,
            optimization_managers,
            analysis_managers,
            refactoring_managers,
            execution_managers,
        ) = create_all_managers(project_root)

        # Create and return container
        container = cls._create_container_instance(
            foundation_managers=foundation_managers,
            linking_managers=linking_managers,
            optimization_managers=optimization_managers,
            analysis_managers=analysis_managers,
            refactoring_managers=refactoring_managers,
            execution_managers=execution_managers,
        )

        # Post-initialization setup
        await container._post_init_setup(project_root)

        return container

    async def _post_init_setup(self, project_root: Path):
        """Perform post-initialization setup tasks.

        Args:
            project_root: Project root directory
        """
        # Load metadata index if it exists
        index_path = project_root / ".cortex" / "index.json"
        if index_path.exists():
            try:
                _ = await self.metadata_index.load()
            except Exception as e:
                # If load fails, metadata_index will auto-rebuild
                from cortex.core.logging_config import logger

                logger.info(f"Metadata index load failed, will rebuild: {e}")

        # Clean up stale locks
        await self.file_system.cleanup_locks()

        # Initialize rules manager if enabled
        if self.optimization_config.is_rules_enabled():
            try:
                _ = await self.rules_manager.index_rules()
            except Exception as e:
                # Don't fail if rules initialization fails
                from cortex.core.logging_config import logger

                logger.warning(f"Rules initialization failed: {e}")

    @classmethod
    def _create_container_instance(
        cls: type[Self],
        foundation_managers: FoundationManagers,
        linking_managers: LinkingManagers,
        optimization_managers: OptimizationManagers,
        analysis_managers: AnalysisManagers,
        refactoring_managers: RefactoringManagers,
        execution_managers: ExecutionManagers,
    ) -> Self:
        """Create container instance with protocol casts.

        Args:
            foundation_managers: Phase 1 managers
            linking_managers: Phase 2 managers
            optimization_managers: Phase 4 managers
            analysis_managers: Phase 5.1 managers
            refactoring_managers: Phase 5.2 managers
            execution_managers: Phase 5.3-5.4 managers

        Returns:
            Fully initialized container
        """
        unpacked = cls._unpack_all_managers(
            foundation_managers,
            linking_managers,
            optimization_managers,
            analysis_managers,
            refactoring_managers,
            execution_managers,
        )
        return cls._instantiate_container(unpacked)

    @classmethod
    def _unpack_all_managers(
        cls: type[Self],
        foundation_managers: FoundationManagers,
        linking_managers: LinkingManagers,
        optimization_managers: OptimizationManagers,
        analysis_managers: AnalysisManagers,
        refactoring_managers: RefactoringManagers,
        execution_managers: ExecutionManagers,
    ) -> UnpackedManagers:
        """Unpack all manager tuples into a model.

        Args:
            foundation_managers: Phase 1 managers
            linking_managers: Phase 2 managers
            optimization_managers: Phase 4 managers
            analysis_managers: Phase 5.1 managers
            refactoring_managers: Phase 5.2 managers
            execution_managers: Phase 5.3-5.4 managers

        Returns:
            UnpackedManagers model with all managers
        """
        foundation_kwargs = cls._unpack_foundation_managers(foundation_managers)
        linking_kwargs = cls._unpack_linking_managers(linking_managers)
        optimization_kwargs = cls._unpack_optimization_managers(optimization_managers)
        analysis_kwargs = cls._unpack_analysis_managers(analysis_managers)
        refactoring_kwargs = cls._unpack_refactoring_managers(refactoring_managers)
        execution_kwargs = cls._unpack_execution_managers(execution_managers)

        # Combine all kwargs into UnpackedManagers
        return UnpackedManagers.model_construct(
            **foundation_kwargs.model_dump(),
            **linking_kwargs.model_dump(),
            **optimization_kwargs.model_dump(),
            **analysis_kwargs.model_dump(),
            **refactoring_kwargs.model_dump(),
            **execution_kwargs.model_dump(),
        )

    @classmethod
    def _unpack_foundation_managers(
        cls: type[Self], foundation_managers: FoundationManagers
    ) -> FoundationKwargs:
        """Unpack Phase 1 foundation managers."""
        (
            file_system,
            metadata_index,
            token_counter,
            dependency_graph,
            version_manager,
            migration_manager,
            file_watcher,
        ) = foundation_managers
        return FoundationKwargs(
            file_system=file_system,
            metadata_index=metadata_index,
            token_counter=token_counter,
            dependency_graph=dependency_graph,
            version_manager=version_manager,
            migration_manager=migration_manager,
            file_watcher=file_watcher,
        )

    @classmethod
    def _unpack_linking_managers(
        cls: type[Self], linking_managers: LinkingManagers
    ) -> LinkingKwargs:
        """Unpack Phase 2 linking managers."""
        link_parser, transclusion_engine, link_validator = linking_managers
        return LinkingKwargs(
            link_parser=link_parser,
            transclusion_engine=transclusion_engine,
            link_validator=link_validator,
        )

    @classmethod
    def _unpack_optimization_managers(
        cls: type[Self],
        optimization_managers: OptimizationManagers,
    ) -> OptimizationKwargs:
        """Unpack Phase 4 optimization managers."""
        (
            optimization_config,
            relevance_scorer,
            context_optimizer,
            progressive_loader,
            summarization_engine,
            rules_manager,
        ) = optimization_managers
        return OptimizationKwargs(
            optimization_config=optimization_config,
            relevance_scorer=relevance_scorer,
            context_optimizer=context_optimizer,
            progressive_loader=progressive_loader,
            summarization_engine=summarization_engine,
            rules_manager=rules_manager,
        )

    @classmethod
    def _unpack_analysis_managers(
        cls: type[Self], analysis_managers: AnalysisManagers
    ) -> AnalysisKwargs:
        """Unpack Phase 5.1 analysis managers."""
        pattern_analyzer, structure_analyzer, insight_engine = analysis_managers
        return AnalysisKwargs(
            pattern_analyzer=pattern_analyzer,
            structure_analyzer=structure_analyzer,
            insight_engine=insight_engine,
        )

    @classmethod
    def _unpack_refactoring_managers(
        cls: type[Self], refactoring_managers: RefactoringManagers
    ) -> RefactoringKwargs:
        """Unpack Phase 5.2 refactoring managers."""
        (
            refactoring_engine,
            consolidation_detector,
            split_recommender,
            reorganization_planner,
        ) = refactoring_managers
        return RefactoringKwargs(
            refactoring_engine=refactoring_engine,
            consolidation_detector=consolidation_detector,
            split_recommender=split_recommender,
            reorganization_planner=reorganization_planner,
        )

    @classmethod
    def _unpack_execution_managers(
        cls: type[Self], execution_managers: ExecutionManagers
    ) -> ExecutionKwargs:
        """Unpack Phase 5.3-5.4 execution managers."""
        (
            refactoring_executor,
            approval_manager,
            rollback_manager,
            learning_engine,
            adaptation_config,
        ) = execution_managers
        return ExecutionKwargs(
            refactoring_executor=refactoring_executor,
            approval_manager=approval_manager,
            rollback_manager=rollback_manager,
            learning_engine=learning_engine,
            adaptation_config=adaptation_config,
        )

    @classmethod
    def _instantiate_container(cls: type[Self], unpacked: UnpackedManagers) -> Self:
        """Instantiate container from unpacked managers.

        Args:
            unpacked: UnpackedManagers model with all managers

        Returns:
            Fully initialized container
        """
        kwargs_model = cls._build_container_kwargs(unpacked)
        return cls.model_validate(kwargs_model, from_attributes=True)

    @classmethod
    def _build_container_kwargs(
        cls: type[Self], unpacked: UnpackedManagers
    ) -> ContainerKwargs:
        """Build keyword arguments for container instantiation.

        Args:
            unpacked: UnpackedManagers model with all managers

        Returns:
            Dictionary of keyword arguments
        """
        foundation_kwargs = cls._build_foundation_kwargs(unpacked)
        linking_kwargs = cls._build_linking_kwargs(unpacked)
        optimization_kwargs = cls._build_optimization_kwargs(unpacked)
        analysis_kwargs = cls._build_analysis_kwargs(unpacked)
        refactoring_kwargs = cls._build_refactoring_kwargs(unpacked)
        execution_kwargs = cls._build_execution_kwargs(unpacked)

        # Combine all kwargs into a single model
        # Use model_dump() which returns a plain dict internally,
        # but we validate it into ContainerKwargs immediately.
        combined_data = {
            **foundation_kwargs.model_dump(),
            **linking_kwargs.model_dump(),
            **optimization_kwargs.model_dump(),
            **analysis_kwargs.model_dump(),
            **refactoring_kwargs.model_dump(),
            **execution_kwargs.model_dump(),
        }

        return ContainerKwargs.model_validate(combined_data)

    @classmethod
    def _build_foundation_kwargs(
        cls: type[Self], unpacked: UnpackedManagers
    ) -> FoundationKwargs:
        """Build Phase 1 foundation keyword arguments."""
        return FoundationKwargs(
            file_system=unpacked.file_system,
            metadata_index=unpacked.metadata_index,
            token_counter=unpacked.token_counter,
            dependency_graph=unpacked.dependency_graph,
            version_manager=unpacked.version_manager,
            migration_manager=unpacked.migration_manager,
            file_watcher=unpacked.file_watcher,
        )

    @classmethod
    def _build_linking_kwargs(
        cls: type[Self], unpacked: UnpackedManagers
    ) -> LinkingKwargs:
        """Build Phase 2 linking keyword arguments."""
        return LinkingKwargs(
            link_parser=unpacked.link_parser,
            transclusion_engine=unpacked.transclusion_engine,
            link_validator=unpacked.link_validator,
        )

    @classmethod
    def _build_optimization_kwargs(
        cls: type[Self], unpacked: UnpackedManagers
    ) -> OptimizationKwargs:
        """Build Phase 4 optimization keyword arguments."""
        return OptimizationKwargs(
            optimization_config=unpacked.optimization_config,
            relevance_scorer=unpacked.relevance_scorer,
            context_optimizer=unpacked.context_optimizer,
            progressive_loader=unpacked.progressive_loader,
            summarization_engine=unpacked.summarization_engine,
            rules_manager=unpacked.rules_manager,
        )

    @classmethod
    def _build_analysis_kwargs(
        cls: type[Self], unpacked: UnpackedManagers
    ) -> AnalysisKwargs:
        """Build Phase 5.1 analysis keyword arguments."""
        return AnalysisKwargs(
            pattern_analyzer=unpacked.pattern_analyzer,
            structure_analyzer=unpacked.structure_analyzer,
            insight_engine=unpacked.insight_engine,
        )

    @classmethod
    def _build_refactoring_kwargs(
        cls: type[Self], unpacked: UnpackedManagers
    ) -> RefactoringKwargs:
        """Build Phase 5.2 refactoring keyword arguments."""
        return RefactoringKwargs(
            refactoring_engine=unpacked.refactoring_engine,
            consolidation_detector=unpacked.consolidation_detector,
            split_recommender=unpacked.split_recommender,
            reorganization_planner=unpacked.reorganization_planner,
        )

    @classmethod
    def _build_execution_kwargs(
        cls: type[Self], unpacked: UnpackedManagers
    ) -> ExecutionKwargs:
        """Build Phase 5.3-5.4 execution keyword arguments."""
        return ExecutionKwargs(
            refactoring_executor=unpacked.refactoring_executor,
            approval_manager=unpacked.approval_manager,
            rollback_manager=unpacked.rollback_manager,
            learning_engine=unpacked.learning_engine,
            adaptation_config=unpacked.adaptation_config,
        )

    def to_legacy_dict(self) -> ManagersDict:
        """Convert container to ManagersDict model.

        This method provides backward compatibility with code that expects
        a ManagersDict model instead of a container instance.

        Returns:
            ManagersDict model with manager instances
        """
        return ManagersDict(
            # Phase 1
            fs=self.file_system,
            index=self.metadata_index,
            tokens=self.token_counter,
            graph=self.dependency_graph,
            versions=self.version_manager,
            migration=self.migration_manager,
            watcher=self.file_watcher,
            # Phase 2
            link_parser=self.link_parser,
            transclusion=self.transclusion_engine,
            link_validator=self.link_validator,
            # Phase 4
            optimization_config=self.optimization_config,
            relevance_scorer=self.relevance_scorer,
            context_optimizer=self.context_optimizer,
            progressive_loader=self.progressive_loader,
            summarization_engine=self.summarization_engine,
            rules_manager=self.rules_manager,
            # Phase 5.1
            pattern_analyzer=self.pattern_analyzer,
            structure_analyzer=self.structure_analyzer,
            insight_engine=self.insight_engine,
            # Phase 5.2
            refactoring_engine=self.refactoring_engine,
            consolidation_detector=self.consolidation_detector,
            split_recommender=self.split_recommender,
            reorganization_planner=self.reorganization_planner,
            # Phase 5.3-5.4
            refactoring_executor=self.refactoring_executor,
            approval_manager=self.approval_manager,
            rollback_manager=self.rollback_manager,
            learning_engine=self.learning_engine,
            adaptation_config=self.adaptation_config,
        )
