"""Helper types and functions for analysis operations."""

from enum import Enum


class AnalysisTarget(str, Enum):
    """Fixed set of analyze() targets. Use instead of raw strings."""

    USAGE_PATTERNS = "usage_patterns"
    STRUCTURE = "structure"
    INSIGHTS = "insights"


def parse_analysis_target(value: str | None) -> AnalysisTarget | None:
    """Parse string to AnalysisTarget. Returns None if invalid or missing."""
    if value is None:
        return None
    try:
        return AnalysisTarget(value)
    except ValueError:
        return None
