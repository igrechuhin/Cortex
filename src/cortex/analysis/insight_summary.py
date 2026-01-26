"""Insight Summary - Generate summary of insights."""

from .insight_types import InsightDict, SummaryDict
from .models import RecommendationEntry


class InsightSummaryGenerator:
    """Generate summary of insights."""

    def generate_summary(self, insights: list[InsightDict]) -> SummaryDict:
        """
        Generate a summary of insights.

        Args:
            insights: List of generated insights

        Returns:
            Summary dictionary
        """
        if not insights:
            return self._build_excellent_summary()

        severity_counts = self._count_by_severity(insights)
        status, message = self._determine_status_and_message(severity_counts)
        top_recommendations = self._get_top_recommendations(insights)

        return SummaryDict(
            status=status,
            message=message,
            high_severity_count=severity_counts["high"],
            medium_severity_count=severity_counts["medium"],
            low_severity_count=severity_counts["low"],
            top_recommendations=top_recommendations,
        )

    def calculate_impact_counts(
        self, insights: list[InsightDict]
    ) -> tuple[int, int, int]:
        """
        Calculate counts by impact level.

        Args:
            insights: List of insights

        Returns:
            Tuple of (high_count, medium_count, low_count)
        """
        high_impact = len([i for i in insights if i.impact_score >= 0.8])
        medium_impact = len([i for i in insights if 0.5 <= i.impact_score < 0.8])
        low_impact = len([i for i in insights if i.impact_score < 0.5])

        return (high_impact, medium_impact, low_impact)

    def _build_excellent_summary(self) -> SummaryDict:
        """Build summary for case with no insights."""
        return SummaryDict(
            status="excellent",
            message="No significant issues found. Your Memory Bank is well-organized!",
            high_severity_count=0,
            medium_severity_count=0,
            low_severity_count=0,
            top_recommendations=[],
        )

    def _count_by_severity(self, insights: list[InsightDict]) -> dict[str, int]:
        """Count insights by severity level."""
        return {
            "high": len([i for i in insights if i.severity == "high"]),
            "medium": len([i for i in insights if i.severity == "medium"]),
            "low": len([i for i in insights if i.severity == "low"]),
        }

    def _determine_status_and_message(
        self, severity_counts: dict[str, int]
    ) -> tuple[str, str]:
        """Determine overall status and message based on severity counts."""
        if severity_counts["high"] > 0:
            return (
                "needs_attention",
                f"Found {severity_counts['high']} high-priority issues that should be addressed",
            )
        if severity_counts["medium"] >= 3:
            return (
                "could_improve",
                f"Found {severity_counts['medium']} medium-priority opportunities for improvement",
            )
        return (
            "good",
            "Structure is generally good with some minor optimization opportunities",
        )

    def _get_top_recommendations(
        self, insights: list[InsightDict]
    ) -> list[RecommendationEntry]:
        """Get top 5 recommendations sorted by impact score."""
        top_insights = sorted(insights, key=lambda x: x.impact_score, reverse=True)[:5]
        recommendations: list[RecommendationEntry] = []
        for insight in top_insights:
            primary = insight.recommendations[0] if insight.recommendations else ""
            priority = (
                "high"
                if insight.impact_score >= 0.8
                else "medium" if insight.impact_score >= 0.5 else "low"
            )
            recommendations.append(
                RecommendationEntry(
                    title=insight.title,
                    description=primary,
                    priority=priority,
                    estimated_impact=insight.impact_score,
                )
            )
        return recommendations
