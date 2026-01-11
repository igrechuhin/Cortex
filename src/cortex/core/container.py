#!/usr/bin/env python3
"""Dependency injection container for MCP Memory Bank managers.

This module provides a centralized container for all manager instances,
enabling better testability and dependency management.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

# Runtime imports - only protocols and core layer dependencies
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.migration import MigrationManager
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

# Type-checking only imports - not loaded at runtime
if TYPE_CHECKING:
    from cortex.analysis.insight_engine import InsightEngine
    from cortex.managers.container_factory import (
        AnalysisManagers,
        ExecutionManagers,
        FoundationManagers,
        LinkingManagers,
        OptimizationManagers,
        RefactoringManagers,
    )
    from cortex.optimization.optimization_config import OptimizationConfig
    from cortex.refactoring.adaptation_config import AdaptationConfig
    from cortex.refactoring.refactoring_executor import RefactoringExecutor


@dataclass
class ManagerContainer:
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

    # Phase 1: Foundation
    file_system: FileSystemProtocol
    metadata_index: MetadataIndexProtocol
    token_counter: TokenCounterProtocol
    dependency_graph: DependencyGraphProtocol
    version_manager: VersionManagerProtocol
    migration_manager: MigrationManager
    file_watcher: FileWatcherManager

    # Phase 2: DRY Linking
    link_parser: LinkParserProtocol
    transclusion_engine: TransclusionEngineProtocol
    link_validator: LinkValidatorProtocol

    # Phase 4: Optimization - use protocols
    optimization_config: "OptimizationConfig"
    relevance_scorer: RelevanceScorerProtocol
    context_optimizer: ContextOptimizerProtocol
    progressive_loader: ProgressiveLoaderProtocol
    summarization_engine: SummarizationEngineProtocol
    rules_manager: RulesManagerProtocol

    # Phase 5.1: Pattern Analysis - use protocols
    pattern_analyzer: PatternAnalyzerProtocol
    structure_analyzer: StructureAnalyzerProtocol
    insight_engine: "InsightEngine"

    # Phase 5.2: Refactoring Suggestions - use protocols
    refactoring_engine: RefactoringEngineProtocol
    consolidation_detector: ConsolidationDetectorProtocol
    split_recommender: SplitRecommenderProtocol
    reorganization_planner: ReorganizationPlannerProtocol

    # Phase 5.3-5.4: Execution & Learning - use protocols
    refactoring_executor: "RefactoringExecutor"
    approval_manager: ApprovalManagerProtocol
    rollback_manager: RollbackManagerProtocol
    learning_engine: LearningEngineProtocol
    adaptation_config: "AdaptationConfig"

    @classmethod
    async def create(cls, project_root: Path) -> "ManagerContainer":
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
        cls: type["ManagerContainer"],
        foundation_managers: "FoundationManagers",
        linking_managers: "LinkingManagers",
        optimization_managers: "OptimizationManagers",
        analysis_managers: "AnalysisManagers",
        refactoring_managers: "RefactoringManagers",
        execution_managers: "ExecutionManagers",
    ) -> "ManagerContainer":
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
        cls: type["ManagerContainer"],
        foundation_managers: "FoundationManagers",
        linking_managers: "LinkingManagers",
        optimization_managers: "OptimizationManagers",
        analysis_managers: "AnalysisManagers",
        refactoring_managers: "RefactoringManagers",
        execution_managers: "ExecutionManagers",
    ) -> dict[str, object]:
        """Unpack all manager tuples into a dictionary.

        Args:
            foundation_managers: Phase 1 managers
            linking_managers: Phase 2 managers
            optimization_managers: Phase 4 managers
            analysis_managers: Phase 5.1 managers
            refactoring_managers: Phase 5.2 managers
            execution_managers: Phase 5.3-5.4 managers

        Returns:
            Dictionary of unpacked managers
        """
        unpacked: dict[str, object] = {}
        unpacked.update(cls._unpack_foundation_managers(foundation_managers))
        unpacked.update(cls._unpack_linking_managers(linking_managers))
        unpacked.update(cls._unpack_optimization_managers(optimization_managers))
        unpacked.update(cls._unpack_analysis_managers(analysis_managers))
        unpacked.update(cls._unpack_refactoring_managers(refactoring_managers))
        unpacked.update(cls._unpack_execution_managers(execution_managers))
        return unpacked

    @classmethod
    def _unpack_foundation_managers(
        cls: type["ManagerContainer"], foundation_managers: "FoundationManagers"
    ) -> dict[str, object]:
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
        return {
            "file_system": file_system,
            "metadata_index": metadata_index,
            "token_counter": token_counter,
            "dependency_graph": dependency_graph,
            "version_manager": version_manager,
            "migration_manager": migration_manager,
            "file_watcher": file_watcher,
        }

    @classmethod
    def _unpack_linking_managers(
        cls: type["ManagerContainer"], linking_managers: "LinkingManagers"
    ) -> dict[str, object]:
        """Unpack Phase 2 linking managers."""
        link_parser, transclusion_engine, link_validator = linking_managers
        return {
            "link_parser": link_parser,
            "transclusion_engine": transclusion_engine,
            "link_validator": link_validator,
        }

    @classmethod
    def _unpack_optimization_managers(
        cls: type["ManagerContainer"],
        optimization_managers: "OptimizationManagers",
    ) -> dict[str, object]:
        """Unpack Phase 4 optimization managers."""
        (
            optimization_config,
            relevance_scorer,
            context_optimizer,
            progressive_loader,
            summarization_engine,
            rules_manager,
        ) = optimization_managers
        return {
            "optimization_config": optimization_config,
            "relevance_scorer": relevance_scorer,
            "context_optimizer": context_optimizer,
            "progressive_loader": progressive_loader,
            "summarization_engine": summarization_engine,
            "rules_manager": rules_manager,
        }

    @classmethod
    def _unpack_analysis_managers(
        cls: type["ManagerContainer"], analysis_managers: "AnalysisManagers"
    ) -> dict[str, object]:
        """Unpack Phase 5.1 analysis managers."""
        pattern_analyzer, structure_analyzer, insight_engine = analysis_managers
        return {
            "pattern_analyzer": pattern_analyzer,
            "structure_analyzer": structure_analyzer,
            "insight_engine": insight_engine,
        }

    @classmethod
    def _unpack_refactoring_managers(
        cls: type["ManagerContainer"], refactoring_managers: "RefactoringManagers"
    ) -> dict[str, object]:
        """Unpack Phase 5.2 refactoring managers."""
        (
            refactoring_engine,
            consolidation_detector,
            split_recommender,
            reorganization_planner,
        ) = refactoring_managers
        return {
            "refactoring_engine": refactoring_engine,
            "consolidation_detector": consolidation_detector,
            "split_recommender": split_recommender,
            "reorganization_planner": reorganization_planner,
        }

    @classmethod
    def _unpack_execution_managers(
        cls: type["ManagerContainer"], execution_managers: "ExecutionManagers"
    ) -> dict[str, object]:
        """Unpack Phase 5.3-5.4 execution managers."""
        (
            refactoring_executor,
            approval_manager,
            rollback_manager,
            learning_engine,
            adaptation_config,
        ) = execution_managers
        return {
            "refactoring_executor": refactoring_executor,
            "approval_manager": approval_manager,
            "rollback_manager": rollback_manager,
            "learning_engine": learning_engine,
            "adaptation_config": adaptation_config,
        }

    @classmethod
    def _instantiate_container(
        cls: type["ManagerContainer"], unpacked: dict[str, object]
    ) -> "ManagerContainer":
        """Instantiate container from unpacked managers.

        Args:
            unpacked: Dictionary of unpacked managers

        Returns:
            Fully initialized container
        """
        kwargs = cls._build_container_kwargs(unpacked)
        # Values in kwargs are already cast to correct types in _build_*_kwargs methods
        # Pyright can't verify this statically, but runtime types are correct
        return cls(**kwargs)  # pyright: ignore[reportArgumentType]

    @classmethod
    def _build_container_kwargs(
        cls: type["ManagerContainer"], unpacked: dict[str, object]
    ) -> dict[str, object]:
        """Build keyword arguments for container instantiation.

        Args:
            unpacked: Dictionary of unpacked managers

        Returns:
            Dictionary of keyword arguments
        """
        kwargs: dict[str, object] = {}
        kwargs.update(cls._build_foundation_kwargs(unpacked))
        kwargs.update(cls._build_linking_kwargs(unpacked))
        kwargs.update(cls._build_optimization_kwargs(unpacked))
        kwargs.update(cls._build_analysis_kwargs(unpacked))
        kwargs.update(cls._build_refactoring_kwargs(unpacked))
        kwargs.update(cls._build_execution_kwargs(unpacked))
        return kwargs

    @classmethod
    def _build_foundation_kwargs(
        cls: type["ManagerContainer"], unpacked: dict[str, object]
    ) -> dict[str, object]:
        """Build Phase 1 foundation keyword arguments."""
        return {
            "file_system": cast(FileSystemProtocol, unpacked["file_system"]),
            "metadata_index": cast(MetadataIndexProtocol, unpacked["metadata_index"]),
            "token_counter": cast(TokenCounterProtocol, unpacked["token_counter"]),
            "dependency_graph": cast(
                DependencyGraphProtocol, unpacked["dependency_graph"]
            ),
            "version_manager": cast(
                VersionManagerProtocol, unpacked["version_manager"]
            ),
            "migration_manager": cast(MigrationManager, unpacked["migration_manager"]),
            "file_watcher": cast(FileWatcherManager, unpacked["file_watcher"]),
        }

    @classmethod
    def _build_linking_kwargs(
        cls: type["ManagerContainer"], unpacked: dict[str, object]
    ) -> dict[str, object]:
        """Build Phase 2 linking keyword arguments."""
        return {
            "link_parser": cast(LinkParserProtocol, unpacked["link_parser"]),
            "transclusion_engine": cast(
                TransclusionEngineProtocol, unpacked["transclusion_engine"]
            ),
            "link_validator": cast(LinkValidatorProtocol, unpacked["link_validator"]),
        }

    @classmethod
    def _build_optimization_kwargs(
        cls: type["ManagerContainer"], unpacked: dict[str, object]
    ) -> dict[str, object]:
        """Build Phase 4 optimization keyword arguments."""
        return {
            "optimization_config": unpacked["optimization_config"],
            "relevance_scorer": cast(
                RelevanceScorerProtocol, unpacked["relevance_scorer"]
            ),
            "context_optimizer": cast(
                ContextOptimizerProtocol, unpacked["context_optimizer"]
            ),
            "progressive_loader": cast(
                ProgressiveLoaderProtocol, unpacked["progressive_loader"]
            ),
            "summarization_engine": cast(
                SummarizationEngineProtocol, unpacked["summarization_engine"]
            ),
            "rules_manager": cast(RulesManagerProtocol, unpacked["rules_manager"]),
        }

    @classmethod
    def _build_analysis_kwargs(
        cls: type["ManagerContainer"], unpacked: dict[str, object]
    ) -> dict[str, object]:
        """Build Phase 5.1 analysis keyword arguments."""
        return {
            "pattern_analyzer": cast(
                PatternAnalyzerProtocol, unpacked["pattern_analyzer"]
            ),
            "structure_analyzer": cast(
                StructureAnalyzerProtocol, unpacked["structure_analyzer"]
            ),
            "insight_engine": unpacked["insight_engine"],
        }

    @classmethod
    def _build_refactoring_kwargs(
        cls: type["ManagerContainer"], unpacked: dict[str, object]
    ) -> dict[str, object]:
        """Build Phase 5.2 refactoring keyword arguments."""
        return {
            "refactoring_engine": cast(
                RefactoringEngineProtocol, unpacked["refactoring_engine"]
            ),
            "consolidation_detector": cast(
                ConsolidationDetectorProtocol, unpacked["consolidation_detector"]
            ),
            "split_recommender": cast(
                SplitRecommenderProtocol, unpacked["split_recommender"]
            ),
            "reorganization_planner": cast(
                ReorganizationPlannerProtocol, unpacked["reorganization_planner"]
            ),
        }

    @classmethod
    def _build_execution_kwargs(
        cls: type["ManagerContainer"], unpacked: dict[str, object]
    ) -> dict[str, object]:
        """Build Phase 5.3-5.4 execution keyword arguments."""
        return {
            "refactoring_executor": unpacked["refactoring_executor"],
            "approval_manager": cast(
                ApprovalManagerProtocol, unpacked["approval_manager"]
            ),
            "rollback_manager": cast(
                RollbackManagerProtocol, unpacked["rollback_manager"]
            ),
            "learning_engine": cast(
                LearningEngineProtocol, unpacked["learning_engine"]
            ),
            "adaptation_config": unpacked["adaptation_config"],
        }

    def to_legacy_dict(self) -> dict[str, object]:
        """Convert container to legacy dictionary format.

        This method provides backward compatibility with code that expects
        a dictionary of managers instead of a container instance.

        Returns:
            Dictionary mapping manager names to instances
        """
        return {
            # Phase 1
            "fs": self.file_system,
            "index": self.metadata_index,
            "tokens": self.token_counter,
            "graph": self.dependency_graph,
            "versions": self.version_manager,
            "migration": self.migration_manager,
            "watcher": self.file_watcher,
            # Phase 2
            "link_parser": self.link_parser,
            "transclusion": self.transclusion_engine,
            "link_validator": self.link_validator,
            # Phase 4
            "optimization_config": self.optimization_config,
            "relevance_scorer": self.relevance_scorer,
            "context_optimizer": self.context_optimizer,
            "progressive_loader": self.progressive_loader,
            "summarization_engine": self.summarization_engine,
            "rules_manager": self.rules_manager,
            # Phase 5.1
            "pattern_analyzer": self.pattern_analyzer,
            "structure_analyzer": self.structure_analyzer,
            "insight_engine": self.insight_engine,
            # Phase 5.2
            "refactoring_engine": self.refactoring_engine,
            "consolidation_detector": self.consolidation_detector,
            "split_recommender": self.split_recommender,
            "reorganization_planner": self.reorganization_planner,
            # Phase 5.3-5.4
            "refactoring_executor": self.refactoring_executor,
            "approval_manager": self.approval_manager,
            "rollback_manager": self.rollback_manager,
            "learning_engine": self.learning_engine,
            "adaptation_config": self.adaptation_config,
        }
