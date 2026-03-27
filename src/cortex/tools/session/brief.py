"""Session brief building for session_start.

Extracted from session_start_tools to keep file size under 400 lines.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.file_system import FileSystemManager
from cortex.managers.types import ManagersDict
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.session.brief_extraction_helpers import (
    extract_focus_and_completed,
    generate_session_suggestions,
)
from cortex.tools.session.brief_helpers import (
    brief_from_suggestions_and_context,
    session_brief_context_kwargs,
)
from cortex.tools.session.health import calculate_health_summary
from cortex.tools.session.models import (
    ConcurrentSession,
    GitStatusSummary,
    SessionBrief,
    SessionHandoff,
    SessionHealthSummary,
    SessionStartErrorResult,
)
from cortex.tools.session.registry import list_concurrent_sessions
from cortex.tools.session.start_models import BriefInputs as _BriefInputs


async def _read_memory_bank_file(
    fs_manager: FileSystemManager, file_name: str
) -> tuple[str | None, str | None]:
    """Read a memory bank file. Returns (content, error_message)."""
    file_path: Path = fs_manager.memory_bank_dir / file_name
    if not file_path.exists():
        return None, f"{file_name} not found"
    content: str
    content, _ = await fs_manager.read_file(file_path)
    return content, None


async def _extract_project_name(fs_manager: FileSystemManager) -> str:
    """Extract project name from projectBrief.md or return default."""
    project_name: str = "Cortex"
    project_brief_path: Path = fs_manager.memory_bank_dir / MemoryBankFile.PROJECT_BRIEF
    if project_brief_path.exists():
        project_brief_content: str
        project_brief_content, _ = await fs_manager.read_file(project_brief_path)
        first_line: str = (
            project_brief_content.split("\n")[0] if project_brief_content else ""
        )
        if first_line.startswith("#"):
            project_name = first_line.replace("#", "").strip()
    return project_name


async def _load_concurrent_sessions_safe(
    project_root: Path,
) -> list[ConcurrentSession]:
    """Load concurrent sessions, returning empty list on error."""
    import logging

    logger = logging.getLogger(__name__)
    try:
        return await list_concurrent_sessions(project_root, exclude_current=True)
    except Exception as e:
        logger.debug("Failed to load concurrent sessions: %s", e)
        return []


async def _load_locked_tasks_safe(project_root: Path) -> list[str]:
    """Load locked task titles, returning empty list on error."""
    import logging

    from cortex.tools.session.task_locking import list_active_locks

    logger = logging.getLogger(__name__)
    try:
        locks = await list_active_locks(project_root)
        return [lock.task_title for lock in locks]
    except Exception as e:
        logger.debug("Failed to load locked tasks: %s", e)
        return []


async def _load_concurrency_info(
    project_root: Path,
) -> tuple[list[ConcurrentSession], list[str]]:
    """Load concurrent sessions and locked tasks in parallel."""
    concurrent_sessions, locked_tasks = await asyncio.gather(
        _load_concurrent_sessions_safe(project_root),
        _load_locked_tasks_safe(project_root),
    )
    return concurrent_sessions, locked_tasks


def _compute_suggestions_and_create_brief(inp: _BriefInputs) -> SessionBrief:
    """Compute suggestions and build SessionBrief."""
    return brief_from_suggestions_and_context(
        generate_session_suggestions(
            inp.health,
            inp.git_status,
            inp.next_work_item,
            inp.locked_tasks,
            inp.concurrent_sessions,
            mcp_healthy=inp.mcp_healthy,
        ),
        session_brief_context_kwargs(
            inp.project_name,
            inp.current_focus,
            inp.recent_completed,
            inp.next_work_item,
            inp.next_work_plan_path,
            inp.health,
            inp.git_status,
            inp.last_handoff,
            inp.concurrent_sessions,
            inp.locked_tasks,
            inp.mcp_healthy,
            inp.mcp_health_message,
        ),
    )


def _assemble_session_brief(
    project_name: str,
    current_focus: str,
    recent_completed: list[str],
    next_work_item: str | None,
    next_work_plan_path: str | None,
    health: SessionHealthSummary,
    git_status: GitStatusSummary | None,
    last_handoff: SessionHandoff | None,
    concurrent_sessions: list[ConcurrentSession],
    locked_tasks: list[str],
    mcp_healthy: bool = True,
    mcp_health_message: str | None = None,
) -> SessionBrief:
    """Assemble session brief from collected components.

    Includes ``session_scope`` (single-goal discipline) via ``brief_helpers`` assembly.
    """
    inp = _BriefInputs(
        project_name=project_name,
        current_focus=current_focus,
        recent_completed=recent_completed,
        next_work_item=next_work_item,
        next_work_plan_path=next_work_plan_path,
        health=health,
        git_status=git_status,
        last_handoff=last_handoff,
        concurrent_sessions=concurrent_sessions,
        locked_tasks=locked_tasks,
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )
    return _compute_suggestions_and_create_brief(inp)


def _assemble_brief_from_components(
    c: tuple[
        str,
        list[str],
        SessionHealthSummary,
        str,
        SessionHandoff | None,
        list[ConcurrentSession],
        list[str],
    ],
    next_work_item: str | None,
    next_work_plan_path: str | None,
    git_status: GitStatusSummary | None,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> SessionBrief:
    """Unpack gathered components into _assemble_session_brief."""
    return _assemble_session_brief(
        c[3],
        c[0],
        c[1],
        next_work_item,
        next_work_plan_path,
        c[2],
        git_status,
        c[4],
        c[5],
        c[6],
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )


async def _load_brief_async(
    managers: ManagersDict,
    project_root: Path,
    fs_manager: FileSystemManager,
) -> tuple[
    SessionHealthSummary, str, SessionHandoff | None, list[ConcurrentSession], list[str]
]:
    """Load health, project name, handoff, and concurrency for brief in parallel."""
    from cortex.tools.memory.compaction_operations import read_handoff

    health, project_name, last_handoff, (concurrent_sessions, locked_tasks) = (
        await asyncio.gather(
            calculate_health_summary(managers, project_root),
            _extract_project_name(fs_manager),
            read_handoff(project_root, fs_manager),
            _load_concurrency_info(project_root),
        )
    )
    return health, project_name, last_handoff, concurrent_sessions, locked_tasks


_BriefComponents = tuple[
    str,
    list[str],
    SessionHealthSummary,
    str,
    SessionHandoff | None,
    list[ConcurrentSession],
    list[str],
]


async def _gather_brief_components(
    active_context_content: str,
    managers: ManagersDict,
    project_root: Path,
    fs_manager: FileSystemManager,
    git_status: GitStatusSummary | None,
    next_work_item: str | None,
    next_work_plan_path: str | None,
) -> _BriefComponents:
    """Gather components needed to build a session brief (caller provides git/next)."""
    current_focus, recent_completed = extract_focus_and_completed(
        active_context_content
    )
    (
        health,
        project_name,
        last_handoff,
        concurrent_sessions,
        locked_tasks,
    ) = await _load_brief_async(managers, project_root, fs_manager)
    return (
        current_focus,
        recent_completed,
        health,
        project_name,
        last_handoff,
        concurrent_sessions,
        locked_tasks,
    )


async def build_session_brief(
    active_context_content: str,
    managers: ManagersDict,
    project_root: Path,
    fs_manager: FileSystemManager,
    git_status: GitStatusSummary | None,
    next_work_item: str | None,
    next_work_plan_path: str | None,
    mcp_healthy: bool = True,
    mcp_health_message: str | None = None,
) -> SessionBrief:
    """Build session brief from extracted information (caller provides git/next).

    Every successful brief includes ``session_scope`` prompting one primary goal per session.
    """
    c = await _gather_brief_components(
        active_context_content,
        managers,
        project_root,
        fs_manager,
        git_status,
        next_work_item,
        next_work_plan_path,
    )
    return _assemble_brief_from_components(
        c,
        next_work_item,
        next_work_plan_path,
        git_status,
        mcp_healthy,
        mcp_health_message,
    )


async def load_memory_bank_files(
    fs_manager: FileSystemManager,
) -> tuple[str, str] | SessionStartErrorResult:
    """Load activeContext.md and roadmap.md in parallel. Returns tuple or error."""
    (active_content, active_err), (roadmap_content, roadmap_err) = await asyncio.gather(
        _read_memory_bank_file(fs_manager, MemoryBankFile.ACTIVE_CONTEXT),
        _read_memory_bank_file(fs_manager, MemoryBankFile.ROADMAP),
    )
    if active_err:
        return SessionStartErrorResult(status=ToolResultStatus.ERROR, error=active_err)
    if roadmap_err:
        return SessionStartErrorResult(status=ToolResultStatus.ERROR, error=roadmap_err)
    assert active_content is not None and roadmap_content is not None
    return active_content, roadmap_content
