"""Grade, status, and result building for quality metrics."""

from cortex.validation.models import (
    CategoryBreakdown,
    HealthGrade,
    QualityHealthStatus,
    QualityScoreResult,
)


def score_to_grade(score: float) -> HealthGrade:
    """Convert score to letter grade."""
    if score >= 90:
        return HealthGrade.A
    if score >= 80:
        return HealthGrade.B
    if score >= 70:
        return HealthGrade.C
    if score >= 60:
        return HealthGrade.D
    return HealthGrade.F


def score_to_status(score: float) -> QualityHealthStatus:
    """Get health status based on score."""
    if score >= 80:
        return QualityHealthStatus.HEALTHY
    if score >= 60:
        return QualityHealthStatus.WARNING
    return QualityHealthStatus.CRITICAL


def build_score_result(
    overall_score: int,
    category_scores: dict[str, float],
    grade: HealthGrade,
    status: QualityHealthStatus,
    issues: list[str],
    recommendations: list[str],
) -> QualityScoreResult:
    """Build final score result model."""
    return QualityScoreResult(
        overall_score=overall_score,
        breakdown=CategoryBreakdown(
            completeness=int(category_scores["completeness"]),
            consistency=int(category_scores["consistency"]),
            freshness=int(category_scores["freshness"]),
            structure=int(category_scores["structure"]),
            token_efficiency=int(category_scores["token_efficiency"]),
        ),
        grade=grade,
        status=status,
        issues=issues,
        recommendations=recommendations,
    )
