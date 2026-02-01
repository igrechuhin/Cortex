"""Validate session scripts for promotion to permanent tools/scripts."""

from cortex.script_analysis.models import ScriptAnalysisResult
from cortex.script_detection.models import ScriptCaptureRecord
from cortex.script_promotion.models import ValidationResult

_MIN_CONTENT_LEN = 10
_MAX_CONTENT_LEN = 50_000
_MIN_PROMOTION_POTENTIAL = 0.3


def _content_checks(record: ScriptCaptureRecord) -> list[str]:
    """Return list of issues from content/length checks."""
    issues: list[str] = []
    content = (record.script_content or "").strip()
    if len(content) < _MIN_CONTENT_LEN:
        issues.append("Script content too short for promotion")
    if len(content) > _MAX_CONTENT_LEN:
        issues.append("Script content exceeds maximum length for promotion")
    if not (record.task_description or "").strip():
        issues.append("Missing task description")
    return issues


def _quality_score_from_content(record: ScriptCaptureRecord) -> float:
    """Estimate quality 0-1 from content and metadata."""
    score = 0.5
    if (record.task_description or "").strip():
        score += 0.2
    if (record.usage_context or "").strip():
        score += 0.1
    content = (record.script_content or "").strip()
    if "def " in content or "async def " in content:
        score += 0.1
    if "try:" in content or "except " in content:
        score += 0.1
    return min(1.0, score)


def validate_for_promotion(
    record: ScriptCaptureRecord,
    analysis: ScriptAnalysisResult | None = None,
) -> ValidationResult:
    """Validate a captured script for promotion.

    Args:
        record: Captured script record.
        analysis: Optional script analysis result (affects promotion potential).

    Returns:
        ValidationResult with passed, quality_score, and issues.
    """
    issues = _content_checks(record)
    if analysis is not None and analysis.promotion_potential < _MIN_PROMOTION_POTENTIAL:
        issues.append(
            f"Promotion potential below threshold (got {analysis.promotion_potential:.2f})"
        )
    quality = _quality_score_from_content(record)
    if analysis is not None:
        quality = (quality + analysis.reusability_score) / 2
    passed = len(issues) == 0
    return ValidationResult(
        passed=passed,
        quality_score=round(quality, 4),
        issues=issues,
    )
