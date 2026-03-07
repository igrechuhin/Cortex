"""Factory methods for creating Phase 5.2 refactoring manager instances."""

from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.optimization.config import OptimizationConfig
from cortex.refactoring.consolidation_detector import ConsolidationDetector
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.refactoring.reorganization_planner import ReorganizationPlanner
from cortex.refactoring.split_recommender import SplitRecommender

from .container_config import OptimizationManagers, RefactoringManagers


def create_refactoring_managers_from_optimization(
    project_root: Path,
    optimization_managers: OptimizationManagers,
) -> RefactoringManagers:
    """Create refactoring managers from optimization dependencies."""
    memory_bank_path = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    optimization_config = optimization_managers[0]
    return create_refactoring_managers(memory_bank_path, optimization_config)


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
