"""File Operation Lock Guarding

This module provides lock-guarding for file operations to ensure multi-agent
coordination. All file-based operations that modify roadmap.md, activeContext.md,
or progress.md must verify that the current session holds a lock for the
task being modified.

Lock-guarding is automatic and transparent - agents don't need to manage locks
directly. The system:
1. Checks if a lock exists for the task
2. Verifies the current session owns the lock
3. Blocks writes if lock is held by another session
4. Allows writes if no lock exists (backward compatibility)
"""

import logging
import re
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.session_logger import get_session_id
from cortex.tools.task_locking import (
    check_task_available,
    claim_task,
    list_active_locks,
)
from cortex.tools.task_locking_helpers import generate_task_id

logger = logging.getLogger(__name__)

# Memory bank files that require lock-guarding
_LOCK_GUARDED_FILES = {
    MemoryBankFile.ROADMAP,
    MemoryBankFile.ACTIVE_CONTEXT,
    MemoryBankFile.PROGRESS,
}


def _extract_task_title_from_roadmap_content(content: str) -> str | None:
    """Extract task title from roadmap content being written.

    Looks for the first PENDING or IN PROGRESS entry in the content.

    Args:
        content: Roadmap markdown content

    Returns:
        Task title if found, None otherwise
    """
    lines = content.split("\n")
    for line in lines:
        # Look for roadmap entries: "- **Title** - STATUS - Description"
        match = re.match(r"^-\s*\*\*(.+?)\*\*\s*-\s*(PENDING|IN PROGRESS)", line)
        if match:
            return match.group(1).strip()
    return None


async def _get_current_session_locks(project_root: Path) -> list[str]:
    """Get list of task titles locked by current session.

    Args:
        project_root: Project root directory

    Returns:
        List of task titles locked by current session
    """
    session_id = get_session_id()
    locks = await list_active_locks(project_root)
    return [lock.task_title for lock in locks if lock.agent_session_id == session_id]


async def _check_roadmap_lock(
    project_root: Path, content: str, session_id: str, session_locks: list[str]
) -> tuple[bool, str | None]:
    """Check if roadmap write is allowed based on task lock."""
    task_title = _extract_task_title_from_roadmap_content(content)
    if not task_title:
        return (True, None)
    if task_title in session_locks:
        return (True, None)
    available = await check_task_available(project_root, task_title)
    if not available:
        locks = await list_active_locks(project_root)
        task_id = generate_task_id(task_title)
        for lock in locks:
            if lock.task_id == task_id and lock.agent_session_id != session_id:
                return (
                    False,
                    f"Task '{task_title}' is locked by another session (session_id: {lock.agent_session_id})",
                )
    return (True, None)


async def verify_lock_for_file_operation(
    project_root: Path,
    file_name: str,
    content: str | None = None,
    change_description: str | None = None,
) -> tuple[bool, str | None]:
    """Verify lock for file operation.

    Checks if the current session has a lock for the task being modified.
    For roadmap.md writes, extracts task title from content.
    For other files, checks if session has any active locks.

    Args:
        project_root: Project root directory
        file_name: Name of file being written
        content: Optional file content (for extracting task title)
        change_description: Optional change description

    Returns:
        Tuple of (is_allowed, error_message)
        - is_allowed: True if operation is allowed, False if blocked
        - error_message: Error message if blocked, None if allowed
    """
    if file_name not in _LOCK_GUARDED_FILES:
        return (True, None)

    session_id = get_session_id()
    session_locks = await _get_current_session_locks(project_root)

    if file_name == MemoryBankFile.ROADMAP and content:
        return await _check_roadmap_lock(
            project_root, content, session_id, session_locks
        )

    if session_locks:
        logger.debug(
            "File operation on %s allowed: session has %d active lock(s)",
            file_name,
            len(session_locks),
        )
        return (True, None)

    logger.warning(
        "File operation on %s without active lock - allowing for backward compatibility",
        file_name,
    )
    return (True, None)


async def auto_claim_lock_for_roadmap_entry(
    project_root: Path,
    entry_text: str,
    agent_role: str | None = None,
) -> bool:
    """Automatically claim lock for a roadmap entry.

    Extracts task title from roadmap entry text and claims lock.

    Args:
        project_root: Project root directory
        entry_text: Roadmap entry text (e.g., "- **Title** - PENDING - Description")
        agent_role: Optional agent role

    Returns:
        True if lock was claimed, False if already locked by another session
    """
    # Extract task title from entry text
    match = re.match(r"^-\s*\*\*(.+?)\*\*", entry_text)
    if not match:
        return False

    task_title = match.group(1).strip()

    # Try to claim lock
    from cortex.optimization.agent_roles import normalize_role_name

    role = normalize_role_name(agent_role) if agent_role else None
    lock = await claim_task(project_root, task_title, agent_role=role)

    return lock is not None
