"""Task locking MCP tool handler implementations.

Implementation logic for claim_task_lock, release_task_lock, list_active_tasks,
and check_task_available_lock. Extracted to keep task_locking.py under 400 lines.

Uses lazy imports to avoid circular import with task_locking.
"""

from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import OperationStatus
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.tools.models import (
    CheckTaskAvailableResult,
    ClaimTaskErrorResult,
    ClaimTaskResult,
    ListActiveTasksResult,
    ReleaseTaskResult,
    TaskLock,
)
from cortex.tools.task_locking_helpers import generate_task_id


async def claim_task_impl(
    task_title: str, role: str | None, ctx: MCPContext | None
) -> str:
    """Implementation of claim_task MCP tool."""
    from cortex.optimization.agent_roles import normalize_role_name
    from cortex.tools.task_locking import claim_task

    await log_client(ctx, "info", "claim_task: starting", logger_name=__name__)
    root = await resolve_project_root_async(None, ctx)

    agent_role = normalize_role_name(role) if role else None

    lock = await claim_task(root, task_title, agent_role=agent_role)

    if lock is None:
        error_result = ClaimTaskErrorResult(
            error=f"Task '{task_title}' is already locked by another session",
            task_title=task_title,
        )
        await log_client(
            ctx,
            "warning",
            f"claim_task: task already locked: {task_title}",
            logger_name=__name__,
        )
        return error_result.model_dump_json()

    result = ClaimTaskResult(
        status=OperationStatus.SUCCESS,
        lock=lock,
        message=f"Successfully claimed lock on task '{task_title}'",
    )
    await log_client(
        ctx, "info", f"claim_task: success: {task_title}", logger_name=__name__
    )
    return result.model_dump_json()


async def release_task_impl(task_title: str, ctx: MCPContext | None) -> str:
    """Implementation of release_task MCP tool."""
    from cortex.tools.task_locking import release_task

    await log_client(ctx, "info", "release_task: starting", logger_name=__name__)
    root = await resolve_project_root_async(None, ctx)

    released = await release_task(root, task_title)

    if released:
        result = ReleaseTaskResult(
            status=OperationStatus.SUCCESS,
            task_title=task_title,
            released=True,
            message=f"Successfully released lock on task '{task_title}'",
            error=None,
        )
        await log_client(
            ctx, "info", f"release_task: success: {task_title}", logger_name=__name__
        )
    else:
        result = ReleaseTaskResult(
            status=OperationStatus.ERROR,
            task_title=task_title,
            released=False,
            message=f"Failed to release lock on task '{task_title}' (not found or locked by another session)",
            error="Lock not found or belongs to another session",
        )
        await log_client(
            ctx, "warning", f"release_task: failed: {task_title}", logger_name=__name__
        )

    return result.model_dump_json()


async def list_active_tasks_impl(ctx: MCPContext | None) -> str:
    """Implementation of list_active_tasks MCP tool."""
    from cortex.tools.task_locking import list_active_locks

    await log_client(ctx, "info", "list_active_tasks: starting", logger_name=__name__)
    root = await resolve_project_root_async(None, ctx)

    locks = await list_active_locks(root)

    result = ListActiveTasksResult(
        status=OperationStatus.SUCCESS,
        locks=locks,
        count=len(locks),
    )
    await log_client(
        ctx,
        "info",
        f"list_active_tasks: found {len(locks)} locks",
        logger_name=__name__,
    )
    return result.model_dump_json()


async def check_task_available_impl(task_title: str, ctx: MCPContext | None) -> str:
    """Implementation of check_task_available MCP tool."""
    from cortex.tools.task_locking import check_task_available, list_active_locks

    await log_client(
        ctx, "info", "check_task_available: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)

    available = await check_task_available(root, task_title)

    lock: TaskLock | None = None
    if not available:
        locks = await list_active_locks(root)
        task_id = generate_task_id(task_title)
        for active_lock in locks:
            if active_lock.task_id == task_id:
                lock = active_lock
                break

    result = CheckTaskAvailableResult(
        status=OperationStatus.SUCCESS,
        task_title=task_title,
        available=available,
        lock=lock,
    )
    await log_client(
        ctx,
        "info",
        f"check_task_available: {task_title} available={available}",
        logger_name=__name__,
    )
    return result.model_dump_json()
