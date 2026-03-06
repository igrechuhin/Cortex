"""Dependency graph for memory bank files with static and dynamic relationships."""

from pathlib import Path

from cortex.linking.parser import LinkParser

from .dependency_graph_export import (
    build_dependency_graph_export,
    build_graph_dict,
    build_mermaid_diagram,
    build_reference_graph,
    build_transclusion_graph,
)
from .dependency_graph_static import (
    STATIC_DEPENDENCIES,
    FileDependencyInfo,
    add_link_to_maps,
    build_dynamic_deps_from_links,
)
from .graph_algorithms import GraphAlgorithms
from .models import (
    GraphDict,
    ReferenceGraph,
    TransclusionGraph,
)

# Re-export for backward compatibility
__all__ = [
    "DependencyGraph",
    "FileDependencyInfo",
    "STATIC_DEPENDENCIES",
]


class DependencyGraph:
    """
    Manages file dependency relationships and loading order.
    Foundation for progressive loading in Phase 4.
    """

    def __init__(self):
        """Initialize dependency graph with static relationships."""
        self.static_deps: dict[str, FileDependencyInfo] = STATIC_DEPENDENCIES.copy()
        self.dynamic_deps: dict[str, list[str]] = {}
        self.link_types: dict[str, dict[str, str]] = {}

    def compute_loading_order(self, files: list[str] | None = None) -> list[str]:
        """Compute optimal loading order using topological sort."""
        if files is None:
            files = list(self.static_deps.keys())
        if self.dynamic_deps:
            from cortex.core.graph_algorithms import GraphAlgorithms

            try:
                topo_order = GraphAlgorithms.topological_sort(
                    files, self.get_dependencies
                )
                if len(topo_order) == len(files):
                    return topo_order
            except Exception as e:
                from cortex.core.logging_config import logger

                logger.debug("Topological sort failed, using priority sort: %s", e)

        def _sort_key(file_name: str) -> tuple[int, str]:
            file_info = self.static_deps.get(file_name)
            priority = file_info.priority if file_info else 999
            return (priority, file_name)

        return sorted(files, key=_sort_key)

    def get_dependencies(self, file_name: str) -> list[str]:
        """Get immediate dependencies for a file."""
        file_info = self.static_deps.get(file_name)
        static = file_info.depends_on if file_info else []
        dynamic = self.dynamic_deps.get(file_name, [])
        return list(set(static + dynamic))

    def get_dependents(self, file_name: str) -> list[str]:
        """Get files that depend on this file."""
        static_dependents = [
            fname
            for fname, info in self.static_deps.items()
            if file_name in info.depends_on
        ]
        dynamic_dependents = [
            fname for fname, deps in self.dynamic_deps.items() if file_name in deps
        ]
        return list(set(static_dependents + dynamic_dependents))

    def get_minimal_context(self, target_file: str) -> list[str]:
        """Get minimal set of files needed to understand target file."""
        needed = GraphAlgorithms.get_transitive_dependencies(
            target_file, self.get_dependencies
        )
        needed.add(target_file)
        loading_order = self.compute_loading_order()
        return [f for f in loading_order if f in needed]

    def get_file_category(self, file_name: str) -> str:
        """Get category of a file."""
        file_info = self.static_deps.get(file_name)
        return file_info.category if file_info else "unknown"

    def get_file_priority(self, file_name: str) -> int:
        """Get loading priority of a file (lower = load earlier)."""
        file_info = self.static_deps.get(file_name)
        return file_info.priority if file_info else 999

    def get_files_by_category(self, category: str) -> list[str]:
        """Get all files in a category."""
        return [
            fname
            for fname, info in self.static_deps.items()
            if info.category == category
        ]

    def add_dynamic_dependency(self, from_file: str, to_file: str) -> None:
        """Add a dynamic dependency (from markdown links/transclusion)."""
        if from_file not in self.dynamic_deps:
            self.dynamic_deps[from_file] = []
        if to_file not in self.dynamic_deps[from_file]:
            self.dynamic_deps[from_file].append(to_file)

    def remove_dynamic_dependency(self, from_file: str, to_file: str) -> None:
        """Remove a dynamic dependency."""
        if from_file in self.dynamic_deps and to_file in self.dynamic_deps[from_file]:
            self.dynamic_deps[from_file].remove(to_file)

    def clear_dynamic_dependencies(self, file_name: str | None = None) -> None:
        """Clear dynamic dependencies for a file or all files."""
        if file_name:
            _ = self.dynamic_deps.pop(file_name, None)
        else:
            self.dynamic_deps.clear()

    def has_circular_dependency(self) -> bool:
        """Check if there are any circular dependencies."""
        visited: set[str] = set()
        rec_stack: set[str] = set()
        for file in self.static_deps.keys():
            if file not in visited:
                if GraphAlgorithms.has_cycle_dfs(
                    file, visited, rec_stack, self.get_dependencies
                ):
                    return True
        return False

    def to_dict(self):
        """Export dependency graph as dictionary (for metadata index)."""
        return build_dependency_graph_export(self)

    def to_mermaid(self) -> str:
        """Export dependency graph as Mermaid diagram."""
        return build_mermaid_diagram(self)

    async def build_from_links(
        self,
        memory_bank_dir: Path,
        link_parser: LinkParser,
    ) -> None:
        """Build dynamic dependency graph from actual links in files."""
        self.dynamic_deps.clear()
        self.link_types.clear()
        dynamic_deps, link_types = await build_dynamic_deps_from_links(
            memory_bank_dir, link_parser
        )
        self.dynamic_deps.update(dynamic_deps)
        self.link_types.update(link_types)

    def add_link_dependency(
        self, source_file: str, target_file: str, link_type: str = "reference"
    ) -> None:
        """Add a dependency from parsed link."""
        add_link_to_maps(
            self.dynamic_deps, self.link_types, source_file, target_file, link_type
        )

    def get_link_type(self, source_file: str, target_file: str) -> str | None:
        """Get the type of link between two files."""
        return self.link_types.get(source_file, {}).get(target_file)

    def get_transclusion_order(self, start_file: str) -> list[str]:
        """Get order for resolving transclusions (topological on transclusion links)."""

        def get_transclusion_neighbors(node: str) -> list[str]:
            if node not in self.link_types:
                return []
            return [
                target
                for target, lt in self.link_types[node].items()
                if lt == "transclusion"
            ]

        reachable = GraphAlgorithms.get_reachable_nodes(
            start_file, get_transclusion_neighbors
        )
        return GraphAlgorithms.topological_sort(list(reachable), self.get_dependencies)

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular dependencies in the graph."""
        all_files = set(self.static_deps.keys()) | set(self.dynamic_deps.keys())
        return GraphAlgorithms.detect_cycles(list(all_files), self.get_dependencies)

    def get_all_files(self) -> list[str]:
        """Get all files known to the dependency graph."""
        return list(set(self.static_deps.keys()) | set(self.dynamic_deps.keys()))

    def get_transclusion_graph(self) -> TransclusionGraph:
        """Get a graph containing only transclusion links."""
        return build_transclusion_graph(self)

    def get_reference_graph(self) -> ReferenceGraph:
        """Get a graph containing only reference links."""
        return build_reference_graph(self)

    def get_graph_dict(self) -> GraphDict:
        """Get dependency graph in format expected by reorganization planner."""
        return build_graph_dict(self)
