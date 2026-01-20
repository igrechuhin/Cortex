"""
Structure Metrics - Calculate complexity metrics.

This module calculates structural complexity metrics including
dependency depth, cyclomatic complexity, fan-in/fan-out, and hotspots.
"""

from cortex.analysis.models import ComplexityHotspot, DependencyChainResult
from cortex.core.dependency_graph import DependencyGraph


def build_complexity_graph(
    dependency_graph: DependencyGraph,
) -> dict[str, dict[str, list[str]]]:
    """Build graph from dependency graph for complexity analysis.

    Args:
        dependency_graph: DependencyGraph manager instance

    Returns:
        Graph dictionary mapping file names to dependencies and dependents
    """
    all_file_names = dependency_graph.get_all_files()
    graph: dict[str, dict[str, list[str]]] = {}
    for file_name in all_file_names:
        graph[file_name] = {
            "dependencies": dependency_graph.get_dependencies(file_name),
            "dependents": dependency_graph.get_dependents(file_name),
        }
    return graph


def calculate_dependency_depths(
    graph: dict[str, dict[str, list[str]]],
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

    for file_name in graph:
        depth = calculate_depth(file_name, set())
        max_depth = max(max_depth, depth)

    return depth_map, max_depth


def calculate_cyclomatic_metrics(
    graph: dict[str, dict[str, list[str]]],
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


def calculate_fan_metrics(
    graph: dict[str, dict[str, list[str]]],
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


def identify_complexity_hotspots(
    graph: dict[str, dict[str, list[str]]],
    depth_map: dict[str, int],
    fan_in: dict[str, int],
    fan_out: dict[str, int],
) -> list[ComplexityHotspot]:
    """Identify complexity hotspots.

    Args:
        graph: Dependency graph
        depth_map: Map of file names to dependency depths
        fan_in: Map of file names to fan-in counts
        fan_out: Map of file names to fan-out counts

    Returns:
        List of ComplexityHotspot models, sorted by score descending
    """
    hotspots: list[ComplexityHotspot] = []
    for file_name in graph:
        file_depth = depth_map.get(file_name, 0)
        file_fan_in = fan_in.get(file_name, 0)
        file_fan_out = fan_out.get(file_name, 0)
        complexity_score = file_depth * 2 + file_fan_in + file_fan_out

        if complexity_score > 20:
            hotspots.append(
                ComplexityHotspot(
                    file=file_name,
                    score=float(complexity_score),
                    depth=file_depth,
                    fan_in=file_fan_in,
                    fan_out=file_fan_out,
                )
            )

    hotspots.sort(key=lambda h: h.score, reverse=True)
    return hotspots


def assess_depth_complexity(
    max_depth: int, score: int, issues: list[str]
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


def assess_cyclomatic_complexity(
    cyclomatic: int, score: int, issues: list[str]
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


def assess_dependency_complexity(
    avg_deps: float, score: int, issues: list[str]
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


def determine_complexity_grade(score: int) -> tuple[str, str]:
    """Determine grade and status from score.

    Args:
        score: Complexity score

    Returns:
        Tuple of (grade, status)
    """
    if score >= 90:
        return ("A", "excellent")
    if score >= 80:
        return ("B", "good")
    if score >= 70:
        return ("C", "acceptable")
    if score >= 60:
        return ("D", "needs_improvement")
    return ("F", "poor")


def generate_complexity_recommendations(
    max_depth: int, cyclomatic: int, avg_deps: float
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


def find_all_chains(
    graph: dict[str, dict[str, list[str]]], max_chain_length: int
) -> list[DependencyChainResult]:
    """Find all dependency chains in the graph.

    Args:
        graph: Dependency graph structure
        max_chain_length: Maximum chain length to search for

    Returns:
        List of found chains
    """
    chains: list[DependencyChainResult] = []

    def find_chains_from_file(
        start_file: str, current_path: list[str], visited: set[str]
    ) -> None:
        """Recursively find chains from a starting file."""
        if len(current_path) > max_chain_length:
            return

        if start_file in visited:
            if len(current_path) >= 2:
                chains.append(create_circular_chain(current_path, start_file))
            return

        visited.add(start_file)
        dependencies = graph.get(start_file, {}).get("dependencies", [])

        if not dependencies:
            if len(current_path) >= 3:
                chains.append(create_linear_chain(current_path))
        else:
            for dep in dependencies:
                find_chains_from_file(dep, [*current_path, dep], visited.copy())

    for file_name in graph:
        find_chains_from_file(file_name, [file_name], set())

    return chains


def deduplicate_and_sort_chains(
    chains: list[DependencyChainResult],
) -> list[DependencyChainResult]:
    """Remove duplicate chains and sort by length.

    Args:
        chains: List of chains to deduplicate and sort

    Returns:
        Deduplicated and sorted chains
    """
    seen: set[tuple[str, ...]] = set()

    def _is_unique_chain(chain: DependencyChainResult) -> bool:
        """Check if chain is unique and add to seen set."""
        chain_key = tuple(chain.chain)
        if chain_key and chain_key not in seen:
            seen.add(chain_key)
            return True
        return False

    unique_chains: list[DependencyChainResult] = [
        chain for chain in chains if _is_unique_chain(chain)
    ]

    unique_chains.sort(key=lambda c: c.length, reverse=True)
    return unique_chains


def create_circular_chain(
    current_path: list[str], start_file: str
) -> DependencyChainResult:
    """Create a circular chain model.

    Args:
        current_path: Current path in the chain
        start_file: Starting file that creates the cycle

    Returns:
        DependencyChainResult with is_linear=False
    """
    return DependencyChainResult(
        chain=[*current_path, start_file],
        length=len(current_path),
        is_linear=False,
    )


def create_linear_chain(current_path: list[str]) -> DependencyChainResult:
    """Create a linear chain model.

    Args:
        current_path: Current path in the chain

    Returns:
        DependencyChainResult with is_linear=True
    """
    return DependencyChainResult(
        chain=current_path,
        length=len(current_path),
        is_linear=True,
    )
