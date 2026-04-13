# ruff: noqa: F403,F405
"""Split tests from Phase 4 optimization suite."""

from tests.tools.phase4_optimization_common import *  # noqa: F401,F403,F405


class TestGetRelevanceScores:
    """Tests for get_relevance_scores() tool."""

    async def test_get_relevance_scores_files_only(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test getting relevance scores for files only."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.relevance_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_relevance_scores(
                task_description="Test task", include_sections=False
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_scored"] == 2
            assert "file_scores" in result
            assert "section_scores" not in result

    async def test_get_relevance_scores_with_sections(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test getting relevance scores including sections."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.relevance_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_relevance_scores(
                task_description="Test task", include_sections=True
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "file_scores" in result
            assert "section_scores" in result
            assert len(result["section_scores"]) == 2  # Mock returns 2 files

    async def test_get_relevance_scores_sorted(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test that relevance scores are sorted by total_score."""
        # Arrange
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=mock_managers,
            ),
            patch(
                "cortex.tools.optimization.relevance_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await get_relevance_scores(task_description="Test task")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            file_scores = result["file_scores"]
            scores = [v["total_score"] for v in file_scores.values()]
            assert scores == sorted(scores, reverse=True)  # Should be descending

    async def test_get_relevance_scores_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in get_relevance_scores."""
        # Arrange
        with patch(
            "cortex.tools.optimization.handlers.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Scoring failed"),
        ):
            # Act
            result_str = await get_relevance_scores(task_description="Test task")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Scoring failed" in result["error"]
            assert result["error_type"] == "RuntimeError"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for Phase 4 optimization workflows."""

    async def test_full_context_loading_workflow(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test complete workflow: load context -> score -> summarize."""
        (
            opt_data,
            scores_data,
            summary_data,
        ) = await run_full_context_score_summarize_workflow(
            mock_project_root, mock_managers, _get_manager_helper
        )
        assert opt_data["status"] == "success"
        assert scores_data["status"] == "success"
        assert summary_data["status"] == "success"


# ============================================================================
# Context logging (FastMCP)
# ============================================================================


@pytest.mark.asyncio
class TestPhase4OptimizationContextLogging:
    """Test Phase 4 optimization handlers use log_client when ctx is passed."""

    async def test_load_context_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """When ctx is passed, load_context logs start and completion."""
        mock_ctx = AsyncMock()
        mock_log = AsyncMock()
        result, levels_and_messages = await run_load_context_with_log_client_patched(
            mock_project_root,
            mock_managers,
            mock_ctx,
            mock_log,
            _get_manager_helper,
        )
        assert result.get("status") == "success"
        assert ("info", "load_context: starting") in levels_and_messages
        assert ("info", "load_context: completed") in levels_and_messages
