"""File I/O helpers for plan completion.

Handles reading memory bank files and writing with lock-guarding.
"""

from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.exceptions import FileConflictError, FileLockTimeoutError
from cortex.tools.plans.corruption import fix_roadmap_content_if_needed


def read_file(path: Path) -> tuple[str | None, str | None]:
    """Read file. Returns (content, error_message)."""
    if not path.exists():
        return (None, f"File not found: {path}")
    try:
        return (path.read_text(encoding="utf-8"), None)
    except (OSError, UnicodeDecodeError) as e:
        return (None, str(e))


async def write_progress(
    path: Path, content: str, project_root: Path | None = None
) -> str | None:
    """Write progress.md with lock-guarding. Returns error_message if failed."""
    if project_root is not None:
        from cortex.tools.files.lock_guard import verify_lock_for_file_operation

        is_allowed, lock_error = await verify_lock_for_file_operation(
            project_root=project_root,
            file_name=MemoryBankFile.PROGRESS,
            content=content,
            change_description=None,
        )
        if not is_allowed:
            assert lock_error is not None
            return f"Lock verification failed: {lock_error}"

    try:
        _ = path.write_text(content, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except OSError as e:
        return str(e)


async def write_roadmap(
    path: Path, content: str, project_root: Path | None = None
) -> str | None:
    """Write roadmap file with lock-guarding. Returns error_message if failed."""
    if project_root is not None:
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

    try:
        fixed = fix_roadmap_content_if_needed(content)
        _ = path.write_text(fixed, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except OSError as e:
        return str(e)


async def write_active_context(
    path: Path, content: str, project_root: Path | None = None
) -> str | None:
    """Write activeContext file with lock-guarding. Returns error_message if failed."""
    if project_root is not None:
        from cortex.tools.files.lock_guard import verify_lock_for_file_operation

        is_allowed, lock_error = await verify_lock_for_file_operation(
            project_root=project_root,
            file_name=MemoryBankFile.ACTIVE_CONTEXT,
            content=content,
            change_description=None,
        )
        if not is_allowed:
            assert lock_error is not None
            return f"Lock verification failed: {lock_error}"

    try:
        _ = path.write_text(content, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except OSError as e:
        return str(e)
