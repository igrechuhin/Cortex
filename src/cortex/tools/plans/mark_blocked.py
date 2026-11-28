"""Apply an already recorded roadmap block to an existing active plan."""

import hashlib
import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from cortex.core.artifact_graph import compute_artifact_graph
from cortex.core.constants import MemoryBankFile
from cortex.core.context_logging import MCPContext
from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_metadata import read_plan_status_metadata
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.core.usage_context import get_or_resolve_project_root
from cortex.tools.files.document_patch_operations import (
    document_metadata_bytes,
    write_existing_document,
)
from cortex.tools.files.guarded_mutation_evidence import GuardedMutationEvidence
from cortex.tools.files.guarded_operation_outcome import GuardedOperationOutcome
from cortex.tools.files.guarded_operation_refusal import (
    GuardedOperationRefusal,
    validate_guarded_path,
)
from cortex.tools.plans.active_plan_target import require_active_plan_target
from cortex.tools.plans.completion_transaction_io import completion_lock
from cortex.tools.plans.register_helpers import has_explicit_plan_block

_STATUS = re.compile(
    rb"^(?i:status)[ \t]*:[ \t]*(?P<quote>['\"]?)"
    + rb"(?P<status>READY|PENDING|BLOCKED)(?P=quote)"
    + rb"[ \t]*(?:#[^\r\n]*)?\r?$",
    re.M,
)
_TERMINAL_TITLE = re.compile(rb"\((?:DONE|COMPLETE|COMPLETED|CANCELLED)\)", re.I)


class MarkBlockedRequest(BaseModel):
    """Explicit operator intent tied to one exact active plan revision."""

    model_config = ConfigDict(extra=EXTRA_FORBID, strict=True)

    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1)
    dry_run: StrictBool


def _blocked_bytes(
    before: bytes, request: MarkBlockedRequest
) -> tuple[bytes, PlanStatus]:
    if hashlib.sha256(before).hexdigest() != request.expected_sha256:
        raise GuardedOperationRefusal(
            "Stale expected_sha256: plan bytes changed; read again",
            GuardedOperationOutcome.STALE_BASE,
        )
    frontmatter, title = document_metadata_bytes(before)
    if frontmatter is None or (title and _TERMINAL_TITLE.search(title)):
        raise GuardedOperationRefusal("Plan must have active frontmatter and title")
    matches = list(_STATUS.finditer(frontmatter))
    metadata = read_plan_status_metadata(before.decode("utf-8-sig"))
    if (
        len(matches) != 1
        or not metadata.recognized
        or metadata.raw_token != matches[0].group("status").decode()
    ):
        raise GuardedOperationRefusal(
            "Plan must declare one canonical READY, PENDING, or BLOCKED status"
        )
    start, end = matches[0].span("status")
    return before[:start] + b"BLOCKED" + before[end:], metadata.status


def _require_explicit_block(root: Path, roadmap: Path, target: Path) -> None:
    validate_guarded_path(roadmap, root)
    if not has_explicit_plan_block(
        roadmap.read_text(encoding="utf-8"), target.relative_to(root).as_posix()
    ):
        raise GuardedOperationRefusal(
            "Canonical roadmap must contain one explicit BLOCKED row for this plan"
        )
    graph = compute_artifact_graph(target.parent, include_archive=True)
    node = graph.nodes.get(target.stem)
    if node is None or node.blocked_by:
        raise GuardedOperationRefusal(
            "Resolve declared dependency blocks before reconciling an operator block"
        )


def _success_fields(
    relative: str,
    after: bytes,
    previous: PlanStatus,
    request: MarkBlockedRequest,
    evidence: GuardedMutationEvidence,
) -> dict[str, object]:
    return {
        "status": "success",
        "target": relative,
        "before_sha256": request.expected_sha256,
        "after_sha256": hashlib.sha256(after).hexdigest(),
        "previous_status": previous.value,
        "new_status": PlanStatus.BLOCKED.value,
        "reason": request.reason,
        "dry_run": request.dry_run,
        "mutation_performed": evidence.mutation_performed,
    }


async def _block_locked_plan(
    root: Path,
    slug: str | None,
    request: MarkBlockedRequest,
    evidence: GuardedMutationEvidence,
    manager: FileSystemManager,
    roadmap: Path,
    target: Path,
) -> dict[str, object]:
    plan_lock = target.with_suffix(".md.lock")
    validate_guarded_path(plan_lock, root)
    await manager.acquire_lock(plan_lock)
    try:
        target = require_active_plan_target(root, slug)
        relative = target.relative_to(root).as_posix()
        before = evidence.observe(root, target)
        after, previous = _blocked_bytes(before, request)
        _require_explicit_block(root, roadmap, target)
        if before != after and not request.dry_run:
            write_existing_document(root, relative, target, before, after, evidence)
        return _success_fields(relative, after, previous, request, evidence)
    finally:
        await manager.release_lock(plan_lock)


async def _apply_block(
    root: Path,
    slug: str | None,
    request: MarkBlockedRequest,
    evidence: GuardedMutationEvidence,
) -> dict[str, object]:
    target = require_active_plan_target(root, slug)
    _ = _blocked_bytes(evidence.observe(root, target), request)
    roadmap = (
        get_cortex_path(root, CortexResourceType.MEMORY_BANK) / MemoryBankFile.ROADMAP
    )
    lock = roadmap.with_suffix(".md.lock")
    validate_guarded_path(roadmap, root)
    validate_guarded_path(lock, root)
    manager = FileSystemManager(root)
    await manager.acquire_lock(lock)
    try:
        return await _block_locked_plan(
            root, slug, request, evidence, manager, roadmap, target
        )
    finally:
        await manager.release_lock(lock)


async def mark_plan_blocked(
    slug: str | None, content: str | None, ctx: MCPContext | None
) -> str:
    """Reconcile an active plan without granting authority for its work."""
    root = Path(await get_or_resolve_project_root(ctx))
    evidence = GuardedMutationEvidence()
    try:
        if ".." in root.parts or root.absolute() != root.resolve():
            raise GuardedOperationRefusal("Plan project root cannot traverse symlinks")
        request = MarkBlockedRequest.model_validate_json(content or "{}")
        if not request.reason.strip():
            raise GuardedOperationRefusal("Block reason must be nonempty")
        # AI: A completing dependency must finish its graph resync before it
        # can be treated as satisfied by a new operator block.
        async with completion_lock(root):
            result = await _apply_block(root.absolute(), slug, request, evidence)
    except (OSError, ValueError, FileLockTimeoutError) as exc:
        result = evidence.error_fields(exc)
    return json.dumps(
        {"operation": "mark_blocked", "project_root": str(root.absolute()), **result},
        indent=2,
    )
