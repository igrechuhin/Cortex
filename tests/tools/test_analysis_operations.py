"""Tests for analysis operations module."""

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.analysis.models import (
    AntiPatternInfo,
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
    RefactoringSuggestionType,
    ReorganizationImpactModel,
    ReorganizationPlanModel,
)
from cortex.refactoring.split_recommender import SplitRecommendation
from cortex.tools.context.analysis_operations import (
    analyze,
    analyze_resource,
)
from cortex.tools.context.analysis_run_helpers import (
    analyze_insights,
    analyze_structure,
    analyze_usage_patterns,
    dispatch_analysis_target,
    get_analysis_managers,
)
from cortex.tools.refactoring import (
    suggest_refactoring,
    suggest_refactoring_resource,
)
from cortex.tools.refactoring.operation_helpers import (
    convert_opportunities_to_dict,
    convert_recommendations_to_dict,
    get_refactoring_managers,
    get_structure_data,
    handle_preview_mode,
    process_refactoring_request,
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


class TestAnalyzeUsagePatterns:
    """Test _analyze_usage_patterns helper."""

    @pytest.mark.asyncio
    async def test_analyze_usage_patterns_success(self) -> None:
        """Test successful usage patterns analysis."""
        # Arrange
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

        # Act
        result = await analyze_usage_patterns(mock_analyzer, 30)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "usage_patterns"
        assert result_data["time_window_days"] == 30
        assert "patterns" in result_data
        assert result_data["patterns"]["access_frequency"] == {
            "file1.md": 10,
            "file2.md": 5,
        }
        assert result_data["patterns"]["unused_files"] == ["old.md"]


class TestAnalyzeStructure:
    """Test _analyze_structure helper."""

    @pytest.mark.asyncio
    async def test_analyze_structure_success(self) -> None:
        """Test successful structure analysis."""
        # Arrange
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

        # Act
        result = await analyze_structure(mock_analyzer)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "structure"
        assert result_data["analysis"]["organization"]["file_count"] == 10
        assert (
            result_data["analysis"]["complexity_metrics"]["metrics"][
                "max_dependency_depth"
            ]
            == 2
        )


class TestAnalyzeInsights:
    """Test _analyze_insights helper."""

    @pytest.mark.asyncio
    async def test_analyze_insights_json_format(self) -> None:
        """Test insights analysis with JSON format."""
        # Arrange
        mock_engine = MagicMock()
        mock_insights = InsightsResult(
            generated_at="2026-01-01T00:00:00",
            total_insights=1,
            high_impact_count=1,
            medium_impact_count=0,
            low_impact_count=0,
            estimated_total_token_savings=0,
            insights=[],
            summary=SummaryModel(status=SummaryStatus.SUCCESS),
        )
        mock_engine.generate_insights = AsyncMock(return_value=mock_insights)

        # Act
        result = await analyze_insights(mock_engine, "json", None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "insights"
        assert result_data["format"] == "json"
        assert result_data["insights"] == mock_insights.model_dump(mode="json")

    @pytest.mark.asyncio
    async def test_analyze_insights_markdown_format(self) -> None:
        """Test insights analysis with markdown export format."""
        # Arrange
        mock_engine = MagicMock()
        mock_insights = InsightsResult(
            generated_at="2026-01-01T00:00:00",
            total_insights=1,
            high_impact_count=1,
            medium_impact_count=0,
            low_impact_count=0,
            estimated_total_token_savings=0,
            insights=[],
            summary=SummaryModel(status=SummaryStatus.SUCCESS),
        )
        mock_engine.generate_insights = AsyncMock(return_value=mock_insights)
        mock_engine.export_insights = AsyncMock(return_value="# Markdown Report")

        # Act
        result = await analyze_insights(mock_engine, "markdown", None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "insights"
        assert result_data["format"] == "markdown"
        assert result_data["insights"] == "# Markdown Report"
        mock_engine.export_insights.assert_called_once_with(
            mock_insights, format="markdown"
        )

    @pytest.mark.asyncio
    async def test_analyze_insights_text_format(self) -> None:
        """Test insights analysis with text export format."""
        # Arrange
        mock_engine = MagicMock()
        mock_insights = InsightsResult(
            generated_at="2026-01-01T00:00:00",
            total_insights=1,
            high_impact_count=1,
            medium_impact_count=0,
            low_impact_count=0,
            estimated_total_token_savings=0,
            insights=[],
            summary=SummaryModel(status=SummaryStatus.SUCCESS),
        )
        mock_engine.generate_insights = AsyncMock(return_value=mock_insights)
        mock_engine.export_insights = AsyncMock(return_value="Text Report")

        # Act
        result = await analyze_insights(mock_engine, "text", ["duplication"])

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "insights"
        assert result_data["format"] == "text"
        assert result_data["insights"] == "Text Report"
        mock_engine.export_insights.assert_called_once_with(
            mock_insights, format="text"
        )


class TestGetAnalysisManagers:
    """Test _get_analysis_managers helper."""

    @pytest.mark.asyncio
    async def test_get_analysis_managers_success(self) -> None:
        """Test successful retrieval of analysis managers."""
        # Arrange
        mock_pattern = MagicMock()
        mock_structure = MagicMock()
        mock_insight = MagicMock()

        mgrs = make_test_managers(
            pattern_analyzer=mock_pattern,
            structure_analyzer=mock_structure,
            insight_engine=mock_insight,
        )

        # Act
        pattern, structure, insight = await get_analysis_managers(mgrs)

        # Assert
        assert pattern == mock_pattern
        assert structure == mock_structure
        assert insight == mock_insight


@pytest.mark.timeout(10)
class TestAnalyzeHandler:
    """Test main analyze handler."""

    @pytest.mark.asyncio
    async def test_analyze_usage_patterns(self, tmp_path: Path) -> None:
        """Test analyzing usage patterns."""
        # Arrange
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_pattern_analyzer = MagicMock()
            mock_pattern_analyzer.get_access_frequency = AsyncMock(
                return_value={"file1.md": 10}
            )
            mock_pattern_analyzer.get_co_access_patterns = AsyncMock(return_value=[])
            mock_pattern_analyzer.get_task_patterns = AsyncMock(return_value={})
            mock_pattern_analyzer.get_unused_files = AsyncMock(return_value=[])

            mock_get_managers.return_value = make_test_managers(
                pattern_analyzer=mock_pattern_analyzer,
                structure_analyzer=MagicMock(),
                insight_engine=MagicMock(),
            )

            # Act
            result = await analyze(
                target="usage_patterns",
                time_window_days=60,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["target"] == "usage_patterns"
            assert result_data["time_window_days"] == 60

    @pytest.mark.asyncio
    async def test_analyze_structure(self, tmp_path: Path) -> None:
        """Test analyzing structure."""
        # Arrange
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_structure_analyzer = MagicMock()
            mock_structure_analyzer.analyze_file_organization = AsyncMock(
                return_value=FileOrganizationResult(
                    status=ComplexityAnalysisStatus.ANALYZED, file_count=5
                )
            )
            mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
            mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
                return_value=ComplexityAnalysisResult(
                    status=ComplexityAnalysisStatus.ANALYZED
                )
            )
            mock_get_managers.return_value = make_test_managers(
                pattern_analyzer=MagicMock(),
                structure_analyzer=mock_structure_analyzer,
                insight_engine=MagicMock(),
            )

            # Act
            result = await analyze(target="structure")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["target"] == "structure"

    @pytest.mark.asyncio
    async def test_analyze_insights(self, tmp_path: Path) -> None:
        """Test analyzing insights."""
        # Arrange
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_insight_engine = MagicMock()
            mock_insight_engine.generate_insights = AsyncMock(
                return_value=InsightsResult(
                    generated_at="2026-01-01T00:00:00",
                    total_insights=0,
                    high_impact_count=0,
                    medium_impact_count=0,
                    low_impact_count=0,
                    estimated_total_token_savings=0,
                    insights=[],
                    summary=SummaryModel(status=SummaryStatus.SUCCESS),
                )
            )
            mock_get_managers.return_value = make_test_managers(
                pattern_analyzer=MagicMock(),
                structure_analyzer=MagicMock(),
                insight_engine=mock_insight_engine,
            )

            # Act
            result = await analyze(
                target="insights",
                export_format="json",
                categories=["duplication"],
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["target"] == "insights"

    @pytest.mark.asyncio
    async def test_analyze_exception_handling(self, tmp_path: Path) -> None:
        """Test exception handling in analyze."""
        # Arrange
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_get_managers.side_effect = RuntimeError("Test error")

            # Act
            result = await analyze(target="structure")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Test error" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"


@pytest.mark.timeout(10)
class TestAnalyzeContextLogging:
    """Test analyze tool Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_analyze_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, analyze logs start and completion via log_client."""
        # Arrange
        mock_ctx = AsyncMock()
        mock_structure_analyzer = MagicMock()
        mock_structure_analyzer.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(
                status=ComplexityAnalysisStatus.ANALYZED, file_count=5
            )
        )
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(
                status=ComplexityAnalysisStatus.ANALYZED
            )
        )
        with (
            patch(
                "cortex.tools.context.analysis_operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.context.analysis_operations.get_managers",
                new_callable=AsyncMock,
            ) as mock_get_managers,
        ):
            mock_get_managers.return_value = make_test_managers(
                pattern_analyzer=MagicMock(),
                structure_analyzer=mock_structure_analyzer,
                insight_engine=MagicMock(),
            )

            # Act
            result = await analyze(
                target="structure",
                ctx=mock_ctx,
            )

            # Assert
            assert json.loads(result)["status"] == "success"
            args_list = [c[0] for c in mock_log.call_args_list]
            levels_and_messages = [(a[1], a[2]) for a in args_list]
            assert ("info", "analyze: starting") in levels_and_messages
            assert ("info", "analyze: completed") in levels_and_messages

    @pytest.mark.asyncio
    async def test_analyze_calls_log_client_warning_on_invalid_target_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When target is invalid and ctx is passed, analyze logs warning."""
        # Arrange
        mock_ctx = AsyncMock()
        with patch(
            "cortex.tools.context.analysis_operations.log_client",
            new_callable=AsyncMock,
        ) as mock_log:
            # Act
            result = await analyze(
                target="invalid",  # type: ignore[arg-type]
                ctx=mock_ctx,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert any(
                c[0][1] == "warning" and c[0][2] == "analyze: invalid target"
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )

    @pytest.mark.asyncio
    async def test_analyze_calls_log_client_error_on_exception_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When analysis raises and ctx is passed, analyze logs error."""
        # Arrange
        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.context.analysis_operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.context.analysis_operations.get_managers",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Setup failed"),
            ),
        ):
            # Act
            result = await analyze(
                target="structure",
                ctx=mock_ctx,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Setup failed" in result_data["error"]
            error_calls = [
                c[0]
                for c in mock_log.call_args_list
                if len(c[0]) >= 2 and c[0][1] == "error"
            ]
            assert len(error_calls) == 1


class TestDispatchAnalysisTarget:
    """Test _dispatch_analysis_target helper."""

    @pytest.mark.asyncio
    async def test_dispatch_usage_patterns(self) -> None:
        """Test dispatching usage patterns analysis."""
        # Arrange
        mock_pattern_analyzer = MagicMock()
        mock_pattern_analyzer.get_access_frequency = AsyncMock(return_value={})
        mock_pattern_analyzer.get_co_access_patterns = AsyncMock(return_value=[])
        mock_pattern_analyzer.get_task_patterns = AsyncMock(return_value={})
        mock_pattern_analyzer.get_unused_files = AsyncMock(return_value=[])

        analyzers = (mock_pattern_analyzer, MagicMock(), MagicMock())

        # Act
        result = await dispatch_analysis_target(
            "usage_patterns", analyzers, 30, "json", None
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["target"] == "usage_patterns"

    @pytest.mark.asyncio
    async def test_dispatch_structure(self) -> None:
        """Test dispatching structure analysis."""
        # Arrange
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

        # Act
        result = await dispatch_analysis_target(
            "structure", analyzers, None, "json", None
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["target"] == "structure"

    @pytest.mark.asyncio
    async def test_dispatch_insights(self) -> None:
        """Test dispatching insights analysis."""
        # Arrange
        mock_insight_engine = MagicMock()
        mock_insight_engine.generate_insights = AsyncMock(
            return_value=InsightsResult(
                generated_at="2026-01-01T00:00:00",
                total_insights=0,
                high_impact_count=0,
                medium_impact_count=0,
                low_impact_count=0,
                estimated_total_token_savings=0,
                insights=[],
                summary=SummaryModel(status=SummaryStatus.SUCCESS),
            )
        )

        analyzers = (MagicMock(), MagicMock(), mock_insight_engine)

        # Act
        result = await dispatch_analysis_target(
            "insights", analyzers, None, "json", None
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["target"] == "insights"

    @pytest.mark.asyncio
    async def test_dispatch_invalid_target(self) -> None:
        """Test dispatching with invalid target."""
        # Arrange
        analyzers = (MagicMock(), MagicMock(), MagicMock())

        # Act
        result = await dispatch_analysis_target(
            "invalid", analyzers, None, "json", None
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid target: invalid" in result_data["error"]


class TestValidateRefactoringType:
    """Test _validate_refactoring_type helper."""

    def test_validate_valid_consolidation(self) -> None:
        """Test validating consolidation type."""
        # Act
        result = validate_refactoring_type("consolidation")

        # Assert
        assert result is None

    def test_validate_valid_splits(self) -> None:
        """Test validating splits type."""
        # Act
        result = validate_refactoring_type("splits")

        # Assert
        assert result is None

    def test_validate_valid_reorganization(self) -> None:
        """Test validating reorganization type."""
        # Act
        result = validate_refactoring_type("reorganization")

        # Assert
        assert result is None

    def test_validate_invalid_type(self) -> None:
        """Test validating invalid type."""
        # Act
        result = validate_refactoring_type("invalid")

        # Assert
        assert result is not None
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid type: invalid" in result_data["error"]


class TestGetRefactoringManagers:
    """Test _get_refactoring_managers helper."""

    @pytest.mark.asyncio
    async def test_get_refactoring_managers_success(self) -> None:
        """Test successful retrieval of refactoring managers."""
        # Arrange
        mock_consolidation = MagicMock()
        mock_split = MagicMock()
        mock_reorganization = MagicMock()
        mgrs = make_test_managers(
            consolidation_detector=mock_consolidation,
            split_recommender=mock_split,
            reorganization_planner=mock_reorganization,
        )

        # Act
        consolidation, split, reorganization = await get_refactoring_managers(mgrs)

        # Assert
        assert consolidation == mock_consolidation
        assert split == mock_split
        assert reorganization == mock_reorganization


class TestHandlePreviewMode:
    """Test _handle_preview_mode helper."""

    def test_handle_preview_mode_returns_message(self) -> None:
        """Test preview mode returns informational message."""
        # Act
        result = handle_preview_mode("consolidation_001")

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["preview_mode"] is True
        assert result_data["suggestion_id"] == "consolidation_001"
        assert (
            "Preview functionality requires suggestion caching"
            in result_data["message"]
        )


class TestConvertOpportunitiesToDict:
    """Test _convert_opportunities_to_dict helper."""

    def test_convert_dataclass_opportunities(self) -> None:
        """Test converting ConsolidationOpportunity dataclasses."""
        # Arrange
        opportunities = [
            ConsolidationOpportunity(
                opportunity_id="opp1",
                opportunity_type="exact_duplicate",
                affected_files=["a.md", "b.md"],
                common_content="Hello",
                similarity_score=0.85,
                token_savings=10,
                suggested_action="extract",
                extraction_target="shared.md",
                transclusion_syntax=["{{include:shared.md}}", "{{include:shared.md}}"],
            ),
            ConsolidationOpportunity(
                opportunity_id="opp2",
                opportunity_type="similar_content",
                affected_files=["c.md", "d.md"],
                common_content="World",
                similarity_score=0.90,
                token_savings=12,
                suggested_action="extract",
                extraction_target="shared.md",
                transclusion_syntax=["{{include:shared.md}}", "{{include:shared.md}}"],
            ),
        ]

        # Act
        result = convert_opportunities_to_dict(opportunities)

        # Assert
        assert len(result) == 2
        assert result[0]["opportunity_id"] == "opp1"
        assert result[1]["opportunity_id"] == "opp2"

    def test_convert_object_opportunities_with_to_dict(self) -> None:
        """Test converting object opportunities that have to_dict method."""
        # Arrange
        mock_opp = MagicMock()
        mock_opp.to_dict.return_value = {"id": "opp1", "similarity": 0.85}
        opportunities = [mock_opp]

        # Act
        result = convert_opportunities_to_dict(opportunities)

        # Assert
        assert len(result) == 1
        assert result[0]["id"] == "opp1"
        mock_opp.to_dict.assert_called_once()

    def test_convert_object_opportunities_without_to_dict(self) -> None:
        """Test converting object opportunities without to_dict method."""

        # Arrange
        opp = ConsolidationOpportunity(
            opportunity_id="test",
            opportunity_type="similar_content",
            affected_files=["file1.md", "file2.md"],
            common_content="common",
            similarity_score=0.8,
            token_savings=100,
            suggested_action="extract",
            extraction_target="shared.md",
            transclusion_syntax=["{{include:shared.md}}"],
            details={},
        )
        opportunities = [opp]

        # Act
        result = convert_opportunities_to_dict(opportunities)

        # Assert
        assert len(result) == 1
        assert result[0]["opportunity_id"] == "test"


class TestConvertRecommendationsToDict:
    """Test _convert_recommendations_to_dict helper."""

    def test_convert_dataclass_recommendations(self) -> None:
        """Test converting SplitRecommendation dataclasses."""
        # Arrange
        recommendations = [
            SplitRecommendation(
                recommendation_id="rec1",
                file_path="large.md",
                reason="Large file",
                split_strategy="by_size",
                split_points=[],
                estimated_impact={},
                new_structure={},
            ),
            SplitRecommendation(
                recommendation_id="rec2",
                file_path="huge.md",
                reason="Huge file",
                split_strategy="by_size",
                split_points=[],
                estimated_impact={},
                new_structure={},
            ),
        ]

        # Act
        result = convert_recommendations_to_dict(recommendations)

        # Assert
        assert len(result) == 2
        assert result[0]["recommendation_id"] == "rec1"
        assert result[1]["recommendation_id"] == "rec2"

    def test_convert_object_recommendations_with_to_dict(self) -> None:
        """Test converting object recommendations that have to_dict method."""
        # Arrange
        mock_rec = MagicMock()
        mock_rec.to_dict.return_value = {"id": "rec1", "file": "large.md"}
        recommendations = [mock_rec]

        # Act
        result = convert_recommendations_to_dict(recommendations)

        # Assert
        assert len(result) == 1
        assert result[0]["id"] == "rec1"
        mock_rec.to_dict.assert_called_once()

    def test_convert_object_recommendations_without_to_dict(self) -> None:
        """Test converting object recommendations without to_dict method."""

        # Arrange
        rec = SplitRecommendation(
            recommendation_id="test",
            file_path="test.md",
            reason="too large",
            split_strategy="by_sections",
            split_points=[],
            estimated_impact={},
            new_structure={},
            maintain_dependencies=True,
        )
        recommendations = [rec]

        # Act
        result = convert_recommendations_to_dict(recommendations)

        # Assert
        assert len(result) == 1
        assert result[0]["recommendation_id"] == "test"


class TestSuggestConsolidation:
    """Test _suggest_consolidation helper."""

    @pytest.mark.asyncio
    async def test_suggest_consolidation_default_similarity(self) -> None:
        """Test consolidation suggestions with default similarity."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.detect_opportunities = AsyncMock(return_value=[])

        # Act
        result = await suggest_consolidation(mock_detector, None)

        # Assert
        assert mock_detector.min_similarity == 0.80
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["type"] == "consolidation"
        assert result_data["min_similarity"] == 0.80

    @pytest.mark.asyncio
    async def test_suggest_consolidation_custom_similarity(self) -> None:
        """Test consolidation suggestions with custom similarity."""
        # Arrange
        mock_detector = MagicMock()
        mock_detector.detect_opportunities = AsyncMock(
            return_value=[
                ConsolidationOpportunity(
                    opportunity_id="opp1",
                    opportunity_type="exact_duplicate",
                    affected_files=["a.md", "b.md"],
                    common_content="Hello",
                    similarity_score=0.90,
                    token_savings=10,
                    suggested_action="extract",
                    extraction_target="shared.md",
                    transclusion_syntax=[
                        "{{include:shared.md}}",
                        "{{include:shared.md}}",
                    ],
                )
            ]
        )

        # Act
        result = await suggest_consolidation(mock_detector, 0.85)

        # Assert
        assert mock_detector.min_similarity == 0.85
        result_data = json.loads(result)
        assert result_data["min_similarity"] == 0.85
        assert len(result_data["opportunities"]) == 1


class TestSuggestSplits:
    """Test _suggest_splits helper."""

    @pytest.mark.asyncio
    async def test_suggest_splits_default_threshold(self) -> None:
        """Test split suggestions with default threshold."""
        # Arrange
        mock_recommender = MagicMock()
        mock_recommender.suggest_file_splits = AsyncMock(return_value=[])

        # Act
        result = await suggest_splits(mock_recommender, None)

        # Assert
        assert mock_recommender.max_file_size == 2500  # 10000 / 4
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["type"] == "splits"
        assert result_data["size_threshold"] == 10000

    @pytest.mark.asyncio
    async def test_suggest_splits_custom_threshold(self) -> None:
        """Test split suggestions with custom threshold."""
        # Arrange
        mock_recommender = MagicMock()
        mock_recommender.suggest_file_splits = AsyncMock(
            return_value=[
                SplitRecommendation(
                    recommendation_id="split1",
                    file_path="large.md",
                    reason="Large file",
                    split_strategy="by_size",
                    split_points=[],
                    estimated_impact={},
                    new_structure={},
                )
            ]
        )

        # Act
        result = await suggest_splits(mock_recommender, 8000)

        # Assert
        assert mock_recommender.max_file_size == 2000  # 8000 / 4
        result_data = json.loads(result)
        assert result_data["size_threshold"] == 8000
        assert len(result_data["recommendations"]) == 1


class TestGetStructureData:
    """Test _get_structure_data helper."""

    @pytest.mark.asyncio
    async def test_get_structure_data_success(self) -> None:
        """Test successful structure data retrieval."""
        # Arrange
        mock_structure_analyzer = MagicMock()
        mock_structure_analyzer.analyze_file_organization = AsyncMock(
            return_value=FileOrganizationResult(
                status=ComplexityAnalysisStatus.ANALYZED, file_count=10
            )
        )
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(
            return_value=[
                AntiPatternInfo(
                    type="naming_inconsistency",
                    severity=SeverityLevel.LOW,
                    description="Naming inconsistency",
                )
            ]
        )
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
            return_value=ComplexityAnalysisResult(
                status=ComplexityAnalysisStatus.ANALYZED,
                metrics=ComplexityMetrics(max_dependency_depth=2),
            )
        )
        mgrs = make_test_managers(structure_analyzer=mock_structure_analyzer)

        # Act
        result = await get_structure_data(mgrs)

        # Assert
        result_dict = result
        analysis = cast(dict[str, object], result_dict["analysis"])
        file_org = cast(dict[str, object], analysis["file_organization"])
        assert file_org["file_count"] == 10
        anti_patterns = cast(list[object], analysis["anti_patterns"])
        assert len(anti_patterns) == 1
        complexity_metrics = cast(dict[str, object], analysis["complexity_metrics"])
        metrics = cast(dict[str, object], complexity_metrics["metrics"])
        assert metrics["max_dependency_depth"] == 2


class TestSuggestReorganization:
    """Test _suggest_reorganization helper."""

    @pytest.mark.asyncio
    async def test_suggest_reorganization_default_goal(self) -> None:
        """Test reorganization suggestions with default goal."""
        # Arrange
        mock_planner = MagicMock()
        mock_planner.create_reorganization_plan = AsyncMock(
            return_value=ReorganizationPlanModel(
                plan_id="plan-1",
                optimization_goal="dependency_depth",
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
        )

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

        mock_graph = MagicMock()
        mock_graph.to_dict.return_value = DependencyGraphDict()

        mgrs = make_test_managers(
            structure_analyzer=mock_structure_analyzer,
            graph=mock_graph,
        )

        # Act
        result = await suggest_reorganization(mock_planner, mgrs, None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["type"] == "reorganization"
        assert result_data["goal"] == "dependency_depth"

    @pytest.mark.asyncio
    async def test_suggest_reorganization_custom_goal(self) -> None:
        """Test reorganization suggestions with custom goal."""
        # Arrange
        mock_planner = MagicMock()
        mock_planner.create_reorganization_plan = AsyncMock(
            return_value=ReorganizationPlanModel(
                plan_id="plan-2",
                optimization_goal="category",
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
        )

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

        mock_graph = MagicMock()
        mock_graph.to_dict.return_value = DependencyGraphDict()
        mgrs = make_test_managers(
            structure_analyzer=mock_structure_analyzer,
            graph=mock_graph,
        )

        # Act
        result = await suggest_reorganization(mock_planner, mgrs, "category")

        # Assert
        result_data = json.loads(result)
        assert result_data["goal"] == "category"
        assert result_data["plan"]["plan_id"] == "plan-2"


class TestProcessRefactoringRequest:
    """Test _process_refactoring_request helper."""

    @pytest.mark.asyncio
    async def test_process_consolidation_request(self, tmp_path: Path) -> None:
        """Test processing consolidation refactoring request."""
        # Arrange
        with patch(
            "cortex.tools.context.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_detector = MagicMock()
            mock_detector.detect_opportunities = AsyncMock(return_value=[])

            mock_detector_mgr = MagicMock()
            mock_detector_mgr.get = AsyncMock(return_value=mock_detector)

            mock_split_mgr = MagicMock()
            mock_split_mgr.get = AsyncMock(return_value=MagicMock())

            mock_reorg_mgr = MagicMock()
            mock_reorg_mgr.get = AsyncMock(return_value=MagicMock())

            mock_get_managers.return_value = {
                "consolidation_detector": mock_detector_mgr,
                "split_recommender": mock_split_mgr,
                "reorganization_planner": mock_reorg_mgr,
            }

            # Act
            result = await process_refactoring_request(
                RefactoringSuggestionType.CONSOLIDATION,
                str(tmp_path),
                0.85,
                None,
                None,
                None,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["type"] == "consolidation"

    @pytest.mark.asyncio
    async def test_process_splits_request(self, tmp_path: Path) -> None:
        """Test processing splits refactoring request."""
        # Arrange
        with patch(
            "cortex.tools.context.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_recommender = MagicMock()
            mock_recommender.suggest_file_splits = AsyncMock(return_value=[])

            mock_split_mgr = MagicMock()
            mock_split_mgr.get = AsyncMock(return_value=mock_recommender)

            mock_detector_mgr = MagicMock()
            mock_detector_mgr.get = AsyncMock(return_value=MagicMock())

            mock_reorg_mgr = MagicMock()
            mock_reorg_mgr.get = AsyncMock(return_value=MagicMock())

            mock_get_managers.return_value = {
                "consolidation_detector": mock_detector_mgr,
                "split_recommender": mock_split_mgr,
                "reorganization_planner": mock_reorg_mgr,
            }

            # Act
            result = await process_refactoring_request(
                RefactoringSuggestionType.SPLITS,
                str(tmp_path),
                None,
                8000,
                None,
                None,
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["type"] == "splits"

    @pytest.mark.asyncio
    async def test_process_reorganization_request(self, tmp_path: Path) -> None:
        """Test processing reorganization refactoring request."""
        # Arrange
        with patch(
            "cortex.tools.refactoring.operation_helpers.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            with patch(
                "cortex.tools.refactoring.operation_helpers.get_project_root",
                return_value=Path(str(tmp_path)),
            ):
                mock_planner = MagicMock()
                mock_planner.create_reorganization_plan = AsyncMock(
                    return_value=ReorganizationPlanModel(
                        plan_id="plan-3",
                        optimization_goal="category",
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
                )

                mock_structure_analyzer = MagicMock()
                mock_structure_analyzer.analyze_file_organization = AsyncMock(
                    return_value=FileOrganizationResult(
                        status=ComplexityAnalysisStatus.ANALYZED, file_count=0
                    )
                )
                mock_structure_analyzer.detect_anti_patterns = AsyncMock(
                    return_value=[]
                )
                mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
                    return_value=ComplexityAnalysisResult(
                        status=ComplexityAnalysisStatus.ANALYZED
                    )
                )

                mock_graph = MagicMock()
                mock_graph.to_dict.return_value = DependencyGraphDict()

                mock_get_managers.return_value = make_test_managers(
                    reorganization_planner=mock_planner,
                    structure_analyzer=mock_structure_analyzer,
                    graph=mock_graph,
                )

                # Act
                result = await process_refactoring_request(
                    RefactoringSuggestionType.REORGANIZATION,
                    str(tmp_path),
                    None,
                    None,
                    "category",
                    None,
                )

            # Assert
            result_data = json.loads(result)
            assert result_data["type"] == "reorganization"

    @pytest.mark.asyncio
    async def test_process_request_with_preview_mode(self, tmp_path: Path) -> None:
        """Test processing request with preview mode enabled."""
        # Arrange
        with patch(
            "cortex.tools.context.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_detector_mgr = MagicMock()
            mock_detector_mgr.get = AsyncMock(return_value=MagicMock())

            mock_split_mgr = MagicMock()
            mock_split_mgr.get = AsyncMock(return_value=MagicMock())

            mock_reorg_mgr = MagicMock()
            mock_reorg_mgr.get = AsyncMock(return_value=MagicMock())

            mock_get_managers.return_value = {
                "consolidation_detector": mock_detector_mgr,
                "split_recommender": mock_split_mgr,
                "reorganization_planner": mock_reorg_mgr,
            }

            # Act
            result = await process_refactoring_request(
                RefactoringSuggestionType.CONSOLIDATION,
                str(tmp_path),
                None,
                None,
                None,
                "consolidation_001",
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["preview_mode"] is True
            assert result_data["suggestion_id"] == "consolidation_001"


@pytest.mark.timeout(10)
class TestSuggestRefactoringHandler:
    """Test main suggest_refactoring handler."""

    @pytest.mark.asyncio
    async def test_suggest_refactoring_consolidation(self, tmp_path: Path) -> None:
        """Test suggesting consolidation refactorings."""
        # Arrange: patch get_managers where it is used (refactoring.operation_helpers)
        # so the real ConsolidationDetector is not used (avoids slow SequenceMatcher in CI).
        # get_manager() returns dict values as-is when they are not LazyManager, so the
        # consolidation_detector entry must implement detect_opportunities directly.
        sample_opportunity = ConsolidationOpportunity(
            opportunity_id="opp1",
            opportunity_type="similar_content",
            affected_files=["a.md", "b.md"],
            common_content="shared",
            similarity_score=0.85,
            token_savings=10,
            suggested_action="Extract",
            extraction_target="shared.md",
            transclusion_syntax=["{{include:shared.md}}"],
        )
        mock_detector_mgr = MagicMock()
        mock_detector_mgr.detect_opportunities = AsyncMock(
            return_value=[sample_opportunity]
        )
        mock_split_mgr = MagicMock()
        mock_reorg_mgr = MagicMock()
        mock_managers = {
            "consolidation_detector": mock_detector_mgr,
            "split_recommender": mock_split_mgr,
            "reorganization_planner": mock_reorg_mgr,
        }
        with patch(
            "cortex.tools.refactoring.operation_helpers.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_get_managers.return_value = mock_managers
            # Act
            result = await suggest_refactoring(
                type="consolidation",
                min_similarity=0.85,
                response_format="detailed",
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["type"] == "consolidation"

    @pytest.mark.asyncio
    async def test_suggest_refactoring_invalid_type(self, tmp_path: Path) -> None:
        """Test suggesting refactoring with invalid type."""
        # Act
        result = await suggest_refactoring(
            type="invalid",  # type: ignore
            response_format="detailed",
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Invalid type: invalid" in result_data["error"]

    @pytest.mark.asyncio
    async def test_suggest_refactoring_exception_handling(self, tmp_path: Path) -> None:
        """Test exception handling in suggest_refactoring."""
        # Arrange
        with patch(
            "cortex.tools.refactoring.operation_helpers.get_managers"
        ) as mock_get_managers:
            mock_get_managers.side_effect = RuntimeError("Test error")

            # Act
            result = await suggest_refactoring(type="consolidation")

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Test error" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.timeout(10)
class TestRefactoringOperationsContextLogging:
    """Test suggest_refactoring uses log_client when ctx is passed."""

    async def test_suggest_refactoring_calls_log_client_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, suggest_refactoring logs start and completion."""
        mock_ctx = AsyncMock()
        success_json = json.dumps(
            {"status": "success", "type": "consolidation", "opportunities": []},
            indent=2,
        )
        with (
            patch(
                "cortex.tools.refactoring.operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.refactoring.operations.process_refactoring_request",
                new_callable=AsyncMock,
                return_value=success_json,
            ),
        ):
            result = await suggest_refactoring(
                type="consolidation",
                min_similarity=0.85,
                response_format="detailed",
                ctx=mock_ctx,
            )
            result_data = json.loads(result)
        assert result_data["status"] == "success"
        args_list = [c[0] for c in mock_log.call_args_list]
        levels_and_messages = [(a[1], a[2]) for a in args_list]
        assert ("info", "suggest_refactoring: starting") in levels_and_messages
        assert ("info", "suggest_refactoring: completed") in levels_and_messages


@pytest.mark.timeout(10)
class TestAnalyzeResource:
    """Test analyze_resource (Phase 43 Phase 5 Analysis resource)."""

    @pytest.mark.asyncio
    async def test_analyze_resource_returns_json_for_valid_target(
        self, tmp_path: Path
    ) -> None:
        """analyze_resource returns valid JSON for structure target (Phase 43)."""
        with patch(
            "cortex.tools.context.analysis_operations.analyze",
            new_callable=AsyncMock,
            return_value=json.dumps(
                {"status": "success", "target": "structure", "analysis": {}},
                indent=2,
            ),
        ):
            result = await analyze_resource("structure")
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "structure"

    @pytest.mark.asyncio
    async def test_analyze_resource_invalid_target_returns_error(self) -> None:
        """analyze_resource returns error JSON for invalid target (Phase 43)."""
        error_json = json.dumps(
            {
                "status": "error",
                "error": "Invalid target: invalid",
                "valid_targets": [],
            },
            indent=2,
        )
        with (
            patch(
                "cortex.core.mcp_stability_usage.get_current_managers",
                return_value={},
            ),
            patch(
                "cortex.tools.context.analysis_operations.analyze",
                new_callable=AsyncMock,
                return_value=error_json,
            ),
        ):
            result = await analyze_resource("invalid")
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "valid_targets" in result_data


@pytest.mark.timeout(10)
class TestSuggestRefactoringResource:
    """Test suggest_refactoring_resource (Phase 43 Phase 5 Analysis resource)."""

    @pytest.mark.asyncio
    async def test_suggest_refactoring_resource_returns_json_for_valid_type(
        self, tmp_path: Path
    ) -> None:
        """suggest_refactoring_resource returns valid JSON for consolidation (Phase 43)."""
        success_json = json.dumps(
            {"status": "success", "type": "consolidation", "opportunities": []},
            indent=2,
        )
        with patch(
            "cortex.tools.refactoring.operations.suggest_refactoring",
            new_callable=AsyncMock,
            return_value=success_json,
        ):
            result = await suggest_refactoring_resource("consolidation")
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["type"] == "consolidation"

    @pytest.mark.asyncio
    async def test_suggest_refactoring_resource_invalid_type_returns_error(
        self,
    ) -> None:
        """suggest_refactoring_resource returns error JSON for invalid type (Phase 43)."""
        error_json = json.dumps(
            {
                "status": "error",
                "error": "Invalid type: invalid. Valid types: consolidation, splits, reorganization",
            },
            indent=2,
        )
        with (
            patch(
                "cortex.core.mcp_stability_usage.get_current_managers",
                return_value={},
            ),
            patch(
                "cortex.tools.refactoring.operations.suggest_refactoring",
                new_callable=AsyncMock,
                return_value=error_json,
            ),
        ):
            result = await suggest_refactoring_resource("invalid")
        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert (
            "Invalid type" in result_data["error"] or "invalid" in result_data["error"]
        )
