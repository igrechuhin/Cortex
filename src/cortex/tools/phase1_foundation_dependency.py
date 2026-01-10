"""
Dependency Graph Tool

This module provides the get_dependency_graph tool for visualizing
Memory Bank file dependencies.
"""

import json
from typing import cast

from cortex.core.dependency_graph import DependencyGraph, FileDependencyInfo
from cortex.managers.initialization import get_managers, get_project_root
from cortex.server import mcp


@mcp.tool()
async def get_dependency_graph(
    project_root: str | None = None, format: str = "json"
) -> str:
    """Get the Memory Bank dependency graph.

    Shows relationships between files and their loading priority. The graph
    is built from static dependencies (projectBrief → other files) and
    dynamic dependencies (markdown links and transclusions).

    Args:
        project_root: Optional path to project root directory
        format: Output format - "json" or "mermaid" (default: "json")
            - "json": Structured data with files, dependencies, and loading order
            - "mermaid": Mermaid diagram syntax for visualization

    Returns:
        JSON string with dependency graph in requested format.

    Example (JSON format):
        ```json
        {
          "status": "success",
          "format": "json",
          "graph": {
            "files": {
              "projectBrief.md": {
                "priority": 1,
                "dependencies": []
              },
              "activeContext.md": {
                "priority": 2,
                "dependencies": ["projectBrief.md"]
              }
            }
          },
          "loading_order": ["projectBrief.md", "activeContext.md", ...]
        }
        ```

    Example (Mermaid format):
        ```json
        {
          "status": "success",
          "format": "mermaid",
          "diagram": "graph TD\n  projectBrief.md --> activeContext.md\n  ..."
        }
        ```

    Note:
        The loading order is computed using topological sort and respects
        both static priorities and dependency relationships.
    """
    try:
        root = get_project_root(project_root)
        mgrs = await get_managers(root)
        dep_graph = cast(DependencyGraph, mgrs["graph"])

        if format == "mermaid":
            diagram = dep_graph.to_mermaid()
            return json.dumps(
                {"status": "success", "format": "mermaid", "diagram": diagram}, indent=2
            )
        else:
            graph_data = build_graph_data(dep_graph.static_deps)
            return json.dumps(
                {
                    "status": "success",
                    "format": "json",
                    "graph": graph_data,
                    "loading_order": dep_graph.compute_loading_order(),
                },
                indent=2,
            )

    except Exception as e:
        return json.dumps(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            indent=2,
        )


def build_graph_data(static_deps: dict[str, FileDependencyInfo]) -> dict[str, object]:
    """Build graph data dictionary from static dependencies.

    Args:
        static_deps: Static dependencies dictionary

    Returns:
        Graph data dictionary
    """
    return {
        "files": {
            name: {
                "priority": info.get("priority", 0),
                "dependencies": list(info.get("depends_on", [])),
            }
            for name, info in static_deps.items()
        }
    }
