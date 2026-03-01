"""
Roadmap content manipulation (insert, find, remove).

Extracted from roadmap_operations for maintainability.
"""

import re

from cortex.tools.plans.entries_parsing import (
    find_insertion_line,
    parse_roadmap_sections,
)


def _extract_plan_path_from_bullet(line: str) -> str | None:
    """Extract a plan path from a roadmap bullet, if present.

    Expected patterns (examples):
    - "Plan: .cortex/plans/phase-58-...md."
    - "Plan: plans/phase-58-...md"

    Returns:
        The raw plan path string (without surrounding punctuation) or None
        if no plan reference is found.
    """
    match = re.search(r"Plan:\s*([^\s]+)", line)
    if not match:
        return None
    raw = match.group(1).strip()
    return raw.rstrip(".,")


def insert_roadmap_entry(
    content: str,
    section_id: str,
    entry_text: str,
    position: str = "last",
) -> tuple[str, int | None]:
    """Insert a roadmap entry into the specified section.

    Deduplicates entries that reference the same plan path to avoid
    accumulating duplicate blockers for the same plan.
    """
    sections = parse_roadmap_sections(content)

    if section_id not in sections:
        return (content, None)

    section = sections[section_id]
    lines = content.split("\n")

    if not entry_text.startswith("- "):
        entry_text = f"- {entry_text}"

    plan_path = _extract_plan_path_from_bullet(entry_text)
    if plan_path:
        for i in range(section.start_line + 1, section.end_line + 1):
            if i < len(lines):
                existing_plan_path = _extract_plan_path_from_bullet(lines[i])
                if existing_plan_path and plan_path == existing_plan_path:
                    return (content, None)

    section_content = "\n".join(lines[section.start_line : section.end_line + 1])
    if entry_text.strip() in section_content:
        return (content, None)

    insert_line = find_insertion_line(lines, section, position)
    lines.insert(insert_line, entry_text)
    updated_content = "\n".join(lines)

    return (updated_content, insert_line + 1)


ADD_ENTRY_COMPLETED_MESSAGE = (
    "Roadmap records future/upcoming work only. "
    "Do not add COMPLETED entries here; record completed work in activeContext.md."
)


def entry_text_looks_completed(entry_text: str) -> bool:
    """Return True if entry text appears to be a completed-work entry (not allowed in roadmap)."""
    normalized = entry_text.strip()
    if not normalized:
        return False
    if not normalized.startswith("- "):
        normalized = "- " + normalized
    upper = normalized.upper()
    return " - COMPLETED" in upper or " - COMPLETE" in upper or " - DONE" in upper


def validate_section_id(section: str) -> tuple[str | None, str | None]:
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


def find_bullet_line_containing(content: str, substring: str) -> int | None:
    """Return 1-based line number of first bullet line containing substring, or None."""
    needle = substring.strip()
    if not needle:
        return None
    for i, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        if stripped.startswith("- ") and needle in line:
            return i
    return None


def remove_line_at(content: str, one_based_line: int) -> str:
    """Remove the line at the given 1-based index; return new content."""
    lines = content.split("\n")
    idx = one_based_line - 1
    if idx < 0 or idx >= len(lines):
        return content
    new_lines = lines[:idx] + lines[idx + 1 :]
    return "\n".join(new_lines)


def _find_section_end_line(
    lines: list[str],
    header_pattern: re.Pattern[str],
    start_i: int,
    start_level: int,
) -> int:
    """Return 0-based index of last line of section (inclusive)."""
    end_i = start_i
    for i in range(start_i + 1, len(lines)):
        match = header_pattern.match(lines[i])
        if match and len(match.group(1)) <= start_level:
            return i - 1
        end_i = i
    return end_i


def find_section_range_by_heading(
    content: str, section_heading_contains: str
) -> tuple[int, int, str] | None:
    """Find a section by heading text and return (start_0based, end_0based_inclusive, heading).

    Matches ## or ### lines whose rest contains section_heading_contains (case-sensitive).
    Section ends at the line before the next ## or ### of same or higher level, or end of file.
    Returns None if no matching heading found.
    """
    needle = section_heading_contains.strip()
    if not needle:
        return None
    lines = content.split("\n")
    header_pattern = re.compile(r"^(#{2,3})\s+(.+)$")
    for i, line in enumerate(lines):
        match = header_pattern.match(line)
        if not match or needle not in match.group(2).strip():
            continue
        start_heading = match.group(2).strip()
        start_level = len(match.group(1))
        end_i = _find_section_end_line(lines, header_pattern, i, start_level)
        return (i, end_i, start_heading)
    return None


def remove_section_range(content: str, start_0based: int, end_0based: int) -> str:
    """Remove lines [start_0based, end_0based] inclusive; return new content."""
    lines = content.split("\n")
    if start_0based < 0 or end_0based >= len(lines) or start_0based > end_0based:
        return content
    new_lines = lines[:start_0based] + lines[end_0based + 1 :]
    return "\n".join(new_lines)


def extract_plan_path_from_bullet(line: str) -> str | None:
    """Extract a plan path from a roadmap bullet (public for removal module)."""
    return _extract_plan_path_from_bullet(line)
