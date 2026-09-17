"""Evidence-gated status repair for unique archived legacy plans."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.context_logging import MCPContext
from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.models import OperationStatus, PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_identity import build_plan_identity_index
from cortex.core.plan_metadata import read_plan_status_metadata
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.tools.models_base import StrictBaseModel
from cortex.tools.plans.completion_transaction_io import (
    completion_lock,
    hash_text,
    validate_contained_path,
)
from cortex.tools.plans.register_artifact_graph import replace_plan_frontmatter_status

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REPAIRABLE = frozenset({PlanStatus.PENDING, PlanStatus.READY, PlanStatus.DONE})


class PlanStatusRepairResult(StrictBaseModel):
    """Reviewable result for one archived plan status repair."""

    status: OperationStatus
    message: str
    relative_path: str | None = None
    previous_status: str | None = None
    current_status: str | None = None
    changed: bool = False
    error: str | None = None


def _error(message: str, *, path: str | None = None) -> str:
    return PlanStatusRepairResult(
        status=OperationStatus.ERROR,
        message="Plan status repair rejected",
        relative_path=path,
        error=message,
    ).model_dump_json()


def _repair_candidate(plans_dir: Path, slug: str) -> tuple[Path | None, str | None]:
    candidates = sorted(plans_dir.rglob(f"{slug}.md"))
    if not candidates:
        return None, f"No plan file with slug '{slug}'"
    if len(candidates) > 1:
        relative = [path.relative_to(plans_dir).as_posix() for path in candidates]
        return None, f"Ambiguous plan slug '{slug}': {', '.join(relative)}"
    candidate = candidates[0]
    row = build_plan_identity_index(plans_dir, include_archive=True).unique.get(slug)
    if row is None or row.path != candidate:
        return None, f"Plan '{slug}' is a symlink, scaffold, or draft"
    return candidate, None


def _validate_repair_target(root: Path, path: Path) -> str | None:
    archive_root = get_cortex_path(root, CortexResourceType.PLANS_ARCHIVE)
    if not path.is_relative_to(archive_root):
        return "Status repair is restricted to archived plans"
    validate_contained_path(path, archive_root)
    if not path.is_file():
        return "Status repair target is not a regular file"
    return None


async def _write_repaired_status(
    manager: FileSystemManager, path: Path, raw: str
) -> bool:
    updated = replace_plan_frontmatter_status(raw, PlanStatus.DONE)
    metadata = read_plan_status_metadata(updated)
    if (
        not metadata.recognized
        or metadata.conflicting
        or metadata.status != PlanStatus.DONE
    ):
        raise ValueError("Status repair could not produce one canonical DONE status")
    if updated == raw:
        return False
    _ = await manager.write_file(path, updated, expected_hash=hash_text(raw))
    return True


async def _repair_resolved_path(
    root: Path, path: Path, manager: FileSystemManager
) -> str:
    relative_path = path.relative_to(root).as_posix()
    target_error = _validate_repair_target(root, path)
    if target_error is not None:
        return _error(target_error, path=relative_path)
    raw = path.read_text(encoding="utf-8")
    metadata = read_plan_status_metadata(raw)
    if not metadata.recognized or metadata.status not in _REPAIRABLE:
        detail = metadata.raw_token or "missing"
        return _error(
            f"Plan status '{detail}' is not eligible for repair", path=relative_path
        )
    if _validate_repair_target(root, path) is not None:
        return _error("Status repair target changed", path=relative_path)
    changed = await _write_repaired_status(manager, path, raw)
    return PlanStatusRepairResult(
        status=OperationStatus.SUCCESS,
        message="Plan status repaired" if changed else "Plan status already DONE",
        relative_path=relative_path,
        previous_status=metadata.status.value,
        current_status=PlanStatus.DONE.value,
        changed=changed,
    ).model_dump_json()


async def repair_archived_plan_status(
    *,
    slug: str | None,
    requested_status: str,
    include_archive: bool,
    ctx: MCPContext | None,
) -> str:
    """Set one uniquely resolved archived eligible legacy plan to DONE."""
    if slug is None or _SLUG_RE.fullmatch(slug) is None:
        return _error("A valid exact slug is required for status repair")
    if not include_archive:
        return _error("Status repair requires include_archive=true")
    if requested_status.strip().upper() != PlanStatus.DONE.value:
        return _error("Status repair only supports the explicit target DONE")
    root = Path(await get_or_resolve_project_root(ctx))
    plans_dir = get_cortex_path(root, CortexResourceType.PLANS)
    try:
        async with completion_lock(root) as (manager, _operations_root):
            path, candidate_error = _repair_candidate(plans_dir, slug)
            if path is None:
                return _error(
                    candidate_error or "Plan status repair target is unavailable"
                )
            return await _repair_resolved_path(root, path, manager)
    except (
        FileConflictError,
        FileLockTimeoutError,
        GitConflictError,
        OSError,
        ValueError,
    ) as exc:
        return _error(str(exc))
