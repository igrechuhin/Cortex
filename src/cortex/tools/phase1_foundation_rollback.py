"""
Rollback Tool

This module provides the rollback_file_version tool for rolling back
Memory Bank files to previous versions.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.file_system import FileSystemManager
from cortex.core.mcp_stability import execute_tool_with_stability
from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import SectionMetadata
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.managers import initialization
from cortex.server import mcp
from cortex.tools.models import (
    RollbackFileVersionErrorResult,
    RollbackFileVersionResult,
)


class RollbackManagers(BaseModel):
    """Typed manager bundle for rollback operations."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    fs_manager: FileSystemManager = Field(description="File system manager")
    token_counter: TokenCounter = Field(description="Token counter")
    metadata_index: MetadataIndex = Field(description="Metadata index")
    version_manager: VersionManager = Field(description="Version manager")


class RollbackProcessingData(BaseModel):
    """Rollback processing data structure.

    This model replaces `ModelDict` for rollback processing data.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    content_hash: str = Field(..., description="Content hash")
    sections: list[SectionMetadata] = Field(
        default_factory=lambda: list[SectionMetadata](),
        description="Parsed sections",
    )
    token_count: int = Field(..., ge=0, description="Token count")
    size_bytes: int = Field(..., ge=0, description="Size in bytes")


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
        if isinstance(result, dict):
            return json.dumps(result, indent=2)
        return json.dumps(result.model_dump(exclude_none=True), indent=2)
    except Exception as e:
        error_result = build_rollback_error_response(str(e), type(e).__name__)
        return json.dumps(error_result.model_dump(exclude_none=True), indent=2)


async def _execute_rollback(
    file_name: str, version: int, project_root: str | None
) -> RollbackFileVersionResult | RollbackFileVersionErrorResult:
    """Execute rollback workflow.

    Args:
        file_name: Name of file to rollback
        version: Version number to rollback to
        project_root: Optional project root path

    Returns:
        RollbackFileVersionResult or RollbackFileVersionErrorResult
    """
    root = initialization.get_project_root(project_root)
    mgrs = await initialization.get_managers(root)
    # These managers are produced by our initialization pipeline.
    # Avoid re-validating concrete manager instance types here; it makes
    # tests unnecessarily brittle (MagicMock) without improving safety.
    managers = RollbackManagers.model_construct(
        fs_manager=mgrs.fs,
        token_counter=mgrs.tokens,
        metadata_index=mgrs.index,
        version_manager=mgrs.versions,
    )

    validation_result = await _validate_and_get_snapshot(
        managers, root, file_name, version
    )
    if isinstance(validation_result, RollbackFileVersionErrorResult):
        return validation_result

    file_path, content = validation_result
    return await _process_and_finalize_rollback(
        managers, file_name, file_path, content, version
    )


async def _validate_and_get_snapshot(
    managers: RollbackManagers,
    root: Path,
    file_name: str,
    version: int,
) -> tuple[Path, str] | RollbackFileVersionErrorResult:
    """Validate file and get snapshot content.

    Args:
        managers: Managers dictionary
        root: Project root path
        file_name: Name of file
        version: Version number

    Returns:
        Tuple of (file_path, content) or RollbackFileVersionErrorResult
    """
    file_path = await _validate_rollback_file(managers.fs_manager, root, file_name)
    if isinstance(file_path, RollbackFileVersionErrorResult):
        return file_path

    content = await _get_rollback_snapshot(managers.version_manager, file_name, version)
    if isinstance(content, RollbackFileVersionErrorResult):
        return content

    return (file_path, content)


async def _process_and_finalize_rollback(
    managers: RollbackManagers,
    file_name: str,
    file_path: Path,
    content: str,
    version: int,
) -> RollbackFileVersionResult:
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
        managers.fs_manager,
        managers.token_counter,
        file_path,
        content,
    )

    new_version = await _update_rollback_metadata(
        managers.metadata_index,
        file_name,
        file_path,
        content,
        rollback_data,
    )

    await _complete_rollback_finalization(
        managers, file_name, file_path, content, rollback_data, new_version, version
    )

    success_result = build_rollback_success_response(
        file_name, version, new_version, rollback_data.token_count
    )
    return success_result


async def _complete_rollback_finalization(
    managers: RollbackManagers,
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: RollbackProcessingData,
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
        managers.version_manager,
        managers.metadata_index,
        file_name,
        file_path,
        content,
        rollback_data,
        new_version,
        version,
    )


async def _validate_rollback_file(
    fs_manager: FileSystemManager, root: Path, file_name: str
) -> Path | RollbackFileVersionErrorResult:
    """Validate file name for rollback.

    Args:
        fs_manager: File system manager
        root: Project root path
        file_name: Name of file to rollback

    Returns:
        File path or error dict
    """
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    try:
        return fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return RollbackFileVersionErrorResult(
            error=f"Invalid file name: {e}",
            error_type=type(e).__name__,
        )


async def _get_rollback_snapshot(
    version_manager: VersionManager, file_name: str, version: int
) -> str | RollbackFileVersionErrorResult:
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
        return RollbackFileVersionErrorResult(
            error=f"Version {version} not found for '{file_name}'",
            error_type="NotFoundError",
        )

    return await version_manager.get_snapshot_content(snapshot_path)


async def _process_rollback_content(
    fs_manager: FileSystemManager,
    token_counter: TokenCounter,
    file_path: Path,
    content: str,
) -> RollbackProcessingData:
    """Process rollback content: write, parse, and count tokens.

    Args:
        fs_manager: File system manager
        token_counter: Token counter
        file_path: Path to file
        content: Content to write

    Returns:
        Rollback processing data
    """
    new_hash = await fs_manager.write_file(file_path, content)
    sections = fs_manager.parse_sections(content)
    token_count = token_counter.count_tokens(content)

    return RollbackProcessingData(
        content_hash=new_hash,
        sections=sections,
        token_count=token_count,
        size_bytes=len(content.encode("utf-8")),
    )


async def _update_rollback_metadata(
    metadata_index: MetadataIndex,
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: RollbackProcessingData,
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
        size_bytes=rollback_data.size_bytes,
        token_count=rollback_data.token_count,
        content_hash=rollback_data.content_hash,
        sections=rollback_data.sections,
        change_source="rollback",
    )

    file_meta = await metadata_index.get_file_metadata(file_name)
    if not file_meta:
        return 1
    current_raw = file_meta.get("current_version", 0)
    current_version = int(current_raw) if isinstance(current_raw, int) else 0
    return current_version + 1


async def _finalize_rollback(
    version_manager: VersionManager,
    metadata_index: MetadataIndex,
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: RollbackProcessingData,
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
        size_bytes=rollback_data.size_bytes,
        token_count=rollback_data.token_count,
        content_hash=rollback_data.content_hash,
        change_type="rollback",
        change_description=f"Rolled back to version {rolled_back_from_version}",
    )

    await metadata_index.add_version_to_history(file_name, version_meta)
    await metadata_index.save()


def build_rollback_success_response(
    file_name: str, rolled_back_from_version: int, new_version: int, token_count: int
) -> RollbackFileVersionResult:
    """Build success response for rollback.

    Args:
        file_name: Name of file
        rolled_back_from_version: Version rolled back from
        new_version: New version number
        token_count: Token count

    Returns:
        RollbackFileVersionResult model
    """
    from cortex.tools.models import RollbackFileVersionResult

    return RollbackFileVersionResult(
        file_name=file_name,
        rolled_back_from_version=rolled_back_from_version,
        new_version=new_version,
        token_count=token_count,
    )


def build_rollback_error_response(
    error_message: str, error_type: str
) -> RollbackFileVersionErrorResult:
    """Build error response for rollback.

    Args:
        error_message: Error message
        error_type: Error type name

    Returns:
        Error response dict
    """
    from cortex.tools.models import RollbackFileVersionErrorResult

    return RollbackFileVersionErrorResult(
        error=error_message,
        error_type=error_type,
    )
