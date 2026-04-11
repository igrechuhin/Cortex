"""plan(operation=\"graph\") — structured artifact dependency snapshot."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from cortex.core.artifact_graph import ArtifactGraph, compute_artifact_graph
from cortex.core.context_logging import MCPContext
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.tools.models_base import StrictBaseModel


def _empty_str_list() -> list[str]:
    return []


def _empty_cycle_rows() -> list[list[str]]:
    return []


class PlanGraphResult(StrictBaseModel):
    """JSON payload for plan(operation=\"graph\")."""

    status: str = "success"
    ready: list[str] = Field(default_factory=_empty_str_list)
    blocked: dict[str, list[str]] = Field(default_factory=dict)
    in_progress: list[str] = Field(default_factory=_empty_str_list)
    done: list[str] = Field(default_factory=_empty_str_list)
    cycles: list[list[str]] = Field(default_factory=_empty_cycle_rows)
    ascii_dag: str = ""
    message: str | None = None
    error: str | None = None


def _blocked_by_map(graph: ArtifactGraph) -> dict[str, list[str]]:
    detail: dict[str, list[str]] = {}
    for slug in graph.blocked:
        node = graph.nodes.get(slug)
        detail[slug] = list(node.blocked_by) if node is not None else []
    return detail


def _slugs_with_status(graph: ArtifactGraph, wanted: PlanStatus) -> list[str]:
    return sorted(s for s, n in graph.nodes.items() if n.status == wanted)


def render_plan_dependency_edges_ascii(graph: ArtifactGraph, *, max_edges: int) -> str:
    """Render dependent → dependency edges (same order as ``ArtifactGraph.edges``)."""
    if not graph.edges:
        return "(no dependencies)"
    lines: list[str] = []
    for i, (src, dst) in enumerate(graph.edges):
        if i >= max_edges:
            extra = len(graph.edges) - max_edges
            lines.append(f"... ({extra} more edges)")
            break
        lines.append(f"{src} → {dst}")
    return "\n".join(lines)


def build_plan_graph_surface_bundle(
    plans_dir: Path, *, include_archive: bool, max_ascii_edges: int
) -> dict[str, object] | None:
    """Single graph read for session brief, context resource, and roadmap hints."""
    if not plans_dir.is_dir():
        return None
    graph = compute_artifact_graph(plans_dir, include_archive=include_archive)
    blocked_detail: dict[str, list[str]] = {}
    for slug in graph.blocked:
        node = graph.nodes.get(slug)
        blocked_detail[slug] = list(node.blocked_by) if node is not None else []
    blocking_edges = sum(len(v) for v in blocked_detail.values())
    summary = (
        f"{len(graph.ready)} plans READY, {len(graph.blocked)} plans BLOCKED "
        f"by {blocking_edges} outstanding dependency link(s)."
    )
    if graph.cycles:
        summary += f" ({len(graph.cycles)} cycle group(s) in scanned plans.)"
    ascii_edges = render_plan_dependency_edges_ascii(graph, max_edges=max_ascii_edges)
    return {
        "plan_graph_summary": summary,
        "plan_graph_ready": list(graph.ready),
        "plan_graph_blocked": blocked_detail,
        "plan_graph_ascii_edges": ascii_edges,
    }


async def plan_graph_json(ctx: MCPContext | None, *, include_archive: bool) -> str:
    """Compute ``ArtifactGraph`` and return structured JSON for agents and UIs."""
    root_str = await get_or_resolve_project_root(ctx)
    root = Path(root_str)
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    if not plans_dir.is_dir():
        return PlanGraphResult(
            message="Plans directory missing or not a directory",
            ascii_dag="(no plans directory)",
        ).model_dump_json()
    graph = compute_artifact_graph(plans_dir, include_archive=include_archive)
    ascii_dag = render_plan_dependency_edges_ascii(graph, max_edges=80)
    return PlanGraphResult(
        ready=list(graph.ready),
        blocked=_blocked_by_map(graph),
        in_progress=_slugs_with_status(graph, PlanStatus.IN_PROGRESS),
        done=_slugs_with_status(graph, PlanStatus.DONE),
        cycles=[list(c) for c in graph.cycles],
        ascii_dag=ascii_dag,
    ).model_dump_json()
