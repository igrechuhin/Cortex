"""Timestamp validation operations for Memory Bank files."""

from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.tools.validation_helpers import read_all_memory_bank_files
from cortex.validation.timestamp_validator import (
    validate_timestamps_all_files,
    validate_timestamps_single_file,
)


async def handle_timestamps_validation(
    fs_manager: FileSystemManager,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle timestamps validation routing.

    Args:
        fs_manager: File system manager
        root: Project root path
        file_name: Optional specific file to validate

    Returns:
        JSON string with timestamps validation results
    """
    if file_name:
        return await validate_timestamps_single_file(fs_manager, root, file_name)
    else:
        return await validate_timestamps_all_files(
            fs_manager, root, read_all_memory_bank_files
        )
