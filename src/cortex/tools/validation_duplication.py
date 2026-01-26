"""Duplication validation operations for Memory Bank files."""

import json
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.models import JsonValue, ModelDict
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
    duplications = await duplication_detector.scan_all_files(files_content)
    duplications_dict = cast(ModelDict, duplications.model_dump(mode="json"))

    duplication_result: ModelDict = {
        "status": "success",
        "check_type": "duplications",
        "threshold": threshold,
    }
    duplication_result.update(duplications_dict)

    if suggest_fixes and duplications.duplicates_found > 0:
        duplication_result["suggested_fixes"] = cast(
            JsonValue, generate_duplication_fixes(duplications_dict)
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
