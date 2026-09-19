"""
Section relevance scoring for the summarization engine.

Defines `SectionScorer` as an injectable seam so `SummarizationEngine` does
not hardcode a single relevance heuristic (Cortex mandates constructor
injection for dependencies). `HeuristicSectionScorer` is the default
implementation and preserves the pre-existing keyword/length heuristic
byte-for-byte.
"""

from typing import Protocol


class SectionScorer(Protocol):
    """Scores a section's importance for summarization budget selection."""

    identity: str
    """Stable string naming this scorer and any config that changes its
    output. Used to key the summary cache so swapping scorers (or
    reconfiguring one) can't serve a stale hit from a different scorer."""

    def score(self, section_name: str, content: str) -> float:
        """Return an importance score in [0.0, 1.0]; higher sections are kept first."""
        ...


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


class HeuristicSectionScorer:
    """Default `SectionScorer`: the pre-existing keyword/length heuristic."""

    identity: str = "heuristic-v1"

    def score(self, section_name: str, content: str) -> float:
        """Delegate to the existing keyword/length heuristic, unchanged."""
        return score_section_importance(section_name, content)
