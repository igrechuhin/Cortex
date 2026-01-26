"""
Tests for insight_engine.py - Insight generation functionality.

This test module covers:
- InsightEngine initialization
- Comprehensive insight generation
- Category-specific insight generation (usage, organization, redundancy, dependencies, quality)
- Summary generation
- Export formats (JSON, Markdown, Text)
- Impact scoring and filtering
"""

import json
from typing import cast
from unittest.mock import AsyncMock

import pytest
import pytest_mock

from cortex.analysis.insight_engine import InsightDict, InsightEngine
from cortex.analysis.insight_types import InsightsResultDict
from cortex.analysis.models import (
    AntiPatternInfo,
    CoAccessPattern,
    ComplexityAnalysisResult,
    ComplexityAssessment,
    ComplexityHotspot,
    ComplexityMetrics,
)
from cortex.analysis.pattern_types import UnusedFileEntry
from cortex.core.exceptions import MemoryBankError
from cortex.core.models import FileOrganizationResult, FileSizeEntry


class TestInsightEngineInitialization:
    """Tests for InsightEngine initialization."""

    def test_initializes_with_analyzers(self, mocker: "pytest_mock.MockerFixture"):
        """Test initialization with pattern and structure analyzers."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()

        # Act
        engine = InsightEngine(mock_pattern, mock_structure)

        # Assert
        assert engine.pattern_analyzer == mock_pattern
        assert engine.structure_analyzer == mock_structure


class TestInsightGeneration:
    """Tests for comprehensive insight generation."""

    @pytest.mark.asyncio
    async def test_generates_empty_insights_when_no_issues(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates empty insights when no issues detected."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0, issues=[])
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(
                status="analyzed",
                metrics=ComplexityMetrics(max_dependency_depth=3),
                assessment=ComplexityAssessment(
                    score=95, grade="A", status="excellent"
                ),
            )
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights()
        result = result_model.model_dump(mode="json")

        # Assert
        assert result["total_insights"] == 0
        assert result["high_impact_count"] == 0
        assert result["medium_impact_count"] == 0
        assert result["low_impact_count"] == 0
        assert result["insights"] == []
        summary_raw = result["summary"]
        assert isinstance(summary_raw, dict)
        summary: dict[str, object] = cast(dict[str, object], summary_raw)
        assert summary.get("status") == "excellent"

    @pytest.mark.asyncio
    async def test_generates_insights_with_all_categories(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insights across all categories."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(
            return_value=[
                UnusedFileEntry(
                    file="unused1.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                ),
                UnusedFileEntry(
                    file="unused2.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                ),
                UnusedFileEntry(
                    file="unused3.md",
                    status="never_accessed",
                    total_accesses=0,
                    last_access=None,
                ),
            ]
        )
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(
                status="analyzed",
                file_count=5,
                issues=["3 files very large"],
                largest_files=[
                    FileSizeEntry(file="large1.md", size_bytes=100000, tokens=0),
                    FileSizeEntry(file="large2.md", size_bytes=90000, tokens=0),
                ],
                smallest_files=[],
            )
        )
        mock_structure.detect_anti_patterns = AsyncMock(
            return_value=[
                AntiPatternInfo(
                    type="similar_filenames",
                    file="test1.md",
                    files=["test1.md", "test2.md"],
                    severity="medium",
                    description="Similar filenames detected",
                ),
                AntiPatternInfo(
                    type="similar_filenames",
                    file="doc1.md",
                    files=["doc1.md", "doc2.md"],
                    severity="medium",
                    description="Similar filenames detected",
                ),
            ]
        )
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(
                status="analyzed",
                metrics=ComplexityMetrics(max_dependency_depth=8),
                assessment=ComplexityAssessment(
                    score=55,
                    grade="D",
                    status="poor",
                    issues=["High complexity"],
                    recommendations=["Reduce dependencies"],
                ),
            )
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(min_impact_score=0.5)
        result = result_model.model_dump(mode="json")

        # Assert
        assert result["total_insights"] > 0
        assert "insights" in result
        assert "summary" in result
        assert "generated_at" in result

        # Check that insights have required fields
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        for insight in insights:
            assert "id" in insight
            assert "category" in insight
            assert "title" in insight
            assert "description" in insight
            assert "impact_score" in insight
            assert "severity" in insight
            assert "recommendations" in insight

    @pytest.mark.asyncio
    async def test_filters_insights_by_impact_score(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test filters insights by minimum impact score."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(
            return_value=[
                UnusedFileEntry(
                    file=f"unused{i}.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                )
                for i in range(5)
            ]
        )
        mock_pattern.get_co_access_patterns = AsyncMock(
            return_value=[
                CoAccessPattern(file_1="a.md", file_2="b.md") for _ in range(5)
            ]
        )

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act - request only high impact (>0.8)
        result_model = await engine.generate_insights(min_impact_score=0.8)
        result = result_model.model_dump(mode="json")

        # Assert - should only include insights with impact >= 0.8
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        for insight in insights:
            impact_score = insight["impact_score"]
            assert isinstance(impact_score, (int, float))
            assert impact_score >= 0.8

    @pytest.mark.asyncio
    async def test_filters_insights_by_categories(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test filters insights by selected categories."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(
            return_value=[
                UnusedFileEntry(
                    file=f"unused{i}.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                )
                for i in range(5)
            ]
        )
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act - request only usage category
        result_model = await engine.generate_insights(categories=["usage"])
        result = result_model.model_dump(mode="json")

        # Assert - should only include usage insights
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        for insight in insights:
            category = insight["category"]
            assert isinstance(category, str)
            assert category == "usage"

    @pytest.mark.asyncio
    async def test_sorts_insights_by_impact_score(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test sorts insights by impact score descending."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(
            return_value=[
                UnusedFileEntry(
                    file=f"unused{i}.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                )
                for i in range(5)
            ]
        )
        mock_pattern.get_co_access_patterns = AsyncMock(
            return_value=[
                CoAccessPattern(file_1="a.md", file_2="b.md") for _ in range(5)
            ]
        )

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(min_impact_score=0.0)
        result = result_model.model_dump(mode="json")

        # Assert - insights should be sorted by impact score (highest first)
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        scores: list[float] = []
        for insight in insights:
            impact_score = insight["impact_score"]
            assert isinstance(impact_score, (int, float))
            scores.append(float(impact_score))
        assert scores == sorted(scores, reverse=True)


class TestUsageInsights:
    """Tests for usage pattern insights."""

    @pytest.mark.asyncio
    async def test_detects_unused_files_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for unused files."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(
            return_value=[
                UnusedFileEntry(
                    file="unused1.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                ),
                UnusedFileEntry(
                    file="unused2.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                ),
                UnusedFileEntry(
                    file="unused3.md",
                    status="never_accessed",
                    total_accesses=0,
                    last_access=None,
                ),
            ]
        )
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(categories=["usage"])
        result = result_model.model_dump(mode="json")

        # Assert
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        unused_insights = [i for i in insights if i.get("id") == "unused_files"]
        assert len(unused_insights) == 1
        insight = unused_insights[0]
        assert insight["category"] == "usage"
        assert insight["severity"] == "medium"
        assert "unused" in str(insight["title"]).lower()
        recommendations = cast(list[str], insight["recommendations"])
        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_detects_co_access_patterns_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for co-access patterns."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(
            return_value=[
                CoAccessPattern(file_1=f"file{i}.md", file_2=f"file{i + 1}.md")
                for i in range(5)
            ]
        )

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(categories=["usage"])
        result = result_model.model_dump(mode="json")

        # Assert
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        co_access_insights = [
            i for i in insights if i.get("id") == "co_access_patterns"
        ]
        assert len(co_access_insights) == 1
        insight = co_access_insights[0]
        assert insight["category"] == "usage"
        assert insight["severity"] == "low"
        assert "co-accessed" in str(insight["title"]).lower()


class TestOrganizationInsights:
    """Tests for organization insights."""

    @pytest.mark.asyncio
    async def test_detects_large_files_insight(self, mocker: pytest_mock.MockerFixture):
        """Test generates insight for large files."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(
                status="analyzed",
                file_count=3,
                issues=["3 files very large"],
                largest_files=[
                    FileSizeEntry(file="large1.md", size_bytes=100000, tokens=0),
                    FileSizeEntry(file="large2.md", size_bytes=90000, tokens=0),
                    FileSizeEntry(file="large3.md", size_bytes=80000, tokens=0),
                ],
                smallest_files=[],
            )
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(categories=["organization"])
        result = result_model.model_dump(mode="json")

        # Assert
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        large_file_insights = [i for i in insights if i.get("id") == "large_files"]
        assert len(large_file_insights) == 1
        insight = large_file_insights[0]
        assert insight["category"] == "organization"
        assert insight["severity"] == "medium"
        assert "large" in str(insight["title"]).lower()

    @pytest.mark.asyncio
    async def test_detects_small_files_insight(self, mocker: pytest_mock.MockerFixture):
        """Test generates insight for small files."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(
                status="analyzed",
                file_count=5,
                issues=["5 files very small"],
                largest_files=[],
                smallest_files=[
                    FileSizeEntry(file=f"small{i}.md", size_bytes=300, tokens=0)
                    for i in range(5)
                ],
            )
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(categories=["organization"])
        result = result_model.model_dump(mode="json")

        # Assert
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        small_file_insights = [i for i in insights if i.get("id") == "small_files"]
        assert len(small_file_insights) == 1
        insight = small_file_insights[0]
        assert insight["category"] == "organization"
        assert insight["severity"] == "low"
        assert "small" in str(insight["title"]).lower()


class TestRedundancyInsights:
    """Tests for redundancy insights."""

    @pytest.mark.asyncio
    async def test_detects_similar_filenames_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for similar filenames."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(
            return_value=[
                AntiPatternInfo(
                    type="similar_filenames",
                    file="test1.md",
                    files=["test1.md", "test2.md"],
                    severity="medium",
                    description="Similar filenames detected",
                ),
                AntiPatternInfo(
                    type="similar_filenames",
                    file="doc1.md",
                    files=["doc1.md", "doc2.md"],
                    severity="medium",
                    description="Similar filenames detected",
                ),
            ]
        )
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(categories=["redundancy"])
        result = result_model.model_dump(mode="json")

        # Assert
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        similar_insights = [i for i in insights if i.get("id") == "similar_filenames"]
        assert len(similar_insights) == 1
        insight = similar_insights[0]
        assert insight["category"] == "redundancy"
        assert insight["severity"] == "medium"
        assert "similar" in str(insight["title"]).lower()


class TestDependencyInsights:
    """Tests for dependency insights."""

    @pytest.mark.asyncio
    async def test_detects_complexity_insight(self, mocker: pytest_mock.MockerFixture):
        """Test generates insight for dependency complexity."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(
                status="analyzed",
                metrics=ComplexityMetrics(max_dependency_depth=8),
                complexity_hotspots=[ComplexityHotspot(file="complex.md", score=50.0)],
                assessment=ComplexityAssessment(
                    score=55,
                    grade="D",
                    status="poor",
                    issues=["High complexity"],
                    recommendations=["Reduce dependencies"],
                ),
            )
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(categories=["dependencies"])
        result = result_model.model_dump(mode="json")

        # Assert
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        complexity_insights = [
            i for i in insights if i.get("id") == "dependency_complexity"
        ]
        assert len(complexity_insights) == 1
        insight = complexity_insights[0]
        assert insight["category"] == "dependencies"
        assert insight["severity"] in ["high", "medium"]
        assert "complexity" in str(insight["title"]).lower()

    @pytest.mark.asyncio
    async def test_detects_orphaned_files_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for orphaned files."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(
            return_value=[
                AntiPatternInfo(
                    type="orphaned_file",
                    file="orphan1.md",
                    files=["orphan1.md"],
                    severity="medium",
                    description="Orphaned file detected",
                ),
                AntiPatternInfo(
                    type="orphaned_file",
                    file="orphan2.md",
                    files=["orphan2.md"],
                    severity="medium",
                    description="Orphaned file detected",
                ),
            ]
        )
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(categories=["dependencies"])
        result = result_model.model_dump(mode="json")

        # Assert
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        orphaned_insights = [i for i in insights if i.get("id") == "orphaned_files"]
        assert len(orphaned_insights) == 1
        insight = orphaned_insights[0]
        assert insight["category"] == "dependencies"
        assert insight["severity"] == "medium"
        assert "orphaned" in str(insight["title"]).lower()


class TestQualityInsights:
    """Tests for quality insights."""

    @pytest.mark.asyncio
    async def test_detects_deep_dependencies_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for deep dependency chains."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(
                status="analyzed",
                metrics=ComplexityMetrics(max_dependency_depth=8),
                assessment=ComplexityAssessment(score=85),
            )
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        result_model = await engine.generate_insights(categories=["quality"])
        result = result_model.model_dump(mode="json")

        # Assert
        insights_raw = result["insights"]
        assert isinstance(insights_raw, list)
        insights: list[dict[str, object]] = cast(list[dict[str, object]], insights_raw)
        deep_dep_insights = [i for i in insights if i.get("id") == "deep_dependencies"]
        assert len(deep_dep_insights) == 1
        insight = deep_dep_insights[0]
        assert insight["category"] == "quality"
        assert insight["severity"] == "medium"
        assert (
            "deep" in str(insight["title"]).lower()
            or "depth" in str(insight["title"]).lower()
        )


class TestSummaryGeneration:
    """Tests for summary generation."""

    def test_generates_excellent_summary_with_no_insights(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates excellent status when no insights."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()
        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        summary = engine.generate_summary([]).model_dump(mode="json")

        # Assert
        assert summary.get("status") == "excellent"
        assert "No significant issues" in str(summary.get("message", ""))
        assert summary.get("top_recommendations", []) == []

    def test_generates_needs_attention_with_high_severity(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates needs_attention status with high severity."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()
        engine = InsightEngine(mock_pattern, mock_structure)

        insights = [
            InsightDict.model_validate(
                {
                    "id": "test1",
                    "category": "quality",
                    "title": "Critical issue",
                    "description": "Critical issue description",
                    "impact_score": 0.9,
                    "severity": "high",
                    "recommendations": ["Fix this"],
                    "estimated_token_savings": 0,
                    "affected_files": [],
                }
            )
        ]

        # Act
        summary = engine.generate_summary(insights).model_dump(mode="json")

        # Assert
        assert summary.get("status") == "needs_attention"
        assert "high-priority" in str(summary.get("message", ""))
        assert summary.get("high_severity_count") == 1

    def test_generates_could_improve_with_multiple_medium(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates could_improve status with multiple medium severity."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()
        engine = InsightEngine(mock_pattern, mock_structure)

        insights = [
            InsightDict.model_validate(
                {
                    "id": f"test{i}",
                    "category": "quality",
                    "title": f"Issue {i}",
                    "description": f"Issue {i} description",
                    "impact_score": 0.6,
                    "severity": "medium",
                    "recommendations": ["Improve this"],
                    "estimated_token_savings": 0,
                    "affected_files": [],
                }
            )
            for i in range(4)
        ]

        # Act
        summary = engine.generate_summary(insights).model_dump(mode="json")

        # Assert
        assert summary.get("status") == "could_improve"
        assert "medium-priority" in str(summary.get("message", ""))
        assert summary.get("medium_severity_count") == 4


class TestInsightDetails:
    """Tests for getting insight details."""

    @pytest.mark.asyncio
    async def test_gets_insight_details_by_id(self, mocker: pytest_mock.MockerFixture):
        """Test retrieves specific insight by ID."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(
            return_value=[
                UnusedFileEntry(
                    file=f"unused{i}.md",
                    status="stale",
                    total_accesses=0,
                    last_access=None,
                )
                for i in range(5)
            ]
        )
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        insight = await engine.get_insight_details("unused_files")

        # Assert
        assert insight is not None
        assert insight.id == "unused_files"
        assert insight.category == "usage"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test returns None for unknown insight ID."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_pattern.get_unused_files = AsyncMock(return_value=[])
        mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])

        mock_structure = mocker.MagicMock()
        mock_structure.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(status="empty", file_count=0)
        )
        mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(status="no_files")
        )

        engine = InsightEngine(mock_pattern, mock_structure)

        # Act
        insight = await engine.get_insight_details("nonexistent_id")

        # Assert
        assert insight is None


class TestExportFormats:
    """Tests for insight export formats."""

    @pytest.mark.asyncio
    async def test_exports_insights_as_json(self, mocker: "pytest_mock.MockerFixture"):
        """Test exports insights in JSON format."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()
        engine = InsightEngine(mock_pattern, mock_structure)

        insights_data = InsightsResultDict.model_validate(
            {
                "generated_at": "2025-01-01T12:00:00Z",
                "total_insights": 1,
                "high_impact_count": 1,
                "medium_impact_count": 0,
                "low_impact_count": 0,
                "estimated_total_token_savings": 0,
                "insights": [
                    {
                        "id": "test",
                        "category": "quality",
                        "title": "Test Insight",
                        "description": "Test description",
                        "impact_score": 0.9,
                        "severity": "high",
                        "recommendations": [],
                        "estimated_token_savings": 0,
                        "affected_files": [],
                    }
                ],
                "summary": {
                    "status": "good",
                    "message": "Test summary",
                    "high_severity_count": 1,
                    "medium_severity_count": 0,
                    "low_severity_count": 0,
                    "top_recommendations": [],
                },
            }
        )

        # Act
        result = await engine.export_insights(insights_data, format="json")

        # Assert
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["total_insights"] == 1
        assert parsed["insights"][0]["id"] == "test"

    @pytest.mark.asyncio
    async def test_exports_insights_as_markdown(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test exports insights in Markdown format."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()
        engine = InsightEngine(mock_pattern, mock_structure)

        insights_data = InsightsResultDict.model_validate(
            {
                "generated_at": "2025-01-01T12:00:00Z",
                "total_insights": 1,
                "high_impact_count": 1,
                "medium_impact_count": 0,
                "low_impact_count": 0,
                "estimated_total_token_savings": 500,
                "insights": [
                    {
                        "id": "test",
                        "category": "quality",
                        "title": "Test Insight",
                        "description": "Test description",
                        "impact_score": 0.8,
                        "severity": "high",
                        "recommendations": ["Do this", "Do that"],
                        "estimated_token_savings": 500,
                        "affected_files": [],
                    }
                ],
                "summary": {
                    "status": "good",
                    "message": "Test summary",
                    "high_severity_count": 1,
                    "medium_severity_count": 0,
                    "low_severity_count": 0,
                    "top_recommendations": [],
                },
            }
        )

        # Act
        result = await engine.export_insights(insights_data, format="markdown")

        # Assert
        assert isinstance(result, str)
        assert "# Memory Bank Insights Report" in result
        assert "Test Insight" in result
        assert "## Summary" in result
        assert "## Insights" in result

    @pytest.mark.asyncio
    async def test_exports_insights_as_text(self, mocker: "pytest_mock.MockerFixture"):
        """Test exports insights in text format."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()
        engine = InsightEngine(mock_pattern, mock_structure)

        insights_data = InsightsResultDict.model_validate(
            {
                "generated_at": "2025-01-01T12:00:00Z",
                "total_insights": 1,
                "high_impact_count": 1,
                "medium_impact_count": 0,
                "low_impact_count": 0,
                "estimated_total_token_savings": 500,
                "insights": [
                    {
                        "id": "test",
                        "category": "quality",
                        "title": "Test Insight",
                        "description": "Test description",
                        "impact_score": 0.8,
                        "severity": "high",
                        "recommendations": [],
                        "estimated_token_savings": 500,
                        "affected_files": [],
                    }
                ],
                "summary": {
                    "status": "good",
                    "message": "Test summary",
                    "high_severity_count": 1,
                    "medium_severity_count": 0,
                    "low_severity_count": 0,
                    "top_recommendations": [],
                },
            }
        )

        # Act
        result = await engine.export_insights(insights_data, format="text")

        # Assert
        assert isinstance(result, str)
        assert "MEMORY BANK INSIGHTS REPORT" in result
        assert "Test Insight" in result
        assert "SUMMARY:" in result

    @pytest.mark.asyncio
    async def test_raises_error_for_invalid_format(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test raises error for invalid export format."""
        # Arrange
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()
        engine = InsightEngine(mock_pattern, mock_structure)

        insights_data = InsightsResultDict.model_validate(
            {
                "generated_at": "2025-01-01T12:00:00Z",
                "total_insights": 0,
                "high_impact_count": 0,
                "medium_impact_count": 0,
                "low_impact_count": 0,
                "estimated_total_token_savings": 0,
                "insights": [],
                "summary": {
                    "status": "excellent",
                    "message": "No issues",
                    "high_severity_count": 0,
                    "medium_severity_count": 0,
                    "low_severity_count": 0,
                    "top_recommendations": [],
                },
            }
        )

        # Act & Assert
        with pytest.raises(MemoryBankError, match="Unsupported export format"):
            _ = await engine.export_insights(insights_data, format="invalid")
