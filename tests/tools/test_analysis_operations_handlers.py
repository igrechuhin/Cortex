"""Tests for analysis operations handlers and refactoring operations."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.analysis.models import (
    ComplexityAnalysisResult,
    ComplexityAnalysisStatus,
    InsightsResult,
    SummaryModel,
    SummaryStatus,
)
from cortex.core.models import DependencyGraphDict, FileOrganizationResult, RiskLevel
from cortex.refactoring.consolidation_detector import ConsolidationOpportunity
from cortex.refactoring.models import (
    RefactoringSuggestionType,
    ReorganizationImpactModel,
    ReorganizationPlanModel,
)
from cortex.tools.context.analysis_operations import (
    analyze_impl as _analyze_impl,
)
from cortex.tools.refactoring import (
    suggest_refactoring,
    suggest_refactoring_resource,
)
from cortex.tools.refactoring.operation_helpers import (
    process_refactoring_request,
)
from tests.helpers.managers import make_test_managers


@pytest.fixture(autouse=True)
def _skip_usage_context_init():  # pyright: ignore[reportUnusedFunction]
    """Avoid slow resolve_project_root + get_managers in ensure_usage_context."""
    with patch("cortex.core.mcp_stability_usage.get_current_managers", return_value={}):
        yield


def _make_mock_insights() -> InsightsResult:
    """Build a reusable InsightsResult mock."""
    return InsightsResult(
        generated_at="2026-01-01T00:00:00",
        total_insights=0,
        high_impact_count=0,
        medium_impact_count=0,
        low_impact_count=0,
        estimated_total_token_savings=0,
        insights=[],
        summary=SummaryModel(status=SummaryStatus.SUCCESS),
    )


def _mock_pattern_analyzer(
    freq: dict[str, int] | None = None,
) -> MagicMock:
    """Create a mock pattern analyzer with default returns."""
    m = MagicMock()
    m.get_access_frequency = AsyncMock(return_value=freq or {})
    m.get_co_access_patterns = AsyncMock(return_value=[])
    m.get_task_patterns = AsyncMock(return_value={})
    m.get_unused_files = AsyncMock(return_value=[])
    return m


def _mock_structure_analyzer(file_count: int = 5) -> MagicMock:
    """Create a mock structure analyzer."""
    m = MagicMock()
    m.analyze_file_organization = AsyncMock(
        return_value=FileOrganizationResult(
            status=ComplexityAnalysisStatus.ANALYZED, file_count=file_count
        )
    )
    m.detect_anti_patterns = AsyncMock(return_value=[])
    m.measure_complexity_metrics = AsyncMock(
        return_value=ComplexityAnalysisResult(status=ComplexityAnalysisStatus.ANALYZED)
    )
    return m


@pytest.mark.timeout(20)
class TestAnalyzeHandler:
    """Test main analyze handler."""

    @pytest.mark.asyncio
    async def test_analyze_usage_patterns(self, tmp_path: Path) -> None:
        """Test analyzing usage patterns."""
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_get_managers.return_value = make_test_managers(
                pattern_analyzer=_mock_pattern_analyzer({"file1.md": 10}),
                structure_analyzer=MagicMock(),
                insight_engine=MagicMock(),
            )
            result = await _analyze_impl(target="usage_patterns", time_window_days=60)

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "usage_patterns"

    @pytest.mark.asyncio
    async def test_analyze_usage_pattern_alias(self, tmp_path: Path) -> None:
        """Hyphenated usage-pattern alias dispatches to usage_patterns."""
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_get_managers.return_value = make_test_managers(
                pattern_analyzer=_mock_pattern_analyzer(),
                structure_analyzer=MagicMock(),
                insight_engine=MagicMock(),
            )
            result = await _analyze_impl(target="usage-pattern")

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "usage_patterns"

    @pytest.mark.asyncio
    async def test_analyze_structure(self, tmp_path: Path) -> None:
        """Test analyzing structure."""
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_get_managers.return_value = make_test_managers(
                pattern_analyzer=MagicMock(),
                structure_analyzer=_mock_structure_analyzer(),
                insight_engine=MagicMock(),
            )
            result = await _analyze_impl(target="structure")

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "structure"

    @pytest.mark.asyncio
    async def test_analyze_insights(self, tmp_path: Path) -> None:
        """Test analyzing insights."""
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_engine = MagicMock()
            mock_engine.generate_insights = AsyncMock(
                return_value=_make_mock_insights()
            )
            mock_get_managers.return_value = make_test_managers(
                pattern_analyzer=MagicMock(),
                structure_analyzer=MagicMock(),
                insight_engine=mock_engine,
            )
            result = await _analyze_impl(
                target="insights",
                export_format="json",
                categories=["duplication"],
            )

        result_data = json.loads(result)
        assert result_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_analyze_exception_handling(self, tmp_path: Path) -> None:
        """Test exception handling in analyze."""
        with patch(
            "cortex.tools.context.analysis_operations.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_get_managers.side_effect = RuntimeError("Test error")
            result = await _analyze_impl(target="structure")

        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Test error" in result_data["error"]

    @pytest.mark.asyncio
    async def test_analyze_tools_target(self, tmp_path: Path) -> None:
        """tools target dispatches to health-check analysis_type=tools."""
        with patch(
            "cortex.tools.context.analysis_operations.run_health_analysis",
            new_callable=AsyncMock,
            return_value=json.dumps({"status": "success", "analysis_type": "tools"}),
        ) as mock_health:
            result = await _analyze_impl(target="tools")

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert mock_health.await_count == 1


@pytest.mark.timeout(20)
class TestAnalyzeContextLogging:
    """Test analyze tool Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_analyze_logs_start_and_completion(self, tmp_path: Path) -> None:
        """When ctx is passed, analyze logs start and completion."""
        mock_ctx = AsyncMock()
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
                structure_analyzer=_mock_structure_analyzer(),
                insight_engine=MagicMock(),
            )
            result = await _analyze_impl(target="structure", ctx=mock_ctx)

        assert json.loads(result)["status"] == "success"
        args_list = [c[0] for c in mock_log.call_args_list]
        levels_msgs = [(a[1], a[2]) for a in args_list]
        assert ("info", "analyze: starting") in levels_msgs
        assert ("info", "analyze: completed") in levels_msgs

    @pytest.mark.asyncio
    async def test_analyze_logs_warning_on_invalid_target(self, tmp_path: Path) -> None:
        """When target is invalid and ctx is passed, analyze logs warning."""
        mock_ctx = AsyncMock()
        with patch(
            "cortex.tools.context.analysis_operations.log_client",
            new_callable=AsyncMock,
        ) as mock_log:
            result = await _analyze_impl(
                target="invalid",  # type: ignore[arg-type]
                ctx=mock_ctx,
            )

        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert any(
            c[0][1] == "warning" and c[0][2] == "analyze: invalid target"
            for c in mock_log.call_args_list
            if len(c[0]) >= 3
        )

    @pytest.mark.asyncio
    async def test_analyze_logs_error_on_exception(self, tmp_path: Path) -> None:
        """When analysis raises and ctx is passed, analyze logs error."""
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
            result = await _analyze_impl(target="structure", ctx=mock_ctx)

        result_data = json.loads(result)
        assert result_data["status"] == "error"
        error_calls = [
            c[0]
            for c in mock_log.call_args_list
            if len(c[0]) >= 2 and c[0][1] == "error"
        ]
        assert len(error_calls) == 1


def _make_mock_managers_dict(
    detector: MagicMock | None = None,
    recommender: MagicMock | None = None,
    planner: MagicMock | None = None,
) -> dict[str, MagicMock]:
    """Build a managers dict for process_refactoring_request tests."""
    d_mgr = MagicMock()
    d_mgr.get = AsyncMock(return_value=detector or MagicMock())
    s_mgr = MagicMock()
    s_mgr.get = AsyncMock(return_value=recommender or MagicMock())
    r_mgr = MagicMock()
    r_mgr.get = AsyncMock(return_value=planner or MagicMock())
    return {
        "consolidation_detector": d_mgr,
        "split_recommender": s_mgr,
        "reorganization_planner": r_mgr,
    }


def _build_reorg_managers(tmp_path: Path) -> object:
    """Build managers for reorganization request tests."""
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
    mock_sa = _mock_structure_analyzer(file_count=0)
    mock_graph = MagicMock()
    mock_graph.to_dict.return_value = DependencyGraphDict()
    return make_test_managers(
        reorganization_planner=mock_planner,
        structure_analyzer=mock_sa,
        graph=mock_graph,
    )


class TestProcessRefactoringRequest:
    """Test _process_refactoring_request helper."""

    @pytest.mark.asyncio
    async def test_process_consolidation_request(self, tmp_path: Path) -> None:
        mock_detector = MagicMock()
        mock_detector.detect_opportunities = AsyncMock(return_value=[])
        with patch(
            "cortex.tools.context.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_get_managers.return_value = _make_mock_managers_dict(
                detector=mock_detector
            )
            result = await process_refactoring_request(
                RefactoringSuggestionType.CONSOLIDATION,
                str(tmp_path),
                0.85,
                None,
                None,
                None,
            )

        assert json.loads(result)["type"] == "consolidation"

    @pytest.mark.asyncio
    async def test_process_splits_request(self, tmp_path: Path) -> None:
        mock_recommender = MagicMock()
        mock_recommender.suggest_file_splits = AsyncMock(return_value=[])
        with patch(
            "cortex.tools.context.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_get_managers.return_value = _make_mock_managers_dict(
                recommender=mock_recommender
            )
            result = await process_refactoring_request(
                RefactoringSuggestionType.SPLITS,
                str(tmp_path),
                None,
                8000,
                None,
                None,
            )

        assert json.loads(result)["type"] == "splits"

    @pytest.mark.asyncio
    async def test_process_reorganization_request(self, tmp_path: Path) -> None:
        managers = _build_reorg_managers(tmp_path)
        with (
            patch(
                "cortex.tools.refactoring.operation_helpers.get_managers",
                new_callable=AsyncMock,
                return_value=managers,
            ),
            patch(
                "cortex.tools.refactoring.operation_helpers.get_project_root",
                return_value=Path(str(tmp_path)),
            ),
        ):
            result = await process_refactoring_request(
                RefactoringSuggestionType.REORGANIZATION,
                str(tmp_path),
                None,
                None,
                "category",
                None,
            )

        assert json.loads(result)["type"] == "reorganization"

    @pytest.mark.asyncio
    async def test_process_request_with_preview_mode(self, tmp_path: Path) -> None:
        with patch(
            "cortex.tools.context.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_get_managers.return_value = _make_mock_managers_dict()
            result = await process_refactoring_request(
                RefactoringSuggestionType.CONSOLIDATION,
                str(tmp_path),
                None,
                None,
                None,
                "consolidation_001",
            )

        result_data = json.loads(result)
        assert result_data["preview_mode"] is True
        assert result_data["suggestion_id"] == "consolidation_001"


@pytest.mark.timeout(20)
class TestSuggestRefactoringHandler:
    """Test main suggest_refactoring handler."""

    @staticmethod
    def _consolidation_managers(
        sample_opp: ConsolidationOpportunity,
    ) -> dict[str, object]:
        mock_detector_mgr = MagicMock()
        mock_detector_mgr.detect_opportunities = AsyncMock(return_value=[sample_opp])
        return {
            "consolidation_detector": mock_detector_mgr,
            "split_recommender": MagicMock(),
            "reorganization_planner": MagicMock(),
        }

    @pytest.mark.asyncio
    async def test_suggest_refactoring_consolidation(self, tmp_path: Path) -> None:
        sample_opp = ConsolidationOpportunity(
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
        mock_managers = self._consolidation_managers(sample_opp)
        with patch(
            "cortex.tools.refactoring.operation_helpers.get_managers",
            new_callable=AsyncMock,
        ) as mock_get_managers:
            mock_get_managers.return_value = mock_managers
            result = await suggest_refactoring(
                type="consolidation",
                min_similarity=0.85,
                response_format="detailed",
            )

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["type"] == "consolidation"

    @pytest.mark.asyncio
    async def test_suggest_refactoring_invalid_type(self, tmp_path: Path) -> None:
        result = await suggest_refactoring(
            type="invalid",  # type: ignore
            response_format="detailed",
        )
        result_data = json.loads(result)
        assert result_data["status"] == "error"

    @pytest.mark.asyncio
    async def test_suggest_refactoring_exception_handling(self, tmp_path: Path) -> None:
        with patch(
            "cortex.tools.refactoring.operation_helpers.get_managers"
        ) as mock_get_managers:
            mock_get_managers.side_effect = RuntimeError("Test error")
            result = await suggest_refactoring(type="consolidation")

        result_data = json.loads(result)
        assert result_data["status"] == "error"
        assert "Test error" in result_data["error"]


@pytest.mark.asyncio
@pytest.mark.timeout(20)
class TestRefactoringOperationsContextLogging:
    """Test suggest_refactoring uses log_client when ctx is passed."""

    async def test_suggest_refactoring_calls_log_client(self, tmp_path: Path) -> None:
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
        levels_msgs = [(a[1], a[2]) for a in args_list]
        assert ("info", "suggest_refactoring: starting") in levels_msgs
        assert ("info", "suggest_refactoring: completed") in levels_msgs


@pytest.mark.timeout(20)
class TestSuggestRefactoringResource:
    """Test suggest_refactoring_resource (Phase 43)."""

    @pytest.mark.asyncio
    async def test_returns_json_for_valid_type(self, tmp_path: Path) -> None:
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

    @pytest.mark.asyncio
    async def test_invalid_type_returns_error(self) -> None:
        error_json = json.dumps(
            {
                "status": "error",
                "error": "Invalid type: invalid. Valid types: consolidation, splits, reorganization",
            },
            indent=2,
        )
        with (
            patch(
                "cortex.core.mcp_stability_usage.get_current_managers", return_value={}
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
