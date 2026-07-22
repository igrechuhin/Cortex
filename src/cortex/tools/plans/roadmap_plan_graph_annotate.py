"""Annotate roadmap.md reads with live plan-dependency BLOCKED hints."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.artifact_graph import ArtifactGraph, compute_artifact_graph
from cortex.core.path_resolver import CortexResourceType, get_cortex_path

_ROADMAP_PLAN_SLUG = re.compile(r"/plans/([^/\s#?]+)\.md")


def _slug_from_line(line: str) -> str | None:
    match = _ROADMAP_PLAN_SLUG.search(line)
    if match is None:
        return None
    return match.group(1)


def annotate_roadmap_markdown_with_graph(content: str, graph: ArtifactGraph) -> str:
    """Append BLOCKED dependency hints to roadmap lines that reference blocked plans."""
    blocked = set(graph.blocked)
    if not blocked:
        return content
    out_lines: list[str] = []
    raw_lines = content.splitlines()
    for body in raw_lines:
        slug = _slug_from_line(body)
        if slug is not None and slug in blocked:
            node = graph.nodes.get(slug)
            blockers = list(node.blocked_by) if node is not None else []
            if blockers:
                body = f"{body} _(BLOCKED by: {', '.join(blockers)})_"
        out_lines.append(body)
    joined = "\n".join(out_lines)
    if content.endswith("\n"):
        return joined + "\n"
    return joined


def annotate_roadmap_for_project(content: str, project_root: Path) -> str:
    """Load the artifact graph for active plans and annotate roadmap content.

    ``include_archive=True`` so archived dependencies with ``status: DONE``
    are visible to the graph and do not cause false BLOCKED annotations.
    """
    plans_dir = get_cortex_path(project_root, CortexResourceType.PLANS)
    if not plans_dir.is_dir():
        return content
    graph = compute_artifact_graph(plans_dir, include_archive=True)
    return annotate_roadmap_markdown_with_graph(content, graph)
