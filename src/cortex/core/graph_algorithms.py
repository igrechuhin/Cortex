"""
Graph Algorithms for Dependency Analysis.

This module provides algorithmic operations for analyzing dependency graphs,
including cycle detection, topological sorting, and path finding.
"""

from collections.abc import Callable


class GraphAlgorithms:
    """
    Collection of graph algorithms for dependency analysis.

    Features:
    - Cycle detection using DFS
    - Topological sorting using Kahn's algorithm
    - Reachability analysis
    - Graph traversal utilities
    """

    @staticmethod
    def detect_cycles(
        nodes: list[str], get_dependencies_fn: Callable[[str], list[str]]
    ) -> list[list[str]]:
        """
        Detect circular dependencies in the graph using DFS.

        Args:
            nodes: List of all nodes (file names)
            get_dependencies_fn: Function that returns dependencies for a node

        Returns:
            List of cycles, each as a list of files forming the cycle
        """
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: list[str] = []

        def visit(node: str, path: list[str]) -> None:
            if node in rec_stack:
                # Found a cycle
                cycle_start = rec_stack.index(node)
                cycle: list[str] = rec_stack[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.append(node)

            # Check all dependencies
            for dep in get_dependencies_fn(node):
                visit(dep, path + [node])

            _ = rec_stack.pop()  # Remove from recursion stack

        # Check all files
        for node in nodes:
            if node not in visited:
                visit(node, [])

        return cycles

    @staticmethod
    def has_cycle_dfs(
        node: str,
        visited: set[str],
        rec_stack: set[str],
        get_dependencies_fn: Callable[[str], list[str]],
    ) -> bool:
        """
        Check if there's a cycle starting from a node using DFS.

        Args:
            node: Starting node
            visited: Set of visited nodes
            rec_stack: Recursion stack for cycle detection
            get_dependencies_fn: Function that returns dependencies for a node

        Returns:
            True if cycle detected
        """
        visited.add(node)
        rec_stack.add(node)

        for neighbor in get_dependencies_fn(node):
            if neighbor not in visited:
                if GraphAlgorithms.has_cycle_dfs(
                    neighbor, visited, rec_stack, get_dependencies_fn
                ):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node)
        return False

    @staticmethod
    def topological_sort(
        files: list[str], get_dependencies_fn: Callable[[str], list[str]]
    ) -> list[str]:
        """
        Perform topological sort using Kahn's algorithm.

        Args:
            files: List of file names to sort
            get_dependencies_fn: Function that returns dependencies for a file

        Returns:
            Sorted list where dependencies come before dependents
        """
        # Build in-degree map and adjacency list
        in_degree: dict[str, int] = {f: 0 for f in files}
        adj_list: dict[str, list[str]] = {f: [] for f in files}

        for file in files:
            for dep in get_dependencies_fn(file):
                if dep in files:
                    adj_list[dep].append(file)
                    in_degree[file] += 1

        # Kahn's algorithm
        queue: list[str] = [f for f in files if in_degree[f] == 0]
        result: list[str] = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            neighbors = adj_list[current]
            for neighbor in neighbors:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If not all files processed, there's a cycle
        # Return partial order
        return result

    @staticmethod
    def get_reachable_nodes(
        start_node: str,
        get_neighbors_fn: Callable[[str], list[str]],
        filter_fn: Callable[[str, str], bool] | None = None,
    ) -> set[str]:
        """
        Get all nodes reachable from a starting node.

        Args:
            start_node: Node to start from
            get_neighbors_fn: Function that returns neighbors for a node
            filter_fn: Optional filter function for edges

        Returns:
            Set of reachable node names
        """
        reachable: set[str] = set()
        to_visit: list[str] = [start_node]

        while to_visit:
            current = to_visit.pop(0)
            if current in reachable:
                continue
            reachable.add(current)

            for neighbor in get_neighbors_fn(current):
                if filter_fn is None or filter_fn(current, neighbor):
                    if neighbor not in reachable:
                        to_visit.append(neighbor)

        return reachable

    @staticmethod
    def get_transitive_dependencies(
        target: str, get_dependencies_fn: Callable[[str], list[str]]
    ) -> set[str]:
        """
        Get all transitive dependencies of a target using BFS.

        Args:
            target: Target node
            get_dependencies_fn: Function that returns dependencies for a node

        Returns:
            Set of all transitive dependencies (not including target)
        """
        dependencies: set[str] = set()
        to_process: list[str] = [target]
        visited: set[str] = {target}

        while to_process:
            current = to_process.pop(0)
            deps = get_dependencies_fn(current)

            for dep in deps:
                if dep not in visited:
                    visited.add(dep)
                    dependencies.add(dep)
                    to_process.append(dep)

        return dependencies

    @staticmethod
    def compute_priority_order(
        files: list[str], get_priority_fn: Callable[[str], int]
    ) -> list[str]:
        """
        Sort files by priority (lower number = higher priority).

        Args:
            files: List of file names
            get_priority_fn: Function that returns priority for a file

        Returns:
            Files sorted by priority, then alphabetically
        """
        return sorted(files, key=lambda f: (get_priority_fn(f), f))

    @staticmethod
    def build_adjacency_list(
        nodes: list[str], get_dependencies_fn: Callable[[str], list[str]]
    ) -> dict[str, list[str]]:
        """
        Build adjacency list representation of graph.

        Args:
            nodes: List of all nodes
            get_dependencies_fn: Function that returns dependencies for a node

        Returns:
            Dict mapping each node to list of its dependents
        """
        adj_list: dict[str, list[str]] = {node: [] for node in nodes}

        for node in nodes:
            for dep in get_dependencies_fn(node):
                if dep in nodes:
                    adj_list[dep].append(node)

        return adj_list
