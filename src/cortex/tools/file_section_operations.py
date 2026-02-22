"""Section extraction for markdown content.

Used by file metadata (section summaries) and write flow. Kept in a separate
module to keep file_operations and file_metadata_operations under size limits.
"""

import hashlib
import re

from cortex.core.models import SectionMetadata
from cortex.core.token_counter import TokenCounter


def _close_section_and_add(
    current_section: dict[str, str | int],
    line_end: int,
    lines: list[str],
    sections: list[SectionMetadata],
    token_counter: TokenCounter,
) -> None:
    """Close a section and add it to sections list.

    Args:
        current_section: Section dictionary with heading, level, line_start
        line_end: Ending line number (exclusive)
        lines: All file lines
        sections: List to append section to
        token_counter: Token counter instance
    """
    line_start = int(current_section["line_start"])
    section_lines = lines[line_start - 1 : line_end]
    section_content = "\n".join(section_lines)
    section_tokens = token_counter.count_tokens(section_content)
    section_hash = (
        "sha256:" + hashlib.sha256(section_content.encode("utf-8")).hexdigest()
    )

    sections.append(
        SectionMetadata(
            heading=str(current_section["heading"]),
            level=int(current_section["level"]),
            line_start=line_start,
            line_end=line_end,
            content_hash=section_hash,
            token_count=section_tokens,
        )
    )


def extract_sections(
    content: str, token_counter: TokenCounter | None = None
) -> list[SectionMetadata]:
    """Extract sections from markdown content with proper boundaries and token counts.

    Extracts all markdown headings (# through ######) and calculates:
    - Proper line_end by finding next heading of same or higher level
    - Token count for each section
    - Content hash for each section

    Args:
        content: Markdown file content
        token_counter: Optional TokenCounter instance. If None, creates one.

    Returns:
        List of SectionMetadata with proper boundaries and token counts
    """
    lines = content.split("\n")
    sections: list[SectionMetadata] = []
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    if token_counter is None:
        token_counter = TokenCounter()
    current_section: dict[str, str | int] | None = None

    for i, line in enumerate(lines, start=1):
        match = heading_pattern.match(line.strip())

        if match:
            if current_section is not None:
                _close_section_and_add(
                    current_section, i - 1, lines, sections, token_counter
                )

            level = len(match.group(1))
            current_section = {
                "heading": line.strip(),
                "level": level,
                "line_start": i,
            }

    if current_section is not None:
        _close_section_and_add(
            current_section, len(lines), lines, sections, token_counter
        )

    return sections
