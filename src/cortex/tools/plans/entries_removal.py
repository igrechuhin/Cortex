"""
Roadmap entry and section removal logic.

Extracted from roadmap_operations for maintainability.
"""

import re
from pathlib import Path

from cortex.core.constants import MemoryBankFile
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.models import (
    RemoveRoadmapEntryResult,
    RemoveRoadmapSectionResult,
)
from cortex.tools.plans.entries_content import (
    extract_plan_path_from_bullet,
    find_bullet_line_containing,
    find_section_range_by_heading,
    remove_line_at,
    remove_section_range,
)
from cortex.tools.plans.entries_io import (
    read_roadmap_file,
    write_roadmap_file,
)


def _is_plan_marked_complete(plan_path: Path) -> bool:
    """Return True if the plan file exists and its Status line indicates completion."""
    if not plan_path.exists():
        return False
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return False
    status_match = re.search(
        r"^\*\*Status:\*\*\s*(.+)$", text, flags=re.IGNORECASE | re.MULTILINE
    )
    if not status_match:
        return False
    status_value = status_match.group(1).strip().upper()
    return "COMPLETE" in status_value


def _validate_plan_status_before_removal(
    root_path: Path, roadmap_content: str, one_based_line: int
) -> str | None:
    """Enforce guardrail: do not remove roadmap entries for PENDING/IN PROGRESS plans."""
    lines = roadmap_content.split("\n")
    idx = one_based_line - 1
    if idx < 0 or idx >= len(lines):
        return None
    line = lines[idx]
    plan_ref = extract_plan_path_from_bullet(line)
    if not plan_ref:
        return None

    plans_root = get_cortex_path(root_path, CortexResourceType.PLANS)
    if plan_ref.startswith(".cortex/plans/"):
        plan_rel = plan_ref[len(".cortex/plans/") :]
        candidate = plans_root / plan_rel
    elif plan_ref.startswith("plans/"):
        plan_rel = plan_ref[len("plans/") :]
        candidate = plans_root / plan_rel
    elif plan_ref.startswith("cortex/plans/"):
        plan_rel = plan_ref[len("cortex/plans/") :]
        candidate = plans_root / plan_rel
    else:
        return None

    if not _is_plan_marked_complete(candidate):
        return (
            "Refusing to remove roadmap entry for a plan that is not marked "
            "COMPLETE. Update the plan's **Status:** to COMPLETE/COMPLETED and "
            "use complete_plan(), or leave the roadmap entry in place for "
            "PENDING/IN PROGRESS work."
        )
    return None


def _removal_error(message: str, error: str) -> RemoveRoadmapEntryResult:
    """Build error result for roadmap removal."""
    return RemoveRoadmapEntryResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message=message,
        line_removed=None,
        error=error,
    )


def _section_removal_error(message: str, error: str) -> RemoveRoadmapSectionResult:
    """Build error result for roadmap section removal."""
    return RemoveRoadmapSectionResult(
        status=OperationStatus.ERROR,
        file_name=MemoryBankFile.ROADMAP,
        message=message,
        section_heading=None,
        lines_removed=None,
        error=error,
    )


def _prepare_roadmap_for_removal(
    root_path: Path,
) -> tuple[Path, str | None, str | None]:
    """Prepare roadmap file for removal operation."""
    memory_bank_root = get_cortex_path(root_path, CortexResourceType.MEMORY_BANK)
    roadmap_path = memory_bank_root / MemoryBankFile.ROADMAP
    current_content, read_error = read_roadmap_file(roadmap_path)
    return roadmap_path, current_content, read_error


def _find_and_validate_removal_line(
    root_path: Path, current_content: str, entry_contains: str
) -> tuple[int | None, RemoveRoadmapEntryResult | None]:
    """Find and validate the line to remove."""
    line_num = find_bullet_line_containing(current_content, entry_contains)
    if line_num is None:
        return None, _removal_error(
            "No matching bullet found",
            "No bullet line containing given text found in roadmap",
        )

    guardrail_error = _validate_plan_status_before_removal(
        root_path, current_content, line_num
    )
    if guardrail_error is not None:
        return None, _removal_error(
            "Refused to remove roadmap entry for non-complete plan", guardrail_error
        )

    return line_num, None


async def _perform_roadmap_removal(
    roadmap_path: Path,
    current_content: str,
    line_num: int,
    project_root: Path | None = None,
) -> RemoveRoadmapEntryResult:
    """Perform the actual roadmap removal and write."""
    updated = remove_line_at(current_content, line_num)
    write_error = await write_roadmap_file(roadmap_path, updated, project_root)
    if write_error:
        return _removal_error("Failed to write roadmap", write_error)

    return RemoveRoadmapEntryResult(
        status=OperationStatus.SUCCESS,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Removed roadmap entry at line {line_num}",
        line_removed=line_num,
        error=None,
    )


async def execute_roadmap_removal(
    root_path: Path, entry_contains: str
) -> RemoveRoadmapEntryResult:
    """Remove first roadmap bullet line containing entry_contains. Returns result."""
    roadmap_path, current_content, read_error = _prepare_roadmap_for_removal(root_path)
    if read_error:
        return _removal_error("Failed to read roadmap", read_error)
    assert current_content is not None

    line_num, find_error = _find_and_validate_removal_line(
        root_path, current_content, entry_contains
    )
    if find_error:
        return find_error
    assert line_num is not None

    return await _perform_roadmap_removal(
        roadmap_path, current_content, line_num, root_path
    )


async def execute_roadmap_section_removal(
    root_path: Path, section_heading_contains: str
) -> RemoveRoadmapSectionResult:
    """Remove a roadmap section by heading text. Returns result."""
    roadmap_path, current_content, read_error = _prepare_roadmap_for_removal(root_path)
    if read_error:
        return _section_removal_error("Failed to read roadmap", read_error)
    assert current_content is not None

    range_result = find_section_range_by_heading(
        current_content, section_heading_contains
    )
    if range_result is None:
        return _section_removal_error(
            "No matching section found",
            f"No ##/### heading containing '{section_heading_contains.strip()}' found",
        )
    start_i, end_i, heading = range_result
    lines_removed = end_i - start_i + 1
    updated = remove_section_range(current_content, start_i, end_i)
    write_error = await write_roadmap_file(roadmap_path, updated, root_path)
    if write_error:
        return _section_removal_error("Failed to write roadmap", write_error)

    return RemoveRoadmapSectionResult(
        status=OperationStatus.SUCCESS,
        file_name=MemoryBankFile.ROADMAP,
        message=f"Removed section '{heading}' ({lines_removed} lines)",
        section_heading=heading,
        lines_removed=lines_removed,
        error=None,
    )
