"""Session compaction tool and handoff read/write (Phase 56)."""

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
from cortex.core.mcp_annotations import destructive_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.usage_context import (
    get_current_managers,
    get_or_resolve_project_root,
)
from cortex.core.version_manager import VersionManager
from cortex.managers.manager_utils import get_manager
from cortex.managers.types import ManagersDict
from cortex.server import mcp
from cortex.tools.compaction_constants import (
    SESSION_HANDOFF_FILENAME,
    SESSION_HANDOFF_SCHEMA_VERSION,
)
from cortex.tools.compaction_helpers import (
    apply_progress_tiers,
    compact_active_context_completed_work,
    trim_recent_changes,
)
from cortex.tools.file_operations import execute_memory_bank_write
from cortex.tools.models import SessionHandoff

logger = logging.getLogger(__name__)


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
    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    active_path = memory_bank_dir / "activeContext.md"
    progress_path = memory_bank_dir / "progress.md"
    if not active_path.exists() or not progress_path.exists():
        return _compact_error(
            "activeContext.md or progress.md not found in memory bank"
        )
    active_content, _ = await fs_manager.read_file(active_path)
    progress_content, _ = await fs_manager.read_file(progress_path)
    snapshot_active = _pre_compact_snapshot_path(project_root, "activeContext.md")
    snapshot_progress = _pre_compact_snapshot_path(project_root, "progress.md")
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
    return await _compact_write_one(
        project_root,
        "activeContext.md",
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
    try:
        err = await _compact_write_active(
            project_root,
            compacted_active,
            fs_manager,
            metadata_index,
            token_counter,
            version_manager,
        )
        if err is not None:
            return err
        return await _compact_write_one(
            project_root,
            "progress.md",
            compacted_progress,
            fs_manager,
            metadata_index,
            token_counter,
            version_manager,
        )
    except (FileConflictError, FileLockTimeoutError, GitConflictError) as e:
        return _compact_rollback_error(e)


def _compact_apply(
    active_content: str, progress_content: str, today: str
) -> tuple[str, str]:
    """Apply compaction rules; return (compacted_active, compacted_progress)."""
    compacted_active = trim_recent_changes(
        compact_active_context_completed_work(active_content, today)
    )
    compacted_progress = apply_progress_tiers(progress_content, today)
    return compacted_active, compacted_progress


async def _compact_do_handoff(
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
) -> None:
    """Build and write session handoff JSON."""
    handoff = SessionHandoff(
        session_id=_session_id_from_now(),
        completed_tasks=[],
        in_progress=None,
        decisions_made=[],
        blockers=[],
        next_actions=[summary] if summary else [],
        schema_version=SESSION_HANDOFF_SCHEMA_VERSION,
    )
    try:
        await write_handoff(project_root, handoff, fs_manager)
    except Exception as e:
        logger.warning("Failed to write handoff: %s", e)
        # Continue - handoff is nice-to-have, not critical for compaction


async def _compact_apply_and_handoff(
    active_content: str,
    progress_content: str,
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
) -> tuple[str, str]:
    """Apply compaction and write handoff; return (compacted_active, compacted_progress)."""
    compacted_active, compacted_progress = _compact_apply(
        active_content, progress_content, _today_iso()
    )
    await _compact_do_handoff(project_root, summary, fs_manager)
    return compacted_active, compacted_progress


def _compact_success_result(
    token_counter: TokenCounter,
    compacted_active: str,
    compacted_progress: str,
    tokens_before_active: int,
    tokens_before_progress: int,
    snapshot_active: Path,
    snapshot_progress: Path,
) -> str:
    """Build success JSON result."""
    ta = token_counter.count_tokens(compacted_active)
    tp = token_counter.count_tokens(compacted_progress)
    return json.dumps(
        {
            "status": "success",
            "message": "Session compacted; handoff written.",
            "token_savings": {
                "activeContext": tokens_before_active - ta,
                "progress": tokens_before_progress - tp,
                "total": tokens_before_active + tokens_before_progress - ta - tp,
            },
            "tokens_after": {"activeContext": ta, "progress": tp},
            "rollback_snapshots": [str(snapshot_active), str(snapshot_progress)],
        },
        indent=2,
    )


async def _compact_session_write_then_success(
    ctx: _CompactWriteCtx,
    compacted_active: str,
    compacted_progress: str,
    tokens_before_active: int,
    tokens_before_progress: int,
    snapshot_active: Path,
    snapshot_progress: Path,
) -> str:
    """Write back compacted files; return error JSON or success result."""
    write_err = await _compact_session_write_back(
        ctx.project_root,
        compacted_active,
        compacted_progress,
        ctx.fs_manager,
        ctx.metadata_index,
        ctx.token_counter,
        ctx.version_manager,
    )
    if write_err is not None:
        return write_err
    return _compact_success_result(
        ctx.token_counter,
        compacted_active,
        compacted_progress,
        tokens_before_active,
        tokens_before_progress,
        snapshot_active,
        snapshot_progress,
    )


async def _compact_session_apply_write_and_result(
    read_result: tuple[str, str, int, int, Path, Path],
    ctx: _CompactWriteCtx,
    summary: str | None,
) -> str:
    """Apply compaction, handoff, write back; return error JSON or success result."""
    (
        active_content,
        progress_content,
        tokens_before_active,
        tokens_before_progress,
        snapshot_active,
        snapshot_progress,
    ) = read_result
    compacted_active, compacted_progress = await _compact_apply_and_handoff(
        active_content,
        progress_content,
        ctx.project_root,
        summary,
        ctx.fs_manager,
    )
    return await _compact_session_write_then_success(
        ctx,
        compacted_active,
        compacted_progress,
        tokens_before_active,
        tokens_before_progress,
        snapshot_active,
        snapshot_progress,
    )


async def _compact_session_run(
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    metadata_index: MetadataIndex,
    version_manager: VersionManager,
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
        read_result,
        ctx,
        summary,
    )


async def _compact_session_impl(
    summary: str | None,
    project_root: Path,
    managers: dict[str, object],
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
    )


@mcp.tool(annotations=destructive_annotations("Session Compaction"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def compact_session(
    summary: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Compact activeContext and progress, write session handoff for next session.

    USE WHEN: End of session, reducing memory bank size, preparing handoff.

    Reads activeContext.md and progress.md, keeps current date in Completed Work
    and recent entries in progress, summarizes older content, writes handoff JSON
    to .cortex/.cache/session/last_handoff.json, and updates the files.
    Pre-compaction snapshots are saved under .cortex/.cache/session/ for rollback.

    Args:
        summary: Optional free-form summary (stored in handoff next_actions).

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
    return await _compact_session_impl(summary, project_root, managers_raw)
