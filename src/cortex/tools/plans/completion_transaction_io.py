"""Contained persistence and atomic I/O for plan completion transactions."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.memory.wal import WalOperation
from cortex.tools.plans.completion_archive import archive_subdir_for_plan
from cortex.tools.plans.completion_transaction_models import (
    CompletionFileKey,
    CompletionFileRecord,
    CompletionOperationRecord,
    CompletionPhase,
    CompletionRequest,
)

_MAX_COMPLETED_RECORDS = 32
_RECORD_SUFFIX = ".json"


def utc_now_iso() -> str:
    """Return current UTC time for durable operation records."""
    return datetime.now(UTC).isoformat()


def hash_text(content: str) -> str:
    """Return the FileSystemManager-compatible SHA-256 digest."""
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def request_fingerprint(request: CompletionRequest) -> str:
    """Return stable identity for an exact completion request."""
    encoded = request.model_dump_json(exclude_none=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def operation_id(request: CompletionRequest) -> str:
    """Return stable per-plan operation key, independent of retry payload."""
    identity = request.plan_file_name or request.plan_title.casefold()
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _required_file_keys(request: CompletionRequest) -> set[CompletionFileKey]:
    keys = {CompletionFileKey.ROADMAP, CompletionFileKey.ACTIVE_CONTEXT}
    if request.plan_file_name is not None:
        keys.add(CompletionFileKey.PLAN)
    if request.progress_entry is not None:
        keys.add(CompletionFileKey.PROGRESS)
    return keys


def _canonical_relative_path(
    project_root: Path, record: CompletionOperationRecord, key: CompletionFileKey
) -> str:
    if key == CompletionFileKey.PLAN:
        name = record.request.plan_file_name
        if name is None:
            raise ValueError("Completion plan record has no plan filename")
        target = get_cortex_path(project_root, CortexResourceType.PLANS) / name
    else:
        memory = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
        filename = {
            CompletionFileKey.ROADMAP: MemoryBankFile.ROADMAP,
            CompletionFileKey.ACTIVE_CONTEXT: MemoryBankFile.ACTIVE_CONTEXT,
            CompletionFileKey.PROGRESS: MemoryBankFile.PROGRESS,
        }[key]
        target = memory / filename
    return target.relative_to(project_root).as_posix()


def _validate_record_file(
    project_root: Path,
    operations_root: Path,
    record: CompletionOperationRecord,
    expected_op_id: str,
    item: CompletionFileRecord,
) -> None:
    if item.relative_path != _canonical_relative_path(project_root, record, item.key):
        raise ValueError("Completion operation record targets a noncanonical file")
    prefix = f"{expected_op_id}.{item.key.value}"
    if item.before_payload != f"{prefix}.before.txt":
        raise ValueError("Completion operation record has an invalid payload name")
    if item.after_payload != f"{prefix}.after.txt":
        raise ValueError("Completion operation record has an invalid payload name")
    before = read_payload(operations_root, item.before_payload)
    after = read_payload(operations_root, item.after_payload)
    if hash_text(before) != item.before_hash or hash_text(after) != item.after_hash:
        raise ValueError("Completion operation payload hash does not match its record")


def validate_record_consistency(
    project_root: Path,
    operations_root: Path,
    path: Path,
    record: CompletionOperationRecord,
    expected_op_id: str,
) -> None:
    """Reject a truncated or tampered record before replay or rollback."""
    if path != record_path(path.parent, expected_op_id):
        raise ValueError("Completion operation record path does not match request")
    if record.operation_id != expected_op_id:
        raise ValueError(
            "Completion operation record identifier does not match request"
        )
    if record.request_fingerprint != request_fingerprint(record.request):
        raise ValueError("Completion operation record fingerprint is invalid")
    expected_keys = _required_file_keys(record.request)
    if {item.key for item in record.files} != expected_keys:
        raise ValueError("Completion operation record has an invalid file-key set")
    for item in record.files:
        _validate_record_file(
            project_root, operations_root, record, expected_op_id, item
        )


def completion_operations_root(project_root: Path) -> Path:
    """Return canonical flat operation-record directory."""
    return (
        get_cortex_path(project_root, CortexResourceType.SESSION)
        / "completion-operations"
    )


def validate_contained_path(path: Path, anchor: Path) -> None:
    """Reject paths escaping ``anchor`` or traversing symlink components."""
    if not path.is_relative_to(anchor):
        raise ValueError(f"Completion path escapes its allowed root: {path}")
    current = anchor
    for part in path.relative_to(anchor).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Completion paths cannot contain symlinks: {current}")
    if anchor.is_symlink() or not path.resolve().is_relative_to(anchor.resolve()):
        raise ValueError(f"Completion path escapes its allowed root: {path}")


def read_required_text(path: Path, anchor: Path) -> str:
    """Read one contained regular UTF-8 file or raise a precise error."""
    validate_contained_path(path, anchor)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Completion input is not a regular file: {path}")
    return path.read_text(encoding="utf-8")


def record_path(operations_root: Path, op_id: str) -> Path:
    """Return record path for ``op_id``."""
    return operations_root / f"{op_id}{_RECORD_SUFFIX}"


def read_record(operations_root: Path, path: Path) -> CompletionOperationRecord | None:
    """Load a persisted operation record."""
    validate_contained_path(path, operations_root)
    if path.parent != operations_root or path.suffix != _RECORD_SUFFIX:
        raise ValueError(f"Malformed completion operation record path: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Malformed completion operation record: {path}")
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        return CompletionOperationRecord.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Malformed completion operation record: {path}") from exc


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace one internal operation file with flushed content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        _ = stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        _ = temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def persist_record(path: Path, record: CompletionOperationRecord) -> None:
    """Persist one bounded operation record atomically."""
    _atomic_write_text(path, record.model_dump_json(indent=2))


def save_record_phase(
    path: Path,
    record: CompletionOperationRecord,
    phase: CompletionPhase,
    error: str | None = None,
) -> None:
    """Advance and atomically persist an operation phase."""
    record.phase = phase
    record.updated_at = utc_now_iso()
    record.error = error
    persist_record(path, record)


def persist_payload(path: Path, content: str) -> None:
    """Persist immutable before/after payload, accepting identical replay."""
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"Completion payload collision: {path.name}")
        return
    _atomic_write_text(path, content)


def read_payload(operations_root: Path, name: str) -> str:
    """Read an operation-owned payload by validated flat filename."""
    if Path(name).name != name or not name:
        raise ValueError(f"Invalid completion payload name: {name}")
    return read_required_text(operations_root / name, operations_root)


def cleanup_operation_payloads(operations_root: Path, op_id: str) -> None:
    """Delete flat orphan payloads for one operation identifier."""
    for path in operations_root.glob(f"{op_id}.*.txt"):
        if path.is_file() and path.parent == operations_root:
            path.unlink()


def resolve_record_file(project_root: Path, item: CompletionFileRecord) -> Path:
    """Resolve and revalidate a persisted transaction file reference."""
    relative = Path(item.relative_path)
    if relative.is_absolute():
        raise ValueError("Completion operation contains an absolute file path")
    target = project_root / relative
    anchor_type = (
        CortexResourceType.PLANS
        if item.key == CompletionFileKey.PLAN
        else CortexResourceType.MEMORY_BANK
    )
    validate_contained_path(target, get_cortex_path(project_root, anchor_type))
    return target


def resolve_archive_paths(
    project_root: Path, record: CompletionOperationRecord
) -> tuple[Path, Path] | None:
    """Resolve and validate project-relative archive paths from a record."""
    if record.archive_source is None or record.archive_destination is None:
        return None
    source_rel = Path(record.archive_source)
    destination_rel = Path(record.archive_destination)
    if source_rel.is_absolute() or destination_rel.is_absolute():
        raise ValueError("Completion archive record contains an absolute path")
    source = project_root / source_rel
    destination = project_root / destination_rel
    plans = get_cortex_path(project_root, CortexResourceType.PLANS)
    archive = get_cortex_path(project_root, CortexResourceType.PLANS_ARCHIVE)
    validate_contained_path(source, plans)
    validate_contained_path(destination, archive)
    name = record.request.plan_file_name
    if name is None:
        raise ValueError("Completion archive record has no plan filename")
    subdir = archive_subdir_for_plan(name)
    if (
        source != plans / name
        or subdir is None
        or destination != archive / subdir / name
    ):
        raise ValueError("Completion archive record paths do not match its plan")
    return source, destination


async def write_owned_text(
    manager: FileSystemManager,
    path: Path,
    content: str,
    expected_hash: str,
    expected_exists: bool,
) -> None:
    """Atomically write when current existence and hash match preparation."""
    if path.exists() != expected_exists:
        raise ValueError(f"Completion write conflict: existence changed for {path}")
    if expected_exists:
        current = path.read_text(encoding="utf-8")
        if hash_text(current) != expected_hash:
            raise ValueError(f"Completion write conflict: content changed for {path}")
    before = path.read_text(encoding="utf-8") if expected_exists else ""
    _ = await manager.write_file(path, content, expected_hash=expected_hash)
    _record_memory_bank_write(manager.project_root, path, before, content)


def _record_memory_bank_write(
    project_root: Path, path: Path, before: str, after: str
) -> None:
    operation = {
        "roadmap.md": WalOperation.WRITE,
        "activeContext.md": WalOperation.ACTIVE_ADD,
        "progress.md": WalOperation.PROGRESS_ADD,
    }.get(path.name)
    if operation is None:
        return
    from cortex.memory.wal_hooks import try_wal_record_text_mutation

    try_wal_record_text_mutation(
        project_root, path, operation, True, before, after, True, None
    )


@asynccontextmanager
async def completion_lock(
    project_root: Path,
) -> AsyncIterator[tuple[FileSystemManager, Path]]:
    """Serialize complete-plan preparation, mutation, and recovery."""
    operations_root = completion_operations_root(project_root)
    validate_contained_path(operations_root, project_root)
    operations_root.mkdir(parents=True, exist_ok=True)
    manager = FileSystemManager(project_root)
    lock_path = operations_root / ".completion.lock"
    await manager.acquire_lock(lock_path)
    try:
        yield manager, operations_root
    finally:
        await manager.release_lock(lock_path)


def cleanup_completed_records(operations_root: Path) -> None:
    """Retain only the newest bounded set of terminal operation records."""
    terminal: list[tuple[str, Path, CompletionOperationRecord]] = []
    for path in operations_root.glob(f"*{_RECORD_SUFFIX}"):
        try:
            record = read_record(operations_root, path)
        except ValueError:
            continue
        if record is not None and record.phase in {
            CompletionPhase.COMPLETED,
            CompletionPhase.ROLLED_BACK,
        }:
            terminal.append((record.updated_at, path, record))
    for _, path, record in sorted(terminal, reverse=True)[_MAX_COMPLETED_RECORDS:]:
        path.unlink(missing_ok=True)
        for item in record.files:
            (operations_root / item.before_payload).unlink(missing_ok=True)
            (operations_root / item.after_payload).unlink(missing_ok=True)


def drop_operation_files(
    operations_root: Path, record: CompletionOperationRecord
) -> None:
    """Remove one rolled-back operation's allowlisted flat files."""
    record_path(operations_root, record.operation_id).unlink(missing_ok=True)
    for item in record.files:
        (operations_root / item.before_payload).unlink(missing_ok=True)
        (operations_root / item.after_payload).unlink(missing_ok=True)
