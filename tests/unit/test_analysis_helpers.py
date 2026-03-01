"""Unit tests for analysis_helpers."""

from cortex.tools.context.analysis_helpers import AnalysisTarget, parse_analysis_target


def test_parse_analysis_target_returns_none_for_none() -> None:
    """parse_analysis_target(None) returns None."""
    assert parse_analysis_target(None) is None


def test_parse_analysis_target_returns_enum_for_valid_values() -> None:
    """parse_analysis_target returns AnalysisTarget for valid strings."""
    assert parse_analysis_target("usage_patterns") is AnalysisTarget.USAGE_PATTERNS
    assert parse_analysis_target("structure") is AnalysisTarget.STRUCTURE
    assert parse_analysis_target("insights") is AnalysisTarget.INSIGHTS


def test_parse_analysis_target_returns_none_for_invalid_value() -> None:
    """parse_analysis_target returns None for invalid string (ValueError branch)."""
    assert parse_analysis_target("invalid") is None
    assert parse_analysis_target("") is None
