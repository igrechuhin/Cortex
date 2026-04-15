"""Tests for analysis operations helper functions."""

import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.analysis.models import (
    AntiPatternInfo,
    AntiPatternKind,
    ComplexityAnalysisResult,
    ComplexityAnalysisStatus,
    ComplexityMetrics,
    InsightsResult,
    SeverityLevel,
    SummaryModel,
    SummaryStatus,
)
from cortex.core.models import DependencyGraphDict, FileOrganizationResult, RiskLevel
from cortex.refactoring.consolidation_detector import (
    ConsolidationOpportunity,
)
from cortex.refactoring.models import (
    ReorganizationImpactModel,
    ReorganizationPlanModel,
)
from cortex.refactoring.split_recommender import SplitRecommendation
from cortex.tools.context.analysis_run_helpers import (
    analyze_insights,
    analyze_structure,
    analyze_usage_patterns,
    dispatch_analysis_target,
    get_analysis_managers,
)
from cortex.tools.refactoring.operation_helpers import (
    convert_opportunities_to_dict,
    convert_recommendations_to_dict,
    get_refactoring_managers,
    get_structure_data,
    handle_preview_mode,
    suggest_consolidation,
    suggest_reorganization,
    suggest_splits,
    validate_refactoring_type,
)
from tests.helpers.managers import make_test_managers


@pytest.fixture(autouse=True)
def _skip_usage_context_init():  # pyright: ignore[reportUnusedFunction]
    """Avoid slow resolve_project_root + get_managers in ensure_usage_context."""
    with patch("cortex.core.mcp_stability_usage.get_current_managers", return_value={}):
        yield


def _make_mock_insights(
    status: SummaryStatus = SummaryStatus.SUCCESS,
) -> InsightsResult:
    """Build a reusable InsightsResult mock."""
    return InsightsResult(
        generated_at="2026-01-01T00:00:00",
        total_insights=1,
        high_impact_count=1,
        medium_impact_count=0,
        low_impact_count=0,
        estimated_total_token_savings=0,
        insights=[],
        summary=SummaryModel(status=status),
    )


class TestAnalyzeUsagePatterns:
    """Test _analyze_usage_patterns helper."""

    @pytest.mark.asyncio
    async def test_analyze_usage_patterns_success(self) -> None:
        """Test successful usage patterns analysis."""
        mock_analyzer = MagicMock()
        mock_analyzer.get_access_frequency = AsyncMock(
            return_value={"file1.md": 10, "file2.md": 5}
        )
        mock_analyzer.get_co_access_patterns = AsyncMock(
            return_value=[{"files": ["file1.md", "file2.md"], "count": 3}]
        )
        mock_analyzer.get_task_patterns = AsyncMock(
            return_value={"task1": ["file1.md"]}
        )
        mock_analyzer.get_unused_files = AsyncMock(return_value=["old.md"])

        result = await analyze_usage_patterns(mock_analyzer, 30)

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "usage_patterns"
        assert result_data["time_window_days"] == 30
        assert "patterns" in result_data
        assert result_data["patterns"]["unused_files"] == ["old.md"]


class TestAnalyzeStructure:
    """Test _analyze_structure helper."""

    @pytest.mark.asyncio
    async def test_analyze_structure_success(self) -> None:
        """Test successful structure analysis."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(
                status=ComplexityAnalysisStatus.ANALYZED, file_count=10
            )
        )
        mock_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        mock_analyzer.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(
                status=ComplexityAnalysisStatus.ANALYZED,
                metrics=ComplexityMetrics(max_dependency_depth=2),
            )
        )

        result = await analyze_structure(mock_analyzer)

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "structure"
        assert result_data["analysis"]["organization"]["file_count"] == 10


class TestAnalyzeInsights:
    """Test _analyze_insights helper."""

    @pytest.mark.asyncio
    async def test_analyze_insights_json_format(self) -> None:
        """Test insights analysis with JSON format."""
        mock_engine = MagicMock()
        mock_insights = _make_mock_insights()
        mock_engine.generate_insights = AsyncMock(return_value=mock_insights)

        result = await analyze_insights(mock_engine, "json", None)

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "insights"
        assert result_data["format"] == "json"

    @pytest.mark.asyncio
    async def test_analyze_insights_markdown_format(self) -> None:
        """Test insights analysis with markdown export format."""
        mock_engine = MagicMock()
        mock_insights = _make_mock_insights()
        mock_engine.generate_insights = AsyncMock(return_value=mock_insights)
        mock_engine.export_insights = AsyncMock(return_value="# Markdown Report")

        result = await analyze_insights(mock_engine, "markdown", None)

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["format"] == "markdown"
        assert result_data["insights"] == "# Markdown Report"

    @pytest.mark.asyncio
    async def test_analyze_insights_text_format(self) -> None:
        """Test insights analysis with text export format."""
        mock_engine = MagicMock()
        mock_insights = _make_mock_insights()
        mock_engine.generate_insights = AsyncMock(return_value=mock_insights)
        mock_engine.export_insights = AsyncMock(return_value="Text Report")

        result = await analyze_insights(mock_engine, "text", ["duplication"])

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["format"] == "text"
        assert result_data["insights"] == "Text Report"


class TestGetAnalysisManagers:
    """Test _get_analysis_managers helper."""

    @pytest.mark.asyncio
    async def test_get_analysis_managers_success(self) -> None:
        """Test successful retrieval of analysis managers."""
        mock_pattern = MagicMock()
        mock_structure = MagicMock()
        mock_insight = MagicMock()

        mgrs = make_test_managers(
            pattern_analyzer=mock_pattern,
            structure_analyzer=mock_structure,
            insight_engine=mock_insight,
        )

        pattern, structure, insight = await get_analysis_managers(mgrs)

        assert pattern == mock_pattern
        assert structure == mock_structure
        assert insight == mock_insight


class TestDispatchAnalysisTarget:
    """Test _dispatch_analysis_target helper."""

    @pytest.mark.asyncio
    async def test_dispatch_usage_patterns(self) -> None:
        """Test dispatching usage patterns analysis."""
        mock_pattern_analyzer = MagicMock()
        mock_pattern_analyzer.get_access_frequency = AsyncMock(return_value={})
        mock_pattern_analyzer.get_co_access_patterns = AsyncMock(return_value=[])
        mock_pattern_analyzer.get_task_patterns = AsyncMock(return_value={})
        mock_pattern_analyzer.get_unused_files = AsyncMock(return_value=[])
        analyzers = (mock_pattern_analyzer, MagicMock(), MagicMock())

        result = await dispatch_analysis_target(
            "usage_patterns", analyzers, 30, "json", None
        )

        result_data = json.loads(result)
        assert result_data["target"] == "usage_patterns"

    @pytest.mark.asyncio
    async def test_dispatch_structure(self) -> None:
        """Test dispatching structure analysis."""
        mock_structure_analyzer = MagicMock()
        mock_structure_analyzer.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(
                status=ComplexityAnalysisStatus.ANALYZED, file_count=1
            )
        )
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(
                status=ComplexityAnalysisStatus.ANALYZED
            )
        )
        analyzers = (MagicMock(), mock_structure_analyzer, MagicMock())

        result = await dispatch_analysis_target(
            "structure", analyzers, None, "json", None
        )

        result_data = json.loads(result)
        assert result_data["target"] == "structure"

    @pytest.mark.asyncio
    async def test_dispatch_insights(self) -> None:
        """Test dispatching insights analysis."""
        mock_insight_engine = MagicMock()
        mock_insight_engine.generate_insights = AsyncMock(
            return_value=_make_mock_insights()
        )
        analyzers = (MagicMock(), MagicMock(), mock_insight_engine)

        result = await dispatch_analysis_target(
            "insights", analyzers, None, "json", None
        )

        result_data = json.loads(result)
        assert result_data["target"] == "insights"

    @pytest.mark.asyncio
    async def test_dispatch_invalid_target(self) -> None:
        """Test dispatching with invalid target."""
        analyzers = (MagicMock(), MagicMock(), MagicMock())

        result = await dispatch_analysis_target(
            "invalid", analyzers, None, "json", None
        )

        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid target: invalid" in result_data["error"]


class TestValidateRefactoringType:
    """Test _validate_refactoring_type helper."""

    def test_validate_valid_consolidation(self) -> None:
        assert validate_refactoring_type("consolidation") is None

    def test_validate_valid_splits(self) -> None:
        assert validate_refactoring_type("splits") is None

    def test_validate_valid_reorganization(self) -> None:
        assert validate_refactoring_type("reorganization") is None

    def test_validate_invalid_type(self) -> None:
        result = validate_refactoring_type("invalid")
        assert result is not None
        result_data = json.loads(result)
        assert result_data["status"] == "error"


class TestGetRefactoringManagers:
    """Test _get_refactoring_managers helper."""

    @pytest.mark.asyncio
    async def test_get_refactoring_managers_success(self) -> None:
        """Test successful retrieval of refactoring managers."""
        mock_consolidation = MagicMock()
        mock_split = MagicMock()
        mock_reorganization = MagicMock()
        mgrs = make_test_managers(
            consolidation_detector=mock_consolidation,
            split_recommender=mock_split,
            reorganization_planner=mock_reorganization,
        )

        consolidation, split, reorganization = await get_refactoring_managers(mgrs)

        assert consolidation == mock_consolidation
        assert split == mock_split
        assert reorganization == mock_reorganization


class TestHandlePreviewMode:
    """Test _handle_preview_mode helper."""

    def test_handle_preview_mode_returns_message(self) -> None:
        result = handle_preview_mode("consolidation_001")
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["preview_mode"] is True
        assert result_data["suggestion_id"] == "consolidation_001"


class TestConvertOpportunitiesToDict:
    """Test _convert_opportunities_to_dict helper."""

    def _make_opp(self, opp_id: str = "opp1") -> ConsolidationOpportunity:
        """Create a test ConsolidationOpportunity."""
        return ConsolidationOpportunity(
            opportunity_id=opp_id,
            opportunity_type="exact_duplicate",
            affected_files=["a.md", "b.md"],
            common_content="Hello",
            similarity_score=0.85,
            token_savings=10,
            suggested_action="extract",
            extraction_target="shared.md",
            transclusion_syntax=["{{include:shared.md}}"],
        )

    def test_convert_dataclass_opportunities(self) -> None:
        opps = [self._make_opp("opp1"), self._make_opp("opp2")]
        result = convert_opportunities_to_dict(opps)
        assert len(result) == 2
        assert result[0]["opportunity_id"] == "opp1"

    def test_convert_object_with_to_dict(self) -> None:
        mock_opp = MagicMock()
        mock_opp.to_dict.return_value = {"id": "opp1", "similarity": 0.85}
        result = convert_opportunities_to_dict([mock_opp])
        assert len(result) == 1
        assert result[0]["id"] == "opp1"

    def test_convert_object_without_to_dict(self) -> None:
        opp = self._make_opp("test")
        result = convert_opportunities_to_dict([opp])
        assert len(result) == 1
        assert result[0]["opportunity_id"] == "test"


class TestConvertRecommendationsToDict:
    """Test _convert_recommendations_to_dict helper."""

    def _make_rec(self, rec_id: str = "rec1") -> SplitRecommendation:
        return SplitRecommendation(
            recommendation_id=rec_id,
            file_path="large.md",
            reason="Large file",
            split_strategy="by_size",
            split_points=[],
            estimated_impact={},
            new_structure={},
        )

    def test_convert_dataclass_recommendations(self) -> None:
        recs = [self._make_rec("rec1"), self._make_rec("rec2")]
        result = convert_recommendations_to_dict(recs)
        assert len(result) == 2
        assert result[0]["recommendation_id"] == "rec1"

    def test_convert_object_with_to_dict(self) -> None:
        mock_rec = MagicMock()
        mock_rec.to_dict.return_value = {"id": "rec1", "file": "large.md"}
        result = convert_recommendations_to_dict([mock_rec])
        assert len(result) == 1
        assert result[0]["id"] == "rec1"

    def test_convert_object_without_to_dict(self) -> None:
        rec = self._make_rec("test")
        result = convert_recommendations_to_dict([rec])
        assert len(result) == 1
        assert result[0]["recommendation_id"] == "test"


class TestSuggestConsolidation:
    """Test _suggest_consolidation helper."""

    @pytest.mark.asyncio
    async def test_suggest_consolidation_default_similarity(self) -> None:
        mock_detector = MagicMock()
        mock_detector.detect_opportunities = AsyncMock(return_value=[])

        result = await suggest_consolidation(mock_detector, None)

        assert mock_detector.min_similarity == 0.80
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["type"] == "consolidation"

    @pytest.mark.asyncio
    async def test_suggest_consolidation_custom_similarity(self) -> None:
        mock_detector = MagicMock()
        opp = ConsolidationOpportunity(
            opportunity_id="opp1",
            opportunity_type="exact_duplicate",
            affected_files=["a.md", "b.md"],
            common_content="Hello",
            similarity_score=0.90,
            token_savings=10,
            suggested_action="extract",
            extraction_target="shared.md",
            transclusion_syntax=["{{include:shared.md}}"],
        )
        mock_detector.detect_opportunities = AsyncMock(return_value=[opp])

        result = await suggest_consolidation(mock_detector, 0.85)

        assert mock_detector.min_similarity == 0.85
        result_data = json.loads(result)
        assert len(result_data["opportunities"]) == 1


class TestSuggestSplits:
    """Test _suggest_splits helper."""

    @pytest.mark.asyncio
    async def test_suggest_splits_default_threshold(self) -> None:
        mock_recommender = MagicMock()
        mock_recommender.suggest_file_splits = AsyncMock(return_value=[])

        result = await suggest_splits(mock_recommender, None)

        assert mock_recommender.max_file_size == 2500
        result_data = json.loads(result)
        assert result_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_suggest_splits_custom_threshold(self) -> None:
        mock_recommender = MagicMock()
        rec = SplitRecommendation(
            recommendation_id="split1",
            file_path="large.md",
            reason="Large file",
            split_strategy="by_size",
            split_points=[],
            estimated_impact={},
            new_structure={},
        )
        mock_recommender.suggest_file_splits = AsyncMock(return_value=[rec])

        result = await suggest_splits(mock_recommender, 8000)

        assert mock_recommender.max_file_size == 2000
        result_data = json.loads(result)
        assert len(result_data["recommendations"]) == 1


def _make_structure_analyzer_with_anti_patterns() -> MagicMock:
    """Build a mock structure analyzer with anti-patterns for tests."""
    mock_sa = MagicMock()
    mock_sa.analyze_file_organization = AsyncMock(
        return_value=FileOrganizationResult(
            status=ComplexityAnalysisStatus.ANALYZED, file_count=10
        )
    )
    mock_sa.detect_anti_patterns = AsyncMock(
        return_value=[
            AntiPatternInfo(
                type=AntiPatternKind.NAMING_INCONSISTENCY,
                severity=SeverityLevel.LOW,
                description="Naming inconsistency",
            )
        ]
    )
    mock_sa.measure_complexity_metrics = AsyncMock(
        return_value=ComplexityAnalysisResult(
            status=ComplexityAnalysisStatus.ANALYZED,
            metrics=ComplexityMetrics(max_dependency_depth=2),
        )
    )
    return mock_sa


class TestGetStructureData:
    """Test _get_structure_data helper."""

    @pytest.mark.asyncio
    async def test_get_structure_data_success(self) -> None:
        mock_sa = _make_structure_analyzer_with_anti_patterns()
        mgrs = make_test_managers(structure_analyzer=mock_sa)

        result = await get_structure_data(mgrs)

        analysis = cast(dict[str, object], result["analysis"])
        file_org = cast(dict[str, object], analysis["file_organization"])
        assert file_org["file_count"] == 10
        anti_patterns = cast(list[object], analysis["anti_patterns"])
        assert len(anti_patterns) == 1


def _make_reorganization_mocks() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build shared mocks for reorganization tests."""
    mock_structure_analyzer = MagicMock()
    mock_structure_analyzer.analyze_file_organization = AsyncMock(
        return_value=FileOrganizationResult(
            status=ComplexityAnalysisStatus.ANALYZED, file_count=1
        )
    )
    mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
    mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
        return_value=ComplexityAnalysisResult(status=ComplexityAnalysisStatus.ANALYZED)
    )
    mock_graph = MagicMock()
    mock_graph.to_dict.return_value = DependencyGraphDict()

    return mock_structure_analyzer, mock_graph, MagicMock()


def _make_reorg_plan(plan_id: str, goal: str) -> ReorganizationPlanModel:
    """Build a ReorganizationPlanModel for tests."""
    return ReorganizationPlanModel(
        plan_id=plan_id,
        optimization_goal=goal,
        estimated_impact=ReorganizationImpactModel(
            files_moved=0,
            categories_created=0,
            dependency_depth_reduction=0.0,
            complexity_reduction=0.0,
            maintainability_improvement=0.0,
            navigation_improvement=0.0,
            estimated_effort=RiskLevel.LOW,
        ),
    )


class TestSuggestReorganization:
    """Test _suggest_reorganization helper."""

    @pytest.mark.asyncio
    async def test_suggest_reorganization_default_goal(self) -> None:
        mock_planner = MagicMock()
        mock_planner.create_reorganization_plan = AsyncMock(
            return_value=_make_reorg_plan("plan-1", "dependency_depth")
        )
        mock_structure, mock_graph, _ = _make_reorganization_mocks()
        mgrs = make_test_managers(
            structure_analyzer=mock_structure,
            graph=mock_graph,
        )

        result = await suggest_reorganization(mock_planner, mgrs, None)

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["goal"] == "dependency_depth"

    @pytest.mark.asyncio
    async def test_suggest_reorganization_custom_goal(self) -> None:
        mock_planner = MagicMock()
        mock_planner.create_reorganization_plan = AsyncMock(
            return_value=_make_reorg_plan("plan-2", "category")
        )
        mock_structure, mock_graph, _ = _make_reorganization_mocks()
        mgrs = make_test_managers(
            structure_analyzer=mock_structure,
            graph=mock_graph,
        )

        result = await suggest_reorganization(mock_planner, mgrs, "category")

        result_data = json.loads(result)
        assert result_data["goal"] == "category"
