"""
Roadmap file I/O operations.

Extracted from roadmap_operations for maintainability.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.memory.wal import WalOperation
from cortex.tools.plans.completion_transaction_io import hash_text
from cortex.tools.plans.corruption import fix_roadmap_content_if_needed


def read_roadmap_file(roadmap_path: Path) -> tuple[str | None, str | None]:
    """Read roadmap file. Returns (content, error_message)."""
    if not roadmap_path.exists():
        return (None, f"{MemoryBankFile.ROADMAP} not found at {roadmap_path}")

    try:
        content = roadmap_path.read_bytes().decode("utf-8")
        return (content, None)
    except Exception as e:
        return (None, str(e))


async def _roadmap_verify_write_lock(project_root: Path, content: str) -> str | None:
    from cortex.tools.files.lock_guard import verify_lock_for_file_operation

    is_allowed, lock_error = await verify_lock_for_file_operation(
        project_root=project_root,
        file_name=MemoryBankFile.ROADMAP,
        content=content,
        change_description=None,
    )
    if not is_allowed:
        assert lock_error is not None
        return f"Lock verification failed: {lock_error}"
    return None


def _roadmap_disk_write_fail(
    roadmap_path: Path,
    exc: BaseException,
    project_root: Path | None,
    wal_operation: WalOperation | None,
    before_exists: bool,
    before_text: str,
) -> str:
    after_text = _wal_read_text_or_empty(roadmap_path)
    _wal_roadmap_maybe(
        project_root,
        roadmap_path,
        wal_operation,
        before_exists,
        before_text,
        after_text,
        False,
        str(exc),
    )
    return str(exc)


def _roadmap_disk_write_attempt(
    roadmap_path: Path,
    content: str,
    project_root: Path | None,
    wal_operation: WalOperation | None,
    before_exists: bool,
    before_text: str,
    repair_content: bool,
) -> str | None:
    try:
        fixed_content = (
            fix_roadmap_content_if_needed(content) if repair_content else content
        )
        _replace_roadmap_text(roadmap_path, fixed_content, before_exists)
        _wal_roadmap_maybe(
            project_root,
            roadmap_path,
            wal_operation,
            before_exists,
            before_text,
            fixed_content,
            True,
            None,
        )
        return None
    except Exception as e:
        return _roadmap_disk_write_fail(
            roadmap_path, e, project_root, wal_operation, before_exists, before_text
        )


def _replace_roadmap_text(
    roadmap_path: Path, content: str, before_exists: bool
) -> None:
    """Stage bytes beside the target so a failed write never truncates it."""
    with TemporaryDirectory(dir=roadmap_path.parent) as staging:
        staged = Path(staging) / roadmap_path.name
        _ = staged.write_text(content, encoding="utf-8")
        if before_exists:
            staged.chmod(roadmap_path.stat().st_mode)
        _ = staged.replace(roadmap_path)


async def write_roadmap_file(
    roadmap_path: Path,
    content: str,
    project_root: Path | None = None,
    *,
    wal_operation: WalOperation | None = None,
    expected_content: str,
    repair_content: bool = True,
) -> str | None:
    """Write atomically only while the merge preimage still owns the target."""
    try:
        manager = FileSystemManager(project_root or roadmap_path.parent)
        lock = roadmap_path.with_suffix(roadmap_path.suffix + ".lock")
        await manager.acquire_lock(lock)
        try:
            return await write_roadmap_file_locked(
                roadmap_path,
                content,
                project_root,
                wal_operation=wal_operation,
                expected_content=expected_content,
                repair_content=repair_content,
            )
        finally:
            await manager.release_lock(lock)
    except Exception as exc:
        return str(exc)


async def write_roadmap_file_locked(
    roadmap_path: Path,
    content: str,
    project_root: Path | None,
    *,
    wal_operation: WalOperation | None,
    expected_content: str,
    repair_content: bool,
) -> str | None:
    """Write under the caller-owned roadmap lock; never acquire it recursively."""
    try:
        if project_root is not None:
            lock_err = await _roadmap_verify_write_lock(project_root, content)
            if lock_err is not None:
                return lock_err
        if not roadmap_path.exists() or hash_text(
            roadmap_path.read_bytes().decode("utf-8")
        ) != hash_text(expected_content):
            return "Roadmap content changed since the merge read; retry registration"
        if content == expected_content:
            return None
        return _roadmap_disk_write_attempt(
            roadmap_path,
            content,
            project_root,
            wal_operation,
            True,
            expected_content,
            repair_content,
        )
    except Exception as exc:
        return str(exc)


def _wal_read_text_or_empty(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


def _wal_roadmap_maybe(
    project_root: Path | None,
    roadmap_path: Path,
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
        roadmap_path,
        wal_operation,
        before_exists,
        before_text,
        after_text,
        ok,
        err,
    )
