"""
Version Snapshots - Rollback Manager Support

Handle version snapshot operations for rollback functionality.
"""

from pathlib import Path
from typing import cast

from cortex.core.metadata_index import MetadataIndex


async def find_snapshot_for_execution(execution_id: str) -> str | None:
    """Find snapshot ID for an execution.

    Args:
        execution_id: Execution ID

    Returns:
        Snapshot ID or None if not found
    """
    # This would typically come from the execution record
    # For now, we'll construct it from the execution_id
    # In practice, the RefactoringExecutor would store this
    if "exec-" in execution_id:
        # Extract timestamp from execution_id
        # Format: exec-{suggestion_id}-{timestamp}
        parts = execution_id.split("-")
        if len(parts) >= 3:
            timestamp = parts[-1]
            return f"refactoring-{timestamp}"
    return None


async def get_affected_files(
    memory_bank_dir: Path,
    execution_id: str,
    snapshot_id: str,
    metadata_index: MetadataIndex,
) -> list[str]:
    """Get list of files affected by an execution.

    Args:
        memory_bank_dir: Memory bank directory
        execution_id: Execution ID
        snapshot_id: Snapshot ID
        metadata_index: Metadata index instance

    Returns:
        List of affected file paths
    """
    del execution_id  # Unused but kept for API compatibility
    if not snapshot_id:
        return []

    affected_files: list[str] = []
    for file_path in memory_bank_dir.glob("**/*.md"):
        if file_path.is_file():
            rel_path = file_path.relative_to(memory_bank_dir)
            if await _file_has_snapshot(str(rel_path), snapshot_id, metadata_index):
                affected_files.append(str(rel_path))

    return affected_files


async def _file_has_snapshot(
    rel_path: str, snapshot_id: str, metadata_index: MetadataIndex
) -> bool:
    """Check if file has snapshot with matching ID.

    Args:
        rel_path: Relative file path
        snapshot_id: Snapshot ID to check
        metadata_index: Metadata index instance

    Returns:
        True if file has matching snapshot
    """
    file_meta = await metadata_index.get_file_metadata(rel_path)

    if file_meta is None:
        return False

    # file_meta is dict[str, object] - use dict-style access
    version_history_raw = file_meta.get("version_history", [])
    if not isinstance(version_history_raw, list):
        return False

    # Cast the list to proper type for iteration
    version_history: list[object] = cast(list[object], version_history_raw)
    for item in version_history:
        if not isinstance(item, dict):
            continue
        version_dict = cast(dict[str, object], item)
        desc_raw = version_dict.get("change_description", "") or ""
        change_description = str(desc_raw)
        if change_description.startswith(f"Pre-refactoring snapshot: {snapshot_id}"):
            return True

    return False


async def get_version_history(
    file_path: str, metadata_index: MetadataIndex
) -> list[dict[str, object]] | None:
    """Get version history for a file.

    Args:
        file_path: Path to file
        metadata_index: Metadata index instance

    Returns:
        Version history list (as list of dicts) or None if not found
    """
    file_meta = await metadata_index.get_file_metadata(file_path)
    if file_meta is None:
        return None

    # file_meta is dict[str, object] - use dict-style access
    version_history_raw = file_meta.get("version_history", [])
    if not isinstance(version_history_raw, list):
        return None

    # Cast to list of dicts (each version entry is a dict)
    version_list: list[object] = cast(list[object], version_history_raw)
    return [cast(dict[str, object], v) for v in version_list if isinstance(v, dict)]


def find_snapshot_version(
    version_history: list[dict[str, object]], snapshot_id: str
) -> int | None:
    """Find version number for a snapshot.

    Args:
        version_history: Version history list (list of dicts)
        snapshot_id: Snapshot to find

    Returns:
        Version number or None if not found
    """
    for version_dict in version_history:
        change_description = str(version_dict.get("change_description", "") or "")
        if change_description.startswith(f"Pre-refactoring snapshot: {snapshot_id}"):
            version_num = version_dict.get("version")
            if isinstance(version_num, int):
                return version_num

    return None
