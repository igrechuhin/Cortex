"""Tests for gap_analyzer."""

from cortex.script_analysis.gap_analyzer import analyze_gap
from cortex.script_analysis.models import UseCaseExtraction


class TestAnalyzeGap:
    """Tests for analyze_gap."""

    def test_returns_gap_true_when_no_overlap(self) -> None:
        """When no tool/script name overlaps, is_gap is True."""
        use_case = UseCaseExtraction(
            use_case_label="format code",
            keywords=["format", "python", "black"],
        )
        result = analyze_gap(
            use_case,
            known_tool_names=["manage_file", "load_context"],
            known_script_names=["run_tests", "check_spelling"],
            overlap_threshold=0.3,
        )
        assert result.is_gap is True
        assert result.existing_tool_names == []
        assert result.existing_script_names == []
        assert "No existing" in result.gap_reason

    def test_returns_gap_false_when_tool_name_overlaps(self) -> None:
        """When a tool name overlaps (e.g. check_formatting), is_gap is False."""
        use_case = UseCaseExtraction(
            use_case_label="format code",
            keywords=["format", "check"],
        )
        result = analyze_gap(
            use_case,
            known_tool_names=["check_formatting", "fix_formatting"],
            known_script_names=[],
            overlap_threshold=0.3,
        )
        assert result.is_gap is False
        assert len(result.existing_tool_names) >= 1
        assert (
            "check_formatting" in result.existing_tool_names
            or "fix_formatting" in result.existing_tool_names
        )
        assert "Overlapping" in result.gap_reason

    def test_returns_gap_false_when_script_name_overlaps(self) -> None:
        """When a script name overlaps (e.g. check_formatting.py), is_gap is False."""
        use_case = UseCaseExtraction(
            use_case_label="format code",
            keywords=["format"],
        )
        result = analyze_gap(
            use_case,
            known_tool_names=[],
            known_script_names=["check_formatting", "fix_formatting"],
            overlap_threshold=0.3,
        )
        assert result.is_gap is False
        assert len(result.existing_script_names) >= 1

    def test_higher_threshold_reduces_overlap(self) -> None:
        """Higher overlap_threshold may yield no overlap (is_gap True)."""
        use_case = UseCaseExtraction(
            use_case_label="format code",
            keywords=["format"],
        )
        result_high = analyze_gap(
            use_case,
            known_tool_names=["check_formatting"],
            known_script_names=[],
            overlap_threshold=0.99,
        )
        result_low = analyze_gap(
            use_case,
            known_tool_names=["check_formatting"],
            known_script_names=[],
            overlap_threshold=0.1,
        )
        assert result_high.is_gap is True or result_low.is_gap is False
