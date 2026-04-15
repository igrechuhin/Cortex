"""Quality category tests for insight_engine insight generation."""

from typing import cast
from unittest.mock import AsyncMock

import pytest
import pytest_mock

from cortex.analysis.insight_engine import InsightEngine
from cortex.analysis.models import (
    ComplexityAnalysisResult,
    ComplexityAnalysisStatus,
    ComplexityAssessment,
    ComplexityMetrics,
)
from cortex.core.models import FileOrganizationResult


def _build_engine(
    mocker: pytest_mock.MockerFixture, *, complexity: ComplexityAnalysisResult
) -> InsightEngine:
    pattern = mocker.MagicMock()
    pattern.get_unused_files = AsyncMock(return_value=[])
    pattern.get_co_access_patterns = AsyncMock(return_value=[])
    structure = mocker.MagicMock()
    structure.analyze_file_organization = AsyncMock(
        return_value=FileOrganizationResult(status="empty", file_count=0)
    )
    structure.detect_anti_patterns = AsyncMock(return_value=[])
    structure.measure_complexity_metrics = AsyncMock(return_value=complexity)
    return InsightEngine(pattern, structure)


class TestQualityInsights:
    """Tests for quality insights."""

    @pytest.mark.asyncio
    async def test_detects_deep_dependencies_insight(
        self, mocker: pytest_mock.MockerFixture
    ):
        """Test generates insight for deep dependency chains."""
        engine = _build_engine(
            mocker,
            complexity=ComplexityAnalysisResult(
                status=ComplexityAnalysisStatus.ANALYZED,
                metrics=ComplexityMetrics(max_dependency_depth=8),
                assessment=ComplexityAssessment(score=85),
            ),
        )
        result = (await engine.generate_insights(categories=["quality"])).model_dump(
            mode="json"
        )
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
