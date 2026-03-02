"""Helper functions for rollback operations.

Extracted from foundation_rollback to keep the main module within line limits.
"""

from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.tools.models import (
    RollbackFileVersionErrorResult,
    RollbackFileVersionResult,
)

from .foundation_rollback_models import (
    RollbackManagers,
    RollbackProcessingData,
)


async def validate_rollback_file(
    fs_manager: FileSystemManager, root: Path, file_name: str
) -> Path | RollbackFileVersionErrorResult:
    """Validate file name for rollback.

    Args:
        fs_manager: File system manager
        root: Project root path
        file_name: Name of file to rollback

    Returns:
        File path or error result
    """
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    try:
        return fs_manager.construct_safe_path(memory_bank_dir, file_name)
    except (ValueError, PermissionError) as e:
        return RollbackFileVersionErrorResult(
            error=f"Invalid file name: {e}",
            error_type=type(e).__name__,
        )


async def get_rollback_snapshot(
    version_manager: VersionManager, file_name: str, version: int
) -> str | RollbackFileVersionErrorResult:
    """Get snapshot content for rollback.

    Args:
        version_manager: Version manager
        file_name: Name of file
        version: Version number to rollback to

    Returns:
        Content string or error result
    """
    snapshot_path = version_manager.get_snapshot_path(file_name, version)
    if not snapshot_path.exists():
        return RollbackFileVersionErrorResult(
            error=f"Version {version} not found for '{file_name}'",
            error_type="NotFoundError",
        )

    return await version_manager.get_snapshot_content(snapshot_path)


async def process_rollback_content(
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


async def update_rollback_metadata(
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
    sections_raw = rollback_data.sections
    sections = [section.model_dump(mode="json") for section in sections_raw]
    await metadata_index.update_file_metadata(
        file_name=file_name,
        path=file_path,
        exists=True,
        size_bytes=rollback_data.size_bytes,
        token_count=rollback_data.token_count,
        content_hash=rollback_data.content_hash,
        sections=sections,
        change_source="rollback",
    )

    file_meta = await metadata_index.get_file_metadata(file_name)
    if not file_meta:
        return 1
    return file_meta.current_version + 1


async def finalize_rollback(
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

    await metadata_index.add_version_to_history(
        file_name, version_meta.model_dump(mode="json")
    )
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
    return RollbackFileVersionResult(
        file_name=file_name,
        rolled_back_from_version=rolled_back_from_version,
        new_version=new_version,
        token_count=token_count,
    )


async def validate_and_get_snapshot(
    managers: RollbackManagers,
    root: Path,
    file_name: str,
    version: int,
) -> tuple[Path, str] | RollbackFileVersionErrorResult:
    """Validate file and get snapshot content."""
    file_path = await validate_rollback_file(managers.fs_manager, root, file_name)
    if isinstance(file_path, RollbackFileVersionErrorResult):
        return file_path

    content = await get_rollback_snapshot(managers.version_manager, file_name, version)
    if isinstance(content, RollbackFileVersionErrorResult):
        return content

    return (file_path, content)


async def _apply_metadata_and_finalize(
    managers: RollbackManagers,
    file_name: str,
    file_path: Path,
    content: str,
    rollback_data: RollbackProcessingData,
    version: int,
) -> int:
    """Update metadata and finalize rollback; return new version."""
    new_version = await update_rollback_metadata(
        managers.metadata_index,
        file_name,
        file_path,
        content,
        rollback_data,
    )
    await finalize_rollback(
        managers.version_manager,
        managers.metadata_index,
        file_name,
        file_path,
        content,
        rollback_data,
        new_version,
        version,
    )
    return new_version


async def process_and_finalize_rollback(
    managers: RollbackManagers,
    file_name: str,
    file_path: Path,
    content: str,
    version: int,
) -> RollbackFileVersionResult:
    """Process content and finalize rollback."""
    rollback_data = await process_rollback_content(
        managers.fs_manager,
        managers.token_counter,
        file_path,
        content,
    )
    new_version = await _apply_metadata_and_finalize(
        managers, file_name, file_path, content, rollback_data, version
    )
    return build_rollback_success_response(
        file_name, version, new_version, rollback_data.token_count
    )


def build_rollback_error_response(
    error_message: str, error_type: str
) -> RollbackFileVersionErrorResult:
    """Build error response for rollback.

    Args:
        error_message: Error message
        error_type: Error type name

    Returns:
        Error response model
    """
    return RollbackFileVersionErrorResult(
        error=error_message,
        error_type=error_type,
    )
