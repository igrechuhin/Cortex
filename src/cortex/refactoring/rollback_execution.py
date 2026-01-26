"""
Rollback Execution - Rollback Manager Support

Handle file restoration and rollback execution operations.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import VersionMetadata
from cortex.core.version_manager import VersionManager
from cortex.refactoring.version_snapshots import (
    find_snapshot_version,
    get_version_history,
)


async def execute_rollback(
    dry_run: bool,
    affected_files: list[str],
    snapshot_id: str,
    preserve_manual_changes: bool,
    conflicts: list[str],
    memory_bank_dir: Path,
    fs_manager: FileSystemManager,
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
) -> list[str]:
    """Execute rollback operation.

    Args:
        dry_run: Whether to simulate
        affected_files: List of affected files
        snapshot_id: Snapshot ID
        preserve_manual_changes: Whether to preserve manual changes
        conflicts: List of conflicts
        memory_bank_dir: Memory bank directory
        fs_manager: File system manager
        version_manager: Version manager
        metadata_index: Metadata index

    Returns:
        List of restored files
    """
    if not dry_run:
        return await restore_files(
            affected_files,
            snapshot_id,
            preserve_manual_changes,
            conflicts,
            memory_bank_dir,
            fs_manager,
            version_manager,
            metadata_index,
        )
    return affected_files


async def restore_files(
    affected_files: list[str],
    snapshot_id: str,
    preserve_manual_changes: bool,
    conflicts: list[str],
    memory_bank_dir: Path,
    fs_manager: FileSystemManager,
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
) -> list[str]:
    """Restore files from snapshot.

    Args:
        affected_files: List of files to restore
        snapshot_id: Snapshot to restore from
        preserve_manual_changes: Whether to preserve manual edits
        conflicts: List of detected conflicts
        memory_bank_dir: Memory bank directory
        fs_manager: File system manager
        version_manager: Version manager
        metadata_index: Metadata index

    Returns:
        List of successfully restored files
    """
    restored_files: list[str] = []

    for file_path in affected_files:
        # Skip files with conflicts if preserving manual changes
        if await should_skip_conflicted_file(
            file_path, preserve_manual_changes, conflicts, memory_bank_dir, fs_manager
        ):
            continue

        # Restore from snapshot
        restored = await restore_single_file(
            file_path,
            snapshot_id,
            memory_bank_dir,
            version_manager,
            metadata_index,
        )
        if restored:
            restored_files.append(file_path)

    return restored_files


async def should_skip_conflicted_file(
    file_path: str,
    preserve_manual_changes: bool,
    conflicts: list[str],
    memory_bank_dir: Path,
    fs_manager: FileSystemManager,
    backup_fn: Callable[[str], Awaitable[None]] | None = None,
) -> bool:
    """Check if file should be skipped due to conflicts.

    Args:
        file_path: Path to file
        preserve_manual_changes: Whether to preserve manual edits
        conflicts: List of detected conflicts
        memory_bank_dir: Memory bank directory
        fs_manager: File system manager

    Returns:
        True if file should be skipped
    """
    if not preserve_manual_changes:
        return False

    has_conflict = any(file_path in conflict for conflict in conflicts)
    if has_conflict:
        # Create a backup of the current version
        if backup_fn:
            await backup_fn(file_path)
        else:
            await backup_current_version(
                file_path, memory_bank_dir, fs_manager, None, None
            )
        return True

    return False


async def restore_single_file(
    file_path: str,
    snapshot_id: str,
    memory_bank_dir: Path,
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
) -> bool:
    """Restore a single file from snapshot.

    Args:
        file_path: Path to file
        snapshot_id: Snapshot to restore from
        memory_bank_dir: Memory bank directory
        version_manager: Version manager
        metadata_index: Metadata index

    Returns:
        True if file was successfully restored
    """
    try:
        # Get version history from metadata
        version_history = await get_version_history(file_path, metadata_index)
        if version_history is None:
            return False

        # Find snapshot version
        snapshot_version = find_snapshot_version(version_history, snapshot_id)
        if snapshot_version is None:
            return False

        # Rollback to this version
        return await _rollback_file_to_version(
            file_path, version_history, snapshot_version, version_manager
        )

    except Exception as e:
        # Log error but continue with other files
        from cortex.core.logging_config import logger

        logger.warning(f"Failed to restore file {file_path} during rollback: {e}")
        return False


async def _rollback_file_to_version(
    file_path: str,
    version_history: list[VersionMetadata],
    version: int,
    version_manager: VersionManager,
) -> bool:
    """Execute rollback to a specific version.

    Args:
        file_path: Path to file
        version_history: Version history list (Pydantic models)
        version: Version number to rollback to
        version_manager: Version manager

    Returns:
        True if rollback was successful (SnapshotInfo returned, not None)
    """
    result = await version_manager.rollback_to_version(
        file_path, version_history, version
    )
    # rollback_to_version returns SnapshotInfo if successful, None if not found
    return result is not None


async def backup_current_version(
    file_path: str,
    memory_bank_dir: Path,
    fs_manager: FileSystemManager,
    version_manager: VersionManager | None,
    metadata_index: MetadataIndex | None,
):
    """Backup current version before rollback."""
    if version_manager is None or metadata_index is None:
        return

    full_path = memory_bank_dir / file_path
    if not full_path.exists():
        return

    try:
        await _create_backup_snapshot(
            file_path, full_path, fs_manager, version_manager, metadata_index
        )
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.debug(f"Failed to create pre-rollback backup for {file_path}: {e}")


async def _create_backup_snapshot(
    file_path: str,
    full_path: Path,
    fs_manager: FileSystemManager,
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
) -> None:
    """Create backup snapshot for file."""
    content, _ = await fs_manager.read_file(full_path)
    content_hash = fs_manager.compute_hash(content)
    size_bytes = len(content.encode("utf-8"))
    version_count = await _get_version_count(metadata_index, file_path)

    _ = await version_manager.create_snapshot(
        full_path,
        version=version_count + 1,
        content=content,
        size_bytes=size_bytes,
        token_count=0,
        content_hash=content_hash,
        change_type="manual_backup",
        change_description=f"Pre-rollback backup: {datetime.now().isoformat()}",
    )


async def _get_version_count(metadata_index: MetadataIndex, file_path: str) -> int:
    """Get current version count from metadata."""
    file_meta = await metadata_index.get_file_metadata(file_path)
    if not isinstance(file_meta, dict):
        return 0
    version_history_raw: object = file_meta.get("version_history", [])
    if not isinstance(version_history_raw, list):
        return 0
    version_history_list = cast(list[object], version_history_raw)
    return len(version_history_list)
