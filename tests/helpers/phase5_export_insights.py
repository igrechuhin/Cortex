"""Shared InsightsResultDict payloads for Phase 5.1 export tests."""

from cortex.analysis.insight_types import InsightDict, InsightsResultDict, SummaryDict
from cortex.analysis.models import InsightCategory, InsightSummaryStatus, SeverityLevel


def export_test_insights_result() -> InsightsResultDict:
    """Single-insight payload reused by export format tests."""
    return InsightsResultDict(
        generated_at="2025-01-01T00:00:00",
        total_insights=1,
        high_impact_count=1,
        medium_impact_count=0,
        low_impact_count=0,
        estimated_total_token_savings=1000,
        insights=[
            InsightDict(
                id="test",
                category=InsightCategory.USAGE,
                title="Test Insight",
                description="Test",
                impact_score=0.8,
                severity=SeverityLevel.HIGH,
                recommendations=["Fix this"],
                estimated_token_savings=1000,
                affected_files=[],
            )
        ],
        summary=SummaryDict(
            status=InsightSummaryStatus.GOOD,
            message="All good",
            high_severity_count=1,
            medium_severity_count=0,
            low_severity_count=0,
            top_recommendations=[],
        ),
    )
