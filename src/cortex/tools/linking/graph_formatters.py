"""Formatters and helpers for link graph output.

Extracted from graph_operations to keep the main module under 400 lines.
"""

import json
from typing import cast

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.models import JsonValue, ModelDict
from cortex.tools.response_builder import success_response


def generate_mermaid_response(
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
        success_response(
            format="mermaid",
            diagram=mermaid,
            cycles=cast(JsonValue, cycles),
        ),
        indent=2,
    )


def calculate_link_summary(
    link_graph: DependencyGraph, cycles: list[list[str]]
) -> dict[str, int | bool]:
    """Calculate link summary statistics.

    Args:
        link_graph: Dependency graph instance
        cycles: Detected cycles

    Returns:
        Summary dictionary
    """
    reference_links, transclusion_links = count_links_by_type(link_graph)

    return {
        "total_files": len(link_graph.get_all_files()),
        "total_links": reference_links + transclusion_links,
        "reference_links": reference_links,
        "transclusion_links": transclusion_links,
        "has_cycles": len(cycles) > 0,
        "cycle_count": len(cycles),
    }


def count_links_by_type(link_graph: DependencyGraph) -> tuple[int, int]:
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


def generate_json_response(
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

    summary = calculate_link_summary(link_graph, cycles)

    return json.dumps(
        success_response(
            format="json",
            **graph_data,
            cycles=cast(JsonValue, cycles),
            summary=cast(JsonValue, summary),
        ),
        indent=2,
    )
