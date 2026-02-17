"""Task Locking Operations

This module provides task locking functionality for Phase 58 multi-agent
specialization. It allows agents to claim and release locks on roadmap items
to prevent duplicate work across concurrent sessions.

The locking mechanism is file-based and uses concurrent-safe JSON operations
via the cache_json_access module. Locks auto-expire after a configurable timeout
(default 2 hours) to prevent orphaned locks.
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.core.session_logger import get_session_id
from cortex.optimization.agent_roles import AgentRole
from cortex.tools.models import TaskLock

logger = logging.getLogger(__name__)

# Default lock expiry timeout (1 minute)
# Short timeout prevents orphaned locks while allowing quick task switching
_DEFAULT_LOCK_TIMEOUT_HOURS = 1.0 / 60.0  # 1 minute

# Cache key for locks registry
_LOCKS_REGISTRY_KEY = "locks/active.json"


def generate_task_id(task_title: str) -> str:
    """Generate a unique task ID from a roadmap entry title.

    Uses SHA256 hash of the normalized title to create a stable identifier
    that can be used to track locks across sessions.

    Args:
        task_title: Roadmap entry title (e.g., "Phase 58: Multi-Agent Specialization")

    Returns:
        Task ID string (hex digest, first 16 chars)
    """
    normalized = task_title.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


async def _load_locks_registry(
    project_root: Path,
) -> dict[str, TaskLock]:
    """Load locks registry from cache.

    Returns:
        Dictionary mapping task_id -> TaskLock model
    """
    data = await read_cache_json(project_root, _LOCKS_REGISTRY_KEY)
    if data is None or not isinstance(data, dict):
        return {}

    locks: dict[str, TaskLock] = {}
    for task_id_str, lock_dict in data.items():
        if not isinstance(lock_dict, dict):
            continue
        try:
            lock = TaskLock.model_validate(lock_dict)
            locks[str(task_id_str)] = lock
        except Exception as e:
            logger.warning(
                "Failed to parse lock data for task_id=%s: %s, skipping",
                task_id_str,
                e,
            )
            continue

    return locks


async def _save_locks_registry(project_root: Path, locks: dict[str, TaskLock]) -> None:
    """Save locks registry to cache."""
    # Serialize TaskLock models to dict for JSON storage
    locks_dict: dict[str, object] = {
        task_id: lock.model_dump() for task_id, lock in locks.items()
    }
    await write_cache_json(project_root, _LOCKS_REGISTRY_KEY, locks_dict)


async def _cleanup_expired_locks(
    project_root: Path, locks: dict[str, TaskLock]
) -> dict[str, TaskLock]:
    """Remove expired locks from registry.

    Args:
        project_root: Project root directory
        locks: Current locks registry

    Returns:
        Updated locks registry with expired locks removed
    """
    now = datetime.now(UTC)
    active_locks: dict[str, TaskLock] = {}

    for task_id, lock in locks.items():
        try:
            expires_at_str = lock.expires_at.replace("Z", "+00:00")
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at >= now:
                active_locks[task_id] = lock
            else:
                logger.debug(
                    "Removing expired lock: task_id=%s, expired_at=%s",
                    task_id,
                    lock.expires_at,
                )
        except (ValueError, TypeError) as e:
            logger.warning("Invalid expires_at in lock %s: %s, skipping", task_id, e)
            continue

    return active_locks


async def _check_existing_lock(
    locks: dict[str, TaskLock], task_id: str, task_title: str, now: datetime
) -> bool:
    """Check if task is already locked. Returns True if locked."""
    if task_id not in locks:
        return False
    existing_lock = locks[task_id]
    try:
        expires_at_str = existing_lock.expires_at.replace("Z", "+00:00")
        existing_expires = datetime.fromisoformat(expires_at_str)
        if existing_expires >= now:
            logger.info(
                "Task %s already locked by session %s",
                task_title,
                existing_lock.agent_session_id,
            )
            return True
    except (ValueError, TypeError):
        pass
    return False


def _create_task_lock(
    task_id: str,
    task_title: str,
    session_id: str,
    now: datetime,
    expires_at: datetime,
    agent_role: AgentRole | None,
) -> TaskLock:
    """Create a TaskLock model."""
    return TaskLock(
        task_id=task_id,
        task_title=task_title,
        agent_session_id=session_id,
        locked_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        agent_role=agent_role.value if agent_role else None,
    )


async def claim_task(
    project_root: Path,
    task_title: str,
    agent_role: AgentRole | None = None,
    lock_timeout_hours: float = _DEFAULT_LOCK_TIMEOUT_HOURS,
) -> TaskLock | None:
    """Claim a lock on a task.

    Attempts to acquire a lock on the specified task. Returns the lock model
    if successful, None if the task is already locked.

    Args:
        project_root: Project root directory
        task_title: Roadmap entry title to lock
        agent_role: Optional agent role for the lock
        lock_timeout_hours: Lock expiry timeout in hours (default 1 minute = 1/60 hours)

    Returns:
        TaskLock model if lock acquired, None if already locked
    """
    task_id = generate_task_id(task_title)
    session_id = get_session_id()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=lock_timeout_hours)
    locks = await _load_locks_registry(project_root)
    locks = await _cleanup_expired_locks(project_root, locks)
    if await _check_existing_lock(locks, task_id, task_title, now):
        return None
    lock = _create_task_lock(
        task_id, task_title, session_id, now, expires_at, agent_role
    )
    locks[task_id] = lock
    await _save_locks_registry(project_root, locks)

    logger.info(
        "Lock acquired: task_id=%s, task_title=%s, session_id=%s, expires_at=%s",
        task_id,
        task_title,
        session_id,
        expires_at.isoformat(),
    )
    return lock


async def release_task(project_root: Path, task_title: str) -> bool:
    """Release a lock on a task.

    Releases the lock if it exists and belongs to the current session.
    Returns True if lock was released, False if not found or belongs to
    another session.

    Args:
        project_root: Project root directory
        task_title: Roadmap entry title to unlock

    Returns:
        True if lock was released, False otherwise
    """
    task_id = generate_task_id(task_title)
    session_id = get_session_id()

    locks = await _load_locks_registry(project_root)
    locks = await _cleanup_expired_locks(project_root, locks)

    if task_id not in locks:
        logger.debug("No lock found for task %s", task_title)
        return False

    lock = locks[task_id]
    lock_session_id = lock.agent_session_id

    if lock_session_id != session_id:
        logger.warning(
            "Cannot release lock: task %s locked by session %s (current: %s)",
            task_title,
            lock_session_id,
            session_id,
        )
        return False

    del locks[task_id]
    await _save_locks_registry(project_root, locks)

    logger.info("Lock released: task_id=%s, task_title=%s", task_id, task_title)
    return True


async def list_active_locks(project_root: Path) -> list[TaskLock]:
    """List all active (non-expired) locks.

    Args:
        project_root: Project root directory

    Returns:
        List of TaskLock models
    """
    locks = await _load_locks_registry(project_root)
    locks = await _cleanup_expired_locks(project_root, locks)

    return list(locks.values())


async def check_task_available(project_root: Path, task_title: str) -> bool:
    """Check if a task is available (not locked).

    Args:
        project_root: Project root directory
        task_title: Roadmap entry title to check

    Returns:
        True if task is available, False if locked
    """
    task_id = generate_task_id(task_title)
    locks = await _load_locks_registry(project_root)
    locks = await _cleanup_expired_locks(project_root, locks)

    if task_id not in locks:
        return True

    lock = locks[task_id]
    try:
        expires_at_str = lock.expires_at.replace("Z", "+00:00")
        expires_at = datetime.fromisoformat(expires_at_str)
        return expires_at < datetime.now(UTC)
    except (ValueError, TypeError):
        # Invalid expiry, treat as expired
        return True
