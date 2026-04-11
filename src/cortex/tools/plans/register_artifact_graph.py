"""Artifact-graph checks and plan frontmatter updates during roadmap registration."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.artifact_graph import (
    ArtifactGraph,
    compute_artifact_graph,
    list_plan_slug_paths,
    plan_slug_in_dependency_cycle,
    read_plan_status_from_content,
    register_plan_file_status_from_graph,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.register_helpers import create_register_error_result

_FM_STATUS_RE = re.compile(r"^status\s*:\s*.*$", re.MULTILINE | re.IGNORECASE)


def replace_plan_frontmatter_status(content: str, new_status: PlanStatus) -> str:
    """Set or insert ``status`` in the first YAML frontmatter block."""
    if not content.startswith("---"):
        return content
    lines = content.splitlines(keepends=True)
    end: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return content
    head = "".join(lines[: end + 1])
    tail = "".join(lines[end + 1 :])
    replacement = f"status: {new_status.value}"
    updated_head = _FM_STATUS_RE.sub(replacement, head, count=1)
    if updated_head == head:
        insert = "".join(lines[:end]) + f"{replacement}\n" + lines[end]
        return insert + tail
    return updated_head + tail


def _format_cycle_detail(slug: str, graph: ArtifactGraph) -> str:
    labels: list[str] = []
    for comp in graph.cycles:
        if slug in comp:
            labels.append(",".join(sorted(comp)))
    return "; ".join(labels) if labels else slug


def _dependency_cycle_error_json(slug: str, graph: ArtifactGraph) -> str:
    detail = _format_cycle_detail(slug, graph)
    msg = (
        f"Cyclic plan dependencies detected involving '{slug}' ({detail}). "
        + "Resolve the cycle before registering."
    )
    return create_register_error_result(msg).model_dump_json()


async def _warn_unknown_depends_on_targets(
    slug: str, depends_on: list[str], graph: ArtifactGraph, ctx: MCPContext | None
) -> None:
    logger_name = "cortex.tools.plans.register"
    for dep in depends_on:
        if dep not in graph.nodes:
            warn_msg = (
                "register_plan_in_roadmap: depends_on entry "
                + repr(dep)
                + " does not match an existing plan file for "
                + repr(slug)
            )
            await log_client(ctx, "warning", warn_msg, logger_name=logger_name)


async def validate_register_artifact_graph_for_plan(
    root: Path,
    plan_path: Path | None,
    ctx: MCPContext | None,
) -> str | None:
    """Reject registration when the plan sits in a dependency cycle; warn on missing deps."""
    if plan_path is None or not plan_path.is_file():
        return None
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    if not plans_dir.is_dir():
        return None
    graph = compute_artifact_graph(plans_dir)
    slug = plan_path.stem
    if slug not in graph.nodes:
        return None
    if plan_slug_in_dependency_cycle(slug, graph):
        return _dependency_cycle_error_json(slug, graph)
    node = graph.nodes[slug]
    await _warn_unknown_depends_on_targets(slug, node.depends_on, graph, ctx)
    return None


def _graph_and_slug_for_plan_file(
    root: Path, plan_path: Path
) -> tuple[ArtifactGraph, str] | None:
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    if not plans_dir.is_dir():
        return None
    graph = compute_artifact_graph(plans_dir)
    slug = plan_path.stem
    if slug not in graph.nodes:
        return None
    return graph, slug


def _target_plan_status_after_completion_resync(
    slug: str, graph: ArtifactGraph, current: PlanStatus
) -> PlanStatus:
    # AI: Match register defaults for never-blocked plans; promote BLOCKED→READY when deps clear.
    if current == PlanStatus.DONE:
        return PlanStatus.DONE
    if plan_slug_in_dependency_cycle(slug, graph):
        return PlanStatus.BLOCKED
    node = graph.nodes.get(slug)
    if node is None:
        return current
    if node.blocked_by:
        return PlanStatus.BLOCKED
    if current == PlanStatus.IN_PROGRESS:
        return PlanStatus.IN_PROGRESS
    if current == PlanStatus.BLOCKED:
        return PlanStatus.READY
    if current == PlanStatus.READY:
        return PlanStatus.READY
    return PlanStatus.PENDING


async def _persist_resynced_plan_status(
    path: Path,
    raw: str,
    target: PlanStatus,
    ctx: MCPContext | None,
    logger_name: str,
) -> bool:
    """Write frontmatter ``target`` when it changes. Return True on successful write."""
    updated = replace_plan_frontmatter_status(raw, target)
    if updated == raw:
        return False
    try:
        _ = path.write_text(updated, encoding="utf-8")
        return True
    except OSError as exc:
        await log_client(
            ctx,
            "error",
            f"completion resync: could not write {path}: {exc}",
            logger_name=logger_name,
        )
        return False


async def _apply_one_plan_resync_after_completion(
    slug: str,
    path: Path,
    graph: ArtifactGraph,
    ctx: MCPContext | None,
    logger_name: str,
) -> bool:
    """Update one plan file when resync target differs; return True if BLOCKED→READY."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        await log_client(
            ctx,
            "warning",
            f"completion resync: could not read {path}: {exc}",
            logger_name=logger_name,
        )
        return False
    current = read_plan_status_from_content(raw)
    target = _target_plan_status_after_completion_resync(slug, graph, current)
    promoted = current == PlanStatus.BLOCKED and target == PlanStatus.READY
    if target == current:
        return False
    wrote = await _persist_resynced_plan_status(path, raw, target, ctx, logger_name)
    return promoted and wrote


async def sync_plan_dependency_statuses_after_completion(
    root: Path,
    ctx: MCPContext | None,
) -> int:
    """Recompute graph (including archived DONE nodes) and persist dependency-driven status."""
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    if not plans_dir.is_dir():
        return 0
    graph = compute_artifact_graph(plans_dir, include_archive=True)
    unblocked = 0
    logger_name = "cortex.tools.plans.register_artifact_graph"
    for slug, path in list_plan_slug_paths(plans_dir, include_archive=False):
        if await _apply_one_plan_resync_after_completion(
            slug, path, graph, ctx, logger_name
        ):
            unblocked += 1
    return unblocked


async def sync_plan_frontmatter_status_after_register(
    root: Path,
    plan_path: Path | None,
    clarification_blocked: bool,
    ctx: MCPContext | None,
) -> None:
    """Persist dependency/clarification-driven ``status`` into the plan file."""
    if plan_path is None or not plan_path.is_file():
        return
    resolved = _graph_and_slug_for_plan_file(root, plan_path)
    if resolved is None:
        return
    graph, slug = resolved
    new_status = register_plan_file_status_from_graph(
        clarification_blocked=clarification_blocked,
        graph=graph,
        slug=slug,
    )
    try:
        raw = plan_path.read_text(encoding="utf-8")
        updated = replace_plan_frontmatter_status(raw, new_status)
        if updated != raw:
            _ = plan_path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        await log_client(
            ctx,
            "error",
            f"register_plan_in_roadmap: could not update plan status in {plan_path}: {exc}",
            logger_name="cortex.tools.plans.register",
        )
