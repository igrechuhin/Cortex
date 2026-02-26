"""
Section parsing, scoring, and selection for summarization engine.

Extracted from summarization_engine for file size compliance.
"""

import re

from cortex.core.token_counter import TokenCounter
from cortex.optimization.models import ScoredSectionModel


def parse_sections(content: str) -> dict[str, str]:
    """
    Parse markdown sections from content.

    Args:
        content: Markdown content

    Returns:
        Dict mapping section names to content
    """
    sections: dict[str, str] = {}
    current_section = "preamble"
    current_content: list[str] = []

    lines = content.split("\n")

    for line in lines:
        if line.startswith("#"):
            # Save previous section
            if current_content:
                sections[current_section] = "\n".join(current_content)

            # Extract heading text
            heading_match = re.match(r"^#+\s+(.+)$", line)
            if heading_match:
                current_section = heading_match.group(1).strip()
                current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_content:
        sections[current_section] = "\n".join(current_content)

    return sections


def score_section_importance(section_name: str, content: str) -> float:
    """
    Score section importance.

    Args:
        section_name: Section name
        content: Section content

    Returns:
        Importance score (0.0 - 1.0)
    """
    score = 0.5  # Base score
    section_lower = section_name.lower()

    score += _calculate_keyword_bonus(section_lower)
    score += _calculate_length_bonus(len(content))

    return max(0.0, min(1.0, score))


def _calculate_keyword_bonus(section_lower: str) -> float:
    """Calculate bonus/penalty based on section name keywords."""
    important_keywords = [
        "goal",
        "objective",
        "requirement",
        "overview",
        "summary",
        "introduction",
        "problem",
        "solution",
        "status",
        "progress",
    ]

    for keyword in important_keywords:
        if keyword in section_lower:
            return 0.3

    low_value_keywords = [
        "example",
        "reference",
        "appendix",
        "note",
        "detail",
        "history",
    ]

    for keyword in low_value_keywords:
        if keyword in section_lower:
            return -0.2

    return 0.0


def _calculate_length_bonus(content_length: int) -> float:
    """Calculate bonus/penalty based on content length."""
    if content_length < 500:
        return 0.1
    elif content_length > 2000:
        return -0.1
    return 0.0


def handle_no_sections(content: str) -> str:
    """Handle case when no sections are found in content."""
    words = content.split()
    truncated_words = words[: int(len(words) * 0.5)]
    return " ".join(truncated_words) + "\n\n[Content truncated...]"


def score_all_sections(
    sections: dict[str, str],
    token_counter: TokenCounter,
) -> list[ScoredSectionModel]:
    """Score all sections by importance."""
    section_scores: list[ScoredSectionModel] = []

    for section_name, section_content in sections.items():
        score = score_section_importance(section_name, section_content)
        tokens = token_counter.count_tokens(section_content)

        section_scores.append(
            ScoredSectionModel(
                name=section_name,
                content=section_content,
                score=score,
                tokens=tokens,
            )
        )

    return section_scores


def select_sections_by_budget(
    section_scores: list[ScoredSectionModel], target_tokens: int
) -> list[ScoredSectionModel]:
    """Select sections within token budget."""
    selected_sections: list[ScoredSectionModel] = []
    total_tokens = 0

    for section in section_scores:
        if total_tokens + section.tokens <= target_tokens:
            selected_sections.append(section)
            total_tokens += section.tokens
        elif not selected_sections:
            # Include at least one section
            selected_sections.append(section)
            break

    return selected_sections


def reconstruct_content(
    selected_sections: list[ScoredSectionModel], total_sections: int
) -> str:
    """Reconstruct content from selected sections."""
    result_parts: list[str] = []

    for section in selected_sections:
        result_parts.append(f"## {section.name}")
        result_parts.append(section.content)
        result_parts.append("")

    if len(selected_sections) < total_sections:
        result_parts.append(
            f"[{total_sections - len(selected_sections)} sections omitted]"
        )

    return "\n".join(result_parts)
