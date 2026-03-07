"""Factory methods for creating Phase 5.1 analysis manager instances."""

from pathlib import Path

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex

from .container_config import AnalysisManagers, FoundationManagers


def create_analysis_managers_from_deps(
    project_root: Path,
    foundation_managers: FoundationManagers,
) -> AnalysisManagers:
    """Create analysis managers from foundation dependencies."""
    dependency_graph = foundation_managers[3]
    file_system = foundation_managers[0]
    metadata_index = foundation_managers[1]
    return create_analysis_managers(
        project_root, dependency_graph, file_system, metadata_index
    )


def create_analysis_managers(
    project_root: Path,
    dependency_graph: DependencyGraph,
    file_system: FileSystemManager,
    metadata_index: MetadataIndex,
) -> tuple[PatternAnalyzer, StructureAnalyzer, InsightEngine]:
    """Create Phase 5.1 pattern analysis managers."""
    pattern_analyzer = PatternAnalyzer(project_root)
    structure_analyzer = StructureAnalyzer(
        project_root=project_root,
        dependency_graph=dependency_graph,
        file_system=file_system,
        metadata_index=metadata_index,
    )
    insight_engine = InsightEngine(
        pattern_analyzer=pattern_analyzer, structure_analyzer=structure_analyzer
    )

    return pattern_analyzer, structure_analyzer, insight_engine
