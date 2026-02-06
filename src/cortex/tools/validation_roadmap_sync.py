"""Roadmap sync validation operations for Memory Bank files."""

import json
import logging
from pathlib import Path

from cortex.core.file_system import FileSystemManager
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.validation.roadmap_sync import (
    SyncValidationResult,
    validate_roadmap_sync,
)

logger = logging.getLogger(__name__)


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
    missing_entries = [item.model_dump() for item in result.missing_roadmap_entries]
    invalid_refs = [ref.model_dump() for ref in result.invalid_references]
    warnings = list(result.warnings)
    return json.dumps(
        {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": result.valid,
            "missing_roadmap_entries": missing_entries,
            "invalid_references": invalid_refs,
            # Expose unlinked_plans so callers can see which non-archived plans
            # are not referenced in roadmap.md (helps prevent partial updates
            # where plans are completed or removed from roadmap without proper
            # archiving or memory bank updates).
            "unlinked_plans": list(result.unlinked_plans),
            "warnings": warnings,
            "summary": {
                "total_todos_found": result.total_todos_found,
                "missing_entries_count": len(missing_entries),
                "invalid_references_count": len(invalid_refs),
                "warnings_count": len(warnings),
            },
        },
        indent=2,
    )


def _log_roadmap_ghost_sections(roadmap_content: str, roadmap_path: Path) -> None:
    """Log if roadmap content contains ghost sections (debugging)."""
    logger.info(
        "Roadmap sync validation: reading from %s (absolute: %s, size: %d chars, exists: %s)",
        roadmap_path,
        roadmap_path.resolve(),
        len(roadmap_content),
        roadmap_path.exists(),
    )
    ghost_sections = [
        "## Recent Findings",
        "## Completed Milestones",
        "### Planned Phases",
    ]
    found_ghost_sections = [s for s in ghost_sections if s in roadmap_content]
    if found_ghost_sections:
        logger.error(
            (
                "CRITICAL: Roadmap content contains ghost sections that should not exist: %s. "
                + "This indicates the validator is reading from the wrong file or stale content."
            ),
            found_ghost_sections,
        )
        logger.error(
            "Roadmap content preview (first 1000 chars): %s", roadmap_content[:1000]
        )
        logger.error(
            "Roadmap content preview (last 500 chars): %s", roadmap_content[-500:]
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
    _log_roadmap_ghost_sections(roadmap_content, roadmap_path)
    result = validate_roadmap_sync(root, roadmap_content)
    return _build_roadmap_sync_success_response(result)
