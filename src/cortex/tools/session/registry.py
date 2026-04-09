"""Session Registry Operations

This module provides session registry functionality for Phase 58 multi-agent
specialization. It allows agents to register and deregister their sessions
so other agents can see what concurrent work is happening.

The registry is stored in `.cortex/.cache/sessions/active.json` and tracks
active sessions with their role, task, and start time.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import OperationStatus
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.core.session_logger import get_session_id
from cortex.optimization.agent_roles import AgentRole, normalize_role_name
from cortex.tools.session.models import ConcurrentSession, SessionRegistryResult

logger = logging.getLogger(__name__)

# Cache key for sessions registry
_SESSIONS_REGISTRY_KEY = "sessions/active.json"


async def _load_sessions_registry(
    project_root: Path,
) -> dict[str, ConcurrentSession]:
    """Load sessions registry from cache.

    Returns:
        Dictionary mapping session_id -> ConcurrentSession model
    """
    data = await read_cache_json(project_root, _SESSIONS_REGISTRY_KEY)
    if data is None or not isinstance(data, dict):
        return {}

    sessions: dict[str, ConcurrentSession] = {}
    for session_id_str, session_dict in data.items():
        if not isinstance(session_dict, dict):
            continue
        try:
            session = ConcurrentSession.model_validate(session_dict)
            sessions[str(session_id_str)] = session
        except Exception as e:
            logger.warning(
                "Failed to parse session data for session_id=%s: %s, skipping",
                session_id_str,
                e,
            )
            continue

    return sessions


async def _save_sessions_registry(
    project_root: Path, sessions: dict[str, ConcurrentSession]
) -> None:
    """Save sessions registry to cache."""
    # Serialize ConcurrentSession models to dict for JSON storage
    sessions_dict: dict[str, object] = {
        session_id: session.model_dump() for session_id, session in sessions.items()
    }
    await write_cache_json(project_root, _SESSIONS_REGISTRY_KEY, sessions_dict)


async def register_session(
    project_root: Path,
    task_title: str,
    agent_role: AgentRole | None = None,
) -> ConcurrentSession:
    """Register a new session in the registry.

    Args:
        project_root: Project root directory
        task_title: Task title being worked on
        agent_role: Optional agent role

    Returns:
        ConcurrentSession model for the registered session
    """
    session_id = get_session_id()
    now = datetime.now(UTC)

    sessions = await _load_sessions_registry(project_root)

    session = ConcurrentSession(
        agent_role=agent_role.value if agent_role else None,
        task=task_title,
        started=now.isoformat(),
        session_id=session_id,
    )

    sessions[session_id] = session
    await _save_sessions_registry(project_root, sessions)

    logger.info(
        "Session registered: session_id=%s, task=%s, role=%s",
        session_id,
        task_title,
        agent_role.value if agent_role else None,
    )
    return session


async def deregister_session(project_root: Path) -> bool:
    """Deregister the current session from the registry.

    Args:
        project_root: Project root directory

    Returns:
        True if session was deregistered, False if not found
    """
    session_id = get_session_id()
    sessions = await _load_sessions_registry(project_root)

    if session_id not in sessions:
        logger.debug("Session %s not found in registry", session_id)
        return False

    del sessions[session_id]
    await _save_sessions_registry(project_root, sessions)

    logger.info("Session deregistered: session_id=%s", session_id)
    return True


async def list_concurrent_sessions(
    project_root: Path, exclude_current: bool = True
) -> list[ConcurrentSession]:
    """List all concurrent sessions (excluding current session by default).

    Args:
        project_root: Project root directory
        exclude_current: If True, exclude the current session from results

    Returns:
        List of ConcurrentSession models
    """
    sessions = await _load_sessions_registry(project_root)
    session_id = get_session_id()

    result = list(sessions.values())
    if exclude_current:
        result = [s for s in result if s.session_id != session_id]

    return result


# ============================================================================
# MCP Tool Handlers
# ============================================================================


async def _register_session_impl(
    task_title: str, role: str | None, ctx: MCPContext | None
) -> str:
    """Implementation of register_session MCP tool."""
    await log_client(ctx, "info", "register_session: starting", logger_name=__name__)
    root = await resolve_project_root_async(None, ctx)

    # Normalize role string to AgentRole enum
    agent_role = normalize_role_name(role) if role else None

    _ = await register_session(root, task_title, agent_role=agent_role)

    result = SessionRegistryResult(
        status=OperationStatus.SUCCESS,
        message=f"Successfully registered session for task '{task_title}'",
        error=None,
    )
    await log_client(
        ctx, "info", f"register_session: success: {task_title}", logger_name=__name__
    )
    return result.model_dump_json()


# Internal; use session(operation="register") as MCP tool.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def session_register(
    task_title: str,
    role: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Register the current session in the session registry.

    USE WHEN: Starting work on a task to make your session visible to other
    agents; user begins implementation or a tracked task.

    EXAMPLES: session_register(task_title="Implement Phase 58 task locking"),
    session_register(task_title="Fix quality violations", role="quality").

    RETURNS: JSON with status (success/error), message, and optional error.

    Args:
        task_title: Task title being worked on.
        role: Optional agent role (feature, quality, testing, docs, planning,
            debugging, review).
        ctx: MCP context (automatically provided).

    Returns:
        JSON string with SessionRegistryResult (status, message, error).
    """
    try:
        return await _register_session_impl(task_title, role, ctx)
    except Exception as e:
        await log_client(ctx, "error", f"register_session: {e}", logger_name=__name__)
        result = SessionRegistryResult(
            status=OperationStatus.ERROR,
            message=f"Unexpected error: {e}",
            error=str(e),
        )
        return result.model_dump_json()


async def _deregister_session_impl(ctx: MCPContext | None) -> str:
    """Implementation of deregister_session MCP tool."""
    from cortex.setup.claude_settings import remove_once_hooks
    from cortex.tools.session.pipeline_handoff_io import get_file_state_cache

    await log_client(ctx, "info", "deregister_session: starting", logger_name=__name__)
    root = await resolve_project_root_async(None, ctx)
    session_id = get_session_id()
    settings_path = root / ".claude" / "settings.json"
    removed_once_count = remove_once_hooks(settings_path)
    logger.debug(
        "Deregister cleanup removed %d once hooks from %s",
        removed_once_count,
        settings_path,
    )
    get_file_state_cache(session_id, root).drop_all()

    deregistered = await deregister_session(root)
    result = _deregister_result(deregistered)
    await _log_deregister_result(ctx, deregistered)
    return result.model_dump_json()


def _deregister_result(deregistered: bool) -> SessionRegistryResult:
    if deregistered:
        return SessionRegistryResult(
            status=OperationStatus.SUCCESS,
            message="Successfully deregistered session",
            error=None,
        )
    return SessionRegistryResult(
        status=OperationStatus.ERROR,
        message="Session not found in registry",
        error="Session not found",
    )


async def _log_deregister_result(ctx: MCPContext | None, deregistered: bool) -> None:
    if deregistered:
        await log_client(
            ctx, "info", "deregister_session: success", logger_name=__name__
        )
        return
    await log_client(
        ctx,
        "warning",
        "deregister_session: session not found",
        logger_name=__name__,
    )


# Internal; use session(operation="deregister") as MCP tool.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def session_deregister(
    ctx: MCPContext | None = None,
) -> str:
    """Deregister the current session from the session registry.

    USE WHEN: Completing work or ending a session to remove it from the registry.

    EXAMPLES: session_deregister() when finishing a task; call after work is
    done so other agents see the session as inactive.

    RETURNS: JSON with status (success/error), message, and optional error.

    Args:
        ctx: MCP context (automatically provided).

    Example (success):
        >>> await session_deregister()
        {"status": "success", "message": "Successfully deregistered session", "error": null}

    Example (error — session not in registry):
        >>> await session_deregister()
        {"status": "error", "message": "Session not found in registry", "error": "Session not found"}
    """
    try:
        return await _deregister_session_impl(ctx)
    except Exception as e:
        await log_client(ctx, "error", f"deregister_session: {e}", logger_name=__name__)
        result = SessionRegistryResult(
            status=OperationStatus.ERROR,
            message=f"Unexpected error: {e}",
            error=str(e),
        )
        return result.model_dump_json()
