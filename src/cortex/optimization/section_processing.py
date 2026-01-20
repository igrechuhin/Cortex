"""
Section processing utilities for optimization strategies.

This module contains utilities for processing and extracting sections
from files for section-level optimization.
"""

from collections.abc import Callable

from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import SectionScoreModel


def filter_and_sort_sections(
    section_scores: list[SectionScoreModel],
) -> list[SectionScoreModel]:
    """Filter and sort sections by score (highest first).

    Args:
        section_scores: List of SectionScoreModel instances

    Returns:
        Sorted list of valid sections (score >= 0.5)
    """
    valid_sections = [
        section_data
        for section_data in section_scores
        if section_data.section and section_data.score >= 0.5
    ]
    return sorted(
        valid_sections,
        key=lambda x: x.score,
        reverse=True,
    )


def calculate_section_tokens(
    sorted_sections: list[SectionScoreModel],
    content: str,
    extract_section_content: Callable[[str, str], str],
    token_counter: TokenCounter,
) -> list[tuple[str, int]]:
    """Pre-calculate token counts for all sections.

    Args:
        sorted_sections: Sorted list of SectionScoreModel instances
        content: Full file content
        extract_section_content: Function to extract section content
        token_counter: Token counter instance

    Returns:
        List of (section_name, token_count) tuples
    """
    return [
        (
            section_data.section or "",
            token_counter.count_tokens(
                extract_section_content(content, section_data.section or "")
            ),
        )
        for section_data in sorted_sections
    ]


def process_sections_for_file(
    section_scores: list[SectionScoreModel],
    content: str,
    total_tokens: int,
    token_budget: int,
    extract_section_content: Callable[[str, str], str],
    token_counter: TokenCounter,
) -> tuple[list[str], int]:
    """Process sections for a file and add them within budget.

    Args:
        section_scores: List of SectionScoreModel instances
        content: Full file content
        total_tokens: Current token count
        token_budget: Token budget
        extract_section_content: Function to extract section content
        token_counter: Token counter instance

    Returns:
        Tuple of (selected section names, updated token count)
    """
    sorted_sections = filter_and_sort_sections(section_scores)
    section_token_pairs = calculate_section_tokens(
        sorted_sections, content, extract_section_content, token_counter
    )

    # Accumulate sections that fit within budget
    file_sections: list[str] = []
    current_tokens = total_tokens
    for section_name, section_tokens in section_token_pairs:
        if current_tokens + section_tokens <= token_budget:
            file_sections.append(section_name)
            current_tokens += section_tokens
        else:
            break

    return file_sections, current_tokens


def find_section_bounds(
    lines: list[str], section_name: str
) -> tuple[int | None, int | None]:
    """Find start and end indices for a section.

    Args:
        lines: List of content lines
        section_name: Section name to find

    Returns:
        Tuple of (start_index, end_index), both may be None
    """
    section_start_idx: int | None = None

    for i, line in enumerate(lines):
        if not line.startswith("#"):
            continue

        # Check if this is the target section
        if section_name in line:
            section_start_idx = i
        elif section_start_idx is not None:
            # Reached next section, stop
            return (section_start_idx, i)

    return (section_start_idx, None)


def extract_section_content(content: str, section_name: str) -> str:
    """
    Extract content of a specific section.

    Args:
        content: Full file content
        section_name: Section name to extract

    Returns:
        Section content
    """
    lines = content.split("\n")
    section_start_idx, section_end_idx = find_section_bounds(lines, section_name)

    if section_start_idx is None:
        return ""

    if section_end_idx is None:
        section_end_idx = len(lines)

    return "\n".join(lines[section_start_idx:section_end_idx])
