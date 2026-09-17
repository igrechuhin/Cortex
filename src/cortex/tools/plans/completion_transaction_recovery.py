"""Conflict-aware rollback and replay checks for plan completion."""

from __future__ import annotations

from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.exceptions import (
    FileConflictError,
    FileLockTimeoutError,
    GitConflictError,
)
from cortex.core.file_system import FileSystemManager
from cortex.core.models import PlanStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.completion_content import find_roadmap_bullet_line
from cortex.tools.plans.completion_transaction_io import (
    hash_text,
    read_payload,
    read_required_text,
    resolve_archive_paths,
    resolve_record_file,
    save_record_phase,
    write_owned_text,
)
from cortex.tools.plans.completion_transaction_models import (
    CompletionFileKey,
    CompletionOperationRecord,
    CompletionPhase,
)
from cortex.tools.plans.register_artifact_graph import replace_plan_frontmatter_status


def _restore_archive(project_root: Path, record: CompletionOperationRecord) -> None:
    resolved = resolve_archive_paths(project_root, record)
    if resolved is None:
        return
    source, destination = resolved
    if not destination.exists():
        return
    if source.exists():
        raise ValueError("Recovery conflict: plan exists in source and archive")
    plan_state = next(
        item for item in record.files if item.key == CompletionFileKey.PLAN
    )
    if hash_text(destination.read_text()) != plan_state.after_hash:
        raise ValueError("Recovery conflict: archived plan changed")
    source.parent.mkdir(parents=True, exist_ok=True)
    _ = destination.replace(source)


async def _restore_files(
    project_root: Path,
    operations_root: Path,
    manager: FileSystemManager,
    record: CompletionOperationRecord,
) -> None:
    for item in reversed(record.files):
        target = resolve_record_file(project_root, item)
        before = read_payload(operations_root, item.before_payload)
        current_hash = hash_text(target.read_text(encoding="utf-8"))
        if current_hash == item.before_hash:
            continue
        if current_hash != item.after_hash:
            raise ValueError(f"Recovery conflict: unrelated edit detected in {target}")
        await write_owned_text(manager, target, before, item.after_hash, True)


async def rollback_completion(
    project_root: Path,
    operations_root: Path,
    manager: FileSystemManager,
    path: Path,
    record: CompletionOperationRecord,
    cause: str,
) -> str | None:
    """Restore operation-owned state or persist a precise recovery requirement."""
    try:
        _restore_archive(project_root, record)
        await _restore_files(project_root, operations_root, manager, record)
        save_record_phase(path, record, CompletionPhase.ROLLED_BACK, cause)
        return None
    except (
        FileConflictError,
        FileLockTimeoutError,
        GitConflictError,
        OSError,
        ValueError,
    ) as exc:
        detail = f"{cause}; rollback failed: {exc}"
        try:
            save_record_phase(path, record, CompletionPhase.RECOVERY_REQUIRED, detail)
        except OSError:
            pass
        return detail


def completed_state_present(
    project_root: Path, record: CompletionOperationRecord
) -> bool:
    """Verify semantic completion while allowing unrelated later file edits."""
    request = record.request
    mem = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    roadmap = read_required_text(mem / MemoryBankFile.ROADMAP, mem)
    active = read_required_text(mem / MemoryBankFile.ACTIVE_CONTEXT, mem)
    active_line = (
        f"- ✅ **{request.plan_title}** - COMPLETE "
        f"({request.completion_date}) - {request.summary}"
    )
    if find_roadmap_bullet_line(roadmap, request.plan_title) is not None or (
        active_line not in active.splitlines()
    ):
        return False
    if request.progress_entry:
        progress = read_required_text(mem / MemoryBankFile.PROGRESS, mem)
        if f"- {request.progress_entry}" not in progress.splitlines():
            return False
    if record.archive_destination:
        resolved = resolve_archive_paths(project_root, record)
        assert resolved is not None
        source, destination = resolved
        source_exists = source.exists()
        if not destination.is_file() or source_exists:
            return False
        content = destination.read_text(encoding="utf-8")
        if replace_plan_frontmatter_status(content, PlanStatus.DONE) != content:
            return False
    return True
