"""Tests for cortex.script_promotion.script_validator."""

from cortex.script_analysis.models import (
    GapAnalysis,
    ScriptAnalysisResult,
    UseCaseExtraction,
)
from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_promotion.script_validator import validate_for_promotion


def _make_record(
    script_id: str = "sid-1",
    task_description: str = "Run tests",
    script_path: str = "scripts/run_tests.py",
    script_content: str = "def main(): pass",
    usage_context: str | None = None,
) -> ScriptCaptureRecord:
    """Build a minimal ScriptCaptureRecord for tests."""
    return ScriptCaptureRecord(
        script_id=script_id,
        timestamp="2026-01-01T00:00:00Z",
        task_description=task_description,
        script_path=script_path,
        script_content=script_content,
        usage_context=usage_context,
    )


class TestValidateForPromotion:
    """Tests for validate_for_promotion."""

    def test_passes_with_sufficient_content_and_task(self) -> None:
        """Record with enough content and task description passes."""
        record = _make_record(
            script_content="def main():\n    pass\n",
            task_description="Run tests",
        )
        result = validate_for_promotion(record)
        assert result.passed is True
        assert result.issues == []
        assert 0 <= result.quality_score <= 1

    def test_fails_when_content_too_short(self) -> None:
        """Content shorter than minimum fails."""
        record = _make_record(script_content="x")
        result = validate_for_promotion(record)
        assert result.passed is False
        assert any("short" in i.lower() for i in result.issues)

    def test_fails_when_content_exceeds_max(self) -> None:
        """Content exceeding max length fails."""
        record = _make_record(script_content="x" * 50_001)
        result = validate_for_promotion(record)
        assert result.passed is False
        assert any("exceeds" in i.lower() for i in result.issues)

    def test_fails_when_task_description_empty(self) -> None:
        """Empty or blank task description fails."""
        record = _make_record(task_description="   ")
        result = validate_for_promotion(record)
        assert result.passed is False
        assert any(
            "task" in i.lower() or "description" in i.lower() for i in result.issues
        )

    def test_with_analysis_above_threshold_passes(self) -> None:
        """When analysis promotion_potential >= 0.3, no extra issue."""
        record = _make_record(script_content="def foo(): pass")
        analysis = ScriptAnalysisResult(
            script_id=record.script_id,
            use_case=UseCaseExtraction(use_case_label="test", keywords=[]),
            gap=GapAnalysis(gap_reason="ok", is_gap=True),
            reusability_score=0.8,
            promotion_potential=0.5,
        )
        result = validate_for_promotion(record, analysis)
        assert result.passed is True
        assert 0 <= result.quality_score <= 1

    def test_with_analysis_below_potential_threshold_fails(self) -> None:
        """When promotion_potential < 0.3, issue added."""
        record = _make_record(script_content="def foo(): pass")
        analysis = ScriptAnalysisResult(
            script_id=record.script_id,
            use_case=UseCaseExtraction(use_case_label="test", keywords=[]),
            gap=GapAnalysis(gap_reason="ok", is_gap=True),
            reusability_score=0.1,
            promotion_potential=0.2,
        )
        result = validate_for_promotion(record, analysis)
        assert result.passed is False
        assert any(
            "potential" in i.lower() or "threshold" in i.lower() for i in result.issues
        )

    def test_quality_score_combines_content_and_analysis(self) -> None:
        """Quality score blends content-based and analysis reusability."""
        record = _make_record(
            script_content="def foo():\n    try:\n        pass\n    except X: pass",
            task_description="Do thing",
            usage_context="When X",
        )
        analysis = ScriptAnalysisResult(
            script_id=record.script_id,
            use_case=UseCaseExtraction(use_case_label="test", keywords=[]),
            gap=GapAnalysis(gap_reason="ok", is_gap=True),
            reusability_score=0.9,
            promotion_potential=0.5,
        )
        result = validate_for_promotion(record, analysis)
        assert result.passed is True
        assert result.quality_score >= 0.5
