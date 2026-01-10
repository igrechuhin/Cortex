"""Tests for analysis operations module."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.refactoring.consolidation_detector import ConsolidationOpportunity
from cortex.refactoring.split_recommender import SplitRecommendation
from cortex.tools.analysis_operations import (
    analyze,
    analyze_insights,
    analyze_structure,
    analyze_usage_patterns,
    dispatch_analysis_target,
    get_analysis_managers,
)
from cortex.tools.refactoring_operations import (
    convert_opportunities_to_dict,
    convert_recommendations_to_dict,
    get_refactoring_managers,
    get_structure_data,
    handle_preview_mode,
    process_refactoring_request,
    suggest_consolidation,
    suggest_refactoring,
    suggest_reorganization,
    suggest_splits,
    validate_refactoring_type,
)


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
            return_value={"total_files": 10}
        )
        mock_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        mock_analyzer.measure_complexity_metrics = AsyncMock(
            return_value={"avg_depth": 2}
        )

        # Act
        result = await analyze_structure(mock_analyzer)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "structure"
        assert result_data["analysis"]["organization"]["total_files"] == 10
        assert result_data["analysis"]["complexity_metrics"]["avg_depth"] == 2


class TestAnalyzeInsights:
    """Test _analyze_insights helper."""

    @pytest.mark.asyncio
    async def test_analyze_insights_json_format(self) -> None:
        """Test insights analysis with JSON format."""
        # Arrange
        mock_engine = MagicMock()
        mock_insights = {"high_impact": [{"category": "duplication"}]}
        mock_engine.generate_insights = AsyncMock(return_value=mock_insights)

        # Act
        result = await analyze_insights(mock_engine, "json", None)

        # Assert
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["target"] == "insights"
        assert result_data["format"] == "json"
        assert result_data["insights"] == mock_insights

    @pytest.mark.asyncio
    async def test_analyze_insights_markdown_format(self) -> None:
        """Test insights analysis with markdown export format."""
        # Arrange
        mock_engine = MagicMock()
        mock_insights = {"high_impact": [{"category": "duplication"}]}
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
        mock_insights = {"high_impact": [{"category": "duplication"}]}
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

        mock_pattern_mgr = MagicMock()
        mock_pattern_mgr.get = AsyncMock(return_value=mock_pattern)

        mock_structure_mgr = MagicMock()
        mock_structure_mgr.get = AsyncMock(return_value=mock_structure)

        mock_insight_mgr = MagicMock()
        mock_insight_mgr.get = AsyncMock(return_value=mock_insight)

        mgrs = {
            "pattern_analyzer": mock_pattern_mgr,
            "structure_analyzer": mock_structure_mgr,
            "insight_engine": mock_insight_mgr,
        }

        # Act
        pattern, structure, insight = await get_analysis_managers(
            cast(dict[str, object], mgrs)
        )

        # Assert
        assert pattern == mock_pattern
        assert structure == mock_structure
        assert insight == mock_insight


class TestAnalyzeHandler:
    """Test main analyze handler."""

    @pytest.mark.asyncio
    async def test_analyze_usage_patterns(self, tmp_path: Path) -> None:
        """Test analyzing usage patterns."""
        # Arrange
        with patch(
            "cortex.tools.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_pattern_analyzer = MagicMock()
            mock_pattern_analyzer.get_access_frequency = AsyncMock(
                return_value={"file1.md": 10}
            )
            mock_pattern_analyzer.get_co_access_patterns = AsyncMock(return_value=[])
            mock_pattern_analyzer.get_task_patterns = AsyncMock(return_value={})
            mock_pattern_analyzer.get_unused_files = AsyncMock(return_value=[])

            mock_pattern_mgr = MagicMock()
            mock_pattern_mgr.get = AsyncMock(return_value=mock_pattern_analyzer)

            mock_structure_mgr = MagicMock()
            mock_structure_mgr.get = AsyncMock(return_value=MagicMock())

            mock_insight_mgr = MagicMock()
            mock_insight_mgr.get = AsyncMock(return_value=MagicMock())

            mock_get_managers.return_value = {
                "pattern_analyzer": mock_pattern_mgr,
                "structure_analyzer": mock_structure_mgr,
                "insight_engine": mock_insight_mgr,
            }

            # Act
            result = await analyze(
                target="usage_patterns",
                project_root=str(tmp_path),
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
            "cortex.tools.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_structure_analyzer = MagicMock()
            mock_structure_analyzer.analyze_file_organization = AsyncMock(
                return_value={"total_files": 5}
            )
            mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
            mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
                return_value={}
            )

            mock_structure_mgr = MagicMock()
            mock_structure_mgr.get = AsyncMock(return_value=mock_structure_analyzer)

            mock_pattern_mgr = MagicMock()
            mock_pattern_mgr.get = AsyncMock(return_value=MagicMock())

            mock_insight_mgr = MagicMock()
            mock_insight_mgr.get = AsyncMock(return_value=MagicMock())

            mock_get_managers.return_value = {
                "pattern_analyzer": mock_pattern_mgr,
                "structure_analyzer": mock_structure_mgr,
                "insight_engine": mock_insight_mgr,
            }

            # Act
            result = await analyze(target="structure", project_root=str(tmp_path))

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "success"
            assert result_data["target"] == "structure"

    @pytest.mark.asyncio
    async def test_analyze_insights(self, tmp_path: Path) -> None:
        """Test analyzing insights."""
        # Arrange
        with patch(
            "cortex.tools.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_insight_engine = MagicMock()
            mock_insight_engine.generate_insights = AsyncMock(
                return_value={"high_impact": []}
            )

            mock_insight_mgr = MagicMock()
            mock_insight_mgr.get = AsyncMock(return_value=mock_insight_engine)

            mock_pattern_mgr = MagicMock()
            mock_pattern_mgr.get = AsyncMock(return_value=MagicMock())

            mock_structure_mgr = MagicMock()
            mock_structure_mgr.get = AsyncMock(return_value=MagicMock())

            mock_get_managers.return_value = {
                "pattern_analyzer": mock_pattern_mgr,
                "structure_analyzer": mock_structure_mgr,
                "insight_engine": mock_insight_mgr,
            }

            # Act
            result = await analyze(
                target="insights",
                project_root=str(tmp_path),
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
            "cortex.tools.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_get_managers.side_effect = RuntimeError("Test error")

            # Act
            result = await analyze(target="structure", project_root=str(tmp_path))

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Test error" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"


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
        mock_structure_analyzer.analyze_file_organization = AsyncMock(return_value={})
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(return_value={})

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
        mock_insight_engine.generate_insights = AsyncMock(return_value={})

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

        mock_consolidation_mgr = MagicMock()
        mock_consolidation_mgr.get = AsyncMock(return_value=mock_consolidation)

        mock_split_mgr = MagicMock()
        mock_split_mgr.get = AsyncMock(return_value=mock_split)

        mock_reorganization_mgr = MagicMock()
        mock_reorganization_mgr.get = AsyncMock(return_value=mock_reorganization)

        mgrs = {
            "consolidation_detector": mock_consolidation_mgr,
            "split_recommender": mock_split_mgr,
            "reorganization_planner": mock_reorganization_mgr,
        }

        # Act
        consolidation, split, reorganization = await get_refactoring_managers(
            cast(dict[str, object], mgrs)
        )

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

    def test_convert_dict_opportunities(self) -> None:
        """Test converting dictionary opportunities."""
        # Arrange
        opportunities = [
            {"id": "opp1", "similarity": 0.85},
            {"id": "opp2", "similarity": 0.90},
        ]

        # Act
        result = convert_opportunities_to_dict(
            cast(Sequence[ConsolidationOpportunity | dict[str, object]], opportunities)
        )

        # Assert
        assert len(result) == 2
        assert result[0]["id"] == "opp1"
        assert result[1]["id"] == "opp2"

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
        class SimpleOpp:
            pass

        opp = SimpleOpp()
        opportunities = [opp]

        # Act
        result = convert_opportunities_to_dict(
            cast(Sequence[ConsolidationOpportunity | dict[str, object]], opportunities)
        )

        # Assert
        assert len(result) == 1
        # Should be cast to dict (even if it's not really a dict)
        assert result[0] == opp


class TestConvertRecommendationsToDict:
    """Test _convert_recommendations_to_dict helper."""

    def test_convert_dict_recommendations(self) -> None:
        """Test converting dictionary recommendations."""
        # Arrange
        recommendations = [
            {"id": "rec1", "file": "large.md"},
            {"id": "rec2", "file": "huge.md"},
        ]

        # Act
        result = convert_recommendations_to_dict(
            cast(Sequence[SplitRecommendation | dict[str, object]], recommendations)
        )

        # Assert
        assert len(result) == 2
        assert result[0]["id"] == "rec1"
        assert result[1]["id"] == "rec2"

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
        class SimpleRec:
            pass

        rec = SimpleRec()
        recommendations = [rec]

        # Act
        result = convert_recommendations_to_dict(
            cast(Sequence[SplitRecommendation | dict[str, object]], recommendations)
        )

        # Assert
        assert len(result) == 1
        # Should be cast to dict (even if it's not really a dict)
        assert result[0] == rec


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
            return_value=[{"id": "opp1", "similarity": 0.90}]
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
            return_value=[{"id": "split1", "file": "large.md"}]
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
            return_value={"total_files": 10}
        )
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(
            return_value=[{"type": "naming_inconsistency"}]
        )
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
            return_value={"avg_depth": 2}
        )

        mock_structure_mgr = MagicMock()
        mock_structure_mgr.get = AsyncMock(return_value=mock_structure_analyzer)

        mgrs = {"structure_analyzer": mock_structure_mgr}

        # Act
        result = await get_structure_data(cast(dict[str, object], mgrs))

        # Assert
        result_dict = result
        organization = cast(dict[str, object], result_dict["organization"])
        assert organization["total_files"] == 10
        anti_patterns = cast(list[object], result_dict["anti_patterns"])
        assert len(anti_patterns) == 1
        complexity_metrics = cast(dict[str, object], result_dict["complexity_metrics"])
        assert complexity_metrics["avg_depth"] == 2


class TestSuggestReorganization:
    """Test _suggest_reorganization helper."""

    @pytest.mark.asyncio
    async def test_suggest_reorganization_default_goal(self) -> None:
        """Test reorganization suggestions with default goal."""
        # Arrange
        mock_planner = MagicMock()
        mock_planner.create_reorganization_plan = AsyncMock(return_value={"moves": []})

        mock_structure_analyzer = MagicMock()
        mock_structure_analyzer.analyze_file_organization = AsyncMock(return_value={})
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(return_value={})

        mock_structure_mgr = MagicMock()
        mock_structure_mgr.get = AsyncMock(return_value=mock_structure_analyzer)

        mock_graph = MagicMock()
        mock_graph.to_dict.return_value = {"nodes": [], "edges": []}

        mgrs = {"structure_analyzer": mock_structure_mgr, "graph": mock_graph}

        # Act
        result = await suggest_reorganization(
            mock_planner, cast(dict[str, object], mgrs), None
        )

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
            return_value={"moves": [{"from": "a/b.md", "to": "b.md"}]}
        )

        mock_structure_analyzer = MagicMock()
        mock_structure_analyzer.analyze_file_organization = AsyncMock(return_value={})
        mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
        mock_structure_analyzer.measure_complexity_metrics = AsyncMock(return_value={})

        mock_structure_mgr = MagicMock()
        mock_structure_mgr.get = AsyncMock(return_value=mock_structure_analyzer)

        mock_graph = MagicMock()
        mock_graph.to_dict.return_value = {"nodes": [], "edges": []}

        mgrs = {"structure_analyzer": mock_structure_mgr, "graph": mock_graph}

        # Act
        result = await suggest_reorganization(
            mock_planner, cast(dict[str, object], mgrs), "category"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["goal"] == "category"
        assert len(result_data["plan"]["moves"]) == 1


class TestProcessRefactoringRequest:
    """Test _process_refactoring_request helper."""

    @pytest.mark.asyncio
    async def test_process_consolidation_request(self, tmp_path: Path) -> None:
        """Test processing consolidation refactoring request."""
        # Arrange
        with patch(
            "cortex.tools.analysis_operations.get_managers"
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
                "consolidation", str(tmp_path), 0.85, None, None, None
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["type"] == "consolidation"

    @pytest.mark.asyncio
    async def test_process_splits_request(self, tmp_path: Path) -> None:
        """Test processing splits refactoring request."""
        # Arrange
        with patch(
            "cortex.tools.analysis_operations.get_managers"
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
                "splits", str(tmp_path), None, 8000, None, None
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["type"] == "splits"

    @pytest.mark.asyncio
    async def test_process_reorganization_request(self, tmp_path: Path) -> None:
        """Test processing reorganization refactoring request."""
        # Arrange
        with patch(
            "cortex.tools.refactoring_operations.get_managers"
        ) as mock_get_managers:
            with patch(
                "cortex.tools.refactoring_operations.get_project_root",
                return_value=Path(str(tmp_path)),
            ):
                mock_planner = MagicMock()
                mock_planner.create_reorganization_plan = AsyncMock(return_value={})

                mock_reorg_mgr = MagicMock()
                mock_reorg_mgr.get = AsyncMock(return_value=mock_planner)

                mock_detector_mgr = MagicMock()
                mock_detector_mgr.get = AsyncMock(return_value=MagicMock())

                mock_split_mgr = MagicMock()
                mock_split_mgr.get = AsyncMock(return_value=MagicMock())

                mock_structure_analyzer = MagicMock()
                mock_structure_analyzer.analyze_file_organization = AsyncMock(
                    return_value={}
                )
                mock_structure_analyzer.detect_anti_patterns = AsyncMock(return_value=[])
                mock_structure_analyzer.measure_complexity_metrics = AsyncMock(
                    return_value={}
                )

                mock_structure_mgr = MagicMock()
                mock_structure_mgr.get = AsyncMock(return_value=mock_structure_analyzer)

                mock_graph = MagicMock()
                mock_graph.to_dict.return_value = {}

                mock_get_managers.return_value = {
                    "consolidation_detector": mock_detector_mgr,
                    "split_recommender": mock_split_mgr,
                    "reorganization_planner": mock_reorg_mgr,
                    "structure_analyzer": mock_structure_mgr,
                    "graph": mock_graph,
                }

                # Act
                result = await process_refactoring_request(
                    "reorganization", str(tmp_path), None, None, "category", None
                )

            # Assert
            result_data = json.loads(result)
            assert result_data["type"] == "reorganization"

    @pytest.mark.asyncio
    async def test_process_request_with_preview_mode(self, tmp_path: Path) -> None:
        """Test processing request with preview mode enabled."""
        # Arrange
        with patch(
            "cortex.tools.analysis_operations.get_managers"
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
                "consolidation", str(tmp_path), None, None, None, "consolidation_001"
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["preview_mode"] is True
            assert result_data["suggestion_id"] == "consolidation_001"


class TestSuggestRefactoringHandler:
    """Test main suggest_refactoring handler."""

    @pytest.mark.asyncio
    async def test_suggest_refactoring_consolidation(self, tmp_path: Path) -> None:
        """Test suggesting consolidation refactorings."""
        # Arrange
        with patch(
            "cortex.tools.analysis_operations.get_managers"
        ) as mock_get_managers:
            mock_detector = MagicMock()
            mock_detector.detect_opportunities = AsyncMock(
                return_value=[{"id": "opp1", "similarity": 0.85}]
            )

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
            result = await suggest_refactoring(
                type="consolidation", project_root=str(tmp_path), min_similarity=0.85
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
            project_root=str(tmp_path),
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
            "cortex.tools.refactoring_operations.get_managers"
        ) as mock_get_managers:
            mock_get_managers.side_effect = RuntimeError("Test error")

            # Act
            result = await suggest_refactoring(
                type="consolidation", project_root=str(tmp_path)
            )

            # Assert
            result_data = json.loads(result)
            assert result_data["status"] == "error"
            assert "Test error" in result_data["error"]
            assert result_data["error_type"] == "RuntimeError"
