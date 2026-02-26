"""Recommendation generation helpers for quality metrics."""


def add_completeness_recommendation(
    recommendations: list[str], completeness: float
) -> None:
    """Add completeness recommendation if needed."""
    if completeness < 80:
        recommendations.append(
            "Run 'validate_memory_bank' to see which sections are missing"
        )


def add_consistency_recommendation(
    recommendations: list[str], consistency: float
) -> None:
    """Add consistency recommendation if needed."""
    if consistency < 80:
        recommendations.append(
            "Run 'check_duplications' to identify and refactor duplicate content"
        )


def add_freshness_recommendation(recommendations: list[str], freshness: float) -> None:
    """Add freshness recommendation if needed."""
    if freshness < 60:
        msg = (
            "Review and update stale files, especially "
            + "activeContext.md and progress.md"
        )
        recommendations.append(msg)


def add_structure_recommendation(recommendations: list[str], structure: float) -> None:
    """Add structure recommendation if needed."""
    if structure < 80:
        recommendations.append(
            "Fix heading hierarchy - avoid skipping levels (## -> ####)"
        )


def add_token_efficiency_recommendation(
    recommendations: list[str], token_efficiency: float
) -> None:
    """Add token efficiency recommendation if needed."""
    if token_efficiency < 70:
        msg = (
            "Review token usage with 'check_token_budget' and "
            + "consider summarizing verbose sections"
        )
        recommendations.append(msg)


def add_general_recommendation(recommendations: list[str], issues: list[str]) -> None:
    """Add general recommendation if no issues."""
    if not issues:
        recommendations.append(
            "Memory Bank is in good shape! Keep maintaining regular updates."
        )


def generate_all_recommendations(
    completeness: float,
    consistency: float,
    freshness: float,
    structure: float,
    token_efficiency: float,
    issues: list[str],
) -> list[str]:
    """Generate actionable recommendations."""
    recommendations: list[str] = []

    add_completeness_recommendation(recommendations, completeness)
    add_consistency_recommendation(recommendations, consistency)
    add_freshness_recommendation(recommendations, freshness)
    add_structure_recommendation(recommendations, structure)
    add_token_efficiency_recommendation(recommendations, token_efficiency)
    add_general_recommendation(recommendations, issues)

    return recommendations
