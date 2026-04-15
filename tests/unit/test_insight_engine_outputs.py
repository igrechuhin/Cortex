"""
Tests for insight_engine.py output helpers and export formats.
"""

import json
from unittest.mock import AsyncMock

import pytest
import pytest_mock

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.insight_types import InsightDict, InsightsResultDict
from cortex.analysis.models import ComplexityAnalysisResult, ComplexityAnalysisStatus
from cortex.analysis.pattern_types import UnusedFileEntry
from cortex.core.exceptions import MemoryBankError
from cortex.core.models import FileOrganizationResult


def _build_engine(mocker: pytest_mock.MockerFixture) -> InsightEngine:
    return InsightEngine(mocker.MagicMock(), mocker.MagicMock())


_BASE_RESULT: dict[str, object] = {
    "generated_at": "2025-01-01T12:00:00Z",
    "total_insights": 1,
    "high_impact_count": 1,
    "medium_impact_count": 0,
    "low_impact_count": 0,
    "summary": {
        "status": "good",
        "message": "Test summary",
        "high_severity_count": 1,
        "medium_severity_count": 0,
        "low_severity_count": 0,
        "top_recommendations": [],
    },
}


def _build_insights_result(
    *, token_savings: int = 0, recommendations: list[str] | None = None
) -> InsightsResultDict:
    return InsightsResultDict.model_validate(
        _BASE_RESULT
        | {
            "estimated_total_token_savings": token_savings,
            "insights": [
                {
                    "id": "test",
                    "category": "quality",
                    "title": "Test Insight",
                    "description": "Test description",
                    "impact_score": 0.8,
                    "severity": "high",
                    "recommendations": recommendations or [],
                    "estimated_token_savings": token_savings,
                    "affected_files": [],
                }
            ],
        }
    )


class TestSummaryGeneration:
    """Tests for summary generation."""

    def test_generates_excellent_summary_with_no_insights(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates excellent status when no insights."""
        mock_pattern = mocker.MagicMock()
        mock_structure = mocker.MagicMock()
        engine = InsightEngine(mock_pattern, mock_structure)

        summary = engine.generate_summary([]).model_dump(mode="json")

        assert summary.get("status") == "excellent"
        assert "No significant issues" in str(summary.get("message", ""))
        assert summary.get("top_recommendations", []) == []

    def test_generates_needs_attention_with_high_severity(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates needs_attention status with high severity."""
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

        summary = engine.generate_summary(insights).model_dump(mode="json")

        assert summary.get("status") == "needs_attention"
        assert "high-priority" in str(summary.get("message", ""))
        assert summary.get("high_severity_count") == 1

    def test_generates_could_improve_with_multiple_medium(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates could_improve status with multiple medium severity."""
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

        summary = engine.generate_summary(insights).model_dump(mode="json")

        assert summary.get("status") == "could_improve"
        assert "medium-priority" in str(summary.get("message", ""))
        assert summary.get("medium_severity_count") == 4


class TestInsightDetails:
    """Tests for getting insight details."""

    @pytest.mark.asyncio
    async def test_gets_insight_details_by_id(self, mocker: pytest_mock.MockerFixture):
        """Test retrieves specific insight by ID."""
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
            return_value=ComplexityAnalysisResult(
                status=ComplexityAnalysisStatus.NO_FILES
            )
        )

        engine = InsightEngine(mock_pattern, mock_structure)
        insight = await engine.get_insight_details("unused_files")

        assert insight is not None
        assert insight.id == "unused_files"
        assert insight.category == "usage"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test returns None for unknown insight ID."""
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
                status=ComplexityAnalysisStatus.NO_FILES
            )
        )

        engine = InsightEngine(mock_pattern, mock_structure)
        insight = await engine.get_insight_details("nonexistent_id")

        assert insight is None


class TestExportFormats:
    """Tests for insight export formats."""

    @pytest.mark.asyncio
    async def test_exports_insights_as_json(self, mocker: "pytest_mock.MockerFixture"):
        """Test exports insights in JSON format."""
        engine = _build_engine(mocker)
        insights_data = _build_insights_result()
        result = await engine.export_insights(insights_data, format="json")
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["total_insights"] == 1
        assert parsed["insights"][0]["id"] == "test"

    @pytest.mark.asyncio
    async def test_exports_insights_as_markdown(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test exports insights in Markdown format."""
        engine = _build_engine(mocker)
        insights_data = _build_insights_result(
            token_savings=500, recommendations=["Do this", "Do that"]
        )
        result = await engine.export_insights(insights_data, format="markdown")
        assert isinstance(result, str)
        assert "# Memory Bank Insights Report" in result
        assert "Test Insight" in result
        assert "## Summary" in result
        assert "## Insights" in result

    @pytest.mark.asyncio
    async def test_exports_insights_as_text(self, mocker: "pytest_mock.MockerFixture"):
        """Test exports insights in text format."""
        engine = _build_engine(mocker)
        insights_data = _build_insights_result(token_savings=500)
        result = await engine.export_insights(insights_data, format="text")
        assert isinstance(result, str)
        assert "MEMORY BANK INSIGHTS REPORT" in result
        assert "Test Insight" in result
        assert "SUMMARY:" in result

    @pytest.mark.asyncio
    async def test_raises_error_for_invalid_format(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test raises error for invalid export format."""
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

        with pytest.raises(MemoryBankError, match="Unsupported export format"):
            _ = await engine.export_insights(insights_data, format="invalid")
