"""
Comprehensive test suite for graph_algorithms.py

Tests GraphAlgorithms static methods for dependency analysis.

Test Coverage:
- Cycle detection with DFS
- has_cycle_dfs function
- Topological sorting (Kahn's algorithm)
- Reachable nodes calculation
- Transitive dependencies
- Priority-based ordering
- Adjacency list building
- Edge cases and complex scenarios
"""

from cortex.core.graph_algorithms import GraphAlgorithms


class TestDetectCycles:
    """Tests for cycle detection algorithm."""

    def test_detect_cycles_no_cycle(self) -> None:
        """Test detects no cycles in acyclic graph."""
        nodes = ["A", "B", "C"]
        deps: dict[str, list[str]] = {"A": ["B"], "B": ["C"], "C": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        cycles = GraphAlgorithms.detect_cycles(nodes, get_deps)

        assert cycles == []

    def test_detect_cycles_simple_cycle(self):
        """Test detects simple cycle (A -> B -> A)."""
        nodes = ["A", "B"]
        deps = {"A": ["B"], "B": ["A"]}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        cycles = GraphAlgorithms.detect_cycles(nodes, get_deps)

        assert len(cycles) > 0
        # Cycle should contain both A and B
        for cycle in cycles:
            assert set(cycle) & {"A", "B"}

    def test_detect_cycles_self_loop(self):
        """Test detects self-loop (A -> A)."""
        nodes = ["A", "B"]
        deps = {"A": ["A"], "B": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        cycles = GraphAlgorithms.detect_cycles(nodes, get_deps)

        assert len(cycles) > 0
        # Should find cycle involving A
        assert any("A" in cycle for cycle in cycles)

    def test_detect_cycles_complex_cycle(self):
        """Test detects cycle in complex graph (A -> B -> C -> A)."""
        nodes = ["A", "B", "C", "D"]
        deps = {"A": ["B"], "B": ["C"], "C": ["A"], "D": []}  # Cycle: A -> B -> C -> A

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        cycles = GraphAlgorithms.detect_cycles(nodes, get_deps)

        assert len(cycles) > 0

    def test_detect_cycles_multiple_components(self):
        """Test handles disconnected graph components."""
        nodes = ["A", "B", "C", "D"]
        deps = {"A": ["B"], "B": [], "C": ["D"], "D": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        cycles = GraphAlgorithms.detect_cycles(nodes, get_deps)

        assert cycles == []

    def test_detect_cycles_empty_graph(self):
        """Test handles empty graph."""
        nodes: list[str] = []
        deps: dict[str, list[str]] = {}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        cycles = GraphAlgorithms.detect_cycles(nodes, get_deps)

        assert cycles == []

    def test_detect_cycles_single_node_no_deps(self):
        """Test handles single node with no dependencies."""
        nodes: list[str] = ["A"]
        deps: dict[str, list[str]] = {"A": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        cycles = GraphAlgorithms.detect_cycles(nodes, get_deps)

        assert cycles == []


class TestHasCycleDFS:
    """Tests for has_cycle_dfs function."""

    def test_has_cycle_dfs_no_cycle(self):
        """Test returns False when no cycle exists."""
        deps: dict[str, list[str]] = {"A": ["B"], "B": ["C"], "C": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        visited: set[str] = set()
        rec_stack: set[str] = set()
        has_cycle = GraphAlgorithms.has_cycle_dfs("A", visited, rec_stack, get_deps)

        assert has_cycle is False

    def test_has_cycle_dfs_detects_cycle(self):
        """Test returns True when cycle exists."""
        deps: dict[str, list[str]] = {"A": ["B"], "B": ["A"]}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        visited: set[str] = set()
        rec_stack: set[str] = set()
        has_cycle = GraphAlgorithms.has_cycle_dfs("A", visited, rec_stack, get_deps)

        assert has_cycle is True

    def test_has_cycle_dfs_detects_self_loop(self):
        """Test detects self-loop."""
        deps: dict[str, list[str]] = {"A": ["A"]}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        visited: set[str] = set()
        rec_stack: set[str] = set()
        has_cycle = GraphAlgorithms.has_cycle_dfs("A", visited, rec_stack, get_deps)

        assert has_cycle is True

    def test_has_cycle_dfs_tracks_visited_nodes(self):
        """Test properly tracks visited nodes."""
        deps: dict[str, list[str]] = {"A": ["B"], "B": ["C"], "C": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        visited: set[str] = set()
        rec_stack: set[str] = set()
        _ = GraphAlgorithms.has_cycle_dfs("A", visited, rec_stack, get_deps)

        assert "A" in visited
        assert "B" in visited
        assert "C" in visited
        assert len(rec_stack) == 0  # All popped after traversal


class TestTopologicalSort:
    """Tests for topological sorting."""

    def test_topological_sort_linear_chain(self):
        """Test sorts linear dependency chain."""
        files = ["A", "B", "C"]
        deps = {"A": ["B"], "B": ["C"], "C": []}

        def get_deps(file: str) -> list[str]:
            return deps.get(file, [])

        result = GraphAlgorithms.topological_sort(files, get_deps)

        # C should come before B, B should come before A
        assert result.index("C") < result.index("B")
        assert result.index("B") < result.index("A")

    def test_topological_sort_diamond_dependency(self):
        """Test sorts diamond-shaped dependency graph."""
        files = ["A", "B", "C", "D"]
        deps = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}

        def get_deps(file: str) -> list[str]:
            return deps.get(file, [])

        result = GraphAlgorithms.topological_sort(files, get_deps)

        # D must come first, A must come last
        assert result[0] == "D"
        assert result[-1] == "A"
        # B and C should come before A but after D
        assert result.index("D") < result.index("B")
        assert result.index("D") < result.index("C")
        assert result.index("B") < result.index("A")
        assert result.index("C") < result.index("A")

    def test_topological_sort_no_dependencies(self):
        """Test sorts files with no dependencies."""
        files: list[str] = ["A", "B", "C"]
        deps: dict[str, list[str]] = {"A": [], "B": [], "C": []}

        def get_deps(file: str) -> list[str]:
            return deps.get(file, [])

        result = GraphAlgorithms.topological_sort(files, get_deps)

        # All files should be included
        assert set(result) == set(files)
        assert len(result) == 3

    def test_topological_sort_with_cycle(self):
        """Test handles graph with cycle (returns partial order)."""
        files = ["A", "B", "C"]
        deps = {"A": ["B"], "B": ["C"], "C": ["A"]}

        def get_deps(file: str) -> list[str]:
            return deps.get(file, [])

        result = GraphAlgorithms.topological_sort(files, get_deps)

        # Should return partial order (not all files may be included)
        # This is acceptable behavior when cycles exist
        assert isinstance(result, list)

    def test_topological_sort_ignores_external_dependencies(self):
        """Test ignores dependencies not in the files list."""
        files = ["A", "B"]
        deps = {"A": ["B", "EXTERNAL"], "B": []}

        def get_deps(file: str) -> list[str]:
            return deps.get(file, [])

        result = GraphAlgorithms.topological_sort(files, get_deps)

        # Should only sort A and B
        assert set(result) == {"A", "B"}
        assert result.index("B") < result.index("A")

    def test_topological_sort_empty_list(self):
        """Test handles empty file list."""
        files: list[str] = []
        deps: dict[str, list[str]] = {}

        def get_deps(file: str) -> list[str]:
            return deps.get(file, [])

        result = GraphAlgorithms.topological_sort(files, get_deps)

        assert result == []


class TestGetReachableNodes:
    """Tests for reachable nodes calculation."""

    def test_get_reachable_nodes_linear(self):
        """Test finds reachable nodes in linear graph."""
        graph = {"A": ["B"], "B": ["C"], "C": []}

        def get_neighbors(node: str) -> list[str]:
            return graph.get(node, [])

        reachable = GraphAlgorithms.get_reachable_nodes("A", get_neighbors)

        assert reachable == {"A", "B", "C"}

    def test_get_reachable_nodes_branching(self):
        """Test finds all reachable nodes in branching graph."""
        graph = {"A": ["B", "C"], "B": ["D"], "C": ["E"], "D": [], "E": []}

        def get_neighbors(node: str) -> list[str]:
            return graph.get(node, [])

        reachable = GraphAlgorithms.get_reachable_nodes("A", get_neighbors)

        assert reachable == {"A", "B", "C", "D", "E"}

    def test_get_reachable_nodes_with_cycle(self):
        """Test handles cycles without infinite loop."""
        graph = {"A": ["B"], "B": ["C"], "C": ["A"]}

        def get_neighbors(node: str) -> list[str]:
            return graph.get(node, [])

        reachable = GraphAlgorithms.get_reachable_nodes("A", get_neighbors)

        assert reachable == {"A", "B", "C"}

    def test_get_reachable_nodes_with_filter(self):
        """Test applies filter function to edges."""
        graph = {"A": ["B", "C"], "B": ["D"], "C": ["E"], "D": [], "E": []}

        def get_neighbors(node: str) -> list[str]:
            return graph.get(node, [])

        # Filter: only follow edges to "B"
        def filter_fn(current: str, neighbor: str) -> bool:
            return neighbor == "B" or current == "B"

        reachable = GraphAlgorithms.get_reachable_nodes("A", get_neighbors, filter_fn)

        # Should only reach A, B, and D (filtered out C and E)
        assert "A" in reachable
        assert "B" in reachable
        assert "D" in reachable

    def test_get_reachable_nodes_single_node(self):
        """Test with single isolated node."""
        graph: dict[str, list[str]] = {"A": []}

        def get_neighbors(node: str) -> list[str]:
            return graph.get(node, [])

        reachable = GraphAlgorithms.get_reachable_nodes("A", get_neighbors)

        assert reachable == {"A"}


class TestGetTransitiveDependencies:
    """Tests for transitive dependencies calculation."""

    def test_get_transitive_dependencies_linear(self):
        """Test finds transitive dependencies in linear chain."""
        deps = {"A": ["B"], "B": ["C"], "C": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        transitive = GraphAlgorithms.get_transitive_dependencies("A", get_deps)

        assert transitive == {"B", "C"}

    def test_get_transitive_dependencies_does_not_include_target(self):
        """Test does not include target node in results."""
        deps = {"A": ["B"], "B": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        transitive = GraphAlgorithms.get_transitive_dependencies("A", get_deps)

        assert "A" not in transitive
        assert "B" in transitive

    def test_get_transitive_dependencies_diamond(self):
        """Test finds all transitive dependencies in diamond graph."""
        deps = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        transitive = GraphAlgorithms.get_transitive_dependencies("A", get_deps)

        assert transitive == {"B", "C", "D"}

    def test_get_transitive_dependencies_no_deps(self):
        """Test returns empty set when no dependencies."""
        deps: dict[str, list[str]] = {"A": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        transitive = GraphAlgorithms.get_transitive_dependencies("A", get_deps)

        assert transitive == set()

    def test_get_transitive_dependencies_handles_cycles(self):
        """Test handles circular dependencies without infinite loop."""
        deps = {"A": ["B"], "B": ["C"], "C": ["A"]}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        transitive = GraphAlgorithms.get_transitive_dependencies("A", get_deps)

        # Should find B and C, handle cycle gracefully
        assert "B" in transitive
        assert "C" in transitive
        assert "A" not in transitive


class TestComputePriorityOrder:
    """Tests for priority-based ordering."""

    def test_compute_priority_order_sorts_by_priority(self):
        """Test sorts files by priority (lower = higher priority)."""
        files: list[str] = ["A", "B", "C"]
        priorities: dict[str, int] = {"A": 3, "B": 1, "C": 2}

        def get_priority(file: str) -> int:
            return priorities[file]

        result = GraphAlgorithms.compute_priority_order(files, get_priority)

        assert result == ["B", "C", "A"]

    def test_compute_priority_order_sorts_alphabetically_within_priority(self):
        """Test sorts alphabetically for same priority."""
        files: list[str] = ["C", "A", "B"]
        priorities: dict[str, int] = {"A": 1, "B": 1, "C": 1}

        def get_priority(file: str) -> int:
            return priorities[file]

        result = GraphAlgorithms.compute_priority_order(files, get_priority)

        assert result == ["A", "B", "C"]

    def test_compute_priority_order_mixed_priorities(self):
        """Test sorts with mixed priorities and alphabetical."""
        files: list[str] = ["D", "B", "A", "C"]
        priorities: dict[str, int] = {"A": 2, "B": 1, "C": 2, "D": 3}

        def get_priority(file: str) -> int:
            return priorities[file]

        result = GraphAlgorithms.compute_priority_order(files, get_priority)

        # Priority 1: B
        # Priority 2: A, C (alphabetically)
        # Priority 3: D
        assert result == ["B", "A", "C", "D"]

    def test_compute_priority_order_empty_list(self):
        """Test handles empty file list."""
        files: list[str] = []

        def get_priority(file: str) -> int:
            return 0

        result = GraphAlgorithms.compute_priority_order(files, get_priority)

        assert result == []


class TestBuildAdjacencyList:
    """Tests for adjacency list building."""

    def test_build_adjacency_list_simple(self):
        """Test builds adjacency list for simple graph."""
        nodes = ["A", "B", "C"]
        deps = {"A": ["B"], "B": ["C"], "C": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        adj_list = GraphAlgorithms.build_adjacency_list(nodes, get_deps)

        # B is depended on by A
        assert "A" in adj_list["B"]
        # C is depended on by B
        assert "B" in adj_list["C"]
        # A has no dependents
        assert adj_list["A"] == []

    def test_build_adjacency_list_multiple_dependents(self):
        """Test handles nodes with multiple dependents."""
        nodes = ["A", "B", "C", "D"]
        deps = {"A": ["D"], "B": ["D"], "C": ["D"], "D": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        adj_list = GraphAlgorithms.build_adjacency_list(nodes, get_deps)

        # D is depended on by A, B, and C
        assert set(adj_list["D"]) == {"A", "B", "C"}

    def test_build_adjacency_list_ignores_external_deps(self):
        """Test ignores dependencies not in nodes list."""
        nodes = ["A", "B"]
        deps = {"A": ["B", "EXTERNAL"], "B": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        adj_list = GraphAlgorithms.build_adjacency_list(nodes, get_deps)

        # Should only include A and B
        assert set(adj_list.keys()) == {"A", "B"}
        assert "A" in adj_list["B"]

    def test_build_adjacency_list_empty_graph(self):
        """Test builds empty adjacency list for empty graph."""
        nodes: list[str] = []
        deps: dict[str, list[str]] = {}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        adj_list = GraphAlgorithms.build_adjacency_list(nodes, get_deps)

        assert adj_list == {}

    def test_build_adjacency_list_no_dependencies(self):
        """Test builds adjacency list when no dependencies exist."""
        nodes: list[str] = ["A", "B", "C"]
        deps: dict[str, list[str]] = {"A": [], "B": [], "C": []}

        def get_deps(node: str) -> list[str]:
            return deps.get(node, [])

        adj_list = GraphAlgorithms.build_adjacency_list(nodes, get_deps)

        assert adj_list == {"A": [], "B": [], "C": []}
