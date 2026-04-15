"""
Roadmap file I/O operations.

Extracted from roadmap_operations for maintainability.
"""

from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.memory.wal import WalOperation
from cortex.tools.plans.corruption import fix_roadmap_content_if_needed


def read_roadmap_file(roadmap_path: Path) -> tuple[str | None, str | None]:
    """Read roadmap file. Returns (content, error_message)."""
    if not roadmap_path.exists():
        return (None, f"{MemoryBankFile.ROADMAP} not found at {roadmap_path}")

    try:
        content = roadmap_path.read_text(encoding="utf-8")
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
) -> str | None:
    try:
        fixed_content = fix_roadmap_content_if_needed(content)
        _ = roadmap_path.write_text(fixed_content, encoding="utf-8")
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


async def write_roadmap_file(
    roadmap_path: Path,
    content: str,
    project_root: Path | None = None,
    *,
    wal_operation: WalOperation | None = None,
) -> str | None:
    """Write updated roadmap with lock-guarding. Returns error_message if failed."""
    before_exists = roadmap_path.exists()
    before_text = roadmap_path.read_text(encoding="utf-8") if before_exists else ""
    if project_root is not None:
        lock_err = await _roadmap_verify_write_lock(project_root, content)
        if lock_err is not None:
            return lock_err

    return _roadmap_disk_write_attempt(
        roadmap_path, content, project_root, wal_operation, before_exists, before_text
    )


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
