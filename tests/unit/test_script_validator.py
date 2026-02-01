"""Tests for script_promotion.script_validator."""

from cortex.script_analysis.models import (
    GapAnalysis,
    ScriptAnalysisResult,
    UseCaseExtraction,
)
from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_promotion.script_validator import validate_for_promotion


def _record(
    script_content: str = "def main(): pass",
    task_description: str = "Format code",
) -> ScriptCaptureRecord:
    """Build a minimal ScriptCaptureRecord."""
    return ScriptCaptureRecord(
        script_id="sid-1",
        timestamp="2026-01-16T10:00:00Z",
        task_description=task_description,
        script_path="format.py",
        script_content=script_content,
    )


class TestValidateForPromotion:
    """Tests for validate_for_promotion."""

    def test_passes_when_content_and_task_present(self) -> None:
        """Validation passes when content and task_description are present."""
        record = _record(script_content="def foo(): pass", task_description="Format")
        result = validate_for_promotion(record, analysis=None)
        assert result.passed is True
        assert result.quality_score >= 0
        assert len(result.issues) == 0

    def test_fails_when_content_too_short(self) -> None:
        """Validation fails when script content is too short."""
        record = _record(script_content="x", task_description="Format")
        result = validate_for_promotion(record, analysis=None)
        assert result.passed is False
        assert any("short" in i.lower() for i in result.issues)

    def test_fails_when_task_description_empty(self) -> None:
        """Validation fails when task_description is empty."""
        record = _record(script_content="def foo(): pass", task_description="")
        result = validate_for_promotion(record, analysis=None)
        assert result.passed is False
        assert any(
            "task" in i.lower() or "description" in i.lower() for i in result.issues
        )

    def test_fails_when_promotion_potential_below_threshold(self) -> None:
        """Validation fails when analysis promotion_potential is below threshold."""
        record = _record(script_content="def foo(): pass", task_description="Format")
        analysis = ScriptAnalysisResult(
            script_id="sid-1",
            use_case=UseCaseExtraction(use_case_label="session script", keywords=[]),
            gap=GapAnalysis(gap_reason="N/A", is_gap=True),
            reusability_score=0.2,
            promotion_potential=0.1,
        )
        result = validate_for_promotion(record, analysis=analysis)
        assert result.passed is False
        assert any(
            "potential" in i.lower() or "threshold" in i.lower() for i in result.issues
        )
