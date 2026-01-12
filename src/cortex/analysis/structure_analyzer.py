"""
Structure Analyzer - Analyze file organization and dependency structure.

This module analyzes the Memory Bank structure to identify organizational issues,
complexity metrics, and anti-patterns.
"""

from pathlib import Path
from typing import cast

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.exceptions import MemoryBankError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex


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

    async def analyze_file_organization(self) -> dict[str, object]:
        """
        Analyze the overall file organization.

        Returns:
            Dictionary with organization analysis
        """
        memory_bank_dir = self.project_root / ".cortex" / "memory-bank"

        if not memory_bank_dir.exists():
            raise MemoryBankError(f"Memory bank directory not found: {memory_bank_dir}")

        all_files = list(memory_bank_dir.glob("*.md"))
        file_count = len(all_files)

        if file_count == 0:
            return _build_empty_organization_result()

        file_sizes = self._collect_file_sizes(all_files)
        stats = _calculate_size_statistics(file_sizes, file_count)
        issues = _identify_size_issues(file_sizes)

        return _build_organization_analysis_result(
            file_count, stats, file_sizes, issues
        )

    def _collect_file_sizes(self, all_files: list[Path]) -> list[dict[str, object]]:
        """Collect file size information for all files."""

        def _get_file_size(file_path: Path) -> dict[str, object] | None:
            """Get file size info, returning None on error."""
            try:
                size = file_path.stat().st_size
                return {
                    "file": file_path.name,
                    "size_bytes": size,
                    "size_kb": round(size / 1024, 2),
                }
            except OSError:
                return None

        file_sizes = [
            size_info
            for file_path in all_files
            if (size_info := _get_file_size(file_path)) is not None
        ]
        file_sizes.sort(key=_get_size_bytes_for_sort, reverse=True)
        return file_sizes

    def _detect_oversized_files(self, all_files: list[Path]) -> list[dict[str, object]]:
        """
        Detect oversized files (>100KB).

        Args:
            all_files: List of file paths to check

        Returns:
            List of oversized file anti-patterns
        """

        def _check_oversized(file_path: Path) -> dict[str, object] | None:
            """Check if file is oversized, returning pattern dict or None."""
            try:
                size = file_path.stat().st_size
                if size > 100000:  # > 100KB
                    return {
                        "type": "oversized_file",
                        "severity": "high",
                        "file": file_path.name,
                        "description": f"File is very large ({round(size / 1024, 2)}KB)",
                        "recommendation": "Consider splitting into multiple smaller files",
                        "size_bytes": size,
                    }
            except OSError:
                pass
            return None

        return [
            pattern
            for file_path in all_files
            if (pattern := _check_oversized(file_path)) is not None
        ]

    def _build_dependency_graph(self) -> dict[str, dict[str, list[str]]]:
        """
        Build dependency graph from DependencyGraph manager.

        Returns:
            Dictionary mapping file names to their dependencies and dependents
        """
        all_file_names = self.dependency_graph.get_all_files()
        graph: dict[str, dict[str, list[str]]] = {}

        for file_name in all_file_names:
            graph[file_name] = {
                "dependencies": self.dependency_graph.get_dependencies(file_name),
                "dependents": self.dependency_graph.get_dependents(file_name),
            }

        return graph

    def _detect_orphaned_files(
        self, all_files: list[Path], graph: dict[str, dict[str, list[str]]]
    ) -> list[dict[str, object]]:
        """
        Detect orphaned files (no dependencies or dependents).

        Args:
            all_files: List of file paths to check
            graph: Dependency graph

        Returns:
            List of orphaned file anti-patterns
        """
        patterns: list[dict[str, object]] = [
            {
                "type": "orphaned_file",
                "severity": "medium",
                "file": file_path.name,
                "description": "File has no dependencies or dependents",
                "recommendation": "Link to other files or consider if it's still needed",
            }
            for file_path in all_files
            if not (
                file_path.name in graph
                and (
                    graph[file_path.name].get("dependencies")
                    or graph[file_path.name].get("dependents")
                )
            )
        ]

        return patterns

    def _detect_excessive_dependencies(
        self, graph: dict[str, dict[str, list[str]]]
    ) -> list[dict[str, object]]:
        """
        Detect files with excessive dependencies (>15).

        Args:
            graph: Dependency graph

        Returns:
            List of excessive dependency anti-patterns
        """
        return [
            {
                "type": "excessive_dependencies",
                "severity": "medium",
                "file": file_name,
                "description": f"File depends on {dep_count} other files",
                "recommendation": "Consider reducing dependencies or splitting file",
                "dependency_count": dep_count,
            }
            for file_name, file_data in graph.items()
            if (dep_count := len(file_data.get("dependencies", []))) > 15
        ]

    def _detect_excessive_dependents(
        self, graph: dict[str, dict[str, list[str]]]
    ) -> list[dict[str, object]]:
        """
        Detect files with excessive dependents (>15).

        Args:
            graph: Dependency graph

        Returns:
            List of excessive dependent anti-patterns
        """
        return [
            {
                "type": "excessive_dependents",
                "severity": "low",
                "file": file_name,
                "description": f"File is depended upon by {dependent_count} other files",
                "recommendation": "This is a central file - ensure it's stable and well-maintained",
                "dependent_count": dependent_count,
            }
            for file_name, file_data in graph.items()
            if (dependent_count := len(file_data.get("dependents", []))) > 15
        ]

    def _detect_similar_filenames(
        self, all_files: list[Path]
    ) -> list[dict[str, object]]:
        """
        Detect files with similar names (potential duplication).

        Args:
            all_files: List of file paths to check

        Returns:
            List of similar filename anti-patterns
        """
        patterns: list[dict[str, object]] = []
        file_names: list[str] = [f.stem for f in all_files]

        # Optimize: Sort names and use sorted order to reduce comparisons
        # Only check adjacent and nearby names in sorted order, as similar
        # names tend to cluster together alphabetically
        sorted_names = sorted(file_names, key=lambda x: x.lower())

        # Check each name against the next few names (window approach)
        # This reduces complexity from O(n²) to O(n*k) where k is window size
        window_size = min(10, len(sorted_names))  # Check next 10 names max

        similar_names: list[tuple[str, str]] = [
            (sorted_names[i], sorted_names[j])
            for i in range(len(sorted_names))
            for j in range(i + 1, min(i + 1 + window_size, len(sorted_names)))
            if sorted_names[j].lower()[0] == sorted_names[i].lower()[0]
            and (
                sorted_names[i].lower() in sorted_names[j].lower()
                or sorted_names[j].lower() in sorted_names[i].lower()
            )
        ]

        patterns = [
            {
                "type": "similar_filenames",
                "severity": "low",
                "files": [f"{name1}.md", f"{name2}.md"],
                "description": "Files have similar names",
                "recommendation": "Check if content is duplicated or could be consolidated",
            }
            for name1, name2 in similar_names
        ]

        return patterns

    def _sort_patterns_by_severity(
        self, patterns: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """
        Sort anti-patterns by severity (high > medium > low).

        Args:
            patterns: List of anti-patterns to sort

        Returns:
            Sorted list of anti-patterns
        """
        severity_order = {"high": 0, "medium": 1, "low": 2}

        def get_severity_order(pattern: dict[str, object]) -> int:
            """Extract severity order for sorting."""
            severity = pattern.get("severity", "low")
            if isinstance(severity, str):
                return severity_order.get(severity, 2)
            return 2

        sorted_patterns = patterns.copy()
        sorted_patterns.sort(key=get_severity_order)
        return sorted_patterns

    async def detect_anti_patterns(self) -> list[dict[str, object]]:
        """
        Detect organizational anti-patterns.

        Returns:
            List of detected anti-patterns with details
        """
        memory_bank_dir = self.project_root / ".cortex" / "memory-bank"
        all_files = list(memory_bank_dir.glob("*.md"))

        graph = self._build_dependency_graph()

        anti_patterns: list[dict[str, object]] = []
        anti_patterns.extend(self._detect_oversized_files(all_files))
        anti_patterns.extend(self._detect_orphaned_files(all_files, graph))
        anti_patterns.extend(self._detect_excessive_dependencies(graph))
        anti_patterns.extend(self._detect_excessive_dependents(graph))
        anti_patterns.extend(self._detect_similar_filenames(all_files))

        return self._sort_patterns_by_severity(anti_patterns)

    async def measure_complexity_metrics(self) -> dict[str, object]:
        """
        Measure structural complexity metrics.

        Returns:
            Dictionary with complexity metrics
        """
        graph = self._build_complexity_graph()
        if not graph:
            return {"status": "no_files", "metrics": {}}

        depth_map, max_depth = self._calculate_dependency_depths(graph)
        edge_count, node_count, cyclomatic_complexity, avg_dependencies = (
            self._calculate_cyclomatic_metrics(graph)
        )
        fan_in, fan_out, max_fan_in, max_fan_out, avg_fan_in, avg_fan_out = (
            self._calculate_fan_metrics(graph)
        )
        hotspots = self._identify_complexity_hotspots(graph, depth_map, fan_in, fan_out)

        return {
            "status": "analyzed",
            "metrics": {
                "max_dependency_depth": max_depth,
                "cyclomatic_complexity": cyclomatic_complexity,
                "avg_dependencies_per_file": round(avg_dependencies, 2),
                "max_fan_in": max_fan_in,
                "max_fan_out": max_fan_out,
                "avg_fan_in": round(avg_fan_in, 2),
                "avg_fan_out": round(avg_fan_out, 2),
                "total_edges": edge_count,
                "total_nodes": node_count,
            },
            "complexity_hotspots": hotspots[:10],
            "assessment": self.assess_complexity(
                max_depth, cyclomatic_complexity, avg_dependencies
            ),
        }

    def _build_complexity_graph(self) -> dict[str, dict[str, list[str]]]:
        """Build graph from dependency graph for complexity analysis.

        Returns:
            Graph dictionary mapping file names to dependencies and dependents
        """
        all_file_names = self.dependency_graph.get_all_files()
        graph: dict[str, dict[str, list[str]]] = {}
        for file_name in all_file_names:
            graph[file_name] = {
                "dependencies": self.dependency_graph.get_dependencies(file_name),
                "dependents": self.dependency_graph.get_dependents(file_name),
            }
        return graph

    def _calculate_dependency_depths(
        self, graph: dict[str, dict[str, list[str]]]
    ) -> tuple[dict[str, int], int]:
        """Calculate dependency depths for all files.

        Args:
            graph: Dependency graph

        Returns:
            Tuple of (depth_map, max_depth)
        """
        max_depth = 0
        depth_map: dict[str, int] = {}

        def calculate_depth(file_name: str, visited: set[str]) -> int:
            """Calculate maximum dependency depth for a file."""
            if file_name in depth_map:
                return depth_map[file_name]

            if file_name in visited:
                return 0  # Circular dependency

            visited.add(file_name)

            dependencies = graph.get(file_name, {}).get("dependencies", [])
            if not dependencies:
                depth = 0
            else:
                depth = 1 + max(
                    calculate_depth(dep, visited.copy()) for dep in dependencies
                )

            depth_map[file_name] = depth
            return depth

        for file_name in graph.keys():
            depth = calculate_depth(file_name, set())
            max_depth = max(max_depth, depth)

        return depth_map, max_depth

    def _calculate_cyclomatic_metrics(
        self, graph: dict[str, dict[str, list[str]]]
    ) -> tuple[int, int, int, float]:
        """Calculate cyclomatic complexity metrics.

        Args:
            graph: Dependency graph

        Returns:
            Tuple of (edge_count, node_count, cyclomatic_complexity, avg_dependencies)
        """
        edge_count = sum(len(data.get("dependencies", [])) for data in graph.values())
        node_count = len(graph)
        cyclomatic_complexity = edge_count - node_count + 1 if node_count > 0 else 0
        avg_dependencies = edge_count / node_count if node_count > 0 else 0
        return edge_count, node_count, cyclomatic_complexity, avg_dependencies

    def _calculate_fan_metrics(
        self, graph: dict[str, dict[str, list[str]]]
    ) -> tuple[dict[str, int], dict[str, int], int, int, float, float]:
        """Calculate fan-in and fan-out metrics.

        Args:
            graph: Dependency graph

        Returns:
            Tuple of (fan_in, fan_out, max_fan_in, max_fan_out, avg_fan_in, avg_fan_out)
        """
        fan_in: dict[str, int] = {}
        fan_out: dict[str, int] = {}

        for file_name, data in graph.items():
            fan_out[file_name] = len(data.get("dependencies", []))
            fan_in[file_name] = len(data.get("dependents", []))

        max_fan_in = max(fan_in.values()) if fan_in else 0
        max_fan_out = max(fan_out.values()) if fan_out else 0
        avg_fan_in = sum(fan_in.values()) / len(fan_in) if fan_in else 0
        avg_fan_out = sum(fan_out.values()) / len(fan_out) if fan_out else 0

        return fan_in, fan_out, max_fan_in, max_fan_out, avg_fan_in, avg_fan_out

    def _identify_complexity_hotspots(
        self,
        graph: dict[str, dict[str, list[str]]],
        depth_map: dict[str, int],
        fan_in: dict[str, int],
        fan_out: dict[str, int],
    ) -> list[dict[str, object]]:
        """Identify complexity hotspots.

        Args:
            graph: Dependency graph
            depth_map: Map of file names to dependency depths
            fan_in: Map of file names to fan-in counts
            fan_out: Map of file names to fan-out counts

        Returns:
            List of complexity hotspot dictionaries, sorted by score
        """
        hotspots: list[dict[str, object]] = [
            {
                "file": file_name,
                "complexity_score": complexity_score,
                "depth": depth_map.get(file_name, 0),
                "fan_in": fan_in.get(file_name, 0),
                "fan_out": fan_out.get(file_name, 0),
            }
            for file_name in graph.keys()
            if (
                complexity_score := (
                    depth_map.get(file_name, 0) * 2
                    + fan_in.get(file_name, 0)
                    + fan_out.get(file_name, 0)
                )
            )
            > 20
        ]

        def get_complexity_score(hotspot: dict[str, object]) -> int:
            """Extract complexity score for sorting."""
            score = hotspot.get("complexity_score", 0)
            return int(score) if isinstance(score, (int, float)) else 0

        hotspots.sort(key=get_complexity_score, reverse=True)
        return hotspots

    def assess_complexity(
        self, max_depth: int, cyclomatic: int, avg_deps: float
    ) -> dict[str, object]:
        """
        Assess overall complexity and provide recommendations.

        Args:
            max_depth: Maximum dependency depth
            cyclomatic: Cyclomatic complexity
            avg_deps: Average dependencies per file

        Returns:
            Assessment with score and recommendations
        """
        issues: list[str] = []
        score = 100  # Start with perfect score

        score, issues = self._assess_depth_complexity(max_depth, score, issues)
        score, issues = self._assess_cyclomatic_complexity(cyclomatic, score, issues)
        score, issues = self._assess_dependency_complexity(avg_deps, score, issues)

        grade, status = self._determine_complexity_grade(score)
        recommendations = self._generate_complexity_recommendations(
            max_depth, cyclomatic, avg_deps
        )

        return {
            "score": score,
            "grade": grade,
            "status": status,
            "issues": issues if issues else ["No major issues detected"],
            "recommendations": (
                recommendations if recommendations else ["Structure looks good"]
            ),
        }

    def _assess_depth_complexity(
        self, max_depth: int, score: int, issues: list[str]
    ) -> tuple[int, list[str]]:
        """Assess depth complexity and update score.

        Args:
            max_depth: Maximum dependency depth
            score: Current score
            issues: Current issues list

        Returns:
            Tuple of (updated_score, updated_issues)
        """
        if max_depth > 10:
            issues.append("Dependency chains are very deep")
            score -= 20
        elif max_depth > 5:
            issues.append("Dependency chains are moderately deep")
            score -= 10
        return score, issues

    def _assess_cyclomatic_complexity(
        self, cyclomatic: int, score: int, issues: list[str]
    ) -> tuple[int, list[str]]:
        """Assess cyclomatic complexity and update score.

        Args:
            cyclomatic: Cyclomatic complexity value
            score: Current score
            issues: Current issues list

        Returns:
            Tuple of (updated_score, updated_issues)
        """
        if cyclomatic > 20:
            issues.append("High cyclomatic complexity")
            score -= 20
        elif cyclomatic > 10:
            issues.append("Moderate cyclomatic complexity")
            score -= 10
        return score, issues

    def _assess_dependency_complexity(
        self, avg_deps: float, score: int, issues: list[str]
    ) -> tuple[int, list[str]]:
        """Assess dependency complexity and update score.

        Args:
            avg_deps: Average dependencies per file
            score: Current score
            issues: Current issues list

        Returns:
            Tuple of (updated_score, updated_issues)
        """
        if avg_deps > 10:
            issues.append("Files have too many dependencies on average")
            score -= 15
        elif avg_deps > 5:
            issues.append("Files have moderate number of dependencies")
            score -= 5
        return score, issues

    def _determine_complexity_grade(self, score: int) -> tuple[str, str]:
        """Determine grade and status from score.

        Args:
            score: Complexity score

        Returns:
            Tuple of (grade, status)
        """
        if score >= 90:
            return ("A", "excellent")
        elif score >= 80:
            return ("B", "good")
        elif score >= 70:
            return ("C", "acceptable")
        elif score >= 60:
            return ("D", "needs_improvement")
        else:
            return ("F", "poor")

    def _generate_complexity_recommendations(
        self, max_depth: int, cyclomatic: int, avg_deps: float
    ) -> list[str]:
        """Generate recommendations based on complexity metrics.

        Args:
            max_depth: Maximum dependency depth
            cyclomatic: Cyclomatic complexity
            avg_deps: Average dependencies per file

        Returns:
            List of recommendation strings
        """
        recommendations: list[str] = []
        if max_depth > 5:
            recommendations.append("Consider flattening dependency hierarchy")
        if cyclomatic > 10:
            recommendations.append("Simplify dependency structure")
        if avg_deps > 5:
            recommendations.append("Reduce number of dependencies per file")
        return recommendations

    async def find_dependency_chains(
        self, max_chain_length: int = 10
    ) -> list[dict[str, object]]:
        """
        Find long dependency chains.

        Args:
            max_chain_length: Maximum chain length to search for

        Returns:
            List of dependency chains
        """
        graph = self._build_dependency_graph()
        chains = self._find_all_chains(graph, max_chain_length)
        unique_chains = self._deduplicate_and_sort_chains(chains)
        return unique_chains[:20]

    def _find_all_chains(
        self, graph: dict[str, dict[str, list[str]]], max_chain_length: int
    ) -> list[dict[str, object]]:
        """Find all dependency chains in the graph.

        Args:
            graph: Dependency graph structure
            max_chain_length: Maximum chain length to search for

        Returns:
            List of found chains
        """
        chains: list[dict[str, object]] = []

        def find_chains_from_file(
            start_file: str, current_path: list[str], visited: set[str]
        ) -> None:
            """Recursively find chains from a starting file."""
            if len(current_path) > max_chain_length:
                return

            if start_file in visited:
                if len(current_path) >= 2:
                    chains.append(_create_circular_chain_dict(current_path, start_file))
                return

            visited.add(start_file)
            dependencies = graph.get(start_file, {}).get("dependencies", [])

            if not dependencies:
                if len(current_path) >= 3:
                    chains.append(_create_linear_chain_dict(current_path))
            else:
                for dep in dependencies:
                    find_chains_from_file(dep, current_path + [dep], visited.copy())

        for file_name in graph.keys():
            find_chains_from_file(file_name, [file_name], set())

        return chains

    def _deduplicate_and_sort_chains(
        self, chains: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Remove duplicate chains and sort by length.

        Args:
            chains: List of chains to deduplicate and sort

        Returns:
            Deduplicated and sorted chains
        """
        seen: set[tuple[str, ...]] = set()

        def _is_unique_chain(chain: dict[str, object]) -> bool:
            """Check if chain is unique and add to seen set."""
            chain_list_raw = chain.get("chain", [])
            if not isinstance(chain_list_raw, list):
                return False

            chain_list: list[str] = [
                str(part)
                for part in cast(list[object], chain_list_raw)
                if part is not None
            ]
            chain_key = tuple(chain_list)
            if chain_key and chain_key not in seen:
                seen.add(chain_key)
                return True
            return False

        unique_chains: list[dict[str, object]] = [
            chain for chain in chains if _is_unique_chain(chain)
        ]

        def get_chain_length(chain: dict[str, object]) -> int:
            """Extract chain length for sorting."""
            length = chain.get("length", 0)
            return int(length) if isinstance(length, (int, float)) else 0

        unique_chains.sort(key=get_chain_length, reverse=True)
        return unique_chains


def _get_size_bytes_for_sort(file_info: dict[str, object]) -> int:
    """Extract size_bytes as int for sorting."""
    size_raw = file_info.get("size_bytes", 0)
    return int(size_raw) if isinstance(size_raw, (int, float)) else 0


def _build_empty_organization_result() -> dict[str, object]:
    """Build result for empty memory bank.

    Returns:
        Empty organization result dictionary
    """
    return {
        "status": "empty",
        "file_count": 0,
        "issues": ["No files found in memory bank"],
    }


def _build_organization_analysis_result(
    file_count: int,
    stats: dict[str, int],
    file_sizes: list[dict[str, object]],
    issues: list[str],
) -> dict[str, object]:
    """Build organization analysis result dictionary.

    Args:
        file_count: Total number of files
        stats: Size statistics dictionary
        file_sizes: List of file size dictionaries
        issues: List of identified issues

    Returns:
        Organization analysis result dictionary
    """
    return {
        "status": "analyzed",
        "file_count": file_count,
        "total_size_bytes": stats["total_size"],
        "total_size_kb": round(stats["total_size"] / 1024, 2),
        "avg_size_bytes": round(stats["avg_size"]),
        "avg_size_kb": round(stats["avg_size"] / 1024, 2),
        "max_size_bytes": stats["max_size"],
        "min_size_bytes": stats["min_size"],
        "largest_files": file_sizes[:5],
        "smallest_files": file_sizes[-5:],
        "issues": issues if issues else None,
    }


def _calculate_size_statistics(
    file_sizes: list[dict[str, object]], file_count: int
) -> dict[str, int]:
    """Calculate size statistics from file sizes."""
    total_size = sum(_get_size_bytes_for_sort(f) for f in file_sizes)
    avg_size = total_size // file_count if file_count > 0 else 0

    max_size_raw = file_sizes[0].get("size_bytes", 0) if file_sizes else 0
    max_size = int(max_size_raw) if isinstance(max_size_raw, (int, float)) else 0

    min_size_raw = file_sizes[-1].get("size_bytes", 0) if file_sizes else 0
    min_size = int(min_size_raw) if isinstance(min_size_raw, (int, float)) else 0

    return {
        "total_size": total_size,
        "avg_size": avg_size,
        "max_size": max_size,
        "min_size": min_size,
    }


def _identify_size_issues(file_sizes: list[dict[str, object]]) -> list[str]:
    """Identify size-related issues in files."""
    issues: list[str] = []

    large_files = [f for f in file_sizes if _get_size_bytes_for_sort(f) > 50000]
    if large_files:
        issues.append(f"{len(large_files)} files are very large (>50KB)")

    small_files = [f for f in file_sizes if _get_size_bytes_for_sort(f) < 500]
    if small_files:
        issues.append(f"{len(small_files)} files are very small (<500 bytes)")

    return issues


def _create_circular_chain_dict(
    current_path: list[str], start_file: str
) -> dict[str, object]:
    """Create a circular chain dictionary.

    Args:
        current_path: Current path in the chain
        start_file: Starting file that creates the cycle

    Returns:
        Chain dictionary
    """
    return {
        "type": "circular",
        "chain": current_path + [start_file],
        "length": len(current_path),
    }


def _create_linear_chain_dict(current_path: list[str]) -> dict[str, object]:
    """Create a linear chain dictionary.

    Args:
        current_path: Current path in the chain

    Returns:
        Chain dictionary
    """
    return {
        "type": "linear",
        "chain": current_path,
        "length": len(current_path),
    }
