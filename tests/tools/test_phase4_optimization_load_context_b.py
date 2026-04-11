# ruff: noqa: F403,F405
"""Split tests from Phase 4 optimization suite."""

from tests.tools.phase4_optimization_common import *  # noqa: F401,F403,F405


class TestLoadContextPartB:
    """Additional load_context tests split from large module."""

    async def test_load_context_progressive_strategy_by_dependencies(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive strategy with by_dependencies loading."""
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
                "cortex.tools.optimization.progressive_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await _load_context_impl(
                task_description="Test task",
                token_budget=50000,
                strategy="progressive",
                loading_strategy="by_dependencies",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_load_context_progressive_strategy_default_loading(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive strategy with default loading_strategy (by_relevance)."""
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
                "cortex.tools.optimization.progressive_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act - don't specify loading_strategy, should default to "by_relevance"
            result_str = await _load_context_impl(
                task_description="Test task",
                token_budget=50000,
                strategy="progressive",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_load_context_exception_handling(
        self, mock_project_root: Path
    ) -> None:
        """Test exception handling in load_context."""
        # Arrange - exception raised in load module's initialization
        with patch(
            "cortex.tools.optimization.handlers_load.resolve_project_root_async",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Test error"),
        ):
            # Act
            result_str = await _load_context_impl(
                task_description="Test task", token_budget=50000
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "Test error" in result["error"]
            assert result["error_type"] == "RuntimeError"

    async def test_load_context_optimization_disabled(
        self, mock_project_root: Path
    ) -> None:
        """Test load_context when optimization is disabled."""
        # Arrange - create managers with optimization disabled
        disabled_optimization_config = MagicMock()
        disabled_optimization_config.is_optimization_enabled = MagicMock(
            return_value=False
        )
        disabled_managers = make_test_managers(
            optimization_config=disabled_optimization_config
        )
        with (
            patch(
                "cortex.tools.optimization.handlers.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=mock_project_root,
            ),
            patch(
                "cortex.tools.optimization.get_managers",
                return_value=disabled_managers,
            ),
        ):
            # Act
            result_str = await _load_context_impl(
                task_description="Test task", token_budget=50000
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "disabled" in result["error"].lower()

    async def test_load_context_concise_format(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test load_context with concise response format."""
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
                "cortex.tools.context.load_operations.get_manager",
                side_effect=_get_manager_helper,
            ),
        ):
            # Act
            result_str = await _load_context_impl(
                task_description="Test task",
                token_budget=50000,
                response_format="concise",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "file_names" in result  # Concise format uses file_names
            assert "selected_files" not in result  # Detailed format uses selected_files
            assert isinstance(result["file_names"], list)  # file_names is always a list

    async def test_load_context_concise_format_with_non_dict_selected_files(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test concise format when selected_files is not a dict (edge case)."""
        payload = {
            "status": "success",
            "task_description": "Test",
            "strategy": "priority",
            "selected_files": ["file1.md", "file2.md"],
            "total_tokens": 1000,
            "utilization": 0.5,
        }
        result = await run_concise_load_context_with_payload(
            mock_project_root, mock_managers, payload
        )
        assert result["status"] == "success"
        assert result["file_names"] == []

    async def test_load_context_concise_format_with_none_selected_files(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test concise format when selected_files is None (edge case)."""
        payload = {
            "status": "success",
            "task_description": "Test",
            "strategy": "priority",
            "selected_files": None,
            "total_tokens": 1000,
            "utilization": 0.5,
        }
        result = await run_concise_load_context_with_payload(
            mock_project_root, mock_managers, payload
        )
        assert result["status"] == "success"
        assert result["file_names"] == []

    async def test_load_context_concise_format_with_invalid_json(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test concise format when load_context_impl returns invalid JSON (error handling)."""

        # Arrange - patch load_context_impl to return invalid JSON
        async def mock_load_context_impl(*args: Any, **kwargs: Any) -> str:
            """Mock that returns invalid JSON."""
            return "invalid json {"

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
                "cortex.tools.optimization.handlers_load.load_context_impl",
                side_effect=mock_load_context_impl,
            ),
        ):
            # Act
            result_str = await _load_context_impl(
                task_description="Test task",
                token_budget=50000,
                response_format="concise",
            )

            # Assert - when JSON parsing fails, original response is returned
            assert result_str == "invalid json {"
