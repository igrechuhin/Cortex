"""
Reorganization Strategies for MCP Memory Bank.

This module contains different optimization strategies for Memory Bank reorganization:
- Dependency depth optimization
- Category-based organization
- Simplified structure
"""

from pathlib import Path
from typing import cast


class ReorganizationStrategies:
    """
    Generates proposed structures using various optimization strategies.

    Strategies:
    - dependency_depth: Optimize dependency order to minimize depth
    - category_based: Organize files by topic/category
    - complexity: Simplify structure to reduce cognitive load
    """

    def __init__(self, memory_bank_path: Path):
        """
        Initialize the reorganization strategies.

        Args:
            memory_bank_path: Path to Memory Bank directory
        """
        self.memory_bank_path = memory_bank_path

    async def generate_proposed_structure(
        self,
        current_structure: dict[str, object],
        optimize_for: str,
        dependency_graph: dict[str, object],
    ) -> dict[str, object]:
        """
        Generate proposed new structure based on optimization goal.

        Args:
            current_structure: Current structure data
            optimize_for: Optimization goal
            dependency_graph: Dependency graph data

        Returns:
            Proposed structure dictionary
        """
        proposed: dict[str, object] = {
            "organization": current_structure.get("organization"),
            "categories": {},
            "dependency_order": [],
            "naming_conventions": {},
        }

        if optimize_for == "dependency_depth":
            # Propose flatter dependency structure
            proposed["organization"] = "dependency_optimized"
            proposed["dependency_order"] = self.optimize_dependency_order(
                current_structure, dependency_graph
            )

        elif optimize_for == "category_based":
            # Propose category-based organization
            proposed["organization"] = "category_based"
            proposed["categories"] = self.propose_category_structure(current_structure)

        elif optimize_for == "complexity":
            # Propose simplified structure
            proposed["organization"] = "simplified"
            proposed["categories"] = self.propose_simplified_structure(
                current_structure
            )

        return proposed

    def optimize_dependency_order(
        self, current_structure: dict[str, object], dependency_graph: dict[str, object]
    ) -> list[str]:
        """
        Optimize file order to minimize dependency depth.

        Uses topological sort to determine optimal file ordering.

        Args:
            current_structure: Current structure data
            dependency_graph: Dependency graph data

        Returns:
            List of files in optimized order
        """
        files_raw = current_structure.get("files", [])
        files = cast(list[str], files_raw) if isinstance(files_raw, list) else []

        if not dependency_graph:
            return files

        dependencies = _extract_dependencies_from_graph(dependency_graph)
        graph, in_degree = _build_dependency_graph(files, dependencies)
        return _topological_sort(graph, in_degree, files)

    def propose_category_structure(
        self, current_structure: dict[str, object]
    ) -> dict[str, list[str]]:
        """
        Propose category-based organization.

        Refines existing categories and assigns uncategorized files.

        Args:
            current_structure: Current structure data

        Returns:
            Dictionary mapping categories to file lists
        """
        current_categories_raw = current_structure.get("categories", {})
        current_categories = (
            cast(dict[str, object], current_categories_raw)
            if isinstance(current_categories_raw, dict)
            else {}
        )

        # Refine categories
        proposed_categories: dict[str, list[str]] = {}

        for category, files in current_categories.items():
            category_str = str(category)
            files_list: list[str]
            if isinstance(files, list):
                files_list = [str(f) for f in cast(list[object], files)]
            elif isinstance(files, tuple):
                files_list = [str(f) for f in cast(tuple[object, ...], files)]
            else:
                files_list = []
            if category_str == "uncategorized":
                # Try to assign to appropriate categories
                for file in files_list:
                    # Default to context if unclear
                    if "context" not in proposed_categories:
                        proposed_categories["context"] = []
                    proposed_categories["context"].append(file)
            else:
                proposed_categories[category_str] = files_list

        return proposed_categories

    def propose_simplified_structure(
        self, current_structure: dict[str, object]
    ) -> dict[str, list[str]]:
        """
        Propose simplified structure with fewer categories.

        Simplifies to 3 main categories: core, context, reference.

        Args:
            current_structure: Current structure data

        Returns:
            Dictionary mapping simplified categories to file lists
        """
        files_raw = current_structure.get("files", [])
        files = cast(list[str], files_raw) if isinstance(files_raw, list) else []

        # Simplify to 3 main categories
        simplified: dict[str, list[str]] = {
            "core": [],  # Essential files (instructions, brief)
            "context": [],  # Context and status
            "reference": [],  # Technical docs and reference
        }

        for file_path in files:
            filename = Path(file_path).stem.lower()

            if any(
                keyword in filename for keyword in ["instruction", "brief", "overview"]
            ):
                simplified["core"].append(file_path)
            elif any(
                keyword in filename
                for keyword in ["context", "progress", "status", "active"]
            ):
                simplified["context"].append(file_path)
            else:
                simplified["reference"].append(file_path)

        return simplified


def _extract_dependencies_from_graph(
    dependency_graph: dict[str, object],
) -> dict[str, object]:
    """
    Extract dependencies dictionary from dependency graph.

    Args:
        dependency_graph: Dependency graph dictionary

    Returns:
        Dependencies dictionary
    """
    dependencies_raw = dependency_graph.get("dependencies", {})
    return (
        cast(dict[str, object], dependencies_raw)
        if isinstance(dependencies_raw, dict)
        else {}
    )


def _build_dependency_graph(
    files: list[str], dependencies: dict[str, object]
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """
    Build adjacency list and in-degree map from dependencies.

    Args:
        files: List of file names
        dependencies: Dependencies dictionary

    Returns:
        Tuple of (graph adjacency list, in-degree map)
    """
    graph: dict[str, list[str]] = {f: [] for f in files}
    in_degree: dict[str, int] = {f: 0 for f in files}

    for file, deps in dependencies.items():
        file_str = str(file)
        if file_str not in graph:
            continue
        deps_dict = cast(dict[str, object], deps) if isinstance(deps, dict) else {}
        deps_list = cast(list[str], deps_dict.get("dependencies", []))
        for dep in deps_list:
            if dep in graph:
                graph[dep].append(file_str)
                in_degree[file_str] += 1

    return graph, in_degree


def _topological_sort(
    graph: dict[str, list[str]], in_degree: dict[str, int], files: list[str]
) -> list[str]:
    """
    Perform topological sort using Kahn's algorithm.

    Sorts files in dependency order with zero-dependency files first.

    Args:
        graph: Adjacency list
        in_degree: In-degree map
        files: List of all files

    Returns:
        Topologically sorted file list
    """
    queue: list[str] = [f for f in files if in_degree[f] == 0]
    order: list[str] = []

    while queue:
        queue.sort()
        node = queue.pop(0)
        order.append(node)

        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order
