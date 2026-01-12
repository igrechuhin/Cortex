"""
Rollback Tool

This module provides the rollback_file_version tool for rolling back
Memory Bank files to previous versions.
"""

import json
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import execute_tool_with_stability
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.managers.initialization import get_managers, get_project_root
from cortex.server import mcp


@mcp.tool()
async def rollback_file_version(
    file_name: str, version: int, project_root: str | None = None
) -> str:
    """Rollback a Memory Bank file to a previous version.

    Restores content from a snapshot and creates a new version entry.
    This is a safe operation that preserves history - the rollback itself
    becomes a new version, allowing you to undo the rollback if needed.

    Args:
        file_name: Name of the file (e.g., "projectBrief.md")
        version: Version number to rollback to (must exist in history)
        project_root: Optional path to project root directory

    Returns:
        JSON string with rollback status including the new version number
        created by the rollback operation.

    Example (Success):
        ```json
        {
          "status": "success",
          "file_name": "projectBrief.md",
          "rolled_back_from_version": 3,
          "new_version": 6,
          "token_count": 490
        }
        ```

    Example (Error - version not found):
        ```json
        {
          "status": "error",
          "error": "Version 10 not found for 'projectBrief.md'",
          "error_type": "ValueError"
        }
        ```

    Note:
        - Rollback creates a new version (doesn't delete history)
        - Original content is restored from snapshot
        - Metadata (tokens, size, hash) is recalculated
        - Change type is marked as "rollback" in version history
        - To undo a rollback, use get_version_history to find the
          version before rollback, then rollback to that version
    """
    try:
        result = await execute_tool_with_stability(
            _execute_rollback, file_name, version, project_root
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps(
            build_rollback_error_response(str(e), type(e).__name__), indent=2
        )


async def _execute_rollback(
    file_name: str, version: int, project_root: str | None
) -> dict[str, object]:
    """Execute rollback workflow.

    Args:
        file_name: Name of file to rollback
        version: Version number to rollback to
        project_root: Optional project root path

    Returns:
        Result dictionary (success or error)
    """
    root = get_project_root(project_root)
    mgrs = await get_managers(root)
    managers = _extract_rollback_managers(mgrs)

    validation_result = await _validate_and_get_snapshot(
        managers, root, file_name, version
    )
    if isinstance(validation_result, dict):
        return validation_result

    file_path, content = validation_result
    return await _process_and_finalize_rollback(
        managers, file_name, file_path, content, version
    )


async def _validate_and_get_snapshot(
    managers: dict[
        str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager
    ],
    root: Path,
    file_name: str,
    version: int,
) -> tuple[Path, str] | dict[str, object]:
    """Validate file and get snapshot content.

    Args:
        managers: Managers dictionary
        root: Project root path
        file_name: Name of file
        version: Version number

    Returns:
        Tuple of (file_path, content) or error dict
    """
    file_path = await _validate_rollback_file(
        cast(FileSystemManager, managers["fs_manager"]), root, file_name
    )
    if isinstance(file_path, dict):
        return cast(dict[str, object], file_path)

    content = await _get_rollback_snapshot(
        cast(VersionManager, managers["version_manager"]), file_name, version
    )
    if isinstance(content, dict):
        return cast(dict[str, object], content)

    return (file_path, content)


async def _process_and_finalize_rollback(
    managers: dict[
        str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager
    ],
    file_name: str,
    file_path: Path,
    content: str,
    version: int,
) -> dict[str, object]:
    """Process content and finalize rollback.

    Args:
        managers: Managers dictionary
        file_name: Name of file
        file_path: Path to file
        content: File content
        version: Version rolled back from

    Returns:
        Success response dict
    """
    rollback_data = await _process_rollback_content(
        cast(FileSystemManager, managers["fs_manager"]),
        cast(TokenCounter, managers["token_counter"]),
        file_path,
        content,
    )

    new_version = await _update_rollback_metadata(
        cast(MetadataIndex, managers["metadata_index"]),
        file_name,
        file_path,
        content,
        rollback_data,
    )

    await _complete_rollback_finalization(
        managers, file_name, file_path, content, rollback_data, new_version, version
    )

    return build_rollback_success_response(
        file_name, version, new_version, cast(int, rollback_data["token_count"])
    )


async def _complete_rollback_finalization(
    managers: dict[
        str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager
    ],
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: dict[str, object],
    new_version: int,
    version: int,
) -> None:
    """Complete rollback finalization.

    Args:
        managers: Managers dictionary
        file_name: Name of file
        file_path: Path to file
        content: File content
        rollback_data: Rollback processing data
        new_version: New version number
        version: Version rolled back from
    """
    await _finalize_rollback(
        cast(VersionManager, managers["version_manager"]),
        cast(MetadataIndex, managers["metadata_index"]),
        file_name,
        file_path,
        content,
        rollback_data,
        new_version,
        version,
    )


def _extract_rollback_managers(
    mgrs: dict[str, object],
) -> dict[str, FileSystemManager | TokenCounter | MetadataIndex | VersionManager]:
    """Extract managers for rollback operation.

    Args:
        mgrs: Managers dictionary

    Returns:
        Dictionary with extracted managers
    """
    return {
        "fs_manager": cast(FileSystemManager, mgrs["fs"]),
        "token_counter": cast(TokenCounter, mgrs["tokens"]),
        "metadata_index": cast(MetadataIndex, mgrs["index"]),
        "version_manager": cast(VersionManager, mgrs["versions"]),
    }


async def _validate_rollback_file(
    fs_manager: FileSystemManager, root: Path, file_name: str
) -> Path | dict[str, str]:
    """Validate file name for rollback.

    Args:
        fs_manager: File system manager
        root: Project root path
        file_name: Name of file to rollback

    Returns:
        File path or error dict
    """
    memory_bank_dir = root / "memory-bank"
    try:
        return fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return {"status": "error", "error": f"Invalid file name: {e}"}


async def _get_rollback_snapshot(
    version_manager: VersionManager, file_name: str, version: int
) -> str | dict[str, str]:
    """Get snapshot content for rollback.

    Args:
        version_manager: Version manager
        file_name: Name of file
        version: Version number to rollback to

    Returns:
        Content string or error dict
    """
    snapshot_path = version_manager.get_snapshot_path(file_name, version)
    if not snapshot_path.exists():
        return {
            "status": "error",
            "error": f"Version {version} not found for '{file_name}'",
        }

    return await version_manager.get_snapshot_content(snapshot_path)


async def _process_rollback_content(
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    file_path: Path,
    content: str,
) -> dict[str, object]:
    """Process rollback content: write, parse, and count tokens.

    Args:
        fs_manager: File system manager
        token_counter: Token counter
        file_path: Path to file
        content: Content to write

    Returns:
        Dictionary with processing results
    """
    new_hash = await fs_manager.write_file(file_path, content)

    sections_raw = fs_manager.parse_sections(content)
    sections = cast(
        list[dict[str, object]],
        [{k: v for k, v in section.items()} for section in sections_raw],
    )

    token_count = token_counter.count_tokens(content)

    return {
        "content_hash": new_hash,
        "sections": sections,
        "token_count": token_count,
        "size_bytes": len(content.encode("utf-8")),
    }


async def _update_rollback_metadata(
    metadata_index: MetadataIndex,
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: dict[str, object],
) -> int:
    """Update metadata after rollback.

    Args:
        metadata_index: Metadata index
        file_name: Name of file
        file_path: Path to file
        content: File content
        rollback_data: Rollback processing data

    Returns:
        New version number
    """
    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=True,
        size_bytes=cast(int, rollback_data["size_bytes"]),
        token_count=cast(int, rollback_data["token_count"]),
        content_hash=cast(str, rollback_data["content_hash"]),
        sections=cast(list[dict[str, object]], rollback_data["sections"]),
        change_source="rollback",
    )

    file_meta = await metadata_index.get_file_metadata(file_name)
    return cast(int, file_meta.get("current_version", 0)) + 1 if file_meta else 1


async def _finalize_rollback(
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: dict[str, object],
    new_version: int,
    rolled_back_from_version: int,
) -> None:
    """Finalize rollback by creating version snapshot and saving metadata.

    Args:
        version_manager: Version manager
        metadata_index: Metadata index
        file_name: Name of file
        file_path: Path to file
        content: File content
        rollback_data: Rollback processing data
        new_version: New version number
        rolled_back_from_version: Version rolled back from
    """
    version_meta = await version_manager.create_snapshot(
        file_path=file_path,
        version=new_version,
        content=content,
        size_bytes=cast(int, rollback_data["size_bytes"]),
        token_count=cast(int, rollback_data["token_count"]),
        content_hash=cast(str, rollback_data["content_hash"]),
        change_type="rollback",
        change_description=f"Rolled back to version {rolled_back_from_version}",
    )

    await metadata_index.add_version_to_history(file_name, version_meta)
    await metadata_index.save()


def build_rollback_success_response(
    file_name: str, rolled_back_from_version: int, new_version: int, token_count: int
) -> dict[str, object]:
    """Build success response for rollback.

    Args:
        file_name: Name of file
        rolled_back_from_version: Version rolled back from
        new_version: New version number
        token_count: Token count

    Returns:
        Success response dict
    """
    return {
        "status": "success",
        "file_name": file_name,
        "rolled_back_from_version": rolled_back_from_version,
        "new_version": new_version,
        "token_count": token_count,
    }


def build_rollback_error_response(
    error_message: str, error_type: str
) -> dict[str, object]:
    """Build error response for rollback.

    Args:
        error_message: Error message
        error_type: Error type name

    Returns:
        Error response dict
    """
    return {"status": "error", "error": error_message, "error_type": error_type}
