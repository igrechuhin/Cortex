"""Task locking helper functions.

Registry I/O and lock utilities for task_locking module. Extracted to keep
task_locking.py under the 400-line limit.
"""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.optimization.agent_roles import AgentRole
from cortex.tools.models import TaskLock

logger = logging.getLogger(__name__)

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


async def load_locks_registry(project_root: Path) -> dict[str, TaskLock]:
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


async def save_locks_registry(project_root: Path, locks: dict[str, TaskLock]) -> None:
    """Save locks registry to cache."""
    locks_dict: dict[str, object] = {
        task_id: lock.model_dump() for task_id, lock in locks.items()
    }
    await write_cache_json(project_root, _LOCKS_REGISTRY_KEY, locks_dict)


async def cleanup_expired_locks(
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


async def check_existing_lock(
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


def create_task_lock(
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
