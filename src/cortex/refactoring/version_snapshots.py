"""
Version Snapshots - Rollback Manager Support

Handle version snapshot operations for rollback functionality.
"""

from pathlib import Path
from typing import cast

from pydantic import BaseModel

from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import JsonValue, VersionMetadata


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
    version_history = _extract_version_history(file_meta)
    if version_history is None:
        return False

    for version_entry in version_history:
        change_description = version_entry.change_description or ""
        if change_description.startswith(f"Pre-refactoring snapshot: {snapshot_id}"):
            return True

    return False


async def get_version_history(
    file_path: str, metadata_index: MetadataIndex
) -> list[VersionMetadata] | None:
    """Get version history for a file.

    Args:
        file_path: Path to file
        metadata_index: Metadata index instance

    Returns:
        Version history list (as Pydantic models) or None if not found
    """
    file_meta = await metadata_index.get_file_metadata(file_path)
    if file_meta is None:
        return None

    return _extract_version_history(file_meta)


def find_snapshot_version(
    version_history: list[VersionMetadata], snapshot_id: str
) -> int | None:
    """Find version number for a snapshot.

    Args:
        version_history: Version history list (Pydantic models)
        snapshot_id: Snapshot to find

    Returns:
        Version number or None if not found
    """

    for version_entry in version_history:
        change_description = version_entry.change_description or ""
        if not change_description.startswith(
            f"Pre-refactoring snapshot: {snapshot_id}"
        ):
            continue

        return version_entry.version

    return None


def _extract_version_history(file_meta: JsonValue) -> list[VersionMetadata] | None:
    """Extract version_history from either a dict or a metadata model."""
    if file_meta is None:
        return None

    if isinstance(file_meta, dict):
        history_raw = file_meta.get("version_history")
        if not isinstance(history_raw, list):
            return None
        history: list[VersionMetadata] = []
        for item in cast(list[JsonValue], history_raw):
            if isinstance(item, VersionMetadata):
                history.append(item)
            elif isinstance(item, BaseModel):
                history.append(
                    VersionMetadata.model_validate(item.model_dump(mode="json"))
                )
            elif isinstance(item, dict):
                history.append(VersionMetadata.model_validate(item))
        return history

    version_history_attr = getattr(file_meta, "version_history", None)
    if not isinstance(version_history_attr, list):
        return None

    history: list[VersionMetadata] = []
    for item in cast(list[JsonValue], version_history_attr):
        if isinstance(item, BaseModel):
            history.append(VersionMetadata.model_validate(item.model_dump(mode="json")))
        elif isinstance(item, dict):
            history.append(VersionMetadata.model_validate(item))
    return history
