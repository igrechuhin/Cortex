"""Preview-first migration of the three misplaced report directories."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.linking.transclusion_engine import TransclusionEngine
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.types import ManagersDict
from cortex.memory.temporal_store import (
    TemporalFact,
    TemporalFactCategory,
    TemporalMemoryStore,
)
from cortex.memory.wal import wal_atomic_write_bytes
from cortex.optimization.relevance_scorer import RelevanceScorer
from cortex.tools.artifacts.artifact_types import get_artifact_directories
from cortex.tools.files.artifact_migration_io import (
    persist as _persist,
)
from cortex.tools.files.artifact_migration_io import (
    read_current as _read_current,
)
from cortex.tools.files.artifact_migration_io import (
    receipt_path as _receipt_path,
)
from cortex.tools.files.artifact_migration_io import (
    rollback as _rollback,
)
from cortex.tools.files.artifact_migration_io import (
    validate_record as _validate_record,
)
from cortex.tools.files.artifact_migration_io import (
    write_bytes as _write_bytes,
)
from cortex.tools.files.artifact_migration_models import (
    MigrationPhase,
    MigrationPlan,
    MigrationRecord,
    Relocation,
)
from cortex.tools.files.artifact_migration_prepare import (
    byte_hash,
    checked_path,
    prepare_migration,
)
from cortex.tools.plans.completion_transaction_io import validate_contained_path


def _relocation_row(record: MigrationRecord, item: Relocation) -> bytes:
    row = {
        "id": record.plan.digest + ":" + item.source,
        "operation": "artifact_relocation",
        "timestamp": record.created_at,
        **item.model_dump(),
    }
    return (json.dumps(row, sort_keys=True) + "\n").encode("utf-8")


def _append_provenance(root: Path, path: Path, record: MigrationRecord) -> None:
    """Append deterministic relocation facts, never rewrite prior WAL/history/SQL rows."""
    if not record.plan.relocations:
        return
    wal_dir = get_cortex_path(root, CortexResourceType.CORTEX_DIR) / "wal"
    facts_path = wal_dir / "artifact_relocations.jsonl"
    validate_contained_path(facts_path, root)
    old = facts_path.read_bytes() if facts_path.exists() else b""
    existing = {json.loads(line)["id"] for line in old.splitlines() if line.strip()}
    rows: list[bytes] = []
    for item in record.plan.relocations:
        identity = record.plan.digest + ":" + item.source
        if identity not in existing:
            rows.append(_relocation_row(record, item))
    if rows:
        wal_dir.mkdir(parents=True, exist_ok=True)
        wal_atomic_write_bytes(wal_dir, facts_path, old + b"".join(rows))
    _append_temporal_provenance(root, path, record)


def _append_temporal_provenance(
    root: Path, path: Path, record: MigrationRecord
) -> None:
    database = get_cortex_path(root, CortexResourceType.CORTEX_DIR) / "temporal.db"
    validate_contained_path(database, root)
    store = TemporalMemoryStore(database)
    for item in record.plan.relocations:
        store.add_fact(
            TemporalFact(
                category=TemporalFactCategory.STATUS,
                subject=item.source,
                predicate="relocated_to",
                object=item.destination,
                valid_from=record.created_at,
                source_file=path.relative_to(root).as_posix(),
                source_line=1,
                created_at=record.created_at,
            )
        )


async def _invalidate(mgrs: ManagersDict) -> None:
    from cortex.tools.optimization.handlers import invalidate_context_resource_cache
    from cortex.tools.structure.main import invalidate_structure_resource_cache

    mgrs.index.invalidate_cache()
    mgrs.graph.clear_dynamic_dependencies()
    mgrs.graph.link_types.clear()
    mgrs.tokens.clear_cache()
    for manager in (
        mgrs.transclusion,
        mgrs.link_validator,
        mgrs.context_optimizer,
        mgrs.progressive_loader,
        mgrs.relevance_scorer,
        mgrs.summarization_engine,
    ):
        if isinstance(manager, LazyManager):
            await manager.invalidate()
        elif isinstance(manager, TransclusionEngine):
            manager.clear_cache()
        elif isinstance(manager, RelevanceScorer):
            manager.clear_cache()
    invalidate_context_resource_cache()
    invalidate_structure_resource_cache()


def _response(plan: MigrationPlan, *, applied: bool, replayed: bool = False) -> str:
    return json.dumps(
        {
            "status": "success",
            "operation": "migrate_artifacts",
            "apply": applied,
            "preview_digest": plan.digest,
            "project_root": plan.project_root,
            "replayed": replayed,
            "migration_count": len(plan.relocations),
            "relocations": [item.model_dump() for item in plan.relocations],
            "reference_updates": [
                item.path
                for item in plan.edits
                if item.before is not None and item.after is not None
            ],
            "remove_directories": plan.remove_directories,
        },
        indent=2,
    )


def _check_committed(root: Path, record: MigrationRecord) -> None:
    for item in record.plan.relocations:
        if _read_current(root, item.source) is not None:
            raise ValueError(f"Completed migration source reappeared: {item.source}")
        destination = _read_current(root, item.destination)
        if destination is None or byte_hash(destination) != item.after_hash:
            raise ValueError(
                f"Completed migration destination changed: {item.destination}"
            )


async def _finish(
    root: Path, mgrs: ManagersDict, path: Path, record: MigrationRecord
) -> str:
    _check_committed(root, record)
    _append_provenance(root, path, record)
    for relative in record.plan.remove_directories:
        directory = checked_path(root, relative)
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()
    await _invalidate(mgrs)
    record.phase = MigrationPhase.COMPLETED
    record.error = None
    _persist(path, record)
    return _response(record.plan, applied=True)


async def _recover_existing(
    root: Path, mgrs: ManagersDict, path: Path, digest: str
) -> str | None:
    if not path.exists():
        return None
    record = MigrationRecord.model_validate_json(path.read_bytes())
    _validate_record(root, record, digest)
    if record.phase == MigrationPhase.COMPLETED:
        _check_committed(root, record)
        return _response(record.plan, applied=True, replayed=True)
    if record.phase == MigrationPhase.FILES_COMMITTED:
        return await _finish(root, mgrs, path, record)
    if record.phase in {MigrationPhase.PREPARED, MigrationPhase.RECOVERY_REQUIRED}:
        _rollback(root, record)
        _persist(path, record)
    return None


def _rollback_failure(
    root: Path, path: Path, record: MigrationRecord, failure: BaseException
) -> None:
    record.error = str(failure)
    try:
        _rollback(root, record)
    except (OSError, ValueError) as rollback_error:
        record.phase = MigrationPhase.RECOVERY_REQUIRED
        record.error = f"{failure}; {rollback_error}"
    _persist(path, record)


def _check_snapshot(root: Path, mgrs: ManagersDict, plan: MigrationPlan) -> None:
    """Re-discover memberships and bytes after every asynchronous lock wait."""
    if prepare_migration(root, mgrs).digest != plan.digest:
        raise ValueError(
            "Stale preview digest: migration inputs changed while waiting for locks"
        )


def _create_destination_parents(
    root: Path, path: Path, record: MigrationRecord
) -> None:
    """Record ownership before creating each approved missing destination directory."""
    anchors = get_artifact_directories(root)
    absent = [
        relative
        for relative, state in record.plan.snapshot.items()
        if state == "absent_directory"
    ]
    for relative in sorted(absent, key=lambda name: len(Path(name).parts)):
        directory = checked_path(root, relative)
        if (
            not any(directory.is_relative_to(anchor) for anchor in anchors)
            or directory.exists()
        ):
            continue
        record.created_directories.append(relative)
        _persist(path, record)
        directory.mkdir()


async def _execute_files(
    root: Path, mgrs: ManagersDict, path: Path, record: MigrationRecord
) -> None:
    locks: list[Path] = []
    try:
        for item in sorted(record.plan.edits, key=lambda edit: edit.path):
            name = hashlib.sha256(item.path.encode("utf-8")).hexdigest() + ".lock"
            lock = path.parent / "locks" / name
            validate_contained_path(lock, root)
            await mgrs.fs.acquire_lock(lock)
            locks.append(lock)
        _check_snapshot(root, mgrs, record.plan)
        for item in record.plan.edits:
            if _read_current(root, item.path) != item.before:
                raise ValueError(f"Migration input changed after preview: {item.path}")
        record.writes_started = True
        _persist(path, record)
        _create_destination_parents(root, path, record)
        for item in record.plan.edits:
            _write_bytes(root, item.path, item.after)
        record.phase = MigrationPhase.FILES_COMMITTED
        _persist(path, record)
    except BaseException as exc:
        _rollback_failure(root, path, record, exc)
        raise
    finally:
        for lock in reversed(locks):
            await mgrs.fs.release_lock(lock)


async def _apply_locked(root: Path, mgrs: ManagersDict, path: Path, digest: str) -> str:
    existing = await _recover_existing(root, mgrs, path, digest)
    if existing is not None:
        return existing
    plan = prepare_migration(root, mgrs)
    if plan.digest != digest:
        raise ValueError(
            "Stale preview digest: inputs, references, index or destinations changed; preview again"
        )
    if not plan.edits and not plan.remove_directories:
        return _response(plan, applied=True)
    record = MigrationRecord(
        phase=MigrationPhase.PREPARED,
        plan=plan,
        created_at=datetime.now(UTC).isoformat(),
    )
    _persist(path, record)
    await _execute_files(root, mgrs, path, record)
    return await _finish(root, mgrs, path, record)


def _validate_root(root: Path, mgrs: ManagersDict) -> Path:
    if ".." in root.parts:
        raise ValueError("Migration root cannot contain traversal components")
    root = root.absolute()
    validate_contained_path(root, root)
    if root.resolve() != root:
        raise ValueError("Migration root cannot traverse symlinks")
    if root.resolve() != mgrs.fs.project_root:
        raise ValueError("Migration root does not match filesystem manager")
    return root


def _migration_error(root: Path, exc: Exception) -> str:
    return json.dumps(
        {
            "status": "error",
            "operation": "migrate_artifacts",
            "project_root": str(root.absolute()),
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
        indent=2,
    )


def _approved_receipt(root: Path, mgrs: ManagersDict, digest: str) -> Path:
    """Refuse unsafe inputs and stale digests before creating even a lock."""
    path = _receipt_path(root, digest)
    validate_contained_path(path, root)
    if path.exists():
        _validate_record(
            root, MigrationRecord.model_validate_json(path.read_bytes()), digest
        )
    elif prepare_migration(root, mgrs).digest != digest:
        raise ValueError("Stale preview digest; preview again")
    return path


async def migrate_artifacts(
    root: Path,
    mgrs: ManagersDict,
    *,
    apply: bool = False,
    expected_preview_digest: str | None = None,
) -> str:
    """Preview or atomically relocate only memory-bank reviews/analyses/queries.

    Applying requires the exact preview fingerprint. A successful receipt accepts
    replay even after unrelated new filings; interrupted writes retain byte
    preimages for rollback, and committed files resume append-only provenance.
    """
    try:
        root = _validate_root(root, mgrs)
        if not apply:
            return _response(prepare_migration(root, mgrs), applied=False)
        if expected_preview_digest is None:
            raise ValueError("Apply requires expected_preview_digest from a preview")
        path = _approved_receipt(root, mgrs, expected_preview_digest)
        lock = path.parent / ".migration.lock"
        validate_contained_path(lock, root)
        await mgrs.fs.acquire_lock(lock)
        try:
            return await _apply_locked(root, mgrs, path, expected_preview_digest)
        finally:
            await mgrs.fs.release_lock(lock)
    except (OSError, ValueError, FileLockTimeoutError, sqlite3.Error) as exc:
        return _migration_error(root, exc)
    except asyncio.CancelledError:
        raise
