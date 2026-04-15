"""
Tests for insight_engine.py - Insight generation functionality.

This test module covers:
- InsightEngine initialization
- Comprehensive insight generation
- Category-specific insight generation (usage, organization, redundancy,
  dependencies, quality)
- Summary generation
- Export formats (JSON, Markdown, Text)
- Impact scoring and filtering
"""

from typing import cast
from unittest.mock import AsyncMock

import pytest
import pytest_mock

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.models import (
    AntiPatternInfo,
    AntiPatternKind,
    CoAccessPattern,
    ComplexityAnalysisResult,
    ComplexityAnalysisStatus,
    ComplexityAssessment,
    ComplexityAssessmentStatus,
    ComplexityMetrics,
    SeverityLevel,
)
from cortex.analysis.pattern_types import UnusedFileEntry
from cortex.core.models import FileOrganizationResult, FileSizeEntry
from cortex.structure.models import HealthGrade


def _build_empty_engine(mocker: pytest_mock.MockerFixture) -> InsightEngine:
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
            status=ComplexityAnalysisStatus.ANALYZED,
            metrics=ComplexityMetrics(max_dependency_depth=3),
            assessment=ComplexityAssessment(
                score=95,
                grade=HealthGrade.A,
                status=ComplexityAssessmentStatus.EXCELLENT,
            ),
        )
    )
    return InsightEngine(mock_pattern, mock_structure)


def _build_usage_engine(
    mocker: pytest_mock.MockerFixture, *, co_access_count: int = 0
) -> InsightEngine:
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
        return_value=[CoAccessPattern(file_1="a.md", file_2="b.md")] * co_access_count
    )
    mock_structure = mocker.MagicMock()
    mock_structure.analyze_file_organization = AsyncMock(
        return_value=FileOrganizationResult(status="empty", file_count=0)
    )
    mock_structure.detect_anti_patterns = AsyncMock(return_value=[])
    mock_structure.measure_complexity_metrics = AsyncMock(
        return_value=ComplexityAnalysisResult(status=ComplexityAnalysisStatus.NO_FILES)
    )
    return InsightEngine(mock_pattern, mock_structure)


def _all_categories_unused_entries() -> list[UnusedFileEntry]:
    return [
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


def _all_categories_structure_result() -> FileOrganizationResult:
    return FileOrganizationResult(
        status=ComplexityAnalysisStatus.ANALYZED,
        file_count=5,
        issues=["3 files very large"],
        largest_files=[
            FileSizeEntry(file="large1.md", size_bytes=100000, tokens=0),
            FileSizeEntry(file="large2.md", size_bytes=90000, tokens=0),
        ],
        smallest_files=[],
    )


def _all_categories_anti_patterns() -> list[AntiPatternInfo]:
    return [
        AntiPatternInfo(
            type=AntiPatternKind.SIMILAR_FILENAMES,
            file="test1.md",
            files=["test1.md", "test2.md"],
            severity=SeverityLevel.MEDIUM,
            description="Similar filenames detected",
        ),
        AntiPatternInfo(
            type=AntiPatternKind.SIMILAR_FILENAMES,
            file="doc1.md",
            files=["doc1.md", "doc2.md"],
            severity=SeverityLevel.MEDIUM,
            description="Similar filenames detected",
        ),
    ]


def _build_all_categories_engine(mocker: pytest_mock.MockerFixture) -> InsightEngine:
    mock_pattern = mocker.MagicMock()
    mock_pattern.get_unused_files = AsyncMock(
        return_value=_all_categories_unused_entries()
    )
    mock_pattern.get_co_access_patterns = AsyncMock(return_value=[])
    mock_structure = mocker.MagicMock()
    mock_structure.analyze_file_organization = AsyncMock(
        return_value=_all_categories_structure_result()
    )
    mock_structure.detect_anti_patterns = AsyncMock(
        return_value=_all_categories_anti_patterns()
    )
    mock_structure.measure_complexity_metrics = AsyncMock(
        return_value=ComplexityAnalysisResult(
            status=ComplexityAnalysisStatus.ANALYZED,
            metrics=ComplexityMetrics(max_dependency_depth=8),
            assessment=ComplexityAssessment(
                score=55,
                grade=HealthGrade.D,
                status=ComplexityAssessmentStatus.POOR,
                issues=["High complexity"],
                recommendations=["Reduce dependencies"],
            ),
        )
    )
    return InsightEngine(mock_pattern, mock_structure)


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
        engine = _build_empty_engine(mocker)

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
        engine = _build_all_categories_engine(mocker)

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
        engine = _build_usage_engine(mocker, co_access_count=5)

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
        engine = _build_usage_engine(mocker)

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
        engine = _build_usage_engine(mocker, co_access_count=5)

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
