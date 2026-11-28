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
from cortex.core.constants import MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_metadata import (
    read_plan_status_metadata,
    resolve_plan_status_token,
)
from cortex.tools.plans.completion_transaction_io import hash_text
from cortex.tools.plans.register_helpers import (
    create_register_error_result,
    has_explicit_plan_block,
)

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


def _dependency_resync_status(
    slug: str, graph: ArtifactGraph, current: PlanStatus
) -> PlanStatus:
    # AI: Match register defaults for never-blocked plans; promote BLOCKED→READY when deps clear.
    if current in {PlanStatus.DONE, PlanStatus.IN_PROGRESS, PlanStatus.CANCELLED}:
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
    root: Path,
    path: Path,
    raw: str,
    target: PlanStatus,
    ctx: MCPContext | None,
) -> bool:
    """Persist a dependency transition only from the observed plan revision."""
    updated = replace_plan_frontmatter_status(raw, target)
    try:
        await persist_registered_status(root, path, raw, updated)
        return updated != raw
    except (OSError, ValueError, FileLockTimeoutError) as exc:
        await log_client(
            ctx, "error", f"completion resync: could not write {path}: {exc}"
        )
        return False


def _should_preserve_operator_block(
    completed_slug: str | None,
    dependencies: list[str],
    roadmap: str,
    relative: Path,
) -> bool:
    # AI: Legacy dependency-only roadmap rows also used plain BLOCKED.
    return completed_slug not in dependencies and has_explicit_plan_block(
        roadmap, relative.as_posix()
    )


async def _apply_one_plan_resync_after_completion(
    root: Path,
    slug: str,
    path: Path,
    graph: ArtifactGraph,
    roadmap: str,
    completed_slug: str | None,
    ctx: MCPContext | None,
) -> bool:
    """Resync dependency blocks without clearing an explicit roadmap block."""
    try:
        raw = path.read_bytes().decode("utf-8")
        metadata = read_plan_status_metadata(raw)
        if not metadata.recognized:
            return False
        target = _dependency_resync_status(slug, graph, metadata.status)
        if target == metadata.status:
            return False
        promoted = metadata.status == PlanStatus.BLOCKED and target == PlanStatus.READY
        if promoted:
            dependencies = graph.nodes[slug].depends_on
            if _should_preserve_operator_block(
                completed_slug, dependencies, roadmap, path.relative_to(root)
            ):
                return False
    except (OSError, ValueError) as exc:
        await log_client(
            ctx, "warning", f"completion resync: could not verify {path}: {exc}"
        )
        return False
    wrote = await _persist_resynced_plan_status(root, path, raw, target, ctx)
    return promoted and wrote


async def _resync_from_roadmap(
    root: Path,
    plans_dir: Path,
    roadmap_path: Path,
    completed_slug: str | None,
    ctx: MCPContext | None,
) -> int:
    try:
        roadmap = roadmap_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        roadmap = ""
    except (OSError, UnicodeError) as exc:
        await log_client(
            ctx, "warning", f"completion resync: unreadable roadmap: {exc}"
        )
        return 0
    graph = compute_artifact_graph(plans_dir, include_archive=True)
    unblocked = 0
    for slug, path in list_plan_slug_paths(plans_dir, include_archive=False):
        if await _apply_one_plan_resync_after_completion(
            root, slug, path, graph, roadmap, completed_slug, ctx
        ):
            unblocked += 1
    return unblocked


async def sync_plan_dependency_statuses_after_completion(
    root: Path,
    ctx: MCPContext | None,
    *,
    completed_slug: str | None = None,
) -> int:
    """Recompute dependency-driven statuses, preserving explicit roadmap blocks."""
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    if not plans_dir.is_dir():
        return 0
    roadmap_path = (
        get_cortex_path(root, CortexResourceType.MEMORY_BANK) / MemoryBankFile.ROADMAP
    )
    manager = FileSystemManager(root)
    lock = roadmap_path.with_suffix(".md.lock")
    try:
        await manager.acquire_lock(lock)
    except (OSError, FileLockTimeoutError) as exc:
        await log_client(
            ctx, "warning", f"completion resync: unable to lock roadmap: {exc}"
        )
        return 0
    try:
        return await _resync_from_roadmap(
            root, plans_dir, roadmap_path, completed_slug, ctx
        )
    finally:
        await manager.release_lock(lock)


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
    if metadata.status == PlanStatus.CANCELLED:
        raise ValueError("Cancelled plans cannot be registered in roadmap")
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
