"""
Section-level strategy implementation helpers.

This module contains pure helpers for section filtering, token calculation,
and section content extraction used by optimization strategies.
"""

from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import SectionScoreModel


def find_section_bounds(
    lines: list[str], section_name: str
) -> tuple[int | None, int | None]:
    """Find start and end line indices for a section.

    Args:
        lines: List of content lines
        section_name: Section name to find (e.g. heading text)

    Returns:
        Tuple of (start_index, end_index); either may be None if not found
    """
    section_start_idx: int | None = None

    for i, line in enumerate(lines):
        if not line.startswith("#"):
            continue

        if section_name in line:
            section_start_idx = i
        elif section_start_idx is not None:
            return (section_start_idx, i)

    return (section_start_idx, None)


def extract_section_content(content: str, section_name: str) -> str:
    """Extract content of a specific section from full file content.

    Args:
        content: Full file content
        section_name: Section name to extract (e.g. heading text)

    Returns:
        Section content as string, or empty string if section not found
    """
    lines = content.split("\n")
    section_start_idx, section_end_idx = find_section_bounds(lines, section_name)

    if section_start_idx is None:
        return ""

    if section_end_idx is None:
        section_end_idx = len(lines)

    return "\n".join(lines[section_start_idx:section_end_idx])


def filter_and_sort_sections(
    section_scores: list[SectionScoreModel],
) -> list[SectionScoreModel]:
    """Filter sections by score threshold and sort by score descending.

    Args:
        section_scores: List of section scores

    Returns:
        Sorted list of sections with score >= 0.5 and non-empty section name
    """
    valid_sections = [
        section_data
        for section_data in section_scores
        if section_data.section is not None
        and section_data.section
        and section_data.score >= 0.5
    ]
    return sorted(valid_sections, key=lambda x: x.score, reverse=True)


def calculate_section_tokens(
    sorted_sections: list[SectionScoreModel],
    content: str,
    token_counter: TokenCounter,
) -> list[tuple[str, int]]:
    """Pre-calculate token counts for sections.

    Args:
        sorted_sections: Sorted list of section score models
        content: Full file content
        token_counter: Token counter instance

    Returns:
        List of (section_name, token_count) tuples
    """
    pairs: list[tuple[str, int]] = []
    for section_data in sorted_sections:
        section_name = section_data.section
        if section_name is None:
            continue
        section_content = extract_section_content(content, section_name)
        section_tokens = token_counter.count_tokens(section_content)
        pairs.append((section_name, section_tokens))
    return pairs


def process_sections_for_file(
    section_scores: list[SectionScoreModel],
    content: str,
    total_tokens: int,
    token_budget: int,
    token_counter: TokenCounter,
) -> tuple[list[str], int]:
    """Select sections for a file that fit within token budget.

    Args:
        section_scores: List of section scores
        content: Full file content
        total_tokens: Current token count
        token_budget: Token budget
        token_counter: Token counter instance

    Returns:
        Tuple of (selected section names, updated total_tokens)
    """
    sorted_sections = filter_and_sort_sections(section_scores)
    section_token_pairs = calculate_section_tokens(
        sorted_sections, content, token_counter
    )

    file_sections: list[str] = []
    current_tokens = total_tokens
    for section_name, section_tokens in section_token_pairs:
        if current_tokens + section_tokens <= token_budget:
            file_sections.append(section_name)
            current_tokens += section_tokens
        else:
            break

    return file_sections, current_tokens
