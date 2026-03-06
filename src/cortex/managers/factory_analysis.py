#!/usr/bin/env python3
"""Analysis-phase manager factory helpers (Phase 5.1)."""

from pathlib import Path

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import CoreManagersDict
from cortex.optimization.config import OptimizationConfig


async def _create_pattern_analyzer(
    project_root: Path, managers: ManagersBuilder
) -> PatternAnalyzer:
    """Create PatternAnalyzer instance."""
    from cortex.managers.utils import get_manager

    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    if not optimization_config.is_self_evolution_enabled():
        return PatternAnalyzer(
            project_root=project_root,
            pattern_window_days=optimization_config.get_pattern_window_days(),
            min_access_count=optimization_config.get_min_access_count(),
            track_usage_patterns=False,
            track_task_patterns=False,
        )

    return PatternAnalyzer(
        project_root=project_root,
        pattern_window_days=optimization_config.get_pattern_window_days(),
        min_access_count=optimization_config.get_min_access_count(),
        track_usage_patterns=optimization_config.is_usage_tracking_enabled(),
        track_task_patterns=optimization_config.is_task_tracking_enabled(),
    )


async def _create_structure_analyzer(
    project_root: Path, core_managers: CoreManagersDict
) -> StructureAnalyzer:
    """Create StructureAnalyzer instance."""
    dep_graph = core_managers.graph
    fs_manager = core_managers.fs
    metadata_index = core_managers.index

    return StructureAnalyzer(
        project_root=project_root,
        dependency_graph=dep_graph,
        file_system=fs_manager,
        metadata_index=metadata_index,
    )


async def _create_insight_engine(managers: ManagersBuilder) -> InsightEngine:
    """Create InsightEngine instance."""
    from cortex.managers.utils import get_manager

    pattern_analyzer = await get_manager(managers, "pattern_analyzer", PatternAnalyzer)
    structure_analyzer = await get_manager(
        managers, "structure_analyzer", StructureAnalyzer
    )
    optimization_config = await get_manager(
        managers, "optimization_config", OptimizationConfig
    )

    if not optimization_config.is_self_evolution_enabled():
        return InsightEngine(
            pattern_analyzer=pattern_analyzer,
            structure_analyzer=structure_analyzer,
            min_impact_score=optimization_config.get_min_impact_score(),
            categories=optimization_config.get_insight_categories(),
            auto_generate=False,
        )

    return InsightEngine(
        pattern_analyzer=pattern_analyzer,
        structure_analyzer=structure_analyzer,
        min_impact_score=optimization_config.get_min_impact_score(),
        categories=optimization_config.get_insight_categories(),
        auto_generate=optimization_config.is_auto_insights_enabled(),
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
        lambda: _create_pattern_analyzer(project_root, managers),
        name="pattern_analyzer",
    )
    managers["structure_analyzer"] = LazyManager(
        lambda: _create_structure_analyzer(project_root, core_managers),
        name="structure_analyzer",
    )
    managers["insight_engine"] = LazyManager(
        lambda: _create_insight_engine(managers), name="insight_engine"
    )
