"""
Roadmap Operations Tools

This module contains MCP tools and helpers for roadmap manipulation,
including adding entries deterministically to avoid truncation issues.
"""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import MCP_TOOL_TIMEOUT_MEDIUM
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.exceptions import FileConflictError, FileLockTimeoutError
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.models import AddRoadmapEntryResult, RemoveRoadmapEntryResult
from cortex.tools.roadmap_corruption import fix_roadmap_content_if_needed


class RoadmapSection(BaseModel):
    """Represents a section in the roadmap."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field(description="Section name (e.g., 'blockers', 'active_work')")
    header: str = Field(description="Markdown header as it appears in file")
    start_line: int = Field(ge=0, description="Line number where section starts")
    end_line: int = Field(ge=0, description="Line number where section ends")


def _get_header_to_section_map() -> dict[str, str]:
    """Get mapping of header text to section identifiers."""
    return {
        "Blockers (ASAP Priority)": "blockers",
        "Active Work (in progress)": "active_work",
        "Future Enhancements": "future",
        "Pending plans (from .cortex/plans)": "pending",
        "Active Work": "active_work",
    }


def _parse_roadmap_sections(content: str) -> dict[str, RoadmapSection]:
    """Parse roadmap to identify section boundaries."""
    sections: dict[str, RoadmapSection] = {}
    lines = content.split("\n")
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$")
    header_to_section = _get_header_to_section_map()

    current_section_name: str | None = None
    current_section_start = 0

    for i, line in enumerate(lines):
        match = header_pattern.match(line)
        if not match:
            continue
        header_text = match.group(2)
        section_id = header_to_section.get(header_text)
        if current_section_name is not None:
            sections[current_section_name] = RoadmapSection(
                name=current_section_name,
                header=lines[current_section_start],
                start_line=current_section_start,
                end_line=i - 1,
            )
        if section_id:
            current_section_name = section_id
            current_section_start = i

    if current_section_name is not None:
        sections[current_section_name] = RoadmapSection(
            name=current_section_name,
            header=lines[current_section_start],
            start_line=current_section_start,
            end_line=len(lines) - 1,
        )

    return sections


def _get_section_bullet_lines(
    lines: list[str], section: RoadmapSection
) -> tuple[int, int]:
    """Get first and last bullet line numbers in a section."""
    first_bullet = -1
    last_bullet = -1

    for i in range(section.start_line + 1, section.end_line + 1):
        if lines[i].startswith("- "):
            if first_bullet == -1:
                first_bullet = i
            last_bullet = i

    return (first_bullet, last_bullet)


def _find_insertion_line(
    lines: list[str],
    section: RoadmapSection,
    position: str,
) -> int:
    """Determine insertion line number for a new entry."""
    first_bullet, last_bullet = _get_section_bullet_lines(lines, section)

    if position == "first":
        if first_bullet == -1:
            return section.start_line + 1
        return first_bullet

    if last_bullet == -1:
        return section.start_line + 1
    return last_bullet + 1


def _insert_roadmap_entry(
    content: str,
    section_id: str,
    entry_text: str,
    position: str = "last",
) -> tuple[str, int | None]:
    """Insert a roadmap entry into the specified section."""
    sections = _parse_roadmap_sections(content)

    if section_id not in sections:
        return (content, None)

    section = sections[section_id]
    lines = content.split("\n")

    if not entry_text.startswith("- "):
        entry_text = f"- {entry_text}"

    insert_line = _find_insertion_line(lines, section, position)
    lines.insert(insert_line, entry_text)
    updated_content = "\n".join(lines)

    return (updated_content, insert_line + 1)


_ADD_ENTRY_COMPLETED_MESSAGE = (
    "Roadmap records future/upcoming work only. "
    "Do not add COMPLETED entries here; record completed work in activeContext.md."
)


def _entry_text_looks_completed(entry_text: str) -> bool:
    """Return True if entry text appears to be a completed-work entry (not allowed in roadmap)."""
    normalized = entry_text.strip()
    if not normalized:
        return False
    if not normalized.startswith("- "):
        normalized = "- " + normalized
    upper = normalized.upper()
    return " - COMPLETED" in upper or " - COMPLETE" in upper or " - DONE" in upper


def _validate_section_id(section: str) -> tuple[str | None, str | None]:
    """Validate section identifier. Returns (section_id, error_message)."""
    section_map = {
        "blockers": "blockers",
        "active_work": "active_work",
        "future": "future",
        "pending": "pending",
    }

    section_id = section_map.get(section.lower())
    if not section_id:
        error_msg = f"Section must be one of: {', '.join(section_map.keys())}"
        return (None, error_msg)

    return (section_id, None)


def _read_roadmap_file(roadmap_path: Path) -> tuple[str | None, str | None]:
    """Read roadmap file. Returns (content, error_message)."""
    if not roadmap_path.exists():
        return (None, f"roadmap.md not found at {roadmap_path}")

    try:
        content = roadmap_path.read_text(encoding="utf-8")
        return (content, None)
    except Exception as e:
        return (None, str(e))


def _write_roadmap_file(roadmap_path: Path, content: str) -> str | None:
    """Write updated roadmap. Returns error_message if failed."""
    try:
        fixed_content = fix_roadmap_content_if_needed(content)
        _ = roadmap_path.write_text(fixed_content, encoding="utf-8")
        return None
    except (FileConflictError, FileLockTimeoutError) as e:
        return str(e)
    except Exception as e:
        return str(e)


def _find_bullet_line_containing(content: str, substring: str) -> int | None:
    """Return 1-based line number of first bullet line containing substring, or None."""
    needle = substring.strip()
    if not needle:
        return None
    for i, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        if stripped.startswith("- ") and needle in line:
            return i
    return None


def _remove_line_at(content: str, one_based_line: int) -> str:
    """Remove the line at the given 1-based index; return new content."""
    lines = content.split("\n")
    idx = one_based_line - 1
    if idx < 0 or idx >= len(lines):
        return content
    new_lines = lines[:idx] + lines[idx + 1 :]
    return "\n".join(new_lines)


def _removal_error(message: str, error: str) -> RemoveRoadmapEntryResult:
    """Build error result for roadmap removal."""
    return RemoveRoadmapEntryResult(
        status="error",
        file_name="roadmap.md",
        message=message,
        line_removed=None,
        error=error,
    )


def _execute_roadmap_removal(
    root_path: Path, entry_contains: str
) -> RemoveRoadmapEntryResult:
    """Remove first roadmap bullet line containing entry_contains. Returns result."""
    roadmap_path = root_path / ".cortex" / "memory-bank" / "roadmap.md"
    current_content, read_error = _read_roadmap_file(roadmap_path)
    if read_error:
        return _removal_error("Failed to read roadmap", read_error)
    assert current_content is not None
    line_num = _find_bullet_line_containing(current_content, entry_contains)
    if line_num is None:
        return _removal_error(
            "No matching bullet found",
            "No bullet line containing given text found in roadmap",
        )
    updated = _remove_line_at(current_content, line_num)
    write_error = _write_roadmap_file(roadmap_path, updated)
    if write_error:
        return _removal_error("Failed to write roadmap", write_error)
    return RemoveRoadmapEntryResult(
        status="success",
        file_name="roadmap.md",
        message=f"Removed roadmap entry at line {line_num}",
        line_removed=line_num,
        error=None,
    )


def _handle_read_error(
    section_id: str | None, read_error: str
) -> AddRoadmapEntryResult:
    """Handle read errors. Returns error result."""
    return AddRoadmapEntryResult(
        status="error",
        file_name="roadmap.md",
        message="Failed to read roadmap",
        line_inserted=None,
        section=None,
        error=read_error,
    )


def _handle_insert_failure(
    section_id: str,
) -> AddRoadmapEntryResult:
    """Handle insert failures. Returns error result."""
    return AddRoadmapEntryResult(
        status="error",
        file_name="roadmap.md",
        message="Failed to insert entry",
        line_inserted=None,
        section=section_id,
        error=f"Could not find section '{section_id}' in roadmap",
    )


def _handle_write_error(section_id: str, write_error: str) -> AddRoadmapEntryResult:
    """Handle write errors. Returns error result."""
    return AddRoadmapEntryResult(
        status="error",
        file_name="roadmap.md",
        message="Conflict or lock timeout",
        line_inserted=None,
        section=section_id,
        error=write_error,
    )


def _make_insert_success_result(
    section_id: str, line_inserted: int
) -> AddRoadmapEntryResult:
    """Build success result for roadmap insertion."""
    return AddRoadmapEntryResult(
        status="success",
        file_name="roadmap.md",
        message=f"Entry added to '{section_id}' section at line {line_inserted}",
        line_inserted=line_inserted,
        section=section_id,
        error=None,
    )


def _handle_section_validation_error(
    section: str, section_error: str
) -> AddRoadmapEntryResult:
    """Handle section validation errors."""
    return AddRoadmapEntryResult(
        status="error",
        file_name="roadmap.md",
        message=f"Unknown section: {section}",
        line_inserted=None,
        section=None,
        error=section_error,
    )


def _handle_completed_entry_rejected() -> AddRoadmapEntryResult:
    """Return error result when entry looks like completed work."""
    return AddRoadmapEntryResult(
        status="error",
        file_name="roadmap.md",
        message="Completed entries not allowed in roadmap",
        line_inserted=None,
        section=None,
        error=_ADD_ENTRY_COMPLETED_MESSAGE,
    )


def _execute_roadmap_insertion(
    root_path: Path,
    section: str,
    entry_text: str,
    position: str,
) -> AddRoadmapEntryResult:
    """Execute insertion. Returns AddRoadmapEntryResult."""
    if _entry_text_looks_completed(entry_text):
        return _handle_completed_entry_rejected()

    section_id, section_error = _validate_section_id(section)
    if section_error:
        return _handle_section_validation_error(section, section_error)

    roadmap_path = root_path / ".cortex" / "memory-bank" / "roadmap.md"
    current_content, read_error = _read_roadmap_file(roadmap_path)
    if read_error:
        return _handle_read_error(section_id, read_error)

    assert current_content is not None
    assert section_id is not None

    updated_content, line_inserted = _insert_roadmap_entry(
        current_content, section_id, entry_text, position
    )

    if line_inserted is None:
        return _handle_insert_failure(section_id)

    write_error = _write_roadmap_file(roadmap_path, updated_content)
    if write_error:
        return _handle_write_error(section_id, write_error)

    return _make_insert_success_result(section_id, line_inserted)


async def _add_roadmap_entry_impl(
    section: str,
    entry_text: str,
    position: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of add_roadmap_entry logic."""
    await log_client(ctx, "info", "add_roadmap_entry: starting", logger_name=__name__)

    root = await resolve_project_root_async(None, ctx)
    result = _execute_roadmap_insertion(root, section, entry_text, position)

    await log_client(
        ctx,
        "info" if result.status == "success" else "warning",
        f"add_roadmap_entry: {result.status}",
        logger_name=__name__,
    )

    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Add Roadmap Entry"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def add_roadmap_entry(
    section: str,
    entry_text: str,
    position: str = "last",
    change_description: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Add entry to roadmap section, avoiding truncation from full updates.

    USE WHEN: Create-plan Step 6 needs to register a new plan entry.

    RETURNS: JSON with operation status, line inserted, error if any.

    Sections supported: 'blockers', 'active_work', 'future', 'pending'.
    """
    try:
        return await _add_roadmap_entry_impl(section, entry_text, position, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"add_roadmap_entry: {e}",
            logger_name=__name__,
        )
        error_result = AddRoadmapEntryResult(
            status="error",
            file_name="roadmap.md",
            message="Unexpected error",
            line_inserted=None,
            section=None,
            error=str(e),
        )
        return error_result.model_dump_json()


async def _remove_roadmap_entry_impl(
    entry_contains: str,
    ctx: MCPContext | None,
) -> str:
    """Implementation of remove_roadmap_entry logic."""
    await log_client(
        ctx, "info", "remove_roadmap_entry: starting", logger_name=__name__
    )
    root = await resolve_project_root_async(None, ctx)
    result = _execute_roadmap_removal(root, entry_contains)
    await log_client(
        ctx,
        "info" if result.status == "success" else "warning",
        f"remove_roadmap_entry: {result.status}",
        logger_name=__name__,
    )
    return result.model_dump_json()


@mcp.tool(annotations=safe_write_annotations("Remove Roadmap Entry"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_MEDIUM)
async def remove_roadmap_entry(
    entry_contains: str,
    ctx: MCPContext | None = None,
) -> str:
    """Remove a single roadmap entry (bullet) that contains the given text.

    USE WHEN: Implement Step 5 needs to remove the completed step from the
    roadmap without building or writing full roadmap content (safe update).

    RETURNS: JSON with status, line_removed (1-based), or error.
    """
    try:
        return await _remove_roadmap_entry_impl(entry_contains, ctx)
    except Exception as e:
        await log_client(
            ctx,
            "error",
            f"remove_roadmap_entry: {e}",
            logger_name=__name__,
        )
        error_result = RemoveRoadmapEntryResult(
            status="error",
            file_name="roadmap.md",
            message="Unexpected error",
            line_removed=None,
            error=str(e),
        )
        return error_result.model_dump_json()
