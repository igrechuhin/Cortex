"""
Rollback Conflicts - Rollback Manager Support

Handle conflict detection and resolution for rollback operations.
"""

from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex


async def detect_conflicts(
    affected_files: list[str],
    snapshot_id: str,
    memory_bank_dir: Path,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
) -> list[str]:
    """Detect conflicts between current state and snapshot.

    A conflict occurs when:
    - File has been manually edited since snapshot
    - File structure has changed

    Args:
        affected_files: List of affected files
        snapshot_id: Snapshot ID (for future use)
        memory_bank_dir: Memory bank directory
        fs_manager: File system manager
        metadata_index: Metadata index

    Returns:
        List of conflict descriptions
    """
    conflicts: list[str] = []

    for file_path in affected_files:
        full_path = memory_bank_dir / file_path

        if not full_path.exists():
            conflicts.append(f"{file_path} - File was deleted after refactoring")
            continue

        # Get current content hash
        content, _ = await fs_manager.read_file(full_path)
        current_hash = fs_manager.compute_hash(content)

        # Get metadata to check for external modifications
        metadata = await metadata_index.get_file_metadata(file_path)
        if metadata:
            stored_hash = metadata.get("content_hash")
            if stored_hash and str(stored_hash) != current_hash:
                conflicts.append(f"{file_path} - File has been manually edited")

    return conflicts


async def detect_rollback_conflicts(
    preserve_manual_changes: bool,
    affected_files: list[str],
    snapshot_id: str,
    memory_bank_dir: Path,
    fs_manager: FileSystemManager,
    metadata_index: MetadataIndex,
) -> list[str]:
    """Detect conflicts for rollback.

    Args:
        preserve_manual_changes: Whether to preserve manual changes
        affected_files: List of affected files
        snapshot_id: Snapshot ID
        memory_bank_dir: Memory bank directory
        fs_manager: File system manager
        metadata_index: Metadata index

    Returns:
        List of conflicts
    """
    conflicts: list[str] = []
    if preserve_manual_changes:
        conflicts = await detect_conflicts(
            affected_files, snapshot_id, memory_bank_dir, fs_manager, metadata_index
        )
    return conflicts
