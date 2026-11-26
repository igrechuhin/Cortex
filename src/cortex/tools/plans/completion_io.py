"""File I/O helpers for plan completion.

Handles reading memory bank files and writing with lock-guarding.
"""

from collections.abc import Callable
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.exceptions import FileConflictError, FileLockTimeoutError
from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.memory.wal import WalOperation
from cortex.tools.plans.completion_transaction_io import (
    hash_text,
    validate_contained_path,
)
from cortex.tools.plans.corruption import fix_roadmap_content_if_needed


def read_file(path: Path) -> tuple[str | None, str | None]:
    """Read file. Returns (content, error_message)."""
    if not path.exists():
        return (None, f"File not found: {path}")
    try:
        return (path.read_text(encoding="utf-8"), None)
    except (OSError, UnicodeDecodeError) as e:
        return (None, str(e))


def _read_text_or_empty(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


def _wal_maybe(
    project_root: Path | None,
    path: Path,
    wal_operation: WalOperation | None,
    before_exists: bool,
    before_text: str,
    after_text: str,
    ok: bool,
    err: str | None,
) -> None:
    if project_root is None or wal_operation is None:
        return
    from cortex.memory.wal_hooks import try_wal_record_text_mutation

    try_wal_record_text_mutation(
        project_root,
        path,
        wal_operation,
        before_exists,
        before_text,
        after_text,
        ok,
        err,
    )


async def _verify_lock_for_locked_text(
    project_root: Path,
    lock_file_name: str,
    content: str,
) -> str | None:
    from cortex.tools.files.lock_guard import verify_lock_for_file_operation

    is_allowed, lock_error = await verify_lock_for_file_operation(
        project_root=project_root,
        file_name=lock_file_name,
        content=content,
        change_description=None,
    )
    if not is_allowed:
        assert lock_error is not None
        return f"Lock verification failed: {lock_error}"
    return None


def _locked_text_write_fail(
    path: Path,
    exc: BaseException,
    project_root: Path | None,
    wal_operation: WalOperation | None,
    before_exists: bool,
    before_text: str,
) -> str:
    after_text = _read_text_or_empty(path)
    _wal_maybe(
        project_root,
        path,
        wal_operation,
        before_exists,
        before_text,
        after_text,
        False,
        str(exc),
    )
    return str(exc)


def _locked_text_write_attempt(
    path: Path,
    to_write: str,
    project_root: Path | None,
    wal_operation: WalOperation | None,
    before_exists: bool,
    before_text: str,
) -> str | None:
    try:
        _ = path.write_text(to_write, encoding="utf-8")
        _wal_maybe(
            project_root,
            path,
            wal_operation,
            before_exists,
            before_text,
            to_write,
            True,
            None,
        )
        return None
    except (FileConflictError, FileLockTimeoutError, OSError) as e:
        return _locked_text_write_fail(
            path, e, project_root, wal_operation, before_exists, before_text
        )


async def _write_locked_text(
    path: Path,
    content: str,
    project_root: Path | None,
    lock_file_name: str,
    wal_operation: WalOperation | None,
    transform: Callable[[str], str] | None,
) -> str | None:
    before_exists = path.exists()
    before_text = path.read_text(encoding="utf-8") if before_exists else ""
    if project_root is not None:
        lock_err = await _verify_lock_for_locked_text(
            project_root, lock_file_name, content
        )
        if lock_err is not None:
            return lock_err

    to_write = transform(content) if transform is not None else content
    return _locked_text_write_attempt(
        path, to_write, project_root, wal_operation, before_exists, before_text
    )


async def write_progress(
    path: Path,
    content: str,
    project_root: Path | None = None,
    *,
    wal_operation: WalOperation | None = WalOperation.PROGRESS_ADD,
) -> str | None:
    """Write progress.md with lock-guarding. Returns error_message if failed."""
    return await _write_locked_text(
        path,
        content,
        project_root,
        MemoryBankFile.PROGRESS,
        wal_operation,
        None,
    )


async def write_roadmap(
    path: Path,
    content: str,
    project_root: Path | None = None,
    *,
    wal_operation: WalOperation | None = WalOperation.WRITE,
) -> str | None:
    """Write roadmap file with lock-guarding. Returns error_message if failed."""
    return await _write_locked_text(
        path,
        content,
        project_root,
        MemoryBankFile.ROADMAP,
        wal_operation,
        fix_roadmap_content_if_needed,
    )


async def write_active_context(
    path: Path,
    content: str,
    project_root: Path | None = None,
    *,
    wal_operation: WalOperation | None = WalOperation.ACTIVE_ADD,
) -> str | None:
    """Write activeContext file with lock-guarding. Returns error_message if failed."""
    return await _write_locked_text(
        path,
        content,
        project_root,
        MemoryBankFile.ACTIVE_CONTEXT,
        wal_operation,
        None,
    )


async def write_owned_exact_text(
    manager: FileSystemManager,
    path: Path,
    content: str,
    expected_hash: str,
    expected_exists: bool,
) -> None:
    """Use the byte-atomic document writer under the shared per-file lock."""
    if not expected_exists:
        raise ValueError("Cancellation writes require an existing file")
    root = manager.project_root
    lock = path.with_suffix(path.suffix + ".lock")
    validate_contained_path(lock, root)
    await manager.acquire_lock(lock)
    try:
        _replace_exact_text(root, path, content, expected_hash)
    finally:
        await manager.release_lock(lock)


def _replace_exact_text(
    root: Path, path: Path, content: str, expected_hash: str
) -> None:
    from cortex.tools.files.document_patch_operations import write_existing_document
    from cortex.tools.files.guarded_mutation_evidence import GuardedMutationEvidence

    validate_contained_path(path, root)
    if not path.is_file():
        raise ValueError(f"Cancellation target is no longer a regular file: {path}")
    evidence = GuardedMutationEvidence()
    before = evidence.observe(root, path)
    before_text = before.decode("utf-8")
    if hash_text(before_text) != expected_hash:
        raise ValueError(f"Cancellation write conflict: content changed for {path}")
    relative = path.relative_to(root).as_posix()
    write_existing_document(root, relative, path, before, content.encode(), evidence)
    memory = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    if path == memory / MemoryBankFile.ROADMAP:
        _wal_maybe(
            root, path, WalOperation.WRITE, True, before_text, content, True, None
        )
