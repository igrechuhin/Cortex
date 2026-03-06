#!/usr/bin/env python3
"""Refactoring-phase manager factory helpers (Phase 5.2)."""

from pathlib import Path
from typing import cast

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.lazy_manager import LazyManager
from cortex.refactoring.consolidation_detector import ConsolidationDetector
from cortex.refactoring.refactoring_engine import RefactoringEngine
from cortex.refactoring.reorganization_planner import ReorganizationPlanner
from cortex.refactoring.split_recommender import SplitRecommender


async def _create_refactoring_engine(
    project_root: Path, managers: ManagersBuilder
) -> RefactoringEngine:
    """Create RefactoringEngine instance."""
    from cortex.managers.utils import get_manager
    from cortex.optimization.config import OptimizationConfig

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
