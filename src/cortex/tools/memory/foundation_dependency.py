"""
Dependency Graph Tool

This module provides the get_dependency_graph tool for visualizing
Memory Bank file dependencies.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.dependency_graph import DependencyGraph, FileDependencyInfo
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_resource_wrapper,
    mcp_tool_wrapper,
)
from cortex.core.models import JsonValue, ModelDict
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers import initialization
from cortex.managers.utils import get_manager
from cortex.tools.response_builder import error_response, success_response


# Tool consolidated into query_memory_bank (Phase 50); kept as callable for dispatch.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_dependency_graph(
    format: str = "json",
    ctx: MCPContext | None = None,
) -> str:
    """Get the Memory Bank dependency graph.

    USE WHEN: User asks about file dependencies, user needs to understand
    file relationships, user wants to see transclusion tree, user requests
    dependency visualization.

    EXAMPLES: 'get dependency graph', 'show file dependencies', 'what files
    depend on projectBrief.md', 'visualize transclusion tree'.

    RETURNS: JSON graph structure with nodes (files) and edges
    (dependencies/transclusions).

    Shows relationships between files and their loading priority. The graph
    is built from static dependencies (projectBrief → other files) and
    dynamic dependencies (markdown links and transclusions).

    Args:
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

    Example (Error):
        ```json
        {
          "status": "error",
          "error": "<exception message>",
          "error_type": "ValueError"
        }
        ```

    Note:
        The loading order is computed using topological sort and respects
        both static priorities and dependency relationships.
    """
    await log_client(
        ctx, "info", "get_dependency_graph: starting", logger_name=__name__
    )
    try:
        root = await resolve_project_root_async(None, ctx)
        out = await _get_dependency_graph_impl(root, format)
        await log_client(
            ctx, "info", "get_dependency_graph: completed", logger_name=__name__
        )
        return out
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"get_dependency_graph: failed: {e}",
            logger_name=__name__,
        )
        return json.dumps(
            error_response(error=str(e), error_type=type(e).__name__),
            indent=2,
        )


# MCP resource registration removed
@ensure_usage_context
@mcp_resource_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def get_dependency_graph_resource() -> str:
    """Resource: Dependency graph (default params). Read via cortex://memory-bank/dependency-graph."""
    return await get_dependency_graph(format="json")


async def _get_dependency_graph_impl(root: Path, format: str) -> str:
    """Build dependency graph and return JSON string."""
    try:
        mgrs = await initialization.get_managers(root)
        dep_graph = await get_manager(mgrs, "graph", DependencyGraph)
    except Exception:
        dep_graph = DependencyGraph()

    if format == "mermaid":
        diagram = dep_graph.to_mermaid()
        return json.dumps(
            success_response(format="mermaid", diagram=diagram),
            indent=2,
        )
    graph_data = build_graph_data(dep_graph.static_deps)
    return json.dumps(
        success_response(
            format="json",
            graph=graph_data,
            loading_order=cast(JsonValue, dep_graph.compute_loading_order()),
        ),
        indent=2,
    )


def build_graph_data(static_deps: dict[str, FileDependencyInfo]) -> ModelDict:
    """Build graph data dictionary from static dependencies.

    Args:
        static_deps: Static dependencies dictionary

    Returns:
        Graph data dictionary
    """
    files_data: dict[str, ModelDict] = {}
    for name, info in static_deps.items():
        dependencies: list[JsonValue] = [cast(JsonValue, d) for d in info.depends_on]
        files_data[name] = {"priority": info.priority, "dependencies": dependencies}
    return {"files": cast(JsonValue, files_data)}
