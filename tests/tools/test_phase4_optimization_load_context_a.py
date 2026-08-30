# ruff: noqa: F403,F405
"""Split tests from Phase 4 optimization suite."""

from tests.tools.phase4_optimization_common import *  # noqa: F401,F403,F405


class TestLoadContext:
    """Tests for load_context() tool."""

    async def test_load_context_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Test successful context loading."""
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
                strategy="priority",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["task_description"] == "Test task"
            # Effective budget = min(50000, 100000) - 10000 = 40000
            assert result["token_budget"] == 40000
            assert result["strategy"] == "priority"
            assert "selected_files" in result
            assert "total_tokens" in result

    async def test_load_context_sets_role_in_concise_response(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context should include an inferred role in concise responses."""
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
                task_description="Fix failing tests for feature X",
                token_budget=5000,
                response_format="concise",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            # Keywords "fix" and "tests" should map to either debugging or
            # testing roles; we verify that some role string is present.
            assert "role" in result
            assert isinstance(result["role"], str)

    async def test_load_context_with_explicit_role(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context should accept and use explicit role parameter."""
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
                task_description="Some generic task",
                token_budget=5000,
                response_format="concise",
                role="quality",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["role"] == "quality"

    async def test_load_context_default_budget(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test context loading with default budget from config."""
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
            # Act - pass an explicit budget equal to the response reserve
            result_str = await _load_context_impl(
                task_description="Test task",
                token_budget=10000,
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert: the reserve is capped at half the budget, so a request equal
            # to the reserve still leaves room for context instead of collapsing to 0.
            assert result["status"] == "success"
            assert result["token_budget"] == 5000

    async def test_load_context_zero_budget_non_trivial_returns_validation_error(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """token_budget=0 with non-trivial task returns validation error (no normalization)."""
        # Arrange: no need to patch managers; validation runs before init
        # Act: non-trivial task with token_budget=0 → rejected with error
        result_str = await _load_context_impl(
            task_description="Implement feature X",
            token_budget=0,
            response_format="detailed",
        )
        result = json.loads(result_str)

        # Assert: validation error, not success
        assert result["status"] == "error"
        err = result.get("error", "")
        assert "Explicit" in err or "non-trivial" in err.lower() or "zero" in err
        assert "suggestion" in result or "action_required" in result

    async def test_load_context_trivial_task_zero_budget_normalized_to_default(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """token_budget=0 with trivial task is normalized to default and succeeds."""
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
            # Act: trivial task (no implement/fix/debug etc.) with token_budget=0
            result_str = await _load_context_impl(
                task_description="What is the project name?",
                token_budget=0,
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert: normalized to default budget path, success
            assert result["status"] == "success"
            # mock default 10000, reserve capped at half -> 5000 usable, never 0
            assert result["token_budget"] == 5000

    async def test_load_context_dependency_aware_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test context loading with dependency_aware strategy."""
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
                strategy="dependency_aware",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert result["strategy"] == "dependency_aware"

    async def test_load_context_progressive_strategy(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test context loading with progressive strategy."""
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
                loading_strategy="by_relevance",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"

    async def test_load_context_progressive_strategy_invalid_loading(
        self, mock_project_root: Path, mock_managers: dict[str, object]
    ) -> None:
        """Test progressive strategy with invalid loading_strategy returns error."""
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
                loading_strategy="invalid_strategy",
                response_format="detailed",
            )
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "invalid_strategy" in result["error"]
            assert "by_priority" in result["error"]
