"""Helper types and functions for analysis operations."""

from enum import Enum


class AnalysisTarget(str, Enum):
    """Fixed set of analyze() targets. Use instead of raw strings."""

    USAGE_PATTERNS = "usage_patterns"
    STRUCTURE = "structure"
    INSIGHTS = "insights"


def normalize_analysis_target(value: str | None) -> str | None:
    """Normalize target aliases used by prompts/session config."""
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_")
    alias_map = {
        "usage_pattern": AnalysisTarget.USAGE_PATTERNS.value,
        "usage_patterns": AnalysisTarget.USAGE_PATTERNS.value,
    }
    return alias_map.get(normalized, normalized)


def parse_analysis_target(value: str | None) -> AnalysisTarget | None:
    """Parse string to AnalysisTarget. Returns None if invalid or missing."""
    normalized = normalize_analysis_target(value)
    if normalized is None:
        return None
    try:
        return AnalysisTarget(normalized)
    except ValueError:
        return None
