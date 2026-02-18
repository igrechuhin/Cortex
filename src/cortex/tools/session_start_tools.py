"""Session Start Tool

This module provides the session_start tool that combines orientation tasks
(reading progress, checking git status, loading active context, health check)
into a single call - reducing tokens and time agents spend getting their bearings
at the start of every session.

Total: 1 tool
- session_start: Single tool replacing 3-5 manual orientation calls
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from cortex.core.constants import MCP_TOOL_TIMEOUT_FAST, MemoryBankFile
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import GitCommandResult
from cortex.core.token_counter import TokenCounter
from cortex.core.usage_context import (
    get_current_managers,
    get_or_resolve_project_root,
)
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.server import mcp
from cortex.tools.compaction_operations import read_handoff
from cortex.tools.connection_health import check_mcp_connection_health
from cortex.tools.file_section_helpers import extract_section_from_content
from cortex.tools.models import (
    ConcurrentSession,
    GitStatusSummary,
    MCPHealthCheckResponse,
    SessionBrief,
    SessionHandoff,
    SessionHealthSummary,
    SessionStartErrorResult,
    SessionStartResult,
    SessionStartResultUnion,
)
from cortex.tools.session_registry import list_concurrent_sessions
from cortex.tools.task_locking import list_active_locks

logger = logging.getLogger(__name__)

# Type alias for _gather_brief_components return (keeps function under 30 lines)
_BriefComponents = tuple[
    str,
    list[str],
    str | None,
    str | None,
    SessionHealthSummary,
    GitStatusSummary | None,
    str,
    SessionHandoff | None,
    list[ConcurrentSession],
    list[str],
]


def _parse_roadmap_sections(content: str) -> dict[str, tuple[int, int]]:
    """Parse roadmap to get section boundaries.

    Returns: {section_id: (start_line, end_line)}
    """
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


async def _run_git_command(
    cmd: list[str], cwd: Path | None = None, timeout: float = 5.0
) -> GitCommandResult:
    """Run a git command asynchronously with timeout.

    Args:
        cmd: Command and arguments as list
        cwd: Working directory (default: None)
        timeout: Timeout in seconds (default: 5.0)

    Returns:
        GitCommandResult with success status, stdout, stderr, returncode
    """
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


def _extract_current_focus(active_context_content: str) -> str:
    """Extract current focus from activeContext.md.

    Args:
        active_context_content: Full content of activeContext.md

    Returns:
        Current focus text (empty string if not found)
    """
    section_content, warning = extract_section_from_content(
        active_context_content, "## Current Focus"
    )
    # If section not found, extract_section_from_content returns full content
    if warning or not section_content:
        return ""
    # Remove the heading line and return content
    lines = section_content.split("\n")
    if lines and lines[0].strip().startswith("#"):
        return "\n".join(lines[1:]).strip()
    return section_content.strip()


def _extract_recent_completed(
    active_context_content: str, max_items: int = 5
) -> list[str]:
    """Extract recent completed items from activeContext.md.

    Args:
        active_context_content: Full content of activeContext.md
        max_items: Maximum number of items to return

    Returns:
        List of recent completed item descriptions
    """
    completed_items: list[str] = []
    lines = active_context_content.split("\n")

    # Find all "## Completed Work" sections
    in_completed_section = False
    for line in lines:
        if line.strip().startswith("## Completed Work"):
            in_completed_section = True
            continue
        if in_completed_section:
            # Stop at next top-level section (##)
            if line.strip().startswith("##") and not line.strip().startswith("###"):
                break
            # Extract bullet items (starting with "- ✅")
            if line.strip().startswith("- ✅") or line.strip().startswith("- **"):
                # Extract title/description (remove markdown formatting)
                item_text = line.strip()
                # Remove "- ✅" or "- **" prefix
                item_text = re.sub(r"^-\s*(✅\s*)?\*\*", "", item_text)
                # Remove trailing "**" and status markers
                item_text = re.sub(r"\*\*\s*-.*$", "", item_text)
                item_text = item_text.strip()
                if item_text:
                    completed_items.append(item_text)
                    if len(completed_items) >= max_items:
                        break

    return completed_items


async def _check_task_available_safe(project_root: Path | None, title: str) -> bool:
    """Check if task is available, returning True on error (don't block)."""
    if project_root is None:
        return True
    from cortex.tools.task_locking import check_task_available

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


async def _extract_next_work_item(
    roadmap_content: str, project_root: Path | None = None
) -> tuple[str | None, str | None]:
    """Extract next PENDING work item from roadmap, skipping locked tasks.

    Args:
        roadmap_content: Full content of roadmap.md
        project_root: Optional project root directory for lock checking.
            If None, lock checking is skipped (useful for tests).

    Returns:
        Tuple of (next_work_item_description, plan_path) or (None, None)
    """
    sections = _parse_roadmap_sections(roadmap_content)
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


async def _get_git_status(project_root: Path) -> GitStatusSummary | None:
    """Get git status summary.

    Args:
        project_root: Project root directory

    Returns:
        GitStatusSummary or None if git is unavailable
    """
    # Check if .git exists
    if not (project_root / ".git").exists():
        return None

    # Run git status --porcelain
    result = await _run_git_command(["git", "status", "--porcelain"], cwd=project_root)

    if not result.success:
        return None

    # Parse porcelain output
    modified_count = 0
    untracked_count = 0

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        # Porcelain format: XY filename
        # X = staged, Y = unstaged
        # M = modified, A = added, D = deleted, ?? = untracked
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


def _determine_token_budget_status(
    total_tokens: int, default_budget: int = 80000
) -> Literal["healthy", "warning", "over_budget"]:
    """Determine token budget status from usage.

    Args:
        total_tokens: Total tokens used
        default_budget: Default token budget

    Returns:
        Token budget status
    """
    token_usage_percent = (
        (total_tokens / default_budget * 100) if default_budget > 0 else 0
    )
    if token_usage_percent >= 100:
        return "over_budget"
    if token_usage_percent >= 85:
        return "warning"
    return "healthy"


async def _count_file_tokens(metadata_index: MetadataIndex, file_name: str) -> int:
    """Get token count for a file from metadata."""
    metadata = await metadata_index.get_file_metadata(file_name)
    if metadata and "token_count" in metadata:
        token_count_value = metadata["token_count"]
        if isinstance(token_count_value, int):
            return token_count_value
    return 0


async def _check_file_and_count_tokens(
    metadata_index: MetadataIndex,
    memory_bank_dir: Path,
    file_name: str,
) -> tuple[bool, int]:
    """Check if file exists and get its token count."""
    file_path = memory_bank_dir / file_name
    if file_path.exists():
        return True, await _count_file_tokens(metadata_index, file_name)
    return False, 0


_REQUIRED_FILES = [
    MemoryBankFile.PROJECT_BRIEF,
    MemoryBankFile.ACTIVE_CONTEXT,
    MemoryBankFile.ROADMAP,
    MemoryBankFile.PROGRESS,
    MemoryBankFile.SYSTEM_PATTERNS,
    MemoryBankFile.TECH_CONTEXT,
    MemoryBankFile.PRODUCT_CONTEXT,
]


async def _calculate_health_summary(
    managers: dict[str, object],
    project_root: Path,
) -> SessionHealthSummary:
    """Calculate health summary for session start."""
    managers_dict = cast(ManagersDict, managers)
    fs_manager: FileSystemManager = await get_manager(
        managers_dict, "fs", FileSystemManager
    )
    metadata_index: MetadataIndex = await get_manager(
        managers_dict, "index", MetadataIndex
    )

    file_count = 0
    total_tokens = 0
    missing_files: list[str] = []

    for file_name in _REQUIRED_FILES:
        exists, tokens = await _check_file_and_count_tokens(
            metadata_index, fs_manager.memory_bank_dir, file_name
        )
        if exists:
            file_count += 1
            total_tokens += tokens
        else:
            missing_files.append(file_name)

    return SessionHealthSummary(
        file_count=file_count,
        total_tokens=total_tokens,
        token_budget_status=_determine_token_budget_status(total_tokens),
        missing_files=missing_files,
        has_errors=len(missing_files) > 0,
    )


def _add_concurrency_suggestions(
    suggestions: list[str],
    locked_tasks: list[str] | None,
    concurrent_sessions: list[ConcurrentSession] | None,
) -> None:
    """Add suggestions about concurrent sessions and locked tasks."""
    if concurrent_sessions:
        session_count = len(concurrent_sessions)
        suggestions.append(
            f"{session_count} concurrent session(s) active — check locked_tasks to avoid duplicate work"
        )

    if locked_tasks:
        if len(locked_tasks) == 1:
            suggestions.append(f"Task locked by another session: {locked_tasks[0]}")
        else:
            suggestions.append(
                f"{len(locked_tasks)} tasks locked by other sessions — see locked_tasks field"
            )


def _add_mcp_and_git_suggestions(
    suggestions: list[str],
    mcp_healthy: bool,
    git_status: GitStatusSummary | None,
) -> None:
    """Append MCP and git-related suggestions."""
    if not mcp_healthy:
        suggestions.append(
            "Cortex MCP is disconnected or unhealthy. Reconnect the MCP server and "
            + "re-run this command; do not proceed without MCP."
        )
    if git_status and git_status.has_uncommitted_changes:
        suggestions.append(
            f"You have uncommitted changes ({git_status.modified_files_count} modified, "
            + f"{git_status.untracked_files_count} untracked) — consider committing first"
        )


def _add_budget_and_missing_suggestions(
    suggestions: list[str], health: SessionHealthSummary
) -> None:
    """Append token budget and missing-files suggestions."""
    if health.token_budget_status == "over_budget":
        suggestions.append(
            f"Token budget exceeded ({health.total_tokens} tokens) — consider compaction"
        )
    elif health.token_budget_status == "warning":
        suggestions.append(
            f"Token budget at {health.total_tokens / 80000 * 100:.0f}% — consider compaction"
        )
    if health.missing_files:
        suggestions.append(
            f"Missing required files: {', '.join(health.missing_files)} — run initialization"
        )


def _generate_session_suggestions(
    health: SessionHealthSummary,
    git_status: GitStatusSummary | None,
    next_work_item: str | None,
    locked_tasks: list[str] | None = None,
    concurrent_sessions: list[ConcurrentSession] | None = None,
    mcp_healthy: bool = True,
) -> list[str]:
    """Generate actionable suggestions for the session."""
    suggestions: list[str] = []
    _add_mcp_and_git_suggestions(suggestions, mcp_healthy, git_status)
    _add_budget_and_missing_suggestions(suggestions, health)
    _add_concurrency_suggestions(suggestions, locked_tasks, concurrent_sessions)
    if next_work_item:
        suggestions.append(f"Next roadmap item: {next_work_item}")
    return suggestions


async def _read_memory_bank_file(
    fs_manager: FileSystemManager, file_name: str
) -> tuple[str | None, str | None]:
    """Read a memory bank file.

    Args:
        fs_manager: File system manager
        file_name: Name of file to read

    Returns:
        Tuple of (content, error_message) or (None, error_message) if not found
    """
    file_path: Path = fs_manager.memory_bank_dir / file_name
    if not file_path.exists():
        return None, f"{file_name} not found"
    content: str
    content, _ = await fs_manager.read_file(file_path)
    return content, None


async def _extract_project_name(fs_manager: FileSystemManager) -> str:
    """Extract project name from projectBrief.md or return default.

    Args:
        fs_manager: File system manager

    Returns:
        Project name
    """
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
    try:
        return await list_concurrent_sessions(project_root, exclude_current=True)
    except Exception as e:
        logger.debug("Failed to load concurrent sessions: %s", e)
        return []


async def _load_locked_tasks_safe(project_root: Path) -> list[str]:
    """Load locked task titles, returning empty list on error."""
    try:
        locks = await list_active_locks(project_root)
        return [lock.task_title for lock in locks]
    except Exception as e:
        logger.debug("Failed to load locked tasks: %s", e)
        return []


async def _load_concurrency_info(
    project_root: Path,
) -> tuple[list[ConcurrentSession], list[str]]:
    """Load concurrent sessions and locked tasks."""
    concurrent_sessions = await _load_concurrent_sessions_safe(project_root)
    locked_tasks = await _load_locked_tasks_safe(project_root)
    return concurrent_sessions, locked_tasks


def _create_session_brief(
    project_name: str,
    current_focus: str,
    recent_completed: list[str],
    next_work_item: str | None,
    next_work_plan_path: str | None,
    health: SessionHealthSummary,
    git_status: GitStatusSummary | None,
    session_suggestions: list[str],
    last_handoff: SessionHandoff | None,
    concurrent_sessions: list[ConcurrentSession],
    locked_tasks: list[str],
    mcp_healthy: bool = True,
    mcp_health_message: str | None = None,
) -> SessionBrief:
    """Create SessionBrief from components."""
    return SessionBrief(
        project_name=project_name,
        current_focus=current_focus,
        recent_completed=recent_completed,
        next_work_item=next_work_item,
        next_work_plan_path=next_work_plan_path,
        health=health,
        git_status=git_status,
        session_suggestions=session_suggestions,
        last_handoff=last_handoff,
        concurrent_sessions=concurrent_sessions,
        locked_tasks=locked_tasks,
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )


def _create_brief_with_suggestions(
    suggestions: list[str],
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
    """Build SessionBrief from suggestions and components."""
    return _create_session_brief(
        project_name,
        current_focus,
        recent_completed,
        next_work_item,
        next_work_plan_path,
        health,
        git_status,
        suggestions,
        last_handoff,
        concurrent_sessions,
        locked_tasks,
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )


def _compute_suggestions_and_create_brief(
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
    """Compute suggestions and build SessionBrief."""
    suggestions = _generate_session_suggestions(
        health,
        git_status,
        next_work_item,
        locked_tasks,
        concurrent_sessions,
        mcp_healthy=mcp_healthy,
    )
    return _create_brief_with_suggestions(
        suggestions,
        project_name,
        current_focus,
        recent_completed,
        next_work_item,
        next_work_plan_path,
        health,
        git_status,
        last_handoff,
        concurrent_sessions,
        locked_tasks,
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
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
    """Assemble session brief from collected components."""
    return _compute_suggestions_and_create_brief(
        project_name,
        current_focus,
        recent_completed,
        next_work_item,
        next_work_plan_path,
        health,
        git_status,
        last_handoff,
        concurrent_sessions,
        locked_tasks,
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )


async def _gather_brief_components(
    active_context_content: str,
    roadmap_content: str,
    managers: dict[str, object],
    project_root: Path,
    fs_manager: FileSystemManager,
) -> _BriefComponents:
    """Gather all components needed to build a session brief."""
    current_focus = _extract_current_focus(active_context_content)
    recent_completed = _extract_recent_completed(active_context_content)
    next_work_item, next_work_plan_path = await _extract_next_work_item(
        roadmap_content, project_root
    )
    health = await _calculate_health_summary(managers, project_root)
    git_status = await _get_git_status(project_root)
    project_name = await _extract_project_name(fs_manager)
    last_handoff = await read_handoff(project_root, fs_manager)
    concurrent_sessions, locked_tasks = await _load_concurrency_info(project_root)
    return (
        current_focus,
        recent_completed,
        next_work_item,
        next_work_plan_path,
        health,
        git_status,
        project_name,
        last_handoff,
        concurrent_sessions,
        locked_tasks,
    )


async def _build_session_brief(
    active_context_content: str,
    roadmap_content: str,
    managers: dict[str, object],
    project_root: Path,
    fs_manager: FileSystemManager,
    mcp_healthy: bool = True,
    mcp_health_message: str | None = None,
) -> SessionBrief:
    """Build session brief from extracted information."""
    c = await _gather_brief_components(
        active_context_content, roadmap_content, managers, project_root, fs_manager
    )
    return _assemble_session_brief(
        c[6],
        c[0],
        c[1],
        c[2],
        c[3],
        c[4],
        c[5],
        c[7],
        c[8],
        c[9],
        mcp_healthy=mcp_healthy,
        mcp_health_message=mcp_health_message,
    )


async def _load_memory_bank_files(
    fs_manager: FileSystemManager,
) -> tuple[str, str] | SessionStartErrorResult:
    """Load activeContext.md and roadmap.md files.

    Returns:
        Tuple of (active_context_content, roadmap_content) or error result
    """
    active_context_content, error = await _read_memory_bank_file(
        fs_manager, MemoryBankFile.ACTIVE_CONTEXT
    )
    if error:
        return SessionStartErrorResult(status="error", error=error)

    roadmap_content, error = await _read_memory_bank_file(
        fs_manager, MemoryBankFile.ROADMAP
    )
    if error:
        return SessionStartErrorResult(status="error", error=error)

    assert active_context_content is not None
    assert roadmap_content is not None
    return active_context_content, roadmap_content


def _parse_mcp_health(health_json: str) -> tuple[bool, str | None]:
    """Parse check_mcp_connection_health JSON; return (healthy, message)."""
    try:
        data = MCPHealthCheckResponse.model_validate_json(health_json)
        if data.status != "success":
            return False, data.error or "MCP health check failed"
        if data.health is None:
            return False, "MCP health check response invalid"
        if data.health.healthy:
            return True, None
        return False, "MCP connection unhealthy"
    except (json.JSONDecodeError, TypeError, ValidationError):
        return False, "MCP health check response invalid"


async def _get_mcp_health_status() -> tuple[bool, str | None]:
    """Run MCP health check; return (healthy, message)."""
    try:
        health_json = await check_mcp_connection_health()
        return _parse_mcp_health(health_json)
    except Exception as e:
        logger.debug("MCP health check failed: %s", e)
        return False, str(e) or "MCP health check failed"


async def _session_start_success_result(
    brief: SessionBrief,
    managers_dict: ManagersDict,
) -> SessionStartResult:
    """Build SessionStartResult with token count from brief."""
    tc: TokenCounter = await get_manager(managers_dict, "tokens", TokenCounter)
    return SessionStartResult(
        status="success",
        brief=brief,
        token_count=tc.count_tokens(brief.model_dump_json()),
    )


async def _load_brief_and_return_result(
    fs_manager: FileSystemManager,
    managers_dict: ManagersDict,
    managers: dict[str, object],
    project_root: Path,
    mcp_healthy: bool,
    mcp_health_message: str | None,
) -> SessionStartResultUnion:
    """Load memory bank, build brief, return result or error."""
    try:
        memory_bank_result = await _load_memory_bank_files(fs_manager)
        if isinstance(memory_bank_result, SessionStartErrorResult):
            return memory_bank_result
        act, rdm = memory_bank_result
        brief = await _build_session_brief(
            act,
            rdm,
            managers,
            project_root,
            fs_manager,
            mcp_healthy=mcp_healthy,
            mcp_health_message=mcp_health_message,
        )
        return await _session_start_success_result(brief, managers_dict)
    except Exception as e:
        logger.exception("Error in session_start")
        return SessionStartErrorResult(
            status="error", error=f"Failed to generate session brief: {str(e)}"
        )


async def _session_start_impl(
    task_description: str | None,
    project_root: Path,
    managers: dict[str, object],
) -> SessionStartResultUnion:
    """Implementation of session_start tool."""
    managers_dict = cast(ManagersDict, managers)
    fs_manager: FileSystemManager = await get_manager(
        managers_dict, "fs", FileSystemManager
    )
    mcp_healthy, mcp_health_message = await _get_mcp_health_status()
    return await _load_brief_and_return_result(
        fs_manager,
        managers_dict,
        managers,
        project_root,
        mcp_healthy,
        mcp_health_message,
    )


@mcp.tool(
    annotations=read_only_annotations(
        "Session Start Initializer",
        idempotent=False,
    ),
)
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
        {
          "status": "success",
          "brief": {
            "project_name": "Cortex",
            "current_focus": "Implementing Phase 54: Session Start Initializer",
            "recent_completed": [
              "Phase 50 Step 6: Testing and Validation",
              "Phase 51: Just-in-Time Context with Section-Level Loading"
            ],
            "next_work_item": "Phase 54: Session Start Initializer Pattern",
            "next_work_plan_path": ".cortex/plans/phase-54-session-start-initializer-pattern.md",
            "health": {
              "file_count": 7,
              "total_tokens": 45000,
              "token_budget_status": "healthy",
              "missing_files": [],
              "has_errors": false
            },
            "git_status": {
              "has_uncommitted_changes": true,
              "modified_files_count": 2,
              "untracked_files_count": 0
            },
            "session_suggestions": [
              "You have uncommitted changes (2 modified, 0 untracked) — consider committing first",
              "Next roadmap item: Phase 54: Session Start Initializer Pattern"
            ]
          },
          "token_count": 856
        }
    """
    await log_client(ctx, "info", "session_start: starting", logger_name=__name__)

    project_root: Path = await get_or_resolve_project_root(ctx)
    managers_raw = get_current_managers()
    if managers_raw is None:
        return SessionStartErrorResult(
            status="error",
            error="Managers not initialized",
        ).model_dump_json(exclude_none=True)
    managers: dict[str, object] = managers_raw

    result = await _session_start_impl(task_description, project_root, managers)

    return result.model_dump_json(exclude_none=True)
