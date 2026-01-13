"""
Tests for container_factory.py - Factory methods for creating manager instances.

This module tests:
- create_foundation_managers() with valid/invalid project roots
- create_linking_managers_from_foundation()
- create_optimization_managers_from_deps()
- create_analysis_managers_from_deps()
- create_refactoring_managers_from_optimization()
- create_execution_managers_from_deps()
- create_all_managers() integration test
- Manager dependency injection correctness
"""

from pathlib import Path

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
from cortex.managers.container_factory import (
    create_all_managers,
    create_analysis_managers_from_deps,
    create_execution_managers_from_deps,
    create_foundation_managers,
    create_linking_managers_from_foundation,
    create_optimization_managers_from_deps,
    create_refactoring_managers_from_optimization,
)
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


class TestCreateFoundationManagers:
    """Tests for create_foundation_managers function."""

    def test_create_foundation_managers_success(self, temp_project_root: Path):
        """Test creating foundation managers with valid project root."""
        # Arrange
        project_root = temp_project_root

        # Act
        managers = create_foundation_managers(project_root)

        # Assert
        assert len(managers) == 7
        # Check each manager type
        assert isinstance(managers[0], FileSystemManager)
        assert isinstance(managers[1], MetadataIndex)
        assert isinstance(managers[2], TokenCounter)
        assert isinstance(managers[3], DependencyGraph)
        assert isinstance(managers[4], VersionManager)
        assert isinstance(managers[5], MigrationManager)
        assert isinstance(managers[6], FileWatcherManager)

    def test_create_foundation_managers_invalid_root(self, tmp_path: Path):
        """Test creating foundation managers with non-existent root."""
        # Arrange
        project_root = tmp_path / "nonexistent" / "path"

        # Act
        managers = create_foundation_managers(project_root)

        # Assert
        # Should still create managers even if path doesn't exist
        assert len(managers) == 7
        assert managers[0].project_root == project_root


class TestCreateLinkingManagersFromFoundation:
    """Tests for create_linking_managers_from_foundation function."""

    def test_create_linking_managers_from_foundation(self, temp_project_root: Path):
        """Test creating linking managers from foundation managers."""
        # Arrange
        foundation_managers = create_foundation_managers(temp_project_root)

        # Act
        linking_managers = create_linking_managers_from_foundation(foundation_managers)

        # Assert
        assert len(linking_managers) == 3
        assert isinstance(linking_managers[0], LinkParser)
        assert isinstance(linking_managers[1], TransclusionEngine)
        assert isinstance(linking_managers[2], LinkValidator)

        # Verify dependency injection
        assert linking_managers[1].fs == foundation_managers[0]
        assert linking_managers[2].fs == foundation_managers[0]


class TestCreateOptimizationManagersFromDeps:
    """Tests for create_optimization_managers_from_deps function."""

    def test_create_optimization_managers_from_deps(self, temp_project_root: Path):
        """Test creating optimization managers from dependencies."""
        # Arrange
        foundation_managers = create_foundation_managers(temp_project_root)

        # Act
        optimization_managers = create_optimization_managers_from_deps(
            temp_project_root, foundation_managers
        )

        # Assert
        assert len(optimization_managers) == 6
        assert isinstance(optimization_managers[0], OptimizationConfig)
        assert isinstance(optimization_managers[1], RelevanceScorer)
        assert isinstance(optimization_managers[2], ContextOptimizer)
        assert isinstance(optimization_managers[3], ProgressiveLoader)
        assert isinstance(optimization_managers[4], SummarizationEngine)
        assert isinstance(optimization_managers[5], RulesManager)

        # Verify dependency injection
        assert optimization_managers[1].dependency_graph == foundation_managers[3]
        assert optimization_managers[1].metadata_index == foundation_managers[1]
        assert optimization_managers[2].token_counter == foundation_managers[2]
        assert optimization_managers[2].relevance_scorer == optimization_managers[1]
        assert optimization_managers[3].file_system == foundation_managers[0]
        assert optimization_managers[4].token_counter == foundation_managers[2]


class TestCreateAnalysisManagersFromDeps:
    """Tests for create_analysis_managers_from_deps function."""

    def test_create_analysis_managers_from_deps(self, temp_project_root: Path):
        """Test creating analysis managers from dependencies."""
        # Arrange
        foundation_managers = create_foundation_managers(temp_project_root)

        # Act
        analysis_managers = create_analysis_managers_from_deps(
            temp_project_root, foundation_managers
        )

        # Assert
        assert len(analysis_managers) == 3
        assert isinstance(analysis_managers[0], PatternAnalyzer)
        assert isinstance(analysis_managers[1], StructureAnalyzer)
        assert isinstance(analysis_managers[2], InsightEngine)

        # Verify dependency injection
        assert analysis_managers[0].project_root == temp_project_root
        assert analysis_managers[1].project_root == temp_project_root
        assert analysis_managers[1].dependency_graph == foundation_managers[3]
        assert analysis_managers[1].file_system == foundation_managers[0]
        assert analysis_managers[1].metadata_index == foundation_managers[1]
        assert analysis_managers[2].pattern_analyzer == analysis_managers[0]
        assert analysis_managers[2].structure_analyzer == analysis_managers[1]


class TestCreateRefactoringManagersFromOptimization:
    """Tests for create_refactoring_managers_from_optimization function."""

    def test_create_refactoring_managers_from_optimization(
        self, temp_project_root: Path
    ):
        """Test creating refactoring managers from optimization dependencies."""
        # Arrange
        foundation_managers = create_foundation_managers(temp_project_root)
        optimization_managers = create_optimization_managers_from_deps(
            temp_project_root, foundation_managers
        )
        # Factory uses project_root / ".cortex" / "memory-bank"
        memory_bank_path = temp_project_root / ".cortex" / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)

        # Act
        refactoring_managers = create_refactoring_managers_from_optimization(
            temp_project_root, optimization_managers
        )

        # Assert
        assert len(refactoring_managers) == 4
        assert isinstance(refactoring_managers[0], RefactoringEngine)
        assert isinstance(refactoring_managers[1], ConsolidationDetector)
        assert isinstance(refactoring_managers[2], SplitRecommender)
        assert isinstance(refactoring_managers[3], ReorganizationPlanner)

        # Verify dependency injection
        assert refactoring_managers[0].memory_bank_path == memory_bank_path


class TestCreateExecutionManagersFromDeps:
    """Tests for create_execution_managers_from_deps function."""

    def test_create_execution_managers_from_deps(self, temp_project_root: Path):
        """Test creating execution managers from dependencies."""
        # Arrange
        foundation_managers = create_foundation_managers(temp_project_root)
        linking_managers = create_linking_managers_from_foundation(foundation_managers)
        optimization_managers = create_optimization_managers_from_deps(
            temp_project_root, foundation_managers
        )
        # Factory uses project_root / ".cortex" / "memory-bank"
        memory_bank_path = temp_project_root / ".cortex" / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)

        # Act
        execution_managers = create_execution_managers_from_deps(
            temp_project_root,
            foundation_managers,
            linking_managers,
            optimization_managers,
        )

        # Assert
        assert len(execution_managers) == 5
        assert isinstance(execution_managers[0], RefactoringExecutor)
        assert isinstance(execution_managers[1], ApprovalManager)
        assert isinstance(execution_managers[2], RollbackManager)
        assert isinstance(execution_managers[3], LearningEngine)
        assert isinstance(execution_managers[4], AdaptationConfig)

        # Verify dependency injection
        assert execution_managers[0].memory_bank_dir == memory_bank_path
        assert execution_managers[0].fs_manager == foundation_managers[0]
        assert execution_managers[0].version_manager == foundation_managers[4]
        assert execution_managers[0].link_validator == linking_managers[2]
        assert execution_managers[1].memory_bank_dir == memory_bank_path
        assert execution_managers[2].memory_bank_dir == memory_bank_path
        assert execution_managers[2].fs_manager == foundation_managers[0]
        assert execution_managers[2].version_manager == foundation_managers[4]


class TestCreateAllManagers:
    """Tests for create_all_managers integration function."""

    def test_create_all_managers_integration(self, temp_project_root: Path):
        """Test creating all managers in integration."""
        # Arrange
        # Factory uses project_root / ".cortex" / "memory-bank"
        memory_bank_path = temp_project_root / ".cortex" / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)

        # Act
        all_managers = create_all_managers(temp_project_root)

        # Assert
        assert len(all_managers) == 6
        foundation, linking, optimization, analysis, refactoring, execution = (
            all_managers
        )

        # Verify foundation managers
        assert len(foundation) == 7

        # Verify linking managers
        assert len(linking) == 3

        # Verify optimization managers
        assert len(optimization) == 6

        # Verify analysis managers
        assert len(analysis) == 3

        # Verify refactoring managers
        assert len(refactoring) == 4

        # Verify execution managers
        assert len(execution) == 5

    def test_manager_dependency_injection(self, temp_project_root: Path):
        """Test that manager dependencies are correctly injected."""
        # Arrange
        memory_bank_path = temp_project_root / ".cortex" / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)

        # Act
        all_managers = create_all_managers(temp_project_root)
        foundation, linking, optimization, analysis, _refactoring, execution = (
            all_managers
        )

        # Assert - Verify cross-group dependencies
        # Linking managers use foundation managers
        assert linking[1].fs == foundation[0]
        assert linking[2].fs == foundation[0]

        # Optimization managers use foundation managers
        assert optimization[1].dependency_graph == foundation[3]
        assert optimization[1].metadata_index == foundation[1]
        assert optimization[2].token_counter == foundation[2]

        # Analysis managers use foundation managers
        assert analysis[1].dependency_graph == foundation[3]
        assert analysis[1].file_system == foundation[0]
        assert analysis[1].metadata_index == foundation[1]

        # Execution managers use foundation, linking, and optimization
        assert execution[0].fs_manager == foundation[0]
        assert execution[0].version_manager == foundation[4]
        assert execution[0].link_validator == linking[2]
        assert execution[2].fs_manager == foundation[0]
        assert execution[2].version_manager == foundation[4]

    def test_error_handling_invalid_dependencies(self, temp_project_root: Path):
        """Test error handling when dependencies are invalid."""
        # Arrange
        # Factory uses project_root / ".cortex" / "memory-bank"
        memory_bank_path = temp_project_root / ".cortex" / "memory-bank"
        memory_bank_path.mkdir(parents=True, exist_ok=True)

        # Act & Assert - Should not raise errors even with non-existent paths
        # The managers should still be created, they just won't have valid paths
        all_managers = create_all_managers(temp_project_root)
        assert all_managers is not None
        assert len(all_managers) == 6
