# ruff: noqa: F403,F405
"""Split tests from Phase 4 optimization suite."""

from tests.tools.phase4_optimization_common import *  # noqa: F401,F403,F405


@pytest.mark.timeout(15)
class TestSummarizeContent:
    """Tests for summarize_content() tool."""

    async def test_summarize_single_file(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarizing a single file."""
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
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(
                file_name="file1.md", target_reduction=0.5
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_summarized"] == 1
            assert result["target_reduction"] == 0.5

    async def test_summarize_all_files(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarizing all files."""
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
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["files_summarized"] == 2  # Mock returns 2 files

    async def test_summarize_uses_config_defaults_when_args_none(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarize_content uses config defaults when target_reduction and strategy are None."""
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_summarization_enabled.return_value = True
        mock_optimization_config.get_summarization_target_reduction.return_value = 0.6
        mock_optimization_config.get_summarization_strategy.return_value = (
            "compress_verbose"
        )
        mock_optimization_config.is_optimization_enabled.return_value = True

        result = await run_summarize_with_config_overrides(
            mock_project_root,
            mock_managers,
            mock_optimization_config,
            _get_manager_helper,
        )
        assert result["status"] == "success"
        assert result["target_reduction"] == 0.6
        assert result["strategy"] == "compress_verbose"
        mock_optimization_config.get_summarization_target_reduction.assert_called_once()
        mock_optimization_config.get_summarization_strategy.assert_called_once()

    async def test_summarize_gated_on_summarization_enabled(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarize_content is gated on summarization.enabled."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_summarization_enabled.return_value = False
        mock_optimization_config.is_optimization_enabled.return_value = True

        def get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
            if key == "optimization_config":
                return mock_optimization_config
            return _get_manager_helper(mgrs, key, _)

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
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(file_name="file1.md")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "disabled" in result["error"].lower()

    async def test_optimization_tools_gated_on_top_level_enabled(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test optimization tools are gated on top-level enabled flag."""
        # Arrange
        mock_optimization_config = MagicMock()
        mock_optimization_config.is_optimization_enabled.return_value = False

        def get_manager_helper(mgrs: ManagersDict, key: str, _: object) -> object:
            if key == "optimization_config":
                return mock_optimization_config
            return _get_manager_helper(mgrs, key, _)

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
                "cortex.tools.optimization.handlers_load.get_manager",
                side_effect=get_manager_helper,
            ),
        ):
            # Act - test load_context (explicit budget so we reach disabled check)
            result_str = await _load_context_impl(
                task_description="test task", token_budget=50000
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "disabled" in result["error"].lower()

    async def test_summarize_with_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test summarization with different strategies."""
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
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await summarize_content(strategy="headers_only")
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["strategy"] == "headers_only"

    async def test_summarize_invalid_reduction(self, mock_project_root: Path) -> None:
        """Test summarization with invalid reduction value."""
        # Arrange - no need to mock managers as validation happens first

        # Act
        result_str = await summarize_content(target_reduction=1.5)
        result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert "target_reduction must be between 0 and 1" in result["error"]

    async def test_summarize_invalid_strategy(self, mock_project_root: Path) -> None:
        """Test summarization with invalid strategy."""
        # Arrange - no need to mock managers as validation happens first

        # Act
        result_str = await summarize_content(strategy="invalid_strategy")
        result = json.loads(result_str)

        # Assert
        assert result["status"] == "error"
        assert "Invalid strategy" in result["error"]

    async def test_summarize_exception_handling(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test exception handling in summarize_content."""
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
                "cortex.tools.optimization.summarization_operations.get_manager",
                side_effect=RuntimeError("Summarization failed"),
            ),
        ):
            # Act
            result_str = await summarize_content()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Summarization failed" in result["error"]


# ============================================================================
# Test get_relevance_scores()
# ============================================================================
