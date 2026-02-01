"""
Structure Analyzer - Analyze file organization and dependency structure.

This module analyzes the Memory Bank structure to identify organizational issues,
complexity metrics, and anti-patterns.
"""

from pathlib import Path

from cortex.analysis import structure_analysis, structure_detection, structure_metrics
from cortex.analysis.models import (
    AntiPatternInfo,
    ComplexityAnalysisResult,
    ComplexityAssessment,
    ComplexityHotspot,
    ComplexityMetrics,
    DependencyChainResult,
)
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.exceptions import MemoryBankError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import FileOrganizationResult, JsonValue, ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path


class StructureAnalyzer:
    """
    Analyzes Memory Bank structure to identify organizational issues.

    Features:
    - Analyze file organization and hierarchy
    - Detect organizational anti-patterns
    - Identify overly complex dependency chains
    - Find circular dependencies
    - Measure structural complexity metrics
    """

    def __init__(
        self,
        project_root: Path,
        dependency_graph: DependencyGraph,
        file_system: FileSystemManager,
        metadata_index: MetadataIndex,
    ):
        """
        Initialize structure analyzer.

        Args:
            project_root: Root directory of the project
            dependency_graph: Dependency graph manager
            file_system: File system manager
            metadata_index: Metadata index
        """
        self.project_root: Path = Path(project_root)
        self.dependency_graph: DependencyGraph = dependency_graph
        self.file_system: FileSystemManager = file_system
        self.metadata_index: MetadataIndex = metadata_index

    async def analyze_file_organization(self) -> FileOrganizationResult:
        """
        Analyze the overall file organization.

        Returns:
            File organization analysis result model
        """
        memory_bank_dir = get_cortex_path(
            self.project_root, CortexResourceType.MEMORY_BANK
        )

        if not memory_bank_dir.exists():
            raise MemoryBankError(f"Memory bank directory not found: {memory_bank_dir}")

        all_files = list(memory_bank_dir.glob("*.md"))
        file_count = len(all_files)

        if file_count == 0:
            return structure_analysis.build_empty_organization_result()

        file_sizes = structure_analysis.collect_file_sizes(all_files)
        stats = structure_analysis.calculate_size_statistics(file_sizes, file_count)
        issues = structure_analysis.identify_size_issues(file_sizes)

        return structure_analysis.build_organization_analysis_result(
            file_count, stats, file_sizes, issues
        )

    async def detect_anti_patterns(self) -> list[AntiPatternInfo]:
        """
        Detect organizational anti-patterns.

        Returns:
            List of detected anti-patterns with details
        """
        memory_bank_dir = get_cortex_path(
            self.project_root, CortexResourceType.MEMORY_BANK
        )
        all_files = list(memory_bank_dir.glob("*.md"))
        graph = structure_analysis.build_dependency_graph(self.dependency_graph)

        anti_patterns: list[AntiPatternInfo] = []
        anti_patterns.extend(structure_detection.detect_oversized_files(all_files))
        anti_patterns.extend(
            structure_detection.detect_orphaned_files(all_files, graph)
        )
        anti_patterns.extend(structure_detection.detect_excessive_dependencies(graph))
        anti_patterns.extend(structure_detection.detect_excessive_dependents(graph))
        anti_patterns.extend(structure_detection.detect_similar_filenames(all_files))

        return structure_detection.sort_patterns_by_severity(anti_patterns)

    async def measure_complexity_metrics(self) -> ComplexityAnalysisResult:
        """
        Measure structural complexity metrics.

        Returns:
            ComplexityAnalysisResult model with complexity metrics
        """
        graph = structure_metrics.build_complexity_graph(self.dependency_graph)
        if not graph:
            return ComplexityAnalysisResult(status="no_files")

        depth_map, max_depth = structure_metrics.calculate_dependency_depths(graph)
        edge_count, node_count, cyclomatic_complexity, avg_dependencies = (
            structure_metrics.calculate_cyclomatic_metrics(graph)
        )
        fan_in, fan_out, max_fan_in, max_fan_out, avg_fan_in, avg_fan_out = (
            structure_metrics.calculate_fan_metrics(graph)
        )
        hotspots = structure_metrics.identify_complexity_hotspots(
            graph, depth_map, fan_in, fan_out
        )
        metrics = _build_complexity_metrics(
            max_depth,
            cyclomatic_complexity,
            avg_dependencies,
            max_fan_in,
            max_fan_out,
            avg_fan_in,
            avg_fan_out,
            edge_count,
            node_count,
        )
        assessment = _assess_complexity_model(
            max_depth, cyclomatic_complexity, avg_dependencies
        )
        return _build_complexity_result(metrics, hotspots[:10], assessment)

    def assess_complexity(
        self, max_depth: int, cyclomatic: int, avg_deps: float
    ) -> ComplexityAssessment:
        """Assess complexity and return a typed model."""
        return _assess_complexity_model(
            max_depth=max_depth, cyclomatic=cyclomatic, avg_deps=avg_deps
        )

    async def find_dependency_chains(
        self, max_chain_length: int = 10
    ) -> list[ModelDict]:
        """
        Find long dependency chains.

        Args:
            max_chain_length: Maximum chain length to search for

        Returns:
            List of dependency chains
        """
        graph = structure_analysis.build_dependency_graph(self.dependency_graph)
        chains = structure_metrics.find_all_chains(graph, max_chain_length)
        unique_chains = structure_metrics.deduplicate_and_sort_chains(chains)
        return [_chain_result_to_dict(c) for c in unique_chains[:20]]


def _build_complexity_metrics(
    max_depth: int,
    cyclomatic_complexity: int,
    avg_dependencies: float,
    max_fan_in: int,
    max_fan_out: int,
    avg_fan_in: float,
    avg_fan_out: float,
    edge_count: int,
    node_count: int,
) -> ComplexityMetrics:
    """Build ComplexityMetrics from calculated values."""
    return ComplexityMetrics(
        max_dependency_depth=max_depth,
        cyclomatic_complexity=int(cyclomatic_complexity),
        avg_dependencies_per_file=round(avg_dependencies, 2),
        max_fan_in=max_fan_in,
        max_fan_out=max_fan_out,
        avg_fan_in=round(avg_fan_in, 2),
        avg_fan_out=round(avg_fan_out, 2),
        total_edges=edge_count,
        total_nodes=node_count,
    )


def _build_complexity_result(
    metrics: ComplexityMetrics,
    hotspots: list[ComplexityHotspot],
    assessment: ComplexityAssessment,
) -> ComplexityAnalysisResult:
    """Build complexity analysis result."""
    return ComplexityAnalysisResult(
        status="analyzed",
        metrics=metrics,
        complexity_hotspots=hotspots,
        assessment=assessment,
    )


def _assess_complexity_model(
    max_depth: int, cyclomatic: int, avg_deps: float
) -> ComplexityAssessment:
    """Assess overall complexity and return assessment model."""
    issues: list[str] = []
    score = 100

    score, issues = structure_metrics.assess_depth_complexity(max_depth, score, issues)
    score, issues = structure_metrics.assess_cyclomatic_complexity(
        cyclomatic, score, issues
    )
    score, issues = structure_metrics.assess_dependency_complexity(
        avg_deps, score, issues
    )

    grade, status = structure_metrics.determine_complexity_grade(score)
    recommendations = structure_metrics.generate_complexity_recommendations(
        max_depth, cyclomatic, avg_deps
    )

    return ComplexityAssessment(
        score=score,
        grade=grade,
        status=status,
        issues=issues if issues else ["No major issues detected"],
        recommendations=(
            recommendations if recommendations else ["Structure looks good"]
        ),
    )


def _chain_result_to_dict(chain_result: DependencyChainResult) -> ModelDict:
    """Convert DependencyChainResult to ModelDict for find_dependency_chains API."""
    chain_json: list[JsonValue] = list(chain_result.chain)
    return {
        "type": "linear" if chain_result.is_linear else "circular",
        "chain": chain_json,
        "length": chain_result.length,
        "is_linear": chain_result.is_linear,
    }
