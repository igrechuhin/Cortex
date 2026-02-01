"""Tests for script_analyzer."""

from cortex.script_analysis.script_analyzer import analyze_script
from cortex.script_detection.models import ScriptCaptureRecord


def _record(
    script_id: str = "sid-1",
    task_description: str = "Format code",
    script_content: str = "print(1)",
    script_path: str = "format.py",
) -> ScriptCaptureRecord:
    """Build a minimal ScriptCaptureRecord."""
    return ScriptCaptureRecord(
        script_id=script_id,
        timestamp="2026-01-16T10:00:00Z",
        task_description=task_description,
        script_path=script_path,
        script_content=script_content,
    )


class TestAnalyzeScript:
    """Tests for analyze_script."""

    def test_returns_script_analysis_result(self) -> None:
        """analyze_script returns ScriptAnalysisResult with script_id, use_case, gap."""
        record = _record(
            script_id="sid-1",
            task_description="Format Python files",
            script_content="import black",
        )
        result = analyze_script(
            record,
            known_tool_names=["manage_file"],
            known_script_names=["run_tests"],
        )
        assert result.script_id == "sid-1"
        assert result.use_case.use_case_label
        assert result.gap.gap_reason
        assert 0 <= result.reusability_score <= 1
        assert 0 <= result.promotion_potential <= 1

    def test_gap_is_true_when_no_overlapping_tools(self) -> None:
        """When no known tool/script overlaps, gap.is_gap is True."""
        record = _record(
            task_description="Format code",
            script_content="black",
        )
        result = analyze_script(
            record,
            known_tool_names=["manage_file", "load_context"],
            known_script_names=["run_tests", "check_spelling"],
        )
        assert result.gap.is_gap is True

    def test_gap_is_false_when_tool_overlaps(self) -> None:
        """When a known tool name overlaps (e.g. check_formatting), gap.is_gap is False."""
        record = _record(
            task_description="Format code",
            script_content="format",
        )
        result = analyze_script(
            record,
            known_tool_names=["check_formatting", "fix_formatting"],
            known_script_names=[],
        )
        assert result.gap.is_gap is False
        assert len(result.gap.existing_tool_names) >= 1

    def test_promotion_potential_higher_when_gap(self) -> None:
        """Promotion potential is higher when is_gap is True (gap represents opportunity)."""
        record = _record(
            task_description="Format code with black",
            script_content="black",
        )
        result_gap = analyze_script(
            record,
            known_tool_names=["manage_file"],
            known_script_names=[],
        )
        result_no_gap = analyze_script(
            record,
            known_tool_names=["check_formatting", "fix_formatting"],
            known_script_names=["check_formatting"],
        )
        assert result_gap.gap.is_gap is True
        assert result_no_gap.gap.is_gap is False
        assert result_gap.promotion_potential >= result_no_gap.promotion_potential
