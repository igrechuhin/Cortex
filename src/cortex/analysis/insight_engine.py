"""Insight Engine - Generate actionable insights and recommendations.

This module combines pattern and structure analysis to generate human-readable
insights with specific recommendations for improvement.
"""

from datetime import UTC, datetime

from .insight_dep_quality import DependencyQualityInsights
from .insight_formatter import InsightFormatter
from .insight_summary import InsightSummaryGenerator
from .insight_types import InsightDict, InsightsResultDict, SummaryDict
from .insight_usage_org import UsageOrganizationInsights
from .models import InsightModel, InsightStatistics
from .pattern_analyzer import PatternAnalyzer
from .structure_analyzer import StructureAnalyzer


class InsightEngine:
    """
    Generate actionable insights from pattern and structure analysis.

    Features:
    - Generate human-readable insights
    - Prioritize recommendations by impact
    - Provide evidence for each insight
    - Estimate token savings potential
    - Suggest specific actions
    """

    def __init__(
        self,
        pattern_analyzer: PatternAnalyzer,
        structure_analyzer: StructureAnalyzer,
    ) -> None:
        """
        Initialize insight engine.

        Args:
            pattern_analyzer: Pattern analyzer instance
            structure_analyzer: Structure analyzer instance
        """
        self.pattern_analyzer: PatternAnalyzer = pattern_analyzer
        self.structure_analyzer: StructureAnalyzer = structure_analyzer
        self.formatter: InsightFormatter = InsightFormatter()
        self.usage_org: UsageOrganizationInsights = UsageOrganizationInsights(
            pattern_analyzer, structure_analyzer
        )
        self.dep_quality: DependencyQualityInsights = DependencyQualityInsights(
            structure_analyzer
        )
        self.summary_generator: InsightSummaryGenerator = InsightSummaryGenerator()

    async def generate_insights(
        self,
        min_impact_score: float = 0.5,
        categories: list[str] | None = None,
        include_reasoning: bool = True,  # noqa: ARG002
    ) -> InsightsResultDict:
        """
        Generate comprehensive insights and recommendations.

        Args:
            min_impact_score: Minimum impact score (0-1) to include insight
            categories: Optional list of categories to include
            include_reasoning: Whether to include detailed reasoning

        Returns:
            Dictionary with insights, recommendations, and metadata
        """
        selected_categories = self._get_selected_categories(categories)

        # Generate insights by category
        insights = await self._generate_insights_by_category(selected_categories)

        # Filter, sort, and build result
        filtered_insights = self._filter_and_sort_insights(insights, min_impact_score)
        statistics = self._calculate_insight_statistics(filtered_insights)

        return self._build_insights_result(filtered_insights, statistics)

    def _get_selected_categories(self, categories: list[str] | None) -> list[str]:
        """Get selected categories or default to all.

        Args:
            categories: Optional list of categories

        Returns:
            List of selected categories
        """
        all_categories = [
            "usage",
            "organization",
            "redundancy",
            "dependencies",
            "quality",
        ]
        return categories if categories else all_categories

    async def _generate_insights_by_category(
        self, selected_categories: list[str]
    ) -> list[InsightDict]:
        """Generate insights for selected categories.

        Args:
            selected_categories: List of categories to generate insights for

        Returns:
            List of generated insights
        """
        insights: list[InsightDict] = []

        if "usage" in selected_categories:
            usage_insights = await self.usage_org.generate_usage_insights()
            insights.extend(usage_insights)

        if "organization" in selected_categories:
            org_insights = await self.usage_org.generate_organization_insights()
            insights.extend(org_insights)

        if "redundancy" in selected_categories:
            redundancy_insights = await self.usage_org.generate_redundancy_insights()
            insights.extend(redundancy_insights)

        if "dependencies" in selected_categories:
            dep_insights = await self.dep_quality.generate_dependency_insights()
            insights.extend(dep_insights)

        if "quality" in selected_categories:
            quality_insights = await self.dep_quality.generate_quality_insights()
            insights.extend(quality_insights)

        return insights

    def _filter_and_sort_insights(
        self, insights: list[InsightDict], min_impact_score: float
    ) -> list[InsightDict]:
        """Filter and sort insights by impact score.

        Args:
            insights: List of insights to filter and sort
            min_impact_score: Minimum impact score threshold

        Returns:
            Filtered and sorted list of insights
        """
        filtered = [i for i in insights if i.impact_score >= min_impact_score]
        filtered.sort(key=lambda x: x.impact_score, reverse=True)
        return filtered

    def _calculate_insight_statistics(
        self, insights: list[InsightDict]
    ) -> InsightStatistics:
        """Calculate summary statistics for insights.

        Args:
            insights: List of filtered insights

        Returns:
            Insight statistics model
        """
        total_potential_savings = sum(i.estimated_token_savings for i in insights)

        high_impact, medium_impact, low_impact = (
            self.summary_generator.calculate_impact_counts(insights)
        )

        return InsightStatistics(
            total_potential_savings=total_potential_savings,
            high_impact=high_impact,
            medium_impact=medium_impact,
            low_impact=low_impact,
        )

    def _build_insights_result(
        self,
        insights: list[InsightDict],
        statistics: InsightStatistics,
    ) -> InsightsResultDict:
        """Build final insights result dictionary.

        Args:
            insights: List of filtered and sorted insights
            statistics: Calculated statistics

        Returns:
            Complete insights result dictionary
        """
        return InsightsResultDict(
            generated_at=datetime.now(UTC).isoformat(),
            total_insights=len(insights),
            high_impact_count=statistics.high_impact,
            medium_impact_count=statistics.medium_impact,
            low_impact_count=statistics.low_impact,
            estimated_total_token_savings=statistics.total_potential_savings,
            insights=insights,
            summary=self.generate_summary(insights),
        )

    async def generate_usage_insights(self) -> list[InsightDict]:
        """Generate insights from usage patterns."""
        return await self.usage_org.generate_usage_insights()

    async def generate_organization_insights(self) -> list[InsightDict]:
        """Generate insights from file organization."""
        return await self.usage_org.generate_organization_insights()

    def generate_summary(self, insights: list[InsightDict]) -> SummaryDict:
        """
        Generate a summary of insights.

        Args:
            insights: List of generated insights

        Returns:
            Summary dictionary
        """
        return self.summary_generator.generate_summary(insights)

    async def get_insight_details(self, insight_id: str) -> InsightModel | None:
        """
        Get detailed information about a specific insight.

        Args:
            insight_id: ID of the insight

        Returns:
            Detailed insight model or None if not found
        """
        insights_result = await self.generate_insights(min_impact_score=0.0)

        for insight in insights_result.insights:
            if insight.id == insight_id:
                return InsightModel.model_validate(insight.model_dump(mode="json"))

        return None

    async def export_insights(
        self, insights: InsightsResultDict, format: str = "json"
    ) -> str:
        """
        Export insights in various formats.

        Args:
            insights: Insights dictionary from generate_insights()
            format: Export format ("json", "markdown", "text")

        Returns:
            Formatted string
        """
        return self.formatter.export_insights(insights, format)
