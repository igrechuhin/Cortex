"""Helper functions for extracting sections from markdown content.

Extracted from file_operations to reduce file size.
"""

import re


def extract_content_sections(
    content_str: str,
    sections: list[str] | None,
) -> tuple[str, str | None]:
    """Extract sections from content if requested.

    Args:
        content_str: Full file content
        sections: List of section headings to extract (can be single item)

    Returns:
        Tuple of (extracted_content, warning_message)
    """
    if sections is not None:
        return extract_sections_from_content(content_str, sections)
    return (content_str, None)


def extract_nested_section(
    lines: list[str], section_parts: list[str]
) -> tuple[str, str | None]:
    """Extract nested section from lines.

    Args:
        lines: All file lines
        section_parts: Split section path (e.g., ["## Parent", "### Child"])

    Returns:
        Tuple of (extracted_content, warning_message)
    """
    parent_section = section_parts[0].strip()
    child_section = section_parts[-1].strip()

    parent_start, parent_level = find_section_heading(lines, parent_section)
    if parent_start is None:
        return (
            "\n".join(lines),
            f"Section '{parent_section}' not found, returning full file",
        )

    parent_end = find_section_end(lines, parent_start, parent_level)
    parent_lines = lines[parent_start:parent_end]
    child_start, child_level = find_section_heading(parent_lines, child_section)

    if child_start is None:
        return (
            "\n".join(lines),
            f"Section '{child_section}' not found within '{parent_section}', returning full file",
        )

    child_end = find_section_end(parent_lines, child_start, child_level)
    section_lines = parent_lines[child_start:child_end]
    return ("\n".join(section_lines), None)


def extract_section_from_content(
    content: str, section_path: str
) -> tuple[str, str | None]:
    """Extract a single section from content by heading path.

    Supports nested headings using "/" separator.
    Example: "## Completed Work/### 2026-02-11"

    Args:
        content: Full file content
        section_path: Section heading or path (e.g., "## Current Focus" or "## Completed Work/### 2026-02-11")

    Returns:
        Tuple of (extracted_content, warning_message)
    """
    lines = content.split("\n")
    section_parts = section_path.split("/")

    if len(section_parts) > 1:
        return extract_nested_section(lines, section_parts)

    section_start, section_level = find_section_heading(lines, section_path.strip())
    if section_start is None:
        return (
            content,
            f"Section '{section_path}' not found, returning full file",
        )

    section_end = find_section_end(lines, section_start, section_level)
    section_lines = lines[section_start:section_end]
    return ("\n".join(section_lines), None)


def extract_sections_from_content(
    content: str, section_headings: list[str]
) -> tuple[str, str | None]:
    """Extract multiple sections from content.

    Args:
        content: Full file content
        section_headings: List of section headings to extract

    Returns:
        Tuple of (extracted_content, warning_message)
    """
    extracted_parts: list[str] = []
    warnings: list[str] = []

    for heading in section_headings:
        section_content, warning = extract_section_from_content(content, heading)
        if warning:
            warnings.append(warning)
        else:
            extracted_parts.append(section_content)

    combined_content = "\n\n---\n\n".join(extracted_parts)
    warning_msg = "; ".join(warnings) if warnings else None

    return (combined_content, warning_msg)


def find_section_heading(
    lines: list[str], section_heading: str
) -> tuple[int | None, int | None]:
    """Find section heading in lines.

    Args:
        lines: List of file lines
        section_heading: Heading to find (e.g., "## Current Focus" or "Current Focus")

    Returns:
        Tuple of (line_index, heading_level) or (None, None) if not found
    """
    # Normalize heading (remove leading # if present, we'll match the full line)
    heading_text = section_heading.strip()
    if heading_text.startswith("#"):
        # Full heading match (e.g., "## Current Focus")
        heading_pattern = re.compile(r"^(#+)\s+(.+)$")
        for i, line in enumerate(lines):
            match = heading_pattern.match(line.strip())
            if match and line.strip() == heading_text:
                level = len(match.group(1))
                return (i, level)
    else:
        # Text-only match (e.g., "Current Focus")
        heading_pattern = re.compile(r"^(#+)\s+(.+)$")
        for i, line in enumerate(lines):
            match = heading_pattern.match(line.strip())
            if match:
                level = len(match.group(1))
                heading_text_from_line = match.group(2).strip()
                if heading_text_from_line.lower() == heading_text.lower():
                    return (i, level)

    return (None, None)


def find_section_end(
    lines: list[str], section_start: int, section_level: int | None
) -> int:
    """Find end of section (next heading of same or higher level).

    Args:
        lines: List of file lines
        section_start: Starting line index
        section_level: Heading level (1-6)

    Returns:
        Ending line index (exclusive)
    """
    if section_level is None:
        return len(lines)

    # Find next heading at same or higher level
    for i in range(section_start + 1, len(lines)):
        heading_match = re.match(r"^(#+)\s+", lines[i].strip())
        if not heading_match:
            continue

        level = len(heading_match.group(1))
        if level <= section_level:
            return i

    return len(lines)
