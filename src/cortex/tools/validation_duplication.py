"""Duplication validation operations for Memory Bank files."""

import json
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.tools.validation_helpers import (
    generate_duplication_fixes,
    read_all_memory_bank_files,
)
from cortex.validation.duplication_detector import DuplicationDetector
from cortex.validation.validation_config import ValidationConfig


async def validate_duplications(
    fs_manager: FileSystemManager,
    duplication_detector: DuplicationDetector,
    validation_config: ValidationConfig,
    root: Path,
    similarity_threshold: float | None,
    suggest_fixes: bool,
) -> str:
    """Detect duplicate content across files."""
    threshold = similarity_threshold or validation_config.get_duplication_threshold()
    files_content = await read_all_memory_bank_files(fs_manager, root)
    duplication_detector.threshold = threshold
    duplications_dict = await duplication_detector.scan_all_files(files_content)

    duplication_result: dict[str, object] = {
        "status": "success",
        "check_type": "duplications",
        "threshold": threshold,
    }
    duplication_result.update(duplications_dict)

    duplicates_found = cast(int, duplications_dict.get("duplicates_found", 0))
    if suggest_fixes and duplicates_found > 0:
        duplication_result["suggested_fixes"] = generate_duplication_fixes(
            duplications_dict
        )

    return json.dumps(duplication_result, indent=2)


async def handle_duplications_validation(
    fs_manager: FileSystemManager,
    duplication_detector: DuplicationDetector,
    validation_config: ValidationConfig,
    root: Path,
    similarity_threshold: float | None,
    suggest_fixes: bool,
) -> str:
    """Handle duplications validation.

    Args:
        fs_manager: File system manager
        duplication_detector: Duplication detector instance
        validation_config: Validation configuration
        root: Project root path
        similarity_threshold: Threshold for duplications
        suggest_fixes: Whether to include fix suggestions

    Returns:
        JSON string with duplications validation results
    """
    return await validate_duplications(
        fs_manager,
        duplication_detector,
        validation_config,
        root,
        similarity_threshold,
        suggest_fixes,
    )
