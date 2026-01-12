"""Dependency graph for memory bank files with static and dynamic relationships."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from .async_file_utils import open_async_text_file
from .graph_algorithms import GraphAlgorithms

if TYPE_CHECKING:
    from cortex.linking.link_parser import LinkParser


class FileDependencyInfo(TypedDict):
    """Type definition for file dependency information."""

    depends_on: list[str]
    priority: int
    category: str


# Static dependency hierarchy based on template structure
STATIC_DEPENDENCIES: dict[str, FileDependencyInfo] = {
    "memorybankinstructions.md": {
        "depends_on": [],
        "priority": 0,  # Always load first
        "category": "meta",
    },
    "projectBrief.md": {
        "depends_on": [],
        "priority": 1,  # Foundation
        "category": "foundation",
    },
    "productContext.md": {
        "depends_on": ["projectBrief.md"],
        "priority": 2,  # Context layer
        "category": "context",
    },
    "systemPatterns.md": {
        "depends_on": ["projectBrief.md"],
        "priority": 2,
        "category": "context",
    },
    "techContext.md": {
        "depends_on": ["projectBrief.md"],
        "priority": 2,
        "category": "context",
    },
    "activeContext.md": {
        "depends_on": ["productContext.md", "systemPatterns.md", "techContext.md"],
        "priority": 3,  # Active work
        "category": "active",
    },
    "progress.md": {
        "depends_on": ["activeContext.md"],
        "priority": 4,  # Status
        "category": "status",
    },
}


class DependencyGraph:
    """
    Manages file dependency relationships and loading order.
    Foundation for progressive loading in Phase 4.
    """

    def __init__(self):
        """Initialize dependency graph with static relationships."""
        self.static_deps: dict[str, FileDependencyInfo] = STATIC_DEPENDENCIES.copy()
        # Dynamic dependencies will be added in Phase 2 (from markdown links)
        self.dynamic_deps: dict[str, list[str]] = {}
        # Track link types (reference vs transclusion)
        self.link_types: dict[str, dict[str, str]] = (
            {}
        )  # {from_file: {to_file: "reference"|"transclusion"}}

    def compute_loading_order(self, files: list[str] | None = None) -> list[str]:
        """
        Compute optimal loading order using topological sort.

        Args:
            files: List of file names to order. If None, orders all known files.

        Returns:
            Files in order where dependencies are loaded first.
        """
        if files is None:
            files = list(self.static_deps.keys())

        # If we have dynamic dependencies, use topological sort
        if self.dynamic_deps:
            from cortex.core.graph_algorithms import GraphAlgorithms

            try:
                topo_order = GraphAlgorithms.topological_sort(
                    files, self.get_dependencies
                )
                # If topological sort succeeded, use it
                if len(topo_order) == len(files):
                    return topo_order
            except Exception as e:
                # Fall back to priority sort if topological sort fails
                from cortex.core.logging_config import logger

                logger.debug(f"Topological sort failed, using priority sort: {e}")

        # Sort by priority, then alphabetically for stability
        sorted_files = sorted(
            files,
            key=lambda f: (
                self.static_deps.get(f, {}).get("priority", 999),
                f,
            ),
        )

        return sorted_files

    def get_dependencies(self, file_name: str) -> list[str]:
        """
        Get immediate dependencies for a file.

        Args:
            file_name: Name of file to get dependencies for

        Returns:
            List of file names that this file depends on
        """
        # Static dependencies
        file_info = self.static_deps.get(file_name)
        static = file_info.get("depends_on", []) if file_info else []

        # Dynamic dependencies (Phase 2+)
        dynamic = self.dynamic_deps.get(file_name, [])

        # Combine and deduplicate
        return list(set(static + dynamic))

    def get_dependents(self, file_name: str) -> list[str]:
        """
        Get files that depend on this file.

        Args:
            file_name: Name of file to find dependents for

        Returns:
            List of file names that depend on this file
        """
        # Check static dependencies
        static_dependents = [
            fname
            for fname, info in self.static_deps.items()
            if file_name in info["depends_on"]
        ]

        # Check dynamic dependencies (Phase 2+)
        dynamic_dependents = [
            fname for fname, deps in self.dynamic_deps.items() if file_name in deps
        ]

        return list(set(static_dependents + dynamic_dependents))

    def get_minimal_context(self, target_file: str) -> list[str]:
        """
        Get minimal set of files needed to understand target file.
        Foundation for smart context selection in Phase 4.

        Uses depth-first search to find all transitive dependencies.

        Args:
            target_file: File to get context for

        Returns:
            List of files needed (including target), in loading order
        """
        # Get all transitive dependencies
        needed = GraphAlgorithms.get_transitive_dependencies(
            target_file, self.get_dependencies
        )
        needed.add(target_file)

        # Return in proper loading order
        loading_order = self.compute_loading_order()
        return [f for f in loading_order if f in needed]

    def get_file_category(self, file_name: str) -> str:
        """
        Get category of a file.

        Args:
            file_name: Name of file

        Returns:
            Category: meta, foundation, context, active, or status
        """
        file_info = self.static_deps.get(file_name)
        return file_info["category"] if file_info else "unknown"

    def get_file_priority(self, file_name: str) -> int:
        """
        Get loading priority of a file (lower = load earlier).

        Args:
            file_name: Name of file

        Returns:
            Priority number (0 = highest priority)
        """
        file_info = self.static_deps.get(file_name)
        return file_info["priority"] if file_info else 999

    def get_files_by_category(self, category: str) -> list[str]:
        """
        Get all files in a category.

        Args:
            category: Category to filter by (meta, foundation, context, active, status)

        Returns:
            List of file names in that category
        """
        return [
            fname
            for fname, info in self.static_deps.items()
            if info["category"] == category
        ]

    def add_dynamic_dependency(self, from_file: str, to_file: str):
        """
        Add a dynamic dependency (Phase 2+ - from markdown links/transclusion).

        Args:
            from_file: File that has the dependency
            to_file: File that is depended upon
        """
        if from_file not in self.dynamic_deps:
            self.dynamic_deps[from_file] = []

        if to_file not in self.dynamic_deps[from_file]:
            self.dynamic_deps[from_file].append(to_file)

    def remove_dynamic_dependency(self, from_file: str, to_file: str):
        """
        Remove a dynamic dependency.

        Args:
            from_file: File that has the dependency
            to_file: File that is depended upon
        """
        if from_file in self.dynamic_deps:
            if to_file in self.dynamic_deps[from_file]:
                self.dynamic_deps[from_file].remove(to_file)

    def clear_dynamic_dependencies(self, file_name: str | None = None):
        """
        Clear dynamic dependencies for a file or all files.

        Args:
            file_name: File to clear dependencies for. If None, clears all.
        """
        if file_name:
            _ = self.dynamic_deps.pop(file_name, None)
        else:
            self.dynamic_deps.clear()

    def has_circular_dependency(self) -> bool:
        """
        Check if there are any circular dependencies.
        Important for Phase 2+ when dynamic links are added.

        Returns:
            True if circular dependency detected
        """
        visited: set[str] = set()
        rec_stack: set[str] = set()

        for file in self.static_deps.keys():
            if file not in visited:
                if GraphAlgorithms.has_cycle_dfs(
                    file, visited, rec_stack, self.get_dependencies
                ):
                    return True

        return False

    def to_dict(self) -> dict[str, object]:
        """
        Export dependency graph as dictionary (for metadata index).

        Returns:
            Dict representation of graph with nodes and edges
        """
        nodes = _build_dependency_nodes(self.static_deps)

        # Optimize: Pre-compute all dependencies once instead of calling get_dependencies in loop
        all_files = set(self.static_deps.keys()) | set(self.dynamic_deps.keys())
        all_dependencies = {
            file_name: self.get_dependencies(file_name) for file_name in all_files
        }

        # Build edges using pre-computed dependencies
        edges: list[dict[str, object]] = [
            _create_dependency_edge(
                file_name, dep, self.dynamic_deps, self.get_file_priority
            )
            for file_name, deps in all_dependencies.items()
            for dep in deps
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "progressive_loading_order": self.compute_loading_order(),
        }

    def to_mermaid(self) -> str:
        """
        Export dependency graph as Mermaid diagram.

        Returns:
            Mermaid flowchart syntax
        """
        lines = ["flowchart TD"]
        self._add_mermaid_nodes(lines)
        self._add_mermaid_edges(lines)
        self._add_mermaid_styling(lines)
        return "\n".join(lines)

    def _add_mermaid_nodes(self, lines: list[str]) -> None:
        """Add nodes to Mermaid diagram."""

        def _format_node(file_name: str, category: str) -> str:
            """Format a single node line."""
            node_id = file_name.replace(".md", "").replace("-", "")
            label = file_name.replace(".md", "")
            style_map = {
                "meta": f'    {node_id}["{label}"]:::meta',
                "foundation": f'    {node_id}["{label}"]:::foundation',
                "active": f'    {node_id}["{label}"]:::active',
            }
            return style_map.get(category, f'    {node_id}["{label}"]')

        node_lines = [
            _format_node(file_name, info["category"])
            for file_name, info in self.static_deps.items()
        ]
        lines.extend(node_lines)

    def _add_mermaid_edges(self, lines: list[str]) -> None:
        """Add edges to Mermaid diagram."""
        all_dependencies = {
            file_name: self.get_dependencies(file_name)
            for file_name in self.static_deps.keys()
        }
        edge_lines = [
            f"    {dep.replace('.md', '').replace('-', '')} --> {file_name.replace('.md', '').replace('-', '')}"
            for file_name, deps in all_dependencies.items()
            for dep in deps
        ]
        lines.extend(edge_lines)

    def _add_mermaid_styling(self, lines: list[str]) -> None:
        """Add styling to Mermaid diagram."""
        lines.extend(
            [
                "",
                "    classDef meta fill:#e1f5ff,stroke:#01579b",
                "    classDef foundation fill:#fff9c4,stroke:#f57f17",
                "    classDef active fill:#f3e5f5,stroke:#4a148c",
            ]
        )

    # Phase 2: Dynamic link-based dependency methods

    async def build_from_links(
        self,
        memory_bank_dir: Path,
        link_parser: "LinkParser",
    ) -> None:
        """
        Build dynamic dependency graph from actual links in files.

        Scans all markdown files, parses links, and builds dynamic graph.
        This replaces or augments the static DEPENDENCY_HIERARCHY.

        Args:
            memory_bank_dir: Path to memory-bank directory
            link_parser: LinkParser instance for parsing files
        """
        self.dynamic_deps.clear()
        self.link_types.clear()
        md_files = list(memory_bank_dir.glob("*.md"))
        for file_path in md_files:
            await self._process_file_links(file_path, link_parser)

    async def _process_file_links(
        self, file_path: Path, link_parser: "LinkParser"
    ) -> None:
        """Process links in a single file."""
        try:
            async with open_async_text_file(file_path, "r", "utf-8") as f:
                content = await f.read()
            parsed: dict[str, list[dict[str, object]]] = await link_parser.parse_file(
                content
            )
            markdown_links = parsed.get("markdown_links", [])
            transclusions = parsed.get("transclusions", [])
            for link in markdown_links:
                target_raw: object = link.get("target")
                if target_raw and isinstance(target_raw, str):
                    self.add_link_dependency(
                        file_path.name, target_raw, link_type="reference"
                    )
            for trans in transclusions:
                trans_target_raw: object = trans.get("target")
                if trans_target_raw and isinstance(trans_target_raw, str):
                    self.add_link_dependency(
                        file_path.name, trans_target_raw, link_type="transclusion"
                    )
        except Exception as e:
            # Skip files that can't be processed
            from cortex.core.logging_config import logger

            logger.warning(f"Failed to parse links from {file_path}: {e}")

    def add_link_dependency(
        self, source_file: str, target_file: str, link_type: str = "reference"
    ):
        """
        Add a dependency from parsed link.

        Args:
            source_file: File containing the link
            target_file: File being linked to
            link_type: "reference" or "transclusion"
        """
        # Add to dynamic dependencies
        if source_file not in self.dynamic_deps:
            self.dynamic_deps[source_file] = []

        if target_file not in self.dynamic_deps[source_file]:
            self.dynamic_deps[source_file].append(target_file)

        # Track link type
        if source_file not in self.link_types:
            self.link_types[source_file] = {}
        self.link_types[source_file][target_file] = link_type

    def get_link_type(self, source_file: str, target_file: str) -> str | None:
        """
        Get the type of link between two files.

        Args:
            source_file: File containing the link
            target_file: File being linked to

        Returns:
            "reference", "transclusion", or None if no link exists
        """
        return self.link_types.get(source_file, {}).get(target_file)

    def get_transclusion_order(self, start_file: str) -> list[str]:
        """
        Get order for resolving transclusions.

        Returns files in order such that dependencies are resolved first.
        Uses topological sort on transclusion dependencies only.

        Args:
            start_file: File to start from

        Returns:
            List of files in resolution order
        """

        # Get all files reachable via transclusion links
        def get_transclusion_neighbors(node: str) -> list[str]:
            if node not in self.link_types:
                return []
            return [
                target
                for target, link_type in self.link_types[node].items()
                if link_type == "transclusion"
            ]

        reachable = GraphAlgorithms.get_reachable_nodes(
            start_file, get_transclusion_neighbors
        )

        # Topological sort on these files
        return GraphAlgorithms.topological_sort(list(reachable), self.get_dependencies)

    def detect_cycles(self) -> list[list[str]]:
        """
        Detect circular dependencies in the graph.

        Returns:
            List of cycles, each as a list of files forming the cycle
        """
        all_files = set(self.static_deps.keys()) | set(self.dynamic_deps.keys())
        return GraphAlgorithms.detect_cycles(list(all_files), self.get_dependencies)

    def get_all_files(self) -> list[str]:
        """
        Get all files known to the dependency graph.

        Returns:
            List of all file names (both static and dynamic)
        """
        return list(set(self.static_deps.keys()) | set(self.dynamic_deps.keys()))

    def get_transclusion_graph(self) -> dict[str, object]:
        """
        Get a graph containing only transclusion links.

        Returns:
            Dict with nodes and edges for transclusion relationships
        """
        all_files = self.get_all_files()

        # Optimize: Build nodes list in one pass
        nodes: list[dict[str, object]] = [{"file": file} for file in all_files]

        # Optimize: Build edges list using list comprehension
        edges: list[dict[str, object]] = [
            {"from": target_file, "to": source_file, "type": "transclusion"}
            for source_file in all_files
            if source_file in self.link_types
            for target_file, link_type in self.link_types[source_file].items()
            if link_type == "transclusion"
        ]

        return {"nodes": nodes, "edges": edges}

    def get_reference_graph(self) -> dict[str, object]:
        """
        Get a graph containing only reference links.

        Returns:
            Dict with nodes and edges for reference relationships
        """
        all_files = self.get_all_files()

        # Optimize: Build nodes list in one pass
        nodes: list[dict[str, object]] = [{"file": file} for file in all_files]

        # Optimize: Build edges list using list comprehension
        edges: list[dict[str, object]] = [
            {"from": source_file, "to": target_file, "type": "reference"}
            for source_file in all_files
            if source_file in self.link_types
            for target_file, link_type in self.link_types[source_file].items()
            if link_type == "reference"
        ]

        return {"nodes": nodes, "edges": edges}

    def get_graph_dict(self) -> dict[str, object]:
        """
        Get dependency graph in format expected by reorganization planner.

        Returns:
            Dict with "dependencies" key containing file dependency information
        """
        dependencies: dict[str, dict[str, object]] = {}
        all_files = self.get_all_files()

        for file_name in all_files:
            deps = self.get_dependencies(file_name)
            dependents = self.get_dependents(file_name)
            dependencies[file_name] = {
                "depends_on": deps,
                "dependents": dependents,
            }

        return {"dependencies": dependencies}


def _build_dependency_nodes(
    static_deps: dict[str, FileDependencyInfo],
) -> list[dict[str, object]]:
    """Build node list from static dependencies.

    Args:
        static_deps: Static dependencies dictionary

    Returns:
        List of node dictionaries
    """
    return [
        {
            "file": file_name,
            "priority": info["priority"],
            "category": info["category"],
        }
        for file_name, info in static_deps.items()
    ]


def _create_dependency_edge(
    file_name: str,
    dep: str,
    dynamic_deps: dict[str, list[str]],
    get_file_priority: Callable[[str], int],
) -> dict[str, object]:
    """Create a single dependency edge dictionary.

    Args:
        file_name: Source file name
        dep: Dependency file name
        dynamic_deps: Dynamic dependencies dictionary
        get_file_priority: Function to get priority for a file

    Returns:
        Edge dictionary
    """
    is_dynamic = dep in dynamic_deps.get(file_name, [])
    edge_type = "links" if is_dynamic else "informs"

    from_priority = get_file_priority(file_name)
    to_priority = get_file_priority(dep)
    strength = "strong" if abs(from_priority - to_priority) == 1 else "medium"

    return {
        "from": dep,
        "to": file_name,
        "type": edge_type,
        "strength": strength,
    }
