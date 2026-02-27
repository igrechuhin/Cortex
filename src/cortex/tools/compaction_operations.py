"""Session compaction tool and handoff read/write (Phase 56)."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import cast

from cortex.core.cache_utils import CacheType, get_cache_dir
from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.security import acquire_git_operation_slot
from cortex.core.token_counter import TokenCounter
from cortex.core.usage_context import (
    get_current_managers,
    get_or_resolve_project_root,
)
from cortex.core.version_manager import VersionManager
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.tools.compaction_constants import (
    PROGRESS_TOKEN_THRESHOLD_DEFAULT,
    SESSION_HANDOFF_FILENAME,
    SESSION_HANDOFF_SCHEMA_VERSION,
    SESSION_PROGRESS_FILENAME,
)
from cortex.tools.compaction_helpers import (
    apply_progress_tiers,
    compact_active_context_completed_work,
    trim_recent_changes,
)
from cortex.tools.file_operations import execute_memory_bank_write
from cortex.tools.models import InProgressTask, SessionHandoff

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _HandoffParams:
    """Optional structured params for compact_session handoff."""

    completed_tasks: list[str] | None = None
    in_progress_task: str | None = None
    in_progress_notes: str | None = None
    blockers: list[str] | None = None
    decisions_made: list[str] | None = None


@dataclass(frozen=True)
class _CompactWriteCtx:
    project_root: Path
    fs_manager: FileSystemManager
    token_counter: TokenCounter
    metadata_index: MetadataIndex
    version_manager: VersionManager


def _today_iso() -> str:
    """Return today's date as YYYY-MM-DD."""
    return date.today().strftime("%Y-%m-%d")


def _session_id_from_now() -> str:
    """Return session id in format YYYY-MM-DDTHH-MM."""
    return datetime.now().strftime("%Y-%m-%dT%H-%M")


def _handoff_path(project_root: Path) -> Path:
    """Path to last_handoff.json under .cortex/.cache/session."""
    session_dir = get_cache_dir(project_root, CacheType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / SESSION_HANDOFF_FILENAME


def _pre_compact_snapshot_path(project_root: Path, file_name: str) -> Path:
    """Path for pre-compaction snapshot file."""
    session_dir = get_cache_dir(project_root, CacheType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    base = file_name.replace(".md", "")
    return session_dir / f"{base}.pre_compact.md"


async def write_handoff(
    project_root: Path, handoff: SessionHandoff, fs_manager: FileSystemManager
) -> None:
    """Write session handoff JSON to .cortex/.cache/session/last_handoff.json."""
    path = _handoff_path(project_root)
    content = handoff.model_dump_json(indent=2)
    _ = await fs_manager.write_file(path, content, expected_hash=None)


async def read_handoff(
    project_root: Path, fs_manager: FileSystemManager
) -> SessionHandoff | None:
    """Read last session handoff from .cortex/.cache/session/last_handoff.json.

    Returns None if file does not exist or is invalid.
    """
    path = _handoff_path(project_root)
    if not path.exists():
        return None
    try:
        content, _ = await fs_manager.read_file(path)
        data = json.loads(content)
        return SessionHandoff.model_validate(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to read handoff %s: %s", path, e)
        return None


def _compact_error(msg: str) -> str:
    """Return error JSON for compaction."""
    return json.dumps({"status": "error", "error": msg}, indent=2)


async def _write_snapshots(
    snapshot_active: Path,
    snapshot_progress: Path,
    active_content: str,
    progress_content: str,
    fs_manager: FileSystemManager,
) -> None:
    """Write snapshot files for rollback."""
    snapshot_active.parent.mkdir(parents=True, exist_ok=True)
    snapshot_progress.parent.mkdir(parents=True, exist_ok=True)
    try:
        _ = await fs_manager.write_file(
            snapshot_active, active_content, expected_hash=None
        )
        _ = await fs_manager.write_file(
            snapshot_progress, progress_content, expected_hash=None
        )
    except Exception as e:
        logger.warning("Failed to write snapshots: %s", e)
        # Continue anyway - snapshots are for rollback, not critical for operation


async def _compact_session_read_and_snapshot(
    project_root: Path,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
) -> str | tuple[str, str, int, int, Path, Path]:
    """Read activeContext/progress and save snapshots. Return error JSON or (active, progress, tok_a, tok_p, snap_a, snap_p)."""
    from cortex.core.constants import MemoryBankFile

    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    active_path = memory_bank_dir / MemoryBankFile.ACTIVE_CONTEXT
    progress_path = memory_bank_dir / MemoryBankFile.PROGRESS
    if not active_path.exists() or not progress_path.exists():
        return _compact_error(
            f"{MemoryBankFile.ACTIVE_CONTEXT} or {MemoryBankFile.PROGRESS} not found in memory bank"
        )
    active_content, _ = await fs_manager.read_file(active_path)
    progress_content, _ = await fs_manager.read_file(progress_path)
    snapshot_active, snapshot_progress = (
        _pre_compact_snapshot_path(project_root, MemoryBankFile.ACTIVE_CONTEXT),
        _pre_compact_snapshot_path(project_root, MemoryBankFile.PROGRESS),
    )
    await _write_snapshots(
        snapshot_active, snapshot_progress, active_content, progress_content, fs_manager
    )
    return (
        active_content,
        progress_content,
        token_counter.count_tokens(active_content),
        token_counter.count_tokens(progress_content),
        snapshot_active,
        snapshot_progress,
    )


async def _compact_write_one(
    project_root: Path,
    file_name: str,
    content: str,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str | None:
    """Write one memory bank file. Returns error JSON or None on success."""
    result = await execute_memory_bank_write(
        project_root,
        file_name,
        content,
        "Compacted by compact_session",
        fs_manager,
        metadata_index,
        token_counter,
        version_manager,
    )
    return result if json.loads(result).get("status") == "error" else None


def _compact_rollback_error(exc: Exception) -> str:
    """Build rollback error JSON."""
    return json.dumps(
        {
            "status": "error",
            "error": str(exc),
            "rollback": "Use snapshot in .cortex/.cache/session/",
        },
        indent=2,
    )


async def _compact_write_active(
    project_root: Path,
    compacted_active: str,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str | None:
    """Write compacted activeContext. Returns error JSON or None on success."""
    from cortex.core.constants import MemoryBankFile

    return await _compact_write_one(
        project_root,
        MemoryBankFile.ACTIVE_CONTEXT,
        compacted_active,
        fs_manager,
        metadata_index,
        token_counter,
        version_manager,
    )


async def _compact_session_write_back(
    project_root: Path,
    compacted_active: str,
    compacted_progress: str,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
    token_counter: TokenCounter,
    version_manager: VersionManager,
) -> str | None:
    """Write compacted content back. Returns error JSON or None on success."""
    from cortex.core.constants import MemoryBankFile

    try:
        if err := await _compact_write_active(
            project_root,
            compacted_active,
            fs_manager,
            metadata_index,
            token_counter,
            version_manager,
        ):
            return err
        return await _compact_write_one(
            project_root,
            MemoryBankFile.PROGRESS,
            compacted_progress,
            fs_manager,
            metadata_index,
            token_counter,
            version_manager,
        )
    except (FileConflictError, FileLockTimeoutError, GitConflictError) as e:
        return _compact_rollback_error(e)


def _compact_apply(
    active_content: str,
    progress_content: str,
    today: str,
    progress_tokens: int,
    progress_token_threshold: int = PROGRESS_TOKEN_THRESHOLD_DEFAULT,
) -> tuple[str, str]:
    """Apply compaction rules; return (compacted_active, compacted_progress).

    Progress summarization is applied only when progress_tokens >= threshold
    (auto-trigger when progress.md exceeds token threshold).
    """
    compacted_active = trim_recent_changes(
        compact_active_context_completed_work(active_content, today)
    )
    if progress_tokens >= progress_token_threshold:
        compacted_progress = apply_progress_tiers(progress_content, today)
    else:
        compacted_progress = progress_content
    return compacted_active, compacted_progress


def _progress_txt_path(project_root: Path) -> Path:
    """Path to progress.txt under .cortex/.cache/session."""
    session_dir = get_cache_dir(project_root, CacheType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / SESSION_PROGRESS_FILENAME


def _progress_section(
    title: str, items: list[str] | None, default: str = "- (none)"
) -> list[str]:
    """Build a ## section with bullet items."""
    out = [f"## {title}"]
    for x in items or []:
        out.append(f"- {x}")
    if not items:
        out.append(default)
    return out


def _render_progress_txt(handoff: SessionHandoff) -> str:
    """Render handoff as human-readable progress file (Anthropic Step 5)."""
    lines = [f"# Session Progress - {handoff.session_id}", ""]
    lines.extend(_progress_section("Completed", handoff.completed_tasks))
    lines.append("")
    lines.append("## In Progress")
    if handoff.in_progress:
        lines.append(f"- {handoff.in_progress.task}")
        if handoff.in_progress.notes:
            lines.append(f"  Notes: {handoff.in_progress.notes}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.extend(_progress_section("Next Actions", handoff.next_actions))
    lines.append("")
    lines.extend(_progress_section("Blockers", handoff.blockers))
    if handoff.decisions_made:
        lines.append("")
        lines.extend(_progress_section("Decisions", handoff.decisions_made))
    return "\n".join(lines) + "\n"


async def _write_progress_txt(
    project_root: Path,
    handoff: SessionHandoff,
    fs_manager: FileSystemManager,
) -> None:
    """Write human-readable progress file (Anthropic Step 5 structured format)."""
    path = _progress_txt_path(project_root)
    content = _render_progress_txt(handoff)
    try:
        _ = await fs_manager.write_file(path, content, expected_hash=None)
    except Exception as e:
        logger.warning("Failed to write progress.txt: %s", e)


async def _create_git_checkpoint(project_root: Path) -> bool:
    """Create lightweight git tag for session rollback. Returns True on success."""
    await acquire_git_operation_slot()
    tag_name = f"cortex/session-{_session_id_from_now()}"
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            "tag",
            tag_name,
            cwd=str(project_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _ = await process.communicate()
        return process.returncode == 0
    except Exception as e:
        logger.warning("Failed to create git checkpoint %s: %s", tag_name, e)
        return False


def _build_handoff(
    summary: str | None, params: _HandoffParams | None
) -> SessionHandoff:
    """Build SessionHandoff from summary and optional structured params."""
    hp = params or _HandoffParams()
    in_progress: InProgressTask | None = None
    if hp.in_progress_task and hp.in_progress_task.strip():
        in_progress = InProgressTask(
            task=hp.in_progress_task.strip(),
            notes=hp.in_progress_notes.strip() if hp.in_progress_notes else None,
        )
    return SessionHandoff(
        session_id=_session_id_from_now(),
        completed_tasks=hp.completed_tasks or [],
        in_progress=in_progress,
        decisions_made=hp.decisions_made or [],
        blockers=hp.blockers or [],
        next_actions=[summary] if summary else [],
        schema_version=SESSION_HANDOFF_SCHEMA_VERSION,
    )


async def _compact_do_handoff(
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
    params: _HandoffParams | None = None,
) -> SessionHandoff:
    """Build and write session handoff JSON and progress.txt."""
    handoff = _build_handoff(summary, params)
    try:
        await write_handoff(project_root, handoff, fs_manager)
        await _write_progress_txt(project_root, handoff, fs_manager)
    except Exception as e:
        logger.warning("Failed to write handoff: %s", e)
    return handoff


async def _compact_apply_and_handoff(
    active_content: str,
    progress_content: str,
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
    progress_tokens: int,
    progress_token_threshold: int = PROGRESS_TOKEN_THRESHOLD_DEFAULT,
    handoff_params: _HandoffParams | None = None,
) -> tuple[str, str]:
    """Apply compaction and write handoff; return (compacted_active, compacted_progress)."""
    compacted_active, compacted_progress = _compact_apply(
        active_content,
        progress_content,
        _today_iso(),
        progress_tokens,
        progress_token_threshold,
    )
    _ = await _compact_do_handoff(project_root, summary, fs_manager, handoff_params)
    return compacted_active, compacted_progress


def _compact_success_result(
    token_counter: TokenCounter,
    compacted_active: str,
    compacted_progress: str,
    tokens_before_active: int,
    tokens_before_progress: int,
    snapshot_active: Path,
    snapshot_progress: Path,
    checkpoint_created: bool = False,
) -> str:
    """Build success JSON result."""
    ta = token_counter.count_tokens(compacted_active)
    tp = token_counter.count_tokens(compacted_progress)
    payload: dict[str, object] = {
        "status": "success",
        "message": "Session compacted; handoff written.",
        "token_savings": {
            "activeContext": tokens_before_active - ta,
            "progress": tokens_before_progress - tp,
            "total": tokens_before_active + tokens_before_progress - ta - tp,
        },
        "tokens_after": {"activeContext": ta, "progress": tp},
        "rollback_snapshots": [str(snapshot_active), str(snapshot_progress)],
    }
    if checkpoint_created:
        payload["checkpoint_created"] = True
    return json.dumps(payload, indent=2)


async def _compact_write_back_from_ctx(
    ctx: _CompactWriteCtx, compacted_active: str, compacted_progress: str
) -> str | None:
    """Write compacted files via ctx; return error JSON or None on success."""
    return await _compact_session_write_back(
        ctx.project_root,
        compacted_active,
        compacted_progress,
        ctx.fs_manager,
        ctx.metadata_index,
        ctx.token_counter,
        ctx.version_manager,
    )


async def _compact_session_write_then_success(
    ctx: _CompactWriteCtx,
    compacted_active: str,
    compacted_progress: str,
    tokens_before_active: int,
    tokens_before_progress: int,
    snapshot_active: Path,
    snapshot_progress: Path,
    *,
    checkpoint_created: bool = False,
) -> str:
    """Write back compacted files; return error JSON or success result."""
    err = await _compact_write_back_from_ctx(ctx, compacted_active, compacted_progress)
    return (
        err
        if err is not None
        else _compact_success_result(
            ctx.token_counter,
            compacted_active,
            compacted_progress,
            tokens_before_active,
            tokens_before_progress,
            snapshot_active,
            snapshot_progress,
            checkpoint_created,
        )
    )


def _to_handoff_params(
    completed_tasks: list[str] | None,
    in_progress_task: str | None,
    in_progress_notes: str | None,
    blockers: list[str] | None,
    decisions_made: list[str] | None,
) -> _HandoffParams | None:
    """Build HandoffParams if any field is non-empty."""
    if any([completed_tasks, in_progress_task, blockers, decisions_made]):
        return _HandoffParams(
            completed_tasks=completed_tasks,
            in_progress_task=in_progress_task,
            in_progress_notes=in_progress_notes,
            blockers=blockers,
            decisions_made=decisions_made,
        )
    return None


async def _do_compact_apply(
    read_result: tuple[str, str, int, int, Path, Path],
    ctx: _CompactWriteCtx,
    summary: str | None,
    handoff_params: _HandoffParams | None,
) -> tuple[str, str, int, int, Path, Path]:
    """Run compact apply; return (compacted_active, compacted_progress, ...)."""
    (ac, pc, tba, tbp, sa, sp) = read_result
    compacted_active, compacted_progress = await _compact_apply_and_handoff(
        ac,
        pc,
        ctx.project_root,
        summary,
        ctx.fs_manager,
        tbp,
        PROGRESS_TOKEN_THRESHOLD_DEFAULT,
        handoff_params,
    )
    return (compacted_active, compacted_progress, tba, tbp, sa, sp)


async def _compact_session_apply_write_and_result(
    read_result: tuple[str, str, int, int, Path, Path],
    ctx: _CompactWriteCtx,
    summary: str | None,
    handoff_params: _HandoffParams | None,
    create_checkpoint: bool,
) -> str:
    """Apply compaction, handoff, write back; return error JSON or success result."""
    out = await _do_compact_apply(read_result, ctx, summary, handoff_params)
    checkpoint_created = (
        await _create_git_checkpoint(ctx.project_root) if create_checkpoint else False
    )
    return await _compact_session_write_then_success(
        ctx, *out, checkpoint_created=checkpoint_created
    )


async def _compact_session_run(
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    metadata_index: MetadataIndex,
    version_manager: VersionManager,
    handoff_params: _HandoffParams | None,
    create_checkpoint: bool,
) -> str:
    """Run compaction: read, then apply/handoff/write/result."""
    ctx = _CompactWriteCtx(
        project_root=project_root,
        fs_manager=fs_manager,
        token_counter=token_counter,
        metadata_index=metadata_index,
        version_manager=version_manager,
    )
    read_result = await _compact_session_read_and_snapshot(
        project_root, fs_manager, token_counter
    )
    if isinstance(read_result, str):
        return read_result
    return await _compact_session_apply_write_and_result(
        read_result, ctx, summary, handoff_params, create_checkpoint
    )


async def _compact_session_impl(
    summary: str | None,
    project_root: Path,
    managers: dict[str, object],
    handoff_params: _HandoffParams | None,
    create_checkpoint: bool,
) -> str:
    """Implementation of compact_session: resolve managers and run compaction."""
    managers_dict = cast(ManagersDict, managers)
    fs_manager = await get_manager(managers_dict, "fs", FileSystemManager)
    token_counter = await get_manager(managers_dict, "tokens", TokenCounter)
    metadata_index = await get_manager(managers_dict, "index", MetadataIndex)
    version_manager = await get_manager(managers_dict, "versions", VersionManager)
    return await _compact_session_run(
        project_root,
        summary,
        fs_manager,
        token_counter,
        metadata_index,
        version_manager,
        handoff_params,
        create_checkpoint,
    )


# Internal; use session(operation="compact") as MCP tool.
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def compact_session(
    summary: str | None = None,
    completed_tasks: list[str] | None = None,
    in_progress_task: str | None = None,
    in_progress_notes: str | None = None,
    blockers: list[str] | None = None,
    decisions_made: list[str] | None = None,
    create_checkpoint: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Compact activeContext and progress, write session handoff for next session.

    USE WHEN: End of session, reducing memory bank size, preparing handoff.

    EXAMPLES: 'compact_session(summary="Implemented Step 1; next: audit remaining tools")',
    'compact session', 'run session compaction'.

    RETURNS: JSON with status, token_savings, tokens_after, rollback_snapshots.

    Reads activeContext.md and progress.md, keeps current date in Completed Work
    and recent entries in progress, summarizes older content, writes handoff JSON
    to .cortex/.cache/session/last_handoff.json and progress.txt (structured
    format), and updates the files. Pre-compaction snapshots saved for rollback.

    Args:
        summary: Optional free-form summary (stored in handoff next_actions).
        completed_tasks: Optional list of completed tasks this session.
        in_progress_task: Optional task in progress.
        in_progress_notes: Optional notes for in-progress task.
        blockers: Optional list of current blockers.
        decisions_made: Optional list of key decisions.
        create_checkpoint: If True, create git tag cortex/session-YYYY-MM-DD-HH-MM.

    Returns:
        JSON with status, token_savings, tokens_after, rollback_snapshots.
    """
    await log_client(ctx, "info", "compact_session: starting", logger_name=__name__)
    project_root = await get_or_resolve_project_root(ctx)
    managers_raw = get_current_managers()
    if managers_raw is None:
        return json.dumps(
            {"status": "error", "error": "Managers not initialized"}, indent=2
        )
    hp = _to_handoff_params(
        completed_tasks,
        in_progress_task,
        in_progress_notes,
        blockers,
        decisions_made,
    )
    return await _compact_session_impl(
        summary, project_root, managers_raw, hp, create_checkpoint
    )
