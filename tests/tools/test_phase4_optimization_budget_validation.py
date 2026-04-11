# ruff: noqa: F403,F405
"""Split tests from Phase 4 optimization suite."""

from tests.tools.phase4_optimization_common import *  # noqa: F401,F403,F405


class TestContextBudgetValidation:
    """Test context budget validation for non-trivial tasks."""

    def test_is_non_trivial_task_detects_implement(self) -> None:
        """is_non_trivial_task detects 'implement' keyword."""
        assert is_non_trivial_task("Implement a new feature") is True
        assert is_non_trivial_task("implement authentication") is True

    def test_is_non_trivial_task_detects_fix(self) -> None:
        """is_non_trivial_task detects 'fix' keyword."""
        assert is_non_trivial_task("Fix a bug") is True
        assert is_non_trivial_task("debugging the issue") is True

    def test_is_non_trivial_task_detects_refactor(self) -> None:
        """is_non_trivial_task detects 'refactor' keyword."""
        assert is_non_trivial_task("Refactor the code") is True
        assert is_non_trivial_task("restructuring modules") is True

    def test_is_non_trivial_task_detects_test(self) -> None:
        """is_non_trivial_task detects 'test' keyword."""
        assert is_non_trivial_task("Test the functionality") is True
        assert is_non_trivial_task("verify the behavior") is True

    def test_is_non_trivial_task_detects_optimize(self) -> None:
        """is_non_trivial_task detects 'optimize' keyword."""
        assert is_non_trivial_task("Optimize performance") is True
        assert is_non_trivial_task("improving efficiency") is True

    def test_is_non_trivial_task_detects_update(self) -> None:
        """is_non_trivial_task detects 'update' keyword."""
        assert is_non_trivial_task("Update the module") is True
        assert is_non_trivial_task("modify the function") is True

    def test_is_non_trivial_task_detects_plan_and_planning(self) -> None:
        """is_non_trivial_task detects 'plan' and 'planning' keywords."""
        assert is_non_trivial_task("Plan the architecture") is True
        assert is_non_trivial_task("planning session optimization") is True
        assert is_non_trivial_task("Create a plan for Phase 9") is True

    def test_is_non_trivial_task_rejects_trivial(self) -> None:
        """is_non_trivial_task returns False for trivial tasks."""
        assert is_non_trivial_task("Read a file") is False
        assert is_non_trivial_task("Check status") is False
        assert is_non_trivial_task("List items") is False

    @pytest.mark.asyncio
    async def test_load_context_rejects_zero_budget_for_non_trivial(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """load_context returns validation error for token_budget=0 with non-trivial tasks."""
        # No patches: validation runs before initialization
        result_str = await _load_context_impl(
            task_description="Implement a new feature",
            token_budget=0,
            response_format="detailed",
        )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        err = result.get("error", "")
        assert "Explicit" in err or "non-trivial" in err.lower() or "zero" in err
        assert "suggestion" in result or "action_required" in result

    @pytest.mark.asyncio
    async def test_load_context_rejects_omitted_budget_for_non_trivial(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """load_context returns validation error when token_budget is omitted for non-trivial tasks."""
        # No patches: validation runs before initialization (token_budget=None)
        result_str = await _load_context_impl(
            task_description="Refactor the auth module",
            response_format="detailed",
        )
        result = json.loads(result_str)
        assert result.get("status") == "error"
        err = result.get("error", "")
        assert "Explicit" in err or "Omitted" in err or "non-trivial" in err.lower()
        assert "suggestion" in result or "action_required" in result

    @pytest.mark.asyncio
    async def test_load_context_allows_zero_budget_for_trivial(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """load_context allows token_budget=0 for trivial tasks."""
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
            # This should not error - trivial tasks can have zero budget
            # (though the actual loading may still fail if optimization is disabled)
            result_str = await _load_context_impl(
                task_description="Read a file",
                token_budget=0,
            )
            result = json.loads(result_str)
            # Should either succeed or fail for other reasons (optimization disabled, etc.)
            # but NOT fail with "token_budget=0 is not allowed"
            assert "token_budget=0 is not allowed" not in result.get("error", "")

    @pytest.mark.asyncio
    async def test_load_context_warns_zero_files_for_non_trivial(
        self, mock_project_root: Path, mock_managers: ManagersDict
    ) -> None:
        """load_context adds warning when non-trivial task results in zero files."""
        mock_result = json.dumps(
            {
                "status": "success",
                "task_description": "Implement a new feature",
                "token_budget": 10000,
                "selected_files": [],
                "total_tokens": 0,
            }
        )
        result = await run_load_context_impl_with_zero_files_handling_mock(
            mock_project_root, mock_managers, mock_result
        )
        assert result.get("status") == "success"
        warnings = result.get("warnings", [])
        assert len(warnings) > 0
        assert any(
            w.get("type") == "zero_files_selected" for w in warnings
        ), f"Expected zero_files_selected warning, got: {warnings}"


# ============================================================================
# Edge case: Phase 4 module facade exports (Phase 9.5 coverage)
# ============================================================================


def test_optimization_exports_all_public_api() -> None:
    """Validate optimization module exports all items in __all__."""
    import cortex.tools.optimization as m

    for name in m.__all__:
        assert hasattr(m, name), f"optimization.__all__ has {name!r} but missing"
        attr = getattr(m, name)
        assert attr is not None, f"optimization.{name} is None"
