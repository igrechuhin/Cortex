"""Export and diagram helpers for dependency graph (to_dict, to_mermaid, graph views)."""

from typing import Protocol

from .dependency_graph_static import (
    FileDependencyInfo,
    build_dependency_nodes,
    create_dependency_edge,
)
from .models import (
    DependencyGraph as DependencyGraphExport,
)
from .models import (
    FileDependencyDetail,
    GraphDict,
    ReferenceEdge,
    ReferenceGraph,
    TransclusionEdge,
    TransclusionGraph,
    TransclusionNode,
)


class _DependencyGraphView(Protocol):
    """Protocol for graph instance used by export helpers."""

    @property
    def static_deps(self) -> dict[str, FileDependencyInfo]: ...
    @property
    def dynamic_deps(self) -> dict[str, list[str]]: ...
    @property
    def link_types(self) -> dict[str, dict[str, str]]: ...

    def get_dependencies(self, file_name: str) -> list[str]: ...
    def get_dependents(self, file_name: str) -> list[str]: ...
    def get_file_priority(self, file_name: str) -> int: ...
    def compute_loading_order(self, files: list[str] | None) -> list[str]: ...
    def get_all_files(self) -> list[str]: ...


def build_dependency_graph_export(graph: _DependencyGraphView) -> DependencyGraphExport:
    """Build DependencyGraph export model (nodes, edges, loading order)."""
    nodes = build_dependency_nodes(graph.static_deps)
    all_files = set(graph.static_deps.keys()) | set(graph.dynamic_deps.keys())
    all_dependencies = {
        file_name: graph.get_dependencies(file_name) for file_name in all_files
    }
    edges = [
        create_dependency_edge(
            file_name, dep, graph.dynamic_deps, graph.get_file_priority
        )
        for file_name, deps in all_dependencies.items()
        for dep in deps
    ]
    return DependencyGraphExport(
        nodes=nodes,
        edges=edges,
        progressive_loading_order=graph.compute_loading_order(None),
    )


def build_mermaid_diagram(graph: _DependencyGraphView) -> str:
    """Build Mermaid flowchart string for the dependency graph."""
    lines = ["flowchart TD"]
    _add_mermaid_nodes(lines, graph.static_deps)
    _add_mermaid_edges(lines, graph)
    _add_mermaid_styling(lines)
    return "\n".join(lines)


def _add_mermaid_nodes(
    lines: list[str], static_deps: dict[str, FileDependencyInfo]
) -> None:
    """Add nodes to Mermaid diagram."""

    def _format_node(file_name: str, category: str) -> str:
        node_id = file_name.replace(".md", "").replace("-", "")
        label = file_name.replace(".md", "")
        style_map = {
            "meta": f'    {node_id}["{label}"]:::meta',
            "foundation": f'    {node_id}["{label}"]:::foundation',
            "active": f'    {node_id}["{label}"]:::active',
        }
        return style_map.get(category, f'    {node_id}["{label}"]')

    for file_name, info in static_deps.items():
        lines.append(_format_node(file_name, info.category))


def _add_mermaid_edges(lines: list[str], graph: _DependencyGraphView) -> None:
    """Add edges to Mermaid diagram."""
    all_dependencies = {
        file_name: graph.get_dependencies(file_name)
        for file_name in graph.static_deps.keys()
    }
    for file_name, deps in all_dependencies.items():
        for dep in deps:
            dep_id = dep.replace(".md", "").replace("-", "")
            file_id = file_name.replace(".md", "").replace("-", "")
            lines.append(f"    {dep_id} --> {file_id}")


def _add_mermaid_styling(lines: list[str]) -> None:
    """Add styling to Mermaid diagram."""
    lines.extend(
        [
            "",
            "    classDef meta fill:#e1f5ff,stroke:#01579b",
            "    classDef foundation fill:#fff9c4,stroke:#f57f17",
            "    classDef active fill:#f3e5f5,stroke:#4a148c",
        ]
    )


def build_transclusion_graph(graph: _DependencyGraphView) -> TransclusionGraph:
    """Build TransclusionGraph from graph state."""
    all_files = graph.get_all_files()
    nodes = [TransclusionNode(file=file) for file in all_files]
    edges = [
        TransclusionEdge(
            **{"from": target_file, "to": source_file, "type": "transclusion"}
        )
        for source_file in all_files
        if source_file in graph.link_types
        for target_file, link_type in graph.link_types[source_file].items()
        if link_type == "transclusion"
    ]
    return TransclusionGraph(nodes=nodes, edges=edges)


def build_reference_graph(graph: _DependencyGraphView) -> ReferenceGraph:
    """Build ReferenceGraph from graph state."""
    all_files = graph.get_all_files()
    nodes = [TransclusionNode(file=file) for file in all_files]
    edges = [
        ReferenceEdge(**{"from": source_file, "to": target_file, "type": "reference"})
        for source_file in all_files
        if source_file in graph.link_types
        for target_file, link_type in graph.link_types[source_file].items()
        if link_type == "reference"
    ]
    return ReferenceGraph(nodes=nodes, edges=edges)


def build_graph_dict(graph: _DependencyGraphView) -> GraphDict:
    """Build GraphDict (dependencies map) from graph state."""
    dependencies: dict[str, FileDependencyDetail] = {}
    for file_name in graph.get_all_files():
        deps = graph.get_dependencies(file_name)
        dependents = graph.get_dependents(file_name)
        dependencies[file_name] = FileDependencyDetail(
            depends_on=deps,
            dependents=dependents,
        )
    return GraphDict(dependencies=dependencies)
