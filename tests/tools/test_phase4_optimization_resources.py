# ruff: noqa: F403,F405
"""Split tests from Phase 4 optimization suite."""

from tests.tools.phase4_optimization_common import *  # noqa: F401,F403,F405


@pytest.mark.asyncio
class TestPhase4OptimizationResources:
    """Test Phase 4 optimization resources (Phase 43 Step 3.2)."""

    async def test_load_context_returns_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context returns JSON success (zero-arg, session config)."""
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={"task_description": "Test task"},
            ),
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
            result_str = await load_context()
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["task_description"] == "Test task"
        assert result["strategy"] == "dependency_aware"
        assert result["session_scope"] == SESSION_SCOPE_PROMPT
        assert (
            "Defer unrelated issues to a follow-up session" in result["session_scope"]
        )

    async def test_load_context_includes_recent_operations_when_log_exists(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context includes recent_operations section when log.md exists."""
        invalidate_context_resource_cache()
        write_test_operations_log(mock_project_root)
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={"task_description": "Test task with log"},
            ),
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
            result_str = await load_context()
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert "recent_operations" in result
        assert "## Recent Operations" in result["recent_operations"]
        assert "Created plan: One" in result["recent_operations"]

    async def test_load_context_omits_recent_operations_when_log_missing(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context omits recent_operations section when log.md is absent."""
        invalidate_context_resource_cache()
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={"task_description": "Test task without log"},
            ),
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
            result_str = await load_context()
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert "recent_operations" not in result

    async def test_load_context_includes_recent_artifacts_when_present(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context includes recent_artifacts when reviews/ or analyses/ have .md files."""
        invalidate_context_resource_cache()
        write_test_artifact_pages(mock_project_root)
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={"task_description": "Test task with artifacts"},
            ),
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
            result_str = await load_context()
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert "recent_artifacts" in result
        assert "## Recent Artifacts" in result["recent_artifacts"]
        assert "reviews/review-auth-2026-04-07.md" in result["recent_artifacts"]
        assert "Auth Review" in result["recent_artifacts"]

    async def test_load_context_omits_recent_artifacts_when_none(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context omits recent_artifacts when no filed pages exist."""
        invalidate_context_resource_cache()
        with (
            patch(
                "cortex.core.session_config.read_session_config",
                return_value={"task_description": "Test task no artifacts"},
            ),
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
            result_str = await load_context()
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert "recent_artifacts" not in result

    async def test_load_context_includes_scoped_context_packet(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context includes scoped_context and context_stats when scope is set."""
        invalidate_context_resource_cache()
        write_scoped_plan_fixtures(mock_project_root)
        result = await load_scoped_context_result(mock_project_root, mock_managers)
        scoped = cast(dict[str, object], result.get("scoped_context"))
        assert result["status"] == "success"
        assert isinstance(scoped, dict)
        assert scoped.get("scope") == "plan:scoped-plan"
        context_stats = cast(dict[str, object], scoped.get("context_stats"))
        assert context_stats["rules_sections_total"] == 3
        assert context_stats["rules_sections_included"] == 2

    async def test_load_context_derives_scope_from_plan_file(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """load_context builds scoped_context when only plan_file is provided."""
        invalidate_context_resource_cache()
        write_scoped_plan_fixtures(mock_project_root)
        result = await load_scoped_context_with_cfg(
            mock_project_root,
            mock_managers,
            {
                "task_description": "Scoped context from plan file",
                "plan_file": ".cortex/plans/scoped-plan.md",
            },
        )
        assert result["status"] == "success"
        assert scoped_scope(result) == "plan:scoped-plan"

    async def test_load_context_cache_key_includes_scope(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """Different scope values should not reuse the same cached payload."""
        invalidate_context_resource_cache()
        _ = mock_managers
        payload_one = json.dumps({"status": "success", "task_description": "first"})
        payload_two = json.dumps({"status": "success", "task_description": "second"})
        (
            first_result,
            second_result,
            call_count,
        ) = await load_context_scope_cache_results(
            mock_project_root, payload_one, payload_two
        )
        assert first_result["task_description"] == "first"
        assert second_result["task_description"] == "second"
        assert call_count == 2

    async def test_get_relevance_scores_resource_returns_success(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """get_relevance_scores_resource returns JSON success."""
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
            result_str = await get_relevance_scores_resource(
                task_description="relevance%20task"
            )
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert "file_scores" in result

    async def test_summarize_content_resource_single_file(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """summarize_content_resource with file_name returns JSON success."""
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
            result_str = await summarize_content_resource(file_name="file1.md")
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["target_reduction"] == 0.5
        assert result["strategy"] == "extract_key_sections"

    @pytest.mark.timeout(20)
    async def test_summarize_content_resource_all_files_with_underscore(
        self, mock_project_root: Path, mock_managers: dict[str, Any]
    ) -> None:
        """summarize_content_resource with file_name '_' summarizes all files."""
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
            result_str = await summarize_content_resource(file_name="_")
            result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["files_summarized"] == 2
