"""Artifact-graph checks and plan frontmatter updates during roadmap registration."""

from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory

from cortex.core.artifact_graph import (
    ArtifactGraph,
    compute_artifact_graph,
    list_plan_slug_paths,
    plan_slug_in_dependency_cycle,
    register_plan_file_status_from_graph,
)
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.file_system import FileSystemManager
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_metadata import (
    read_plan_status_metadata,
    resolve_plan_status_token,
)
from cortex.tools.plans.completion_transaction_io import hash_text
from cortex.tools.plans.register_helpers import create_register_error_result

_FM_STATUS_RE = re.compile(r"^status\s*:\s*.*$", re.MULTILINE | re.IGNORECASE)


def replace_plan_frontmatter_status(content: str, new_status: PlanStatus) -> str:
    """Set exactly one canonical ``status`` in the first YAML frontmatter block."""
    if not content.startswith("---"):
        return f"---\nstatus: {new_status.value}\n---\n\n{content}"
    lines = content.splitlines(keepends=True)
    end: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return content
    frontmatter = lines[1:end]
    tail = "".join(lines[end + 1 :])
    replacement = f"status: {new_status.value}\n"
    updated: list[str] = []
    inserted = False
    for line in frontmatter:
        if _FM_STATUS_RE.match(line):
            if not inserted:
                updated.append(replacement)
                inserted = True
            continue
        updated.append(line)
    if not inserted:
        updated.append(replacement)
    return "---\n" + "".join(updated) + lines[end] + tail


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
    if current in {PlanStatus.DONE, PlanStatus.IN_PROGRESS}:
        return current
    node = graph.nodes.get(slug)
    if node is None:
        return current
    if current == PlanStatus.BLOCKED and not node.depends_on:
        return current
    if plan_slug_in_dependency_cycle(slug, graph):
        return PlanStatus.BLOCKED
    if node.blocked_by:
        return PlanStatus.BLOCKED
    if current == PlanStatus.BLOCKED and node.depends_on:
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
    metadata = read_plan_status_metadata(raw)
    if not metadata.recognized:
        return False
    current = metadata.status
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


def _dependency_registration_status(root: Path, plan_path: Path, requested: str) -> str:
    resolved = _graph_and_slug_for_plan_file(root, plan_path)
    if resolved is None:
        return requested
    graph, slug = resolved
    proposed = register_plan_file_status_from_graph(
        clarification_blocked=requested.strip().upper() == "BLOCKED",
        graph=graph,
        slug=slug,
    )
    return proposed.value if proposed == PlanStatus.BLOCKED else requested


def resolve_registration_status(
    root: Path, plan_path: Path | None, requested: str
) -> tuple[str, str | None]:
    """Resolve one effective row/frontmatter status from the original plan read."""
    if plan_path is None or not plan_path.is_file():
        return requested, None
    raw = plan_path.read_bytes().decode("utf-8")
    metadata = read_plan_status_metadata(raw)
    if metadata.conflicting:
        raise ValueError(
            "Conflicting plan statuses; resolve metadata before registration"
        )
    if metadata.recognized and metadata.status == PlanStatus.DONE:
        raise ValueError(
            "Completed plans cannot be registered in roadmap; use activeContext.md"
        )
    if not metadata.recognized and metadata.raw_token is not None:
        return metadata.raw_token, raw
    if metadata.status in {
        PlanStatus.IN_PROGRESS,
        PlanStatus.READY,
        PlanStatus.BLOCKED,
    }:
        if resolve_plan_status_token(requested) == metadata.status:
            return requested, raw
        return metadata.status.value.replace("_", " "), raw
    return _dependency_registration_status(root, plan_path, requested), raw


async def sync_plan_frontmatter_status_after_register(
    root: Path,
    plan_path: Path | None,
    status: str,
    expected_content: str | None,
    ctx: MCPContext | None,
) -> str | None:
    """Persist the already-resolved status atomically, rejecting a stale plan read."""
    if plan_path is None or expected_content is None:
        return None
    metadata = read_plan_status_metadata(expected_content)
    target = resolve_plan_status_token(status)
    if target is None or (not metadata.recognized and metadata.raw_token is not None):
        updated = expected_content
    elif metadata.recognized and metadata.status == target:
        updated = expected_content
    else:
        updated = replace_plan_frontmatter_status(expected_content, target)
    try:
        await persist_registered_status(root, plan_path, expected_content, updated)
        return None
    except Exception as exc:
        message = f"Could not update plan status in {plan_path}: {exc}"
        await log_client(ctx, "error", message, logger_name=__name__)
        return message


async def persist_registered_status(
    root: Path, plan_path: Path, before: str, updated: str
) -> None:
    manager = FileSystemManager(root)
    lock = plan_path.with_suffix(plan_path.suffix + ".lock")
    await manager.acquire_lock(lock)
    try:
        if not plan_path.is_file() or hash_text(
            plan_path.read_bytes().decode("utf-8")
        ) != hash_text(before):
            raise ValueError("Plan content changed since registration preparation")
        if updated == before:
            return
        with TemporaryDirectory(dir=plan_path.parent) as staging:
            staged = Path(staging) / plan_path.name
            _ = staged.write_text(updated, encoding="utf-8")
            staged.chmod(plan_path.stat().st_mode)
            _ = staged.replace(plan_path)
    finally:
        await manager.release_lock(lock)
