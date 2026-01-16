"""Roadmap sync validation operations for Memory Bank files."""

import json
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.validation.roadmap_sync import (
    SyncValidationResult,
    validate_roadmap_sync,
)


def _build_roadmap_sync_error_response() -> str:
    """Build error response for missing roadmap.md.

    Returns:
        JSON string with error response
    """
    return json.dumps(
        {
            "status": "error",
            "error": "roadmap.md does not exist in memory bank",
        },
        indent=2,
    )


def _build_roadmap_sync_success_response(
    result: SyncValidationResult,
) -> str:
    """Build success response for roadmap sync validation.

    Args:
        result: Validation result

    Returns:
        JSON string with success response
    """
    return json.dumps(
        {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": result["valid"],
            "missing_roadmap_entries": result["missing_roadmap_entries"],
            "invalid_references": result["invalid_references"],
            "warnings": result["warnings"],
            "summary": {
                "missing_entries_count": len(result["missing_roadmap_entries"]),
                "invalid_references_count": len(result["invalid_references"]),
                "warnings_count": len(result["warnings"]),
            },
        },
        indent=2,
    )


async def handle_roadmap_sync_validation(
    fs_manager: FileSystemManager,
    root: Path,
    file_name: str | None,
) -> str:
    """Handle roadmap synchronization validation.

    Args:
        fs_manager: File system manager
        root: Project root path
        file_name: Ignored (roadmap sync always validates entire roadmap)

    Returns:
        JSON string with roadmap sync validation results
    """
    memory_bank_dir = get_cortex_path(root, CortexResourceType.MEMORY_BANK)
    roadmap_path = memory_bank_dir / "roadmap.md"

    if not roadmap_path.exists():
        return _build_roadmap_sync_error_response()

    roadmap_content, _ = await fs_manager.read_file(roadmap_path)
    result = validate_roadmap_sync(root, roadmap_content)
    return _build_roadmap_sync_success_response(result)
