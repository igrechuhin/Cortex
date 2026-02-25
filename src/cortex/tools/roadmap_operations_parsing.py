"""
Roadmap section parsing.

Extracted from roadmap_operations for maintainability.
"""

import re

from pydantic import BaseModel, ConfigDict, Field


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


def _process_section_header(
    lines: list[str],
    i: int,
    header_text: str,
    header_to_section: dict[str, str],
    current_section_name: str | None,
    current_section_start: int,
    sections: dict[str, RoadmapSection],
) -> tuple[str | None, int]:
    """Process a section header and update sections dict.

    Returns: (new_current_section_name, new_current_section_start)
    """
    section_id = header_to_section.get(header_text)
    if current_section_name is not None:
        sections[current_section_name] = RoadmapSection(
            name=current_section_name,
            header=lines[current_section_start],
            start_line=current_section_start,
            end_line=i - 1,
        )
    if section_id:
        return (section_id, i)
    return (None, current_section_start)


def _finalize_last_section(
    sections: dict[str, RoadmapSection],
    current_section_name: str | None,
    current_section_start: int,
    lines: list[str],
) -> None:
    """Finalize the last section if one is still open."""
    if current_section_name is not None:
        sections[current_section_name] = RoadmapSection(
            name=current_section_name,
            header=lines[current_section_start],
            start_line=current_section_start,
            end_line=len(lines) - 1,
        )


def parse_roadmap_sections(content: str) -> dict[str, RoadmapSection]:
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
        current_section_name, current_section_start = _process_section_header(
            lines,
            i,
            header_text,
            header_to_section,
            current_section_name,
            current_section_start,
            sections,
        )

    _finalize_last_section(sections, current_section_name, current_section_start, lines)
    return sections


def get_section_bullet_lines(
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


def find_insertion_line(
    lines: list[str],
    section: RoadmapSection,
    position: str,
) -> int:
    """Determine insertion line number for a new entry."""
    first_bullet, last_bullet = get_section_bullet_lines(lines, section)

    if position == "first":
        if first_bullet == -1:
            return section.start_line + 1
        return first_bullet

    if last_bullet == -1:
        return section.start_line + 1
    return last_bullet + 1
