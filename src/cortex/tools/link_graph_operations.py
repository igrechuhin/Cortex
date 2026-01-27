"""Link graph operations for Memory Bank files.

This module contains the get_link_graph MCP tool and its helper functions
for building dependency graphs of Memory Bank file links.
"""

import json
from typing import cast

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.models import ModelDict
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.linking.link_parser import LinkParser
from cortex.managers.initialization import get_managers, get_project_root
from cortex.managers.manager_utils import get_manager
from cortex.server import mcp


@mcp.tool()
async def get_link_graph(
    project_root: str | None = None,
    include_transclusions: bool = True,
    format: str = "json",
) -> str:
    """Build and return a dependency graph showing how Memory Bank files
    reference each other through links.

    Analyzes all Memory Bank files to construct a directed graph where:
    - Nodes represent files in the memory-bank directory
    - Edges represent links between files (markdown links and/or
      transclusions)
    - Edge types distinguish between reference links and transclusion
      dependencies

    The graph includes cycle detection to identify circular dependencies
    that could cause issues during transclusion resolution. Can output in
    JSON format for programmatic use or Mermaid diagram format for
    visualization.

    Args:
        project_root: Optional absolute path to project root directory;
            if None, uses current working directory
        include_transclusions: Whether to include transclusion links in
            the graph (default: True); if False, only markdown reference
            links are included
        format: Output format - "json" for structured data or "mermaid"
            for diagram syntax (default: "json")

    Returns:
        JSON string containing link graph in requested format:
        - status: "success" or "error"
        - format: "json" or "mermaid" indicating output format
        - nodes: List of file nodes with metadata (only in JSON format)
        - edges: List of edges with source, target, type, and metadata
          (only in JSON format)
        - cycles: List of detected circular dependency paths
        - summary: Statistics about graph structure (only in JSON format)
        - diagram: Mermaid diagram syntax string (only in Mermaid format)
        - error: Error message (only if status is "error")
        - error_type: Type of error that occurred (only if status is "error")

    Example (JSON format with cycles):
        ```json
        {
          "status": "success",
          "format": "json",
          "nodes": [
            {
              "id": "activeContext.md",
              "type": "file",
              "exists": true
            },
            {
              "id": "systemPatterns.md",
              "type": "file",
              "exists": true
            },
            {
              "id": "techContext.md",
              "type": "file",
              "exists": true
            }
          ],
          "edges": [
            {
              "source": "activeContext.md",
              "target": "systemPatterns.md",
              "type": "reference",
              "line": 15
            },
            {
              "source": "activeContext.md",
              "target": "techContext.md",
              "type": "transclusion",
              "line": 25
            },
            {
              "source": "systemPatterns.md",
              "target": "techContext.md",
              "type": "reference",
              "line": 42
            }
          ],
          "cycles": [
            [
              "productContext.md",
              "activeContext.md",
              "productContext.md"
            ]
          ],
          "summary": {
            "total_files": 7,
            "total_links": 23,
            "reference_links": 15,
            "transclusion_links": 8,
            "has_cycles": true,
            "cycle_count": 1
          }
        }
        ```

    Example (JSON format without transclusions):
        ```json
        {
          "status": "success",
          "format": "json",
          "nodes": [
            {
              "id": "activeContext.md",
              "type": "file",
              "exists": true
            },
            {
              "id": "systemPatterns.md",
              "type": "file",
              "exists": true
            }
          ],
          "edges": [
            {
              "source": "activeContext.md",
              "target": "systemPatterns.md",
              "type": "reference",
              "line": 15
            }
          ],
          "cycles": [],
          "summary": {
            "total_files": 7,
            "total_links": 15,
            "reference_links": 15,
            "transclusion_links": 0,
            "has_cycles": false,
            "cycle_count": 0
          }
        }
        ```

    Example (Mermaid format):
        ```json
        {
          "status": "success",
          "format": "mermaid",
          "diagram": (
              "graph TD\\n  activeContext[activeContext.md]\\n  "
              "systemPatterns[systemPatterns.md]\\n  "
              "techContext[techContext.md]\\n  "
              "activeContext -->|reference| systemPatterns\\n  "
              "activeContext -.->|transclusion| techContext\\n  "
              "systemPatterns -->|reference| techContext\\n  "
              "style activeContext fill:#e1f5ff\\n  "
              "style systemPatterns fill:#e1f5ff\\n  "
              "style techContext fill:#e1f5ff"
          ),
          "cycles": []
        }
        ```

    Example (Error):
        ```json
        {
          "status": "error",
          "error": "Failed to parse links in systemPatterns.md: Invalid syntax",
          "error_type": "ParseError"
        }
        ```

    Note:
        - Cycles indicate circular dependencies that will cause
          transclusion resolution to fail
        - Reference links (markdown links) are shown with solid arrows
          in Mermaid diagrams
        - Transclusion links are shown with dashed arrows in Mermaid
          diagrams
        - The graph only includes files that exist in the memory-bank
          directory
        - Nodes include an 'exists' flag to identify broken links to
          non-existent files
        - Edge line numbers indicate where in the source file the link
          appears
        - Setting include_transclusions=False is useful for analyzing
          reference structure only
        - The summary includes has_cycles and cycle_count for quick cycle detection
    """
    try:
        link_graph, cycles = await _build_link_graph_data(project_root)

        if format == "mermaid":
            return _generate_mermaid_response(link_graph, cycles)

        return _generate_json_response(link_graph, cycles, include_transclusions)

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


async def _build_link_graph_data(
    project_root: str | None,
) -> tuple[DependencyGraph, list[list[str]]]:
    """Build link graph and detect cycles.

    Args:
        project_root: Optional path to project root

    Returns:
        Tuple of (link_graph, cycles)
    """
    root = get_project_root(project_root)
    mgrs = await get_managers(root)

    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    link_parser = await get_manager(mgrs, "link_parser", LinkParser)
    link_graph = await get_manager(mgrs, "graph", DependencyGraph)

    await link_graph.build_from_links(memory_bank_dir, link_parser)
    cycles = link_graph.detect_cycles()

    return link_graph, cycles


def _generate_mermaid_response(
    link_graph: DependencyGraph, cycles: list[list[str]]
) -> str:
    """Generate mermaid format response.

    Args:
        link_graph: Dependency graph instance
        cycles: Detected cycles

    Returns:
        JSON string with mermaid diagram
    """
    mermaid = link_graph.to_mermaid()

    return json.dumps(
        {
            "status": "success",
            "format": "mermaid",
            "diagram": mermaid,
            "cycles": cycles,
        },
        indent=2,
    )


def _calculate_link_summary(
    link_graph: DependencyGraph, cycles: list[list[str]]
) -> dict[str, int | bool]:
    """Calculate link summary statistics.

    Args:
        link_graph: Dependency graph instance
        cycles: Detected cycles

    Returns:
        Summary dictionary
    """
    reference_links, transclusion_links = _count_links_by_type(link_graph)

    return {
        "total_files": len(link_graph.get_all_files()),
        "total_links": reference_links + transclusion_links,
        "reference_links": reference_links,
        "transclusion_links": transclusion_links,
        "has_cycles": len(cycles) > 0,
        "cycle_count": len(cycles),
    }


def _count_links_by_type(link_graph: DependencyGraph) -> tuple[int, int]:
    """Count reference and transclusion links in the graph.

    Args:
        link_graph: Dependency graph instance

    Returns:
        Tuple of (reference_count, transclusion_count)
    """
    reference_links = 0
    transclusion_links = 0

    for source_file in link_graph.get_all_files():
        if source_file not in link_graph.link_types:
            continue

        ref_count, trans_count = _count_links_for_file(
            link_graph.link_types[source_file]
        )
        reference_links += ref_count
        transclusion_links += trans_count

    return reference_links, transclusion_links


def _count_links_for_file(link_types: dict[str, str]) -> tuple[int, int]:
    """Count reference and transclusion links for a single file.

    Args:
        link_types: Dictionary mapping targets to link types

    Returns:
        Tuple of (reference_count, transclusion_count)
    """
    reference_links = 0
    transclusion_links = 0

    for link_type in link_types.values():
        if link_type == "reference":
            reference_links += 1
        elif link_type == "transclusion":
            transclusion_links += 1

    return reference_links, transclusion_links


def _generate_json_response(
    link_graph: DependencyGraph,
    cycles: list[list[str]],
    include_transclusions: bool,
) -> str:
    """Generate JSON format response.

    Args:
        link_graph: Dependency graph instance
        cycles: Detected cycles
        include_transclusions: Whether to include transclusion links

    Returns:
        JSON string with graph data
    """
    if include_transclusions:
        graph_data = cast(ModelDict, link_graph.to_dict().model_dump(mode="json"))
    else:
        graph_data = cast(
            ModelDict, link_graph.get_reference_graph().model_dump(mode="json")
        )

    summary = _calculate_link_summary(link_graph, cycles)

    return json.dumps(
        {
            "status": "success",
            "format": "json",
            **graph_data,
            "cycles": cycles,
            "summary": summary,
        },
        indent=2,
    )
