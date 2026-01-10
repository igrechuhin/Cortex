"""Dependency and Quality Insight Generators.

Generate insights from dependency structure and quality metrics.
"""

from typing import cast

from .insight_types import InsightDict
from .structure_analyzer import StructureAnalyzer


class DependencyQualityInsights:
    """Generate dependency and quality insights."""

    def __init__(self, structure_analyzer: StructureAnalyzer) -> None:
        """
        Initialize dependency and quality insight generators.

        Args:
            structure_analyzer: Structure analyzer instance
        """
        self.structure_analyzer: StructureAnalyzer = structure_analyzer

    async def generate_dependency_insights(self) -> list[InsightDict]:
        """Generate insights about dependency structure."""
        insights: list[InsightDict] = []

        complexity_insight = await self._generate_complexity_insight()
        if complexity_insight:
            insights.append(complexity_insight)

        anti_patterns = await self.structure_analyzer.detect_anti_patterns()
        orphaned_insight = self._generate_orphaned_files_insight(anti_patterns)
        if orphaned_insight:
            insights.append(orphaned_insight)

        excessive_insight = self._generate_excessive_dependencies_insight(anti_patterns)
        if excessive_insight:
            insights.append(excessive_insight)

        return insights

    async def _generate_complexity_insight(self) -> InsightDict | None:
        """Generate insight about dependency complexity."""
        complexity = await self.structure_analyzer.measure_complexity_metrics()

        if str(complexity.get("status", "")) != "analyzed":
            return None

        assessment = self._extract_assessment(complexity)
        score_int = self._extract_complexity_score(assessment)

        if score_int >= 80:
            return None

        description = self._build_complexity_description(assessment)
        hotspots = self._extract_complexity_hotspots(complexity)
        recommendations = self._extract_recommendations(assessment)

        return InsightDict(
            {
                "id": "dependency_complexity",
                "category": "dependencies",
                "title": f"Dependency structure complexity: {str(assessment.get('grade', 'unknown'))}",
                "description": description,
                "impact_score": 0.8,
                "severity": "high" if score_int < 60 else "medium",
                "evidence": {
                    "complexity_score": score_int,
                    "grade": str(assessment.get("grade", "unknown")),
                    "metrics": complexity.get("metrics", {}),
                    "hotspots": hotspots,
                },
                "recommendations": recommendations,
                "estimated_token_savings": int((100 - score_int) * 50),
            }
        )

    def _extract_assessment(self, complexity: dict[str, object]) -> dict[str, object]:
        """Extract assessment dictionary from complexity metrics."""
        assessment_raw: object = complexity.get("assessment", {})
        if isinstance(assessment_raw, dict):
            return cast(dict[str, object], assessment_raw)
        return {}

    def _extract_complexity_score(self, assessment: dict[str, object]) -> int:
        """Extract complexity score as integer."""
        score: object = assessment.get("score", 0)
        return int(score) if isinstance(score, (int, float)) else 0

    def _build_complexity_description(self, assessment: dict[str, object]) -> str:
        """Build description from assessment issues."""
        issues_raw: object = assessment.get("issues", [])
        issue_strings: list[str] = []
        if isinstance(issues_raw, list):
            issues_list = cast(list[object], issues_raw)
            issue_strings = [str(item) for item in issues_list]
        return "; ".join(issue_strings)

    def _extract_complexity_hotspots(
        self, complexity: dict[str, object]
    ) -> list[dict[str, object]]:
        """Extract complexity hotspots from metrics."""
        hotspots_raw: object = complexity.get("complexity_hotspots", [])
        if not isinstance(hotspots_raw, list):
            return []

        hotspots_list = cast(list[object], hotspots_raw)
        return [
            cast(dict[str, object], item)
            for item in hotspots_list[:3]
            if isinstance(item, dict)
        ]

    def _extract_recommendations(self, assessment: dict[str, object]) -> list[str]:
        """Extract recommendations from assessment."""
        recommendations_raw: object = assessment.get("recommendations", [])
        if not isinstance(recommendations_raw, list):
            return []

        recommendations_list = cast(list[object], recommendations_raw)
        return [str(item) for item in recommendations_list if item is not None]

    def _generate_orphaned_files_insight(
        self, anti_patterns: list[dict[str, object]]
    ) -> InsightDict | None:
        """Generate insight about orphaned files."""
        orphaned = [
            ap for ap in anti_patterns if str(ap.get("type", "")) == "orphaned_file"
        ]

        if len(orphaned) < 2:
            return None

        return InsightDict(
            {
                "id": "orphaned_files",
                "category": "dependencies",
                "title": f"Found {len(orphaned)} orphaned files",
                "description": "These files have no dependencies or dependents",
                "impact_score": 0.6,
                "severity": "medium",
                "evidence": {
                    "orphaned_count": len(orphaned),
                    "examples": orphaned[:3],
                },
                "recommendations": [
                    "Add links from main files to orphaned files",
                    "Consider if orphaned files are still needed",
                    "Archive or remove truly unused files",
                ],
                "estimated_token_savings": len(orphaned) * 100,
            }
        )

    def _generate_excessive_dependencies_insight(
        self, anti_patterns: list[dict[str, object]]
    ) -> InsightDict | None:
        """Generate insight about excessive dependencies."""
        excessive_deps = [
            ap
            for ap in anti_patterns
            if str(ap.get("type", "")) == "excessive_dependencies"
        ]

        if not excessive_deps:
            return None

        return InsightDict(
            {
                "id": "excessive_dependencies",
                "category": "dependencies",
                "title": f"{len(excessive_deps)} files have too many dependencies",
                "description": "Files with many dependencies are harder to maintain",
                "impact_score": 0.7,
                "severity": "medium",
                "evidence": {
                    "excessive_count": len(excessive_deps),
                    "examples": excessive_deps[:3],
                },
                "recommendations": [
                    "Refactor to reduce number of dependencies",
                    "Split file into smaller, focused files",
                    "Use transclusion to manage shared content",
                ],
                "estimated_token_savings": len(excessive_deps) * 400,
            }
        )

    async def generate_quality_insights(self) -> list[InsightDict]:
        """Generate insights about overall quality."""
        insights: list[InsightDict] = []

        complexity_insight = await self._analyze_complexity_insights()
        if complexity_insight:
            insights.append(complexity_insight)

        organization_insight = await self._analyze_organization_insights()
        if organization_insight:
            insights.append(organization_insight)

        return insights

    async def _analyze_complexity_insights(self) -> InsightDict | None:
        """Analyze complexity metrics and generate insight if needed.

        Returns:
            Insight dictionary if issue found, None otherwise
        """
        complexity2 = await self.structure_analyzer.measure_complexity_metrics()

        if str(complexity2.get("status", "")) != "analyzed":
            return None

        metrics = self._extract_complexity_metrics(complexity2)
        max_depth = self._extract_max_depth(metrics)

        if max_depth > 5:
            return self._create_deep_dependencies_insight(max_depth)

        return None

    def _extract_complexity_metrics(
        self, complexity2: dict[str, object]
    ) -> dict[str, object]:
        """Extract metrics from complexity analysis."""
        metrics_raw: object = complexity2.get("metrics", {})
        return (
            cast(dict[str, object], metrics_raw)
            if isinstance(metrics_raw, dict)
            else {}
        )

    def _extract_max_depth(self, metrics: dict[str, object]) -> int:
        """Extract max dependency depth from metrics."""
        max_depth_raw: object = metrics.get("max_dependency_depth", 0)
        return int(max_depth_raw) if isinstance(max_depth_raw, (int, float)) else 0

    def _create_deep_dependencies_insight(self, max_depth: int) -> InsightDict:
        """Create insight for deep dependencies."""
        return InsightDict(
            {
                "id": "deep_dependencies",
                "category": "quality",
                "title": "Dependency chains are too deep",
                "description": f"Maximum depth is {max_depth}, recommended is ≤5",
                "impact_score": 0.75,
                "severity": "medium",
                "evidence": {
                    "max_depth": max_depth,
                    "recommended_max": 5,
                },
                "recommendations": [
                    "Flatten dependency hierarchy where possible",
                    "Consider direct references instead of chains",
                    "Review if all dependencies are necessary",
                ],
                "estimated_token_savings": (max_depth - 5) * 200,
            }
        )

    async def _analyze_organization_insights(self) -> InsightDict | None:
        """Analyze organization quality and generate insight if needed.

        Returns:
            Insight dictionary if issue found, None otherwise
        """
        org_analysis2 = await self.structure_analyzer.analyze_file_organization()

        if str(org_analysis2.get("status", "")) != "analyzed":
            return None

        avg_size_raw: object = org_analysis2.get("avg_size_kb", 0)
        avg_size = int(avg_size_raw) if isinstance(avg_size_raw, (int, float)) else 0

        if avg_size > 20:
            return InsightDict(
                {
                    "id": "large_average_size",
                    "category": "quality",
                    "title": "Average file size is large",
                    "description": f"Average file size is {avg_size}KB, consider smaller focused files",
                    "impact_score": 0.6,
                    "severity": "low",
                    "evidence": {"avg_size_kb": avg_size, "recommended_max_kb": 15},
                    "recommendations": [
                        "Split larger files into focused topics",
                        "Use transclusion to compose content",
                        "Aim for files under 15KB when possible",
                    ],
                    "estimated_token_savings": max(0, int((avg_size - 15) * 100)),
                }
            )

        return None
