"""Prepare byte-preserving plan and roadmap edits for cancellation."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.canonical_project import sha256_bytes
from cortex.core.constants import MemoryBankFile
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.plan_identity import build_plan_identity_index
from cortex.core.plan_metadata import read_frontmatter_fields, read_plan_status_metadata
from cortex.tools.files.artifact_migration_links import rewrite_links
from cortex.tools.files.document_patch_operations import document_metadata_bytes
from cortex.tools.models_base import StrictBaseModel
from cortex.tools.plans.completion_transaction_io import (
    read_required_text,
    validate_contained_path,
)
from cortex.tools.plans.completion_transaction_models import (
    CancellationRequest,
    CompletionFileKey,
    PreparedCompletionFile,
)
from cortex.tools.plans.completion_transaction_prepare import plan_archive_paths
from cortex.tools.plans.entries_content import remove_line_at
from cortex.tools.plans.register_helpers import (
    find_live_plan_registration_line,
    unfenced_roadmap_lines,
)

_STATUS = re.compile(
    rb"^status[ \t]*:[ \t]*(?P<quote>['\"]?)(?P<value>[a-z_ -]+?)(?P=quote)"
    + rb"[ \t]*(?:#[^\r\n]*)?\r?$",
    re.IGNORECASE | re.MULTILINE,
)


class PreparedCancellation(StrictBaseModel):
    """Validated paths and byte-preserving edits shared by preview and apply."""

    source: Path
    destination: Path
    files: list[PreparedCompletionFile]
    roadmap_line_removed: int | None


def _validate_identity(source: Path, destination: Path) -> None:
    plans = source.parent
    if destination.exists():
        raise FileExistsError(f"Archive destination already exists: {destination}")
    if any(path != source for path in plans.rglob(source.name)):
        raise ValueError(f"Ambiguous plan identity: multiple paths for {source.stem}")
    row = build_plan_identity_index(plans, include_archive=False).unique.get(
        source.stem
    )
    if row is None or row.path != source:
        raise ValueError("Target must be a real root-level active plan")


def _cancel_status(before: bytes, expected_sha256: str) -> bytes:
    if sha256_bytes(before) != expected_sha256:
        raise ValueError("Stale expected_sha256: plan bytes changed; read again")
    text = before.decode("utf-8-sig")
    metadata = read_plan_status_metadata(text)
    if not metadata.recognized or len(read_frontmatter_fields(text, "status")) != 1:
        raise ValueError("Cancellation requires one recognized frontmatter status")
    if metadata.status == PlanStatus.DONE:
        raise ValueError("Completed plans cannot be archived as cancelled")
    frontmatter, _ = document_metadata_bytes(before)
    matches = list(_STATUS.finditer(frontmatter or b""))
    if len(matches) != 1:
        raise ValueError("Cancellation requires a unique scalar status line")
    start, end = matches[0].span("value")
    return before[:start] + PlanStatus.CANCELLED.value.encode() + before[end:]


def _rewrite_roadmap_references(
    before: str, roadmap: Path, source: Path, destination: Path, root: Path
) -> str:
    linked = rewrite_links(
        before.encode(), roadmap, roadmap, {source: destination}, root
    ).decode()
    # AI: The roadmap can use literal paths and references in inline code.
    suffix = destination.relative_to(source.parent).as_posix()
    pattern = re.compile(
        r"(?<![\w./\\-])(?P<prefix>(?:\.\./|\.?cortex/)?plans/)"
        + re.escape(source.name)
        + r"(?=$|[\s`),.?#:>\]])"
    )
    lines = linked.split("\n")
    for index, line in unfenced_roadmap_lines(lines):
        lines[index] = pattern.sub(lambda match: match["prefix"] + suffix, line)
    return "\n".join(lines)


def rewrite_cancelled_roadmap(
    before: str, roadmap: Path, source: Path, destination: Path, root: Path
) -> tuple[str, int | None]:
    """Remove the exact live registration and update preserved references."""
    line = find_live_plan_registration_line(before, source.relative_to(root).as_posix())
    without_live = before if line is None else remove_line_at(before, line)
    after = _rewrite_roadmap_references(
        without_live, roadmap, source, destination, root
    )
    return after, line


def _prepare_plan(
    root: Path, request: CancellationRequest, source: Path, destination: Path
) -> PreparedCompletionFile:
    validate_contained_path(source, root)
    validate_contained_path(destination, root)
    _validate_identity(source, destination)
    before = read_required_text(source, source.parent, exact=True)
    after_status = _cancel_status(before.encode(), request.expected_sha256)
    after = rewrite_links(
        after_status, source, destination, {source: destination}, root
    )
    return PreparedCompletionFile(
        key=CompletionFileKey.PLAN, path=source, before=before, after=after.decode()
    )


def prepare_cancellation(
    root: Path, request: CancellationRequest
) -> PreparedCancellation:
    """Calculate an archive move and exact-path roadmap update without writing."""
    source, destination = plan_archive_paths(root, request)
    assert source is not None and destination is not None
    plan = _prepare_plan(root, request, source, destination)
    memory = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    roadmap = memory / MemoryBankFile.ROADMAP
    validate_contained_path(roadmap, root)
    roadmap_before = read_required_text(roadmap, memory, exact=True)
    roadmap_after, line = rewrite_cancelled_roadmap(
        roadmap_before, roadmap, source, destination, root
    )
    return PreparedCancellation(
        source=source,
        destination=destination,
        files=[
            plan,
            PreparedCompletionFile(
                key=CompletionFileKey.ROADMAP,
                path=roadmap,
                before=roadmap_before,
                after=roadmap_after,
            ),
        ],
        roadmap_line_removed=line,
    )
