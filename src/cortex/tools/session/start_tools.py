"""Session Start Tool

This module provides the session_start tool that combines orientation tasks
(reading progress, checking git status, loading active context, health check)
into a single call - reducing tokens and time agents spend getting their bearings
at the start of every session.

Implementation is split across:
- session_start_tools: orchestration, roadmap parsing, git, task locking, tool entry
- session_health: health summary and MCP health check
- session_brief: brief building (suggestions, assembly)

Total: 1 tool
- session_start: Single tool replacing 3-5 manual orientation calls
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import cast

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.models import GitCommandResult
from cortex.core.security import acquire_git_operation_slot
from cortex.core.token_counter import TokenCounter
from cortex.core.usage_context import (
    get_current_managers,
    get_or_resolve_project_root,
)
from cortex.managers.types import ManagersDict
from cortex.managers.utils import get_manager
from cortex.tools.models_base import ToolResultStatus
from cortex.tools.session.brief import (
    build_session_brief,
    load_memory_bank_files,
)
from cortex.tools.session.models import (
    GitStatusSummary,
    SessionBrief,
    SessionStartErrorResult,
    SessionStartResult,
    SessionStartResultUnion,
)

logger = logging.getLogger(__name__)


def _session_start_union_to_json(result: SessionStartResultUnion) -> str:
    """Serialize session start result and verify JSON is parseable (stdlib)."""
    raw = result.model_dump_json(exclude_none=True)
    if isinstance(result, SessionStartErrorResult):
        return raw
    try:
        json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("SessionStartResult JSON round-trip failed")
        return SessionStartErrorResult(
            status=ToolResultStatus.ERROR,
            error=(
                "Session brief produced invalid JSON after serialization; "
                "try again or report."
            ),
        ).model_dump_json(exclude_none=True)
    return raw


def _session_has_context_telemetry(project_root: Path) -> bool:
    """Return True when current session already has context-call telemetry."""
    from cortex.core.session_logger import get_session_log_path, read_session_log

    session_log = read_session_log(get_session_log_path(project_root))
    return session_log is not None and bool(session_log.load_context_calls)


def _seed_session_start_context_telemetry(
    project_root: Path,
    token_count: int,
) -> None:
    """Write one early-session telemetry row for context analysis, once per session."""
    if _session_has_context_telemetry(project_root):
        return
    from cortex.core.session_logger import log_load_context_call

    # Keep this non-synthetic and internally consistent so it remains rollup-eligible.
    log_load_context_call(
        project_root=project_root,
        task_description="Session orientation bootstrap",
        token_budget=max(token_count, 1),
        strategy="session_start",
        selected_files=["activeContext.md", "roadmap.md"],
        selected_sections={},
        total_tokens=max(token_count, 1),
        utilization=1.0,
        excluded_files=[],
        relevance_scores={},
        role="feature",
    )


def parse_roadmap_sections(content: str) -> dict[str, tuple[int, int]]:
    """Parse roadmap to get section boundaries. Returns {section_id: (start_line, end_line)}."""
    sections: dict[str, tuple[int, int]] = {}
    lines = content.split("\n")
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$")
    header_to_section = {
        "Blockers (ASAP Priority)": "blockers",
        "Active Work (in progress)": "active_work",
        "Future Enhancements": "future",
        "Pending plans (from .cortex/plans)": "pending",
    }
    current_section_name: str | None = None
    current_section_start = 0
    for i, line in enumerate(lines):
        match = header_pattern.match(line)
        if not match:
            continue
        header_text = match.group(2)
        section_id = header_to_section.get(header_text)
        if current_section_name is not None:
            sections[current_section_name] = (current_section_start, i - 1)
        if section_id:
            current_section_name = section_id
            current_section_start = i
    if current_section_name is not None:
        sections[current_section_name] = (current_section_start, len(lines) - 1)
    return sections


def _create_error_result(msg: str) -> GitCommandResult:
    """Create error GitCommandResult."""
    return GitCommandResult(
        success=False, stdout="", stderr=msg, returncode=None, error=msg
    )


async def run_git_command(
    cmd: list[str], cwd: Path | None = None, timeout: float = 5.0
) -> GitCommandResult:
    """Run a git command asynchronously with timeout."""
    await acquire_git_operation_slot()
    try:
        async with asyncio.timeout(timeout):
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            return GitCommandResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                returncode=process.returncode,
            )
    except TimeoutError:
        return _create_error_result(f"Command timed out after {timeout}s")
    except Exception as e:
        return _create_error_result(str(e))


async def _check_task_available_safe(project_root: Path | None, title: str) -> bool:
    """Check if task is available, returning True on error (don't block)."""
    if project_root is None:
        return True
    from cortex.tools.session.task_locking import check_task_available

    try:
        return await check_task_available(project_root, title)
    except Exception:
        logger.debug("Lock check failed for %s, continuing anyway", title)
        return True


async def _process_pending_line(
    line: str, project_root: Path | None
) -> tuple[str | None, str | None]:
    """Process a PENDING line and return (work_item, plan_path) or (None, None)."""
    match = re.match(
        r"^-\s*\*\*(.+?)\*\*\s*-\s*PENDING\s*-\s*(.+?)(?:\.\s*Plan:\s*(.+?))?\.?$", line
    )
    if match:
        title = match.group(1).strip()
        description = match.group(2).strip()
        plan_path = match.group(3).strip() if match.group(3) else None
        work_item = f"{title} - {description}"
        if await _check_task_available_safe(project_root, title):
            return (work_item, plan_path)
        logger.debug("Skipping locked task: %s (locked by another session)", title)
        return (None, None)
    title_match = re.match(r"^-\s*\*\*(.+?)\*\*", line)
    if title_match:
        title = title_match.group(1).strip()
        if await _check_task_available_safe(project_root, title):
            return (title, None)
        logger.debug("Skipping locked task: %s (locked by another session)", title)
    return (None, None)


async def extract_next_work_item(
    roadmap_content: str, project_root: Path | None = None
) -> tuple[str | None, str | None]:
    """Extract next PENDING work item from roadmap, skipping locked tasks."""
    sections = parse_roadmap_sections(roadmap_content)
    lines = roadmap_content.split("\n")
    for section_id in ["blockers", "active_work", "future", "pending"]:
        if section_id not in sections:
            continue
        section_start, section_end = sections[section_id]
        for i in range(section_start + 1, section_end + 1):
            if i >= len(lines):
                break
            line = lines[i].strip()
            if line.startswith("- **") and "PENDING" in line:
                work_item, plan_path = await _process_pending_line(line, project_root)
                if work_item:
                    return (work_item, plan_path)
    return (None, None)


async def get_git_status(project_root: Path) -> GitStatusSummary | None:
    """Get git status summary. Returns GitStatusSummary or None if git unavailable."""
    if not (project_root / ".git").exists():
        return None
    result = await run_git_command(["git", "status", "--porcelain"], cwd=project_root)
    if not result.success:
        return None
    modified_count = 0
    untracked_count = 0
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        status = line[:2]
        if status == "??":
            untracked_count += 1
        elif status[0] in "MAD" or status[1] in "MAD":
            modified_count += 1
    return GitStatusSummary(
        has_uncommitted_changes=modified_count > 0 or untracked_count > 0,
        modified_files_count=modified_count,
        untracked_files_count=untracked_count,
    )


async def _session_start_success_result(
    brief: SessionBrief,
    managers_dict: ManagersDict,
) -> SessionStartResult:
    """Build SessionStartResult with token count from brief."""
    tc: TokenCounter = await get_manager(managers_dict, "tokens", TokenCounter)
    return SessionStartResult(
        status=ToolResultStatus.SUCCESS,
        brief=brief,
        token_count=tc.count_tokens(brief.model_dump_json()),
    )


async def _get_session_optional_context(
    roadmap_content: str, project_root: Path
) -> tuple[GitStatusSummary | None, str | None, str | None]:
    """Get git status and next work item; return (git_status, next_work_item, plan_path)."""
    try:
        git_status = await get_git_status(project_root)
    except Exception as e:  # pragma: no cover - exercised indirectly via tools
        logger.debug("get_git_status failed in session_start: %s", e)
        git_status = None
    try:
        next_work_item, next_work_plan_path = await extract_next_work_item(
            roadmap_content, project_root
        )
    except Exception as e:  # pragma: no cover - exercised indirectly via tools
        logger.debug("extract_next_work_item failed in session_start: %s", e)
        next_work_item, next_work_plan_path = (None, None)
    return (git_status, next_work_item, next_work_plan_path)


async def _load_and_build_brief(
    fs_manager: FileSystemManager,
    managers: ManagersDict,
    project_root: Path,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> SessionStartResultUnion:
    """Load memory bank files, build brief, return success result or error."""
    memory_bank_result = await load_memory_bank_files(fs_manager)
    if isinstance(memory_bank_result, SessionStartErrorResult):
        return memory_bank_result
    act, rdm = memory_bank_result
    git_status, next_work_item, next_work_plan_path = (
        await _get_session_optional_context(rdm, project_root)
    )
    brief = await build_session_brief(
        act,
        managers,
        project_root,
        fs_manager,
        git_status=git_status,
        next_work_item=next_work_item,
        next_work_plan_path=next_work_plan_path,
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )
    return await _session_start_success_result(brief, managers)


async def _load_brief_and_return_result(
    fs_manager: FileSystemManager,
    managers: ManagersDict,
    project_root: Path,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> SessionStartResultUnion:
    """Load memory bank, build brief, return result or error."""
    try:
        return await _load_and_build_brief(
            fs_manager, managers, project_root, mcp_healthy, mcp_health_message
        )
    except Exception as e:
        logger.exception("Error in session_start")
        return SessionStartErrorResult(
            status=ToolResultStatus.ERROR,
            error=f"Failed to generate session brief: {str(e)}",
        )


async def session_start_impl(
    task_description: str | None,
    project_root: Path,
    managers: ManagersDict,
) -> SessionStartResultUnion:
    """Implementation of session_start tool."""
    fs_manager: FileSystemManager = await get_manager(managers, "fs", FileSystemManager)
    # Import inside function so tests patching cortex.tools.session.health work
    # as expected without relying on re-importing this module.
    from cortex.tools.session import health as session_health

    mcp_healthy, mcp_health_message = await session_health.get_mcp_health_status()
    result = await _load_brief_and_return_result(
        fs_manager,
        managers,
        project_root,
        mcp_healthy,
        mcp_health_message,
    )
    if (
        isinstance(result, SessionStartResult)
        and result.status == ToolResultStatus.SUCCESS
    ):
        _seed_session_start_context_telemetry(project_root, result.token_count)
    return result


# Internal; use session(operation="start") as MCP tool.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_FAST)
async def session_start(
    task_description: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Get session orientation brief combining multiple orientation tasks.

    USE WHEN: Starting a new session, user wants project context, user needs
    orientation, user requests session brief.

    EXAMPLES: 'session start', 'get session brief', 'orient me to the project',
    'what should I work on next'.

    RETURNS: JSON with SessionBrief containing current focus, next work item,
    health check, git status, and actionable suggestions.

    This tool combines 3-5 manual orientation calls into a single call:
    - Reads activeContext.md for current focus and recent completed work
    - Reads roadmap.md to find next PENDING work item
    - Runs lightweight health check (file count, token budget, missing files)
    - Optionally reads git status (uncommitted changes count)
    - Generates actionable suggestions

    The brief is designed to be < 1000 tokens, providing efficient orientation
    without loading full context.

    Args:
        task_description: Optional task description for future relevance scoring.
            Currently unused but reserved for future enhancements.

    Returns:
        JSON string containing SessionStartResult with:
        - status: "success" or "error"
        - brief: SessionBrief with orientation data
        - token_count: Token count of the brief
        - error: Error message (only if status is "error")

    Example:
        >>> session_start()
        {"status": "success", "brief": {"current_focus": "...", "next_work_item": "...",
         "health": {...}, "git_status": {...}, "session_suggestions": [...]}, "token_count": 261}
    """
    await log_client(ctx, "info", "session_start: starting", logger_name=__name__)

    project_root: Path = await get_or_resolve_project_root(ctx)
    managers_raw = get_current_managers()
    if managers_raw is None:
        return SessionStartErrorResult(
            status=ToolResultStatus.ERROR,
            error="Managers not initialized",
        ).model_dump_json(exclude_none=True)
    managers = cast(ManagersDict, managers_raw)

    result = await session_start_impl(task_description, project_root, managers)

    return _session_start_union_to_json(result)
