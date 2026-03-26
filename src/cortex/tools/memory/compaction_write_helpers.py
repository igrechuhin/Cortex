"""Write/snapshot/apply helpers for session compaction (Phase 56).

Orchestrates read, snapshot, compact apply, handoff, and write-back.
Used only by compaction_operations compact_session.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.security import acquire_git_operation_slot
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.tools.files.operations import execute_memory_bank_write
from cortex.tools.memory.compaction_constants import PROGRESS_TOKEN_THRESHOLD_DEFAULT
from cortex.tools.memory.compaction_handoff import (
    HandoffParams,
    compact_do_handoff,
    session_id_from_now,
    today_iso,
)
from cortex.tools.memory.compaction_helpers import (
    apply_progress_tiers,
    compact_active_context_completed_work,
    trim_recent_changes,
)

logger = logging.getLogger(__name__)


def _pre_compact_snapshot_path(project_root: Path, file_name: str) -> Path:
    """Path for pre-compaction snapshot file."""
    from cortex.core.cache_utils import CacheType, get_cache_dir

    session_dir = get_cache_dir(project_root, CacheType.SESSION)
    session_dir.mkdir(parents=True, exist_ok=True)
    base = file_name.replace(".md", "")
    return session_dir / f"{base}.pre_compact.md"


def _compact_error(msg: str) -> str:
    """Return error JSON for compaction."""
    return json.dumps({"status": "error", "error": msg}, indent=2)


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


async def compact_session_read_and_snapshot(
    project_root: Path,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
) -> str | tuple[str, str, int, int, Path, Path]:
    """Read activeContext/progress and save snapshots.

    Return error JSON or (active, progress, tok_a, tok_p, snap_a, snap_p).
    """
    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    active_path = memory_bank_dir / MemoryBankFile.ACTIVE_CONTEXT
    progress_path = memory_bank_dir / MemoryBankFile.PROGRESS
    if not active_path.exists() or not progress_path.exists():
        return _compact_error(
            f"{MemoryBankFile.ACTIVE_CONTEXT} or {MemoryBankFile.PROGRESS} not found"
        )
    active_content, _ = await fs_manager.read_file(active_path)
    progress_content, _ = await fs_manager.read_file(progress_path)
    snapshot_active = _pre_compact_snapshot_path(
        project_root, MemoryBankFile.ACTIVE_CONTEXT
    )
    snapshot_progress = _pre_compact_snapshot_path(
        project_root, MemoryBankFile.PROGRESS
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
        MemoryBankFile.ACTIVE_CONTEXT,
        compacted_active,
        fs_manager,
        metadata_index,
        token_counter,
        version_manager,
    )


async def compact_session_write_back(
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
    """Apply compaction rules; return (compacted_active, compacted_progress)."""
    compacted_active = trim_recent_changes(
        compact_active_context_completed_work(active_content, today)
    )
    if progress_tokens >= progress_token_threshold:
        compacted_progress = apply_progress_tiers(progress_content, today)
    else:
        compacted_progress = progress_content
    return compacted_active, compacted_progress


async def _create_git_checkpoint(project_root: Path) -> bool:
    """Create lightweight git tag for session rollback."""
    await acquire_git_operation_slot()
    tag_name = f"cortex/session-{session_id_from_now()}"
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


async def compact_apply_and_handoff(
    active_content: str,
    progress_content: str,
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
    progress_tokens: int,
    progress_token_threshold: int,
    handoff_params: HandoffParams | None,
) -> tuple[str, str]:
    """Apply compaction and write handoff; return (compacted_active, compacted_progress)."""
    compacted_active, compacted_progress = _compact_apply(
        active_content,
        progress_content,
        today_iso(),
        progress_tokens,
        progress_token_threshold,
    )
    _ = await compact_do_handoff(project_root, summary, fs_manager, handoff_params)
    return compacted_active, compacted_progress


@dataclass(frozen=True)
class _CompactCtx:
    """Context for compaction run."""

    project_root: Path
    fs_manager: FileSystemManager
    token_counter: TokenCounter
    metadata_index: MetadataIndex
    version_manager: VersionManager


def compact_success_result(
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
    # Compaction can be a no-op (or even slightly expand text due to formatting),
    # so savings must be non-negative for stable UX and test expectations.
    savings_active = max(0, tokens_before_active - ta)
    savings_progress = max(0, tokens_before_progress - tp)
    payload: dict[str, object] = {
        "status": "success",
        "message": "Session compacted; handoff written.",
        "token_savings": {
            "activeContext": savings_active,
            "progress": savings_progress,
            "total": savings_active + savings_progress,
        },
        "tokens_after": {"activeContext": ta, "progress": tp},
        "rollback_snapshots": [str(snapshot_active), str(snapshot_progress)],
    }
    if checkpoint_created:
        payload["checkpoint_created"] = True
    return json.dumps(payload, indent=2)


async def _write_back_or_error(
    ctx: _CompactCtx,
    compacted_active: str,
    compacted_progress: str,
) -> str | None:
    """Write back compacted files. Returns error JSON or None on success."""
    return await compact_session_write_back(
        ctx.project_root,
        compacted_active,
        compacted_progress,
        ctx.fs_manager,
        ctx.metadata_index,
        ctx.token_counter,
        ctx.version_manager,
    )


async def _apply_handoff_and_checkpoint(
    ctx: _CompactCtx,
    ac: str,
    pc: str,
    tbp: int,
    summary: str | None,
    handoff_params: HandoffParams | None,
    create_checkpoint: bool,
) -> tuple[str, str, bool]:
    """Apply compaction, handoff, optional checkpoint. Return (active, progress, created)."""
    compacted = await compact_apply_and_handoff(
        ac,
        pc,
        ctx.project_root,
        summary,
        ctx.fs_manager,
        tbp,
        PROGRESS_TOKEN_THRESHOLD_DEFAULT,
        handoff_params,
    )
    created = (
        await _create_git_checkpoint(ctx.project_root) if create_checkpoint else False
    )
    return (*compacted, created)


async def _apply_write_and_result(
    ctx: _CompactCtx,
    read_result: tuple[str, str, int, int, Path, Path],
    summary: str | None,
    handoff_params: HandoffParams | None,
    create_checkpoint: bool,
) -> str:
    """Apply compaction, handoff, write back; return result JSON."""
    (ac, pc, tba, tbp, sa, sp) = read_result
    compacted_active, compacted_progress, checkpoint_created = (
        await _apply_handoff_and_checkpoint(
            ctx, ac, pc, tbp, summary, handoff_params, create_checkpoint
        )
    )
    err = await _write_back_or_error(ctx, compacted_active, compacted_progress)
    if err is not None:
        return err
    return compact_success_result(
        ctx.token_counter,
        compacted_active,
        compacted_progress,
        tba,
        tbp,
        sa,
        sp,
        checkpoint_created,
    )


async def compact_session_run(
    project_root: Path,
    summary: str | None,
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    metadata_index: MetadataIndex,
    version_manager: VersionManager,
    handoff_params: HandoffParams | None,
    create_checkpoint: bool,
) -> str:
    """Run compaction: read, then apply/handoff/write/result."""
    ctx = _CompactCtx(
        project_root=project_root,
        fs_manager=fs_manager,
        token_counter=token_counter,
        metadata_index=metadata_index,
        version_manager=version_manager,
    )
    read_result = await compact_session_read_and_snapshot(
        project_root, fs_manager, token_counter
    )
    if isinstance(read_result, str):
        return read_result
    return await _apply_write_and_result(
        ctx, read_result, summary, handoff_params, create_checkpoint
    )
