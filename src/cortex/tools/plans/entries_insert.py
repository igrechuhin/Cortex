"""
Roadmap entry insertion logic.

Extracted from roadmap_operations for maintainability.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from cortex.core.constants import MemoryBankFile

if TYPE_CHECKING:
    from cortex.tools.models import AddRoadmapEntryResult
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.plans.entries_content import (
    ADD_ENTRY_COMPLETED_MESSAGE,
    entry_text_looks_completed,
    insert_roadmap_entry,
    validate_section_id,
)
from cortex.tools.plans.entries_io import (
    read_roadmap_file,
    write_roadmap_file,
)


def _handle_read_error(
    section_id: str | None, read_error: str
) -> AddRoadmapEntryResult:
    """Handle read errors. Returns error result."""
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="Failed to read roadmap",
        line_inserted=None,
        section=None,
        error=read_error,
    )


def _handle_insert_failure(
    section_id: str,
) -> AddRoadmapEntryResult:
    """Handle insert failures. Returns error result."""
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="Failed to insert entry",
        line_inserted=None,
        section=section_id,
        error=f"Could not find section '{section_id}' in roadmap",
    )


def _handle_write_error(section_id: str, write_error: str) -> AddRoadmapEntryResult:
    """Handle write errors. Returns error result."""
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="Conflict or lock timeout",
        line_inserted=None,
        section=section_id,
        error=write_error,
    )


def _make_insert_success_result(
    section_id: str, line_inserted: int
) -> AddRoadmapEntryResult:
    """Build success result for roadmap insertion."""
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.SUCCESS,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Entry added to '{section_id}' section at line {line_inserted}",
        line_inserted=line_inserted,
        section=section_id,
        error=None,
    )


def _handle_section_validation_error(
    section: str, section_error: str
) -> AddRoadmapEntryResult:
    """Handle section validation errors."""
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Unknown section: {section}",
        line_inserted=None,
        section=None,
        error=section_error,
    )


def _handle_completed_entry_rejected() -> AddRoadmapEntryResult:
    """Return error result when entry looks like completed work."""
    from cortex.tools.models import AddRoadmapEntryResult

    return AddRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message="Completed entries not allowed in roadmap",
        line_inserted=None,
        section=None,
        error=ADD_ENTRY_COMPLETED_MESSAGE,
    )


async def execute_roadmap_insertion(
    root_path: Path,
    section: str,
    entry_text: str,
    position: str,
) -> AddRoadmapEntryResult:
    """Execute insertion. Returns AddRoadmapEntryResult."""
    if entry_text_looks_completed(entry_text):
        return _handle_completed_entry_rejected()

    section_id, section_error = validate_section_id(section)
    if section_error:
        return _handle_section_validation_error(section, section_error)

    memory_bank_root = get_cortex_path(root_path, CortexResourceType.MEMORY_BANK)
    roadmap_path = memory_bank_root / MemoryBankFile.ROADMAP
    current_content, read_error = read_roadmap_file(roadmap_path)
    if read_error:
        return _handle_read_error(section_id, read_error)

    assert current_content is not None
    assert section_id is not None

    updated_content, line_inserted = insert_roadmap_entry(
        current_content, section_id, entry_text, position
    )

    if line_inserted is None:
        return _handle_insert_failure(section_id)

    write_error = await write_roadmap_file(roadmap_path, updated_content, root_path)
    if write_error:
        return _handle_write_error(section_id, write_error)

    return _make_insert_success_result(section_id, line_inserted)
