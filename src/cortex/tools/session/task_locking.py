"""Task Locking Operations

This module provides task locking functionality for Phase 58 multi-agent
specialization. It allows agents to claim and release locks on roadmap items
to prevent duplicate work across concurrent sessions.

The locking mechanism is file-based and uses concurrent-safe JSON operations
via the cache_json_access module. Locks auto-expire after a configurable timeout
(default 2 hours) to prevent orphaned locks.
"""

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import OperationStatus
from cortex.core.session_logger import get_session_id
from cortex.optimization.agent_roles import AgentRole
from cortex.tools.models import (
    CheckTaskAvailableResult,
    ClaimTaskErrorResult,
    ListActiveTasksResult,
    ReleaseTaskResult,
    TaskLock,
)
from cortex.tools.session.task_locking_handlers import (
    check_task_available_impl,
    claim_task_impl,
    list_active_tasks_impl,
    release_task_impl,
)
from cortex.tools.session.task_locking_helpers import (
    check_existing_lock,
    cleanup_expired_locks,
    create_task_lock,
    generate_task_id,
    load_locks_registry,
    save_locks_registry,
)

logger = logging.getLogger(__name__)

# Default lock expiry timeout (2 hours per plan spec)
_DEFAULT_LOCK_TIMEOUT_HOURS = 2.0


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
    locks = await load_locks_registry(project_root)
    locks = await cleanup_expired_locks(project_root, locks)
    if await check_existing_lock(locks, task_id, task_title, now):
        return None
    lock = create_task_lock(
        task_id, task_title, session_id, now, expires_at, agent_role
    )
    locks[task_id] = lock
    await save_locks_registry(project_root, locks)

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

    locks = await load_locks_registry(project_root)
    locks = await cleanup_expired_locks(project_root, locks)

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
    await save_locks_registry(project_root, locks)

    logger.info("Lock released: task_id=%s, task_title=%s", task_id, task_title)
    return True


async def list_active_locks(project_root: Path) -> list[TaskLock]:
    """List all active (non-expired) locks.

    Args:
        project_root: Project root directory

    Returns:
        List of TaskLock models
    """
    locks = await load_locks_registry(project_root)
    locks = await cleanup_expired_locks(project_root, locks)

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
    locks = await load_locks_registry(project_root)
    locks = await cleanup_expired_locks(project_root, locks)

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


# ============================================================================
# MCP Tool Handlers
# ============================================================================


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def claim_task_lock(
    task_title: str,
    role: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Claim a lock on a roadmap task to prevent duplicate work.

    USE WHEN: Starting work on a roadmap item to prevent other sessions
    from working on the same task concurrently.

    EXAMPLES: 'claim task Phase 58: Multi-Agent Specialization', 'lock
    roadmap item Anthropic context engineering alignment'.

    RETURNS: JSON with lock data (task_title, task_id, expires_at, role)
    if successful; error JSON if task already locked.

    Args:
        task_title: Roadmap entry title to lock (e.g., "Phase 58: Multi-Agent Specialization").
        role: Optional agent role (feature, quality, testing, docs, planning, debugging, review).
        ctx: MCP context (automatically provided).

    Returns:
        JSON string with ClaimTaskResult or ClaimTaskErrorResult.
    """
    try:
        return await claim_task_impl(task_title, role, ctx)
    except Exception as e:
        await log_client(ctx, "error", f"claim_task: {e}", logger_name=__name__)
        error_result = ClaimTaskErrorResult(
            error=f"Unexpected error: {e}",
            task_title=task_title,
        )
        return error_result.model_dump_json()


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def release_task_lock(
    task_title: str,
    ctx: MCPContext | None = None,
) -> str:
    """Release a lock on a roadmap task.

    USE WHEN: Completing work on a roadmap item or switching to a different task.

    EXAMPLES: 'release task Phase 58', 'unlock Anthropic context engineering
    alignment', 'release lock on current roadmap item'.

    RETURNS: JSON with release status (released true/false, message).

    Args:
        task_title: Roadmap entry title to unlock.
        ctx: MCP context (automatically provided).

    Returns:
        JSON string with ReleaseTaskResult.
    """
    try:
        return await release_task_impl(task_title, ctx)
    except Exception as e:
        await log_client(ctx, "error", f"release_task: {e}", logger_name=__name__)
        result = ReleaseTaskResult(
            status=OperationStatus.ERROR,
            task_title=task_title,
            released=False,
            message=f"Unexpected error: {e}",
            error=str(e),
        )
        return result.model_dump_json()


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def list_active_tasks(
    ctx: MCPContext | None = None,
) -> str:
    """List all active (non-expired) task locks.

    USE WHEN: Checking what tasks are currently being worked on by other sessions.

    EXAMPLES: 'list active tasks', 'what tasks are locked', 'show active
    roadmap locks'.

    RETURNS: JSON with list of active locks (task_title, task_id, expires_at,
    role) and count.

    Args:
        ctx: MCP context (automatically provided).

    Returns:
        JSON string with ListActiveTasksResult.
    """
    try:
        return await list_active_tasks_impl(ctx)
    except Exception as e:
        await log_client(ctx, "error", f"list_active_tasks: {e}", logger_name=__name__)
        result = ListActiveTasksResult(
            status=OperationStatus.SUCCESS,
            locks=[],
            count=0,
        )
        return result.model_dump_json()


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def check_task_available_lock(
    task_title: str,
    ctx: MCPContext | None = None,
) -> str:
    """Check if a task is available (not locked).

    USE WHEN: Before claiming a task, check if it's already locked.

    EXAMPLES: 'check if Phase 58 is available', 'is Anthropic alignment
    task locked', 'can I work on this roadmap item'.

    RETURNS: JSON with available (true/false), task_title, and lock details
    if locked.

    Args:
        task_title: Roadmap entry title to check.
        ctx: MCP context (automatically provided).

    Returns:
        JSON string with CheckTaskAvailableResult.
    """
    try:
        return await check_task_available_impl(task_title, ctx)
    except Exception as e:
        await log_client(
            ctx, "error", f"check_task_available: {e}", logger_name=__name__
        )
        result = CheckTaskAvailableResult(
            status=OperationStatus.SUCCESS,
            task_title=task_title,
            available=True,  # Treat errors as available to avoid blocking
            lock=None,
        )
        return result.model_dump_json()
