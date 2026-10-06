"""Contained byte IO and receipt validation for artifact migration."""

from __future__ import annotations

import re
from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.memory.wal import wal_atomic_write_bytes
from cortex.tools.artifacts.artifact_types import get_artifact_directories
from cortex.tools.files.artifact_migration_models import (
    MigrationEdit,
    MigrationPhase,
    MigrationPlan,
    MigrationRecord,
)
from cortex.tools.files.artifact_migration_prepare import (
    byte_hash,
    checked_path,
    legacy_directories,
    preview_digest,
)


def receipt_path(root: Path, digest: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("expected_preview_digest must be a SHA-256 preview digest")
    return (
        get_cortex_path(root, CortexResourceType.SESSION)
        / "artifact-migrations"
        / f"{digest}.json"
    )


def persist(path: Path, record: MigrationRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wal_atomic_write_bytes(
        path.parent, path, record.model_dump_json(indent=2).encode("utf-8")
    )


def read_current(root: Path, relative: str) -> bytes | None:
    path = checked_path(root, relative)
    if path.exists() and not path.is_file():
        raise ValueError(f"Migration target is not a regular file: {relative}")
    return path.read_bytes() if path.exists() else None


def _validate_reference_edit(root: Path, item: MigrationEdit) -> None:
    path = checked_path(root, item.path)
    immutable = get_cortex_path(root, CortexResourceType.WIKI) / "sources"
    forbidden = tuple(
        root / relative
        for relative in (
            ".cortex/history",
            ".cortex/synapse",
            ".cortex/wal",
            ".cortex/.session",
            ".git",
            ".venv",
        )
    )
    if path != get_cortex_path(root, CortexResourceType.INDEX) and (
        path.suffix.lower() != ".md"
        or path.is_relative_to(immutable)
        or any(path.is_relative_to(directory) for directory in forbidden)
    ):
        raise ValueError("Migration receipt edits an unsupported file")
    if item.before is None or item.after is None:
        raise ValueError("Migration reference edit cannot create or delete a file")


def _validate_record_paths(root: Path, plan: MigrationPlan) -> None:
    allowed: set[str] = set()
    pairs = tuple(
        zip(legacy_directories(root), get_artifact_directories(root), strict=True)
    )
    for item in plan.relocations:
        source = checked_path(root, item.source)
        destination = checked_path(root, item.destination)
        if not any(
            source.is_relative_to(old) and destination == new / source.relative_to(old)
            for old, new in pairs
        ):
            raise ValueError("Migration receipt contains a noncanonical relocation")
        allowed.update((item.source, item.destination))
    for item in plan.edits:
        if item.path not in allowed:
            _validate_reference_edit(root, item)
    for relative in plan.remove_directories:
        if checked_path(root, relative) not in legacy_directories(root):
            raise ValueError("Migration receipt removes a noncanonical directory")


def _validate_created_directories(root: Path, record: MigrationRecord) -> None:
    anchors = get_artifact_directories(root)
    for relative in record.created_directories:
        path = checked_path(root, relative)
        if record.plan.snapshot.get(relative) != "absent_directory" or not any(
            path.is_relative_to(anchor) for anchor in anchors
        ):
            raise ValueError("Migration receipt owns an unapproved directory")


def _validate_relocation_payloads(plan: MigrationPlan) -> None:
    edits = {item.path: item for item in plan.edits}
    for item in plan.relocations:
        source = edits.get(item.source)
        destination = edits.get(item.destination)
        if (
            source is None
            or destination is None
            or source.before is None
            or source.after is not None
            or destination.before is not None
            or destination.after is None
        ):
            raise ValueError("Migration receipt has incomplete relocation payloads")
        if (
            byte_hash(source.before) != item.before_hash
            or byte_hash(destination.after) != item.after_hash
        ):
            raise ValueError("Migration receipt payload hash mismatch")


def validate_record(root: Path, record: MigrationRecord, digest: str) -> None:
    """Do not trust filesystem paths or payloads from a durable receipt."""
    plan = record.plan
    if (
        plan.digest != digest
        or plan.project_root != str(root)
        or preview_digest(
            plan.snapshot,
            plan.relocations,
            plan.edits,
            plan.remove_directories,
            plan.project_root,
        )
        != digest
    ):
        raise ValueError("Migration receipt content digest mismatch")
    names = [item.path for item in plan.edits]
    if len(names) != len(set(names)):
        raise ValueError("Migration receipt contains duplicate edits")
    _validate_record_paths(root, plan)
    _validate_created_directories(root, record)
    _validate_relocation_payloads(plan)


def write_bytes(root: Path, relative: str, content: bytes | None) -> None:
    path = checked_path(root, relative)
    if content is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        wal_atomic_write_bytes(path.parent, path, content)


def _restore_directory_state(root: Path, record: MigrationRecord) -> None:
    """Remove only empty destination parents that were absent before this operation."""
    anchors = get_artifact_directories(root)
    absent = [checked_path(root, relative) for relative in record.created_directories]
    for directory in sorted(absent, key=lambda path: len(path.parts), reverse=True):
        if (
            any(directory.is_relative_to(anchor) for anchor in anchors)
            and directory.is_dir()
            and not any(directory.iterdir())
        ):
            directory.rmdir()


def rollback(root: Path, record: MigrationRecord) -> None:
    """Retain durable preimages rather than overwrite an unexpected external edit."""
    if not record.writes_started:
        record.phase = MigrationPhase.ROLLED_BACK
        return
    for item in record.plan.edits:
        current = read_current(root, item.path)
        if current not in (item.before, item.after):
            raise ValueError(
                f"Rollback conflict; durable preimage retained: {item.path}"
            )
    for item in reversed(record.plan.edits):
        if read_current(root, item.path) != item.before:
            write_bytes(root, item.path, item.before)
    for relative in record.plan.remove_directories:
        checked_path(root, relative).mkdir(parents=True, exist_ok=True)
    _restore_directory_state(root, record)
    record.phase = MigrationPhase.ROLLED_BACK
