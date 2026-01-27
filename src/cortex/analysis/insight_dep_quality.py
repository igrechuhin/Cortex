"""Dependency and Quality Insight Generators.

Generate insights from dependency structure and quality metrics.
"""

from .insight_types import InsightDict
from .models import (
    AntiPatternInfo,
    ComplexityAnalysisResult,
    ComplexityAssessment,
    ComplexityHotspot,
)
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

        if complexity.status != "analyzed":
            return None

        assessment = complexity.assessment
        score_int: int = assessment.score

        if score_int >= 80:
            return None

        description = self._build_complexity_description(assessment)
        hotspots = self._extract_complexity_hotspots(complexity)
        recommendations = assessment.recommendations

        return InsightDict.model_validate(
            {
                "id": "dependency_complexity",
                "category": "dependencies",
                "title": f"Dependency structure complexity: {assessment.grade}",
                "description": description,
                "impact_score": 0.8,
                "severity": "high" if score_int < 60 else "medium",
                "evidence": {
                    "complexity_score": score_int,
                    "grade": assessment.grade,
                    "metrics": complexity.metrics.model_dump(mode="json"),
                    "hotspots": [h.model_dump(mode="json") for h in hotspots],
                },
                "recommendations": recommendations,
                "estimated_token_savings": int((100 - score_int) * 50),
                "affected_files": [h.file for h in hotspots],
            }
        )

    def _build_complexity_description(self, assessment: ComplexityAssessment) -> str:
        """Build description from assessment issues."""
        return "; ".join(assessment.issues)

    def _extract_complexity_hotspots(
        self, complexity: ComplexityAnalysisResult
    ) -> list[ComplexityHotspot]:
        """Extract complexity hotspots from metrics."""
        return complexity.complexity_hotspots[:3]

    def _generate_orphaned_files_insight(
        self, anti_patterns: list[AntiPatternInfo]
    ) -> InsightDict | None:
        """Generate insight about orphaned files."""
        orphaned = [ap for ap in anti_patterns if ap.type == "orphaned_file"]

        if len(orphaned) < 2:
            return None

        return InsightDict.model_validate(
            {
                "id": "orphaned_files",
                "category": "dependencies",
                "title": f"Found {len(orphaned)} orphaned files",
                "description": "These files have no dependencies or dependents",
                "impact_score": 0.6,
                "severity": "medium",
                "evidence": {
                    "orphaned_count": len(orphaned),
                    "example_patterns": [
                        ap.model_dump(mode="json") for ap in orphaned[:3]
                    ],
                },
                "recommendations": [
                    "Add links from main files to orphaned files",
                    "Consider if orphaned files are still needed",
                    "Archive or remove truly unused files",
                ],
                "estimated_token_savings": len(orphaned) * 100,
                "affected_files": [ap.file for ap in orphaned if ap.file],
            }
        )

    def _generate_excessive_dependencies_insight(
        self, anti_patterns: list[AntiPatternInfo]
    ) -> InsightDict | None:
        """Generate insight about excessive dependencies."""
        excessive_deps = [
            ap for ap in anti_patterns if ap.type == "excessive_dependencies"
        ]

        if not excessive_deps:
            return None

        return InsightDict.model_validate(
            {
                "id": "excessive_dependencies",
                "category": "dependencies",
                "title": f"{len(excessive_deps)} files have too many dependencies",
                "description": "Files with many dependencies are harder to maintain",
                "impact_score": 0.7,
                "severity": "medium",
                "evidence": {
                    "excessive_count": len(excessive_deps),
                    "example_patterns": [
                        ap.model_dump(mode="json") for ap in excessive_deps[:3]
                    ],
                },
                "recommendations": [
                    "Refactor to reduce number of dependencies",
                    "Split file into smaller, focused files",
                    "Use transclusion to manage shared content",
                ],
                "estimated_token_savings": len(excessive_deps) * 400,
                "affected_files": [ap.file for ap in excessive_deps if ap.file],
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

        if complexity2.status != "analyzed":
            return None

        max_depth = complexity2.metrics.max_dependency_depth

        if max_depth > 5:
            return self._create_deep_dependencies_insight(max_depth)

        return None

    def _create_deep_dependencies_insight(self, max_depth: int) -> InsightDict:
        """Create insight for deep dependencies."""
        return InsightDict.model_validate(
            {
                "id": "deep_dependencies",
                "category": "quality",
                "title": "Dependency chains are too deep",
                "description": f"Maximum depth is {max_depth}, recommended is ≤5",
                "impact_score": 0.75,
                "severity": "medium",
                "evidence": {"max_depth": max_depth, "recommended_max": 5},
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

        if org_analysis2.status != "analyzed":
            return None

        avg_size = int(org_analysis2.avg_size_kb)

        if avg_size > 20:
            return InsightDict.model_validate(
                {
                    "id": "large_average_size",
                    "category": "quality",
                    "title": "Average file size is large",
                    "description": (
                        f"Average file size is {avg_size}KB, consider "
                        "smaller focused files"
                    ),
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
