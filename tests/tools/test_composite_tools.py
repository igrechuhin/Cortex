"""Tests for composite tools (run_composite_workflow dispatcher).

Composite tool chains multiple operations. Plan: agent-skills-and-composability Step 2,
tool consolidation.
"""

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.composite_tools import run_composite_workflow


@pytest.mark.asyncio
class TestAgentWorkflowQuickStart:
    """Tests for run_composite_workflow(operation='quick_start')."""

    async def test_quick_start_returns_combined_result(self) -> None:
        """run_composite_workflow(operation='quick_start') returns session_brief and context."""
        brief_data = {"status": "success", "brief": {"current_focus": "test"}}
        context_data = {"status": "success", "total_tokens": 500}
        with patch(
            "cortex.tools.session.dispatcher.session",
            new_callable=AsyncMock,
            return_value=json.dumps(brief_data),
        ):
            with patch(
                "cortex.tools.optimization.load_context_impl",
                new_callable=AsyncMock,
                return_value=json.dumps(context_data),
            ):
                result = await run_composite_workflow(
                    operation="quick_start",
                    task_description="implement feature",
                    token_budget=10000,
                )
        out = json.loads(result)
        assert out["status"] == "success"
        assert "session_brief" in out
        assert out["session_brief"] == brief_data
        assert "context" in out
        assert out["context"] == context_data

    async def test_quick_start_default_budget_when_omitted(self) -> None:
        """run_composite_workflow quick_start uses 10000 token budget when omitted."""
        brief_data = {"status": "success"}
        context_data = {"status": "success"}
        with patch(
            "cortex.tools.session.dispatcher.session",
            new_callable=AsyncMock,
            return_value=json.dumps(brief_data),
        ):
            with patch(
                "cortex.tools.optimization.load_context_impl",
                new_callable=AsyncMock,
                return_value=json.dumps(context_data),
            ) as mock_load:
                _ = await run_composite_workflow(operation="quick_start")
                mock_load.assert_awaited_once()
                call_kwargs = mock_load.call_args[1]
                assert call_kwargs["token_budget"] == 10000

    async def test_quick_start_general_task_when_no_description(self) -> None:
        """run_composite_workflow quick_start uses 'general task' when task_description empty."""
        brief_data = {"status": "success"}
        context_data = {"status": "success"}
        with patch(
            "cortex.tools.session.dispatcher.session",
            new_callable=AsyncMock,
            return_value=json.dumps(brief_data),
        ):
            with patch(
                "cortex.tools.optimization.load_context_impl",
                new_callable=AsyncMock,
                return_value=json.dumps(context_data),
            ) as mock_load:
                _ = await run_composite_workflow(
                    operation="quick_start", task_description=""
                )
                call_kwargs = mock_load.call_args[1]
                assert call_kwargs["task_description"] == "general task"

    async def test_quick_start_error_when_session_returns_invalid_json(self) -> None:
        """quick_start returns error status when session(start) is not valid JSON."""
        context_data = {"status": "success"}
        with patch(
            "cortex.tools.session.dispatcher.session",
            new_callable=AsyncMock,
            return_value="{not valid json",
        ):
            with patch(
                "cortex.tools.optimization.load_context_impl",
                new_callable=AsyncMock,
                return_value=json.dumps(context_data),
            ):
                result = await run_composite_workflow(operation="quick_start")
        out = json.loads(result)
        assert out["status"] == "error"
        assert "session(start)" in out["error"]


@pytest.mark.asyncio
class TestAgentWorkflowQualityCheck:
    """Tests for run_composite_workflow(operation='quality_check')."""

    async def test_quality_check_skips_fix_when_pre_passes(self) -> None:
        """fix_quality not called when execute_pre_commit_checks(quality) passes."""
        pre_result = {
            "status": "success",
            "total_errors": 0,
            "total_warnings": 0,
        }
        with patch(
            "cortex.tools.execution.pre_commit_tools.execute_pre_commit_checks",
            new_callable=AsyncMock,
            return_value=pre_result,
        ) as mock_exec:
            result = await run_composite_workflow(operation="quality_check")
            mock_exec.assert_awaited_once()
        out = json.loads(result)
        assert out["status"] == "success"
        assert out["pre_commit_result"] == pre_result
        assert out["fix_applied"] is False

    async def test_quality_check_calls_fix_quality_when_pre_has_errors(self) -> None:
        """execute_pre_commit_checks(fix_quality) called when quality has errors."""
        pre_result = {"status": "error", "total_errors": 2}
        fix_result: dict[str, object] = {
            "status": "success",
            "files_modified": ["a.py"],
        }
        with patch(
            "cortex.tools.execution.pre_commit_tools.execute_pre_commit_checks",
            new_callable=AsyncMock,
            side_effect=[pre_result, fix_result],
        ) as mock_exec:
            result = await run_composite_workflow(operation="quality_check")
            assert mock_exec.await_count == 2
            calls = mock_exec.call_args_list
            assert calls[0][1]["checks"] == ["quality"]
            assert calls[1][1]["checks"] == ["fix_quality"]
        out = json.loads(result)
        assert out["status"] == "success"
        assert out["fix_applied"] is True
        assert out["fix_result"] == fix_result


@pytest.mark.asyncio
class TestAgentWorkflowSafeManageFile:
    """Tests for run_composite_workflow(operation='safe_manage_file')."""

    async def test_safe_manage_file_returns_pre_file_post(self) -> None:
        """safe_manage_file returns pre_validation, manage_file_result, post_validation."""
        pre_val = {"status": "success", "valid": True}
        file_result = {"status": "success", "file_name": "roadmap.md"}
        post_val = {"status": "success", "valid": True}
        with patch(
            "cortex.tools.validation.operations.validate_impl",
            new_callable=AsyncMock,
            side_effect=[json.dumps(pre_val), json.dumps(post_val)],
        ):
            with patch(
                "cortex.tools.files.crud_operations.manage_file",
                new_callable=AsyncMock,
                return_value=json.dumps(file_result),
            ):
                result = await run_composite_workflow(
                    operation="safe_manage_file",
                    file_name="roadmap.md",
                    file_operation="read",
                    check_type="roadmap_sync",
                )
        out = json.loads(result)
        assert out["status"] == "success"
        assert out["pre_validation"] == pre_val
        assert out["manage_file_result"] == file_result
        assert out["post_validation"] == post_val

    async def test_safe_manage_file_default_check_type(self) -> None:
        """safe_manage_file uses roadmap_sync as default check_type."""
        pre_val = {"status": "success"}
        file_result = {"status": "success"}
        post_val = {"status": "success"}
        with patch(
            "cortex.tools.validation.operations.validate_impl",
            new_callable=AsyncMock,
            side_effect=[json.dumps(pre_val), json.dumps(post_val)],
        ) as mock_validate:
            with patch(
                "cortex.tools.files.crud_operations.manage_file",
                new_callable=AsyncMock,
                return_value=json.dumps(file_result),
            ):
                _ = await run_composite_workflow(
                    operation="safe_manage_file",
                    file_name="activeContext.md",
                    file_operation="read",
                )
                calls = mock_validate.call_args_list
                assert len(calls) == 2
                for call in calls:
                    assert call[1]["check_type"].value == "roadmap_sync"

    async def test_safe_manage_file_requires_file_name_and_operation(self) -> None:
        """Missing file_name or file_operation returns error."""
        result = await run_composite_workflow(operation="safe_manage_file")
        out = json.loads(result)
        assert out["status"] == "error"
        assert "file_name" in out["error"].lower()


@pytest.mark.asyncio
class TestAgentWorkflowFixAll:
    """Tests for run_composite_workflow(operation='fix_all')."""

    async def test_fix_all_returns_all_targets(self) -> None:
        """fix_all returns quality_fix, quality_verify, tests, docs_phase_b, timestamps, roadmap_sync."""
        fix_result = {"status": "success", "files_modified": ["a.py"]}
        verify_result = {"status": "success", "total_errors": 0}
        tests_result = {"status": "success", "coverage": 0.95}
        docs_result = {"status": "success", "docs_phase_passed": True}
        validate_result = json.dumps({"status": "success", "valid": True})

        with patch(
            "cortex.tools.execution.pre_commit_tools.execute_pre_commit_checks",
            new_callable=AsyncMock,
            side_effect=[fix_result, verify_result, tests_result, docs_result],
        ):
            with patch(
                "cortex.tools.validation.operations.validate_impl",
                new_callable=AsyncMock,
                return_value=validate_result,
            ):
                result = await run_composite_workflow(operation="fix_all")

        out = json.loads(result)
        assert out["status"] == "success"
        assert "quality_fix" in out
        assert "quality_verify" in out
        assert "tests" in out
        assert "docs_phase_b" in out
        assert "timestamps" in out
        assert "roadmap_sync" in out

    async def test_fix_all_no_args_runs_fix_all(self) -> None:
        """run_composite_workflow() with no args defaults to fix_all (Cursor bridge sends {})."""
        ok: dict[str, object] = {"status": "success", "total_errors": 0}
        validate_result_dict: dict[str, object] = {"status": "success"}
        _ = json.dumps(validate_result_dict)
        validate_result = json.dumps({"status": "success"})

        with patch(
            "cortex.tools.execution.pre_commit_tools.execute_pre_commit_checks",
            new_callable=AsyncMock,
            return_value=ok,
        ):
            with patch(
                "cortex.tools.validation.operations.validate_impl",
                new_callable=AsyncMock,
                return_value=validate_result,
            ):
                result = await run_composite_workflow()

        out = json.loads(result)
        assert out["status"] == "success"
        assert "quality_fix" in out
        assert "tests" in out

    async def test_fix_all_clears_cache_before_verify(self) -> None:
        """fix_all clears result cache after fix_quality so verify sees fresh results."""
        ok: dict[str, object] = {"status": "success", "total_errors": 0}
        validate_result = json.dumps({"status": "success"})
        from pathlib import Path

        with patch(
            "cortex.tools.execution.pre_commit_tools.execute_pre_commit_checks",
            new_callable=AsyncMock,
            return_value=ok,
        ):
            with patch(
                "cortex.tools.validation.operations.validate_impl",
                new_callable=AsyncMock,
                return_value=validate_result,
            ):
                with patch(
                    "cortex.core.usage_context.get_current_project_root",
                    return_value=Path("/fake/root"),
                ):
                    with patch(
                        "cortex.tools.execution.pre_commit_detached.clear_all_cached_results"
                    ) as mock_clear:
                        _ = await run_composite_workflow(operation="fix_all")

        mock_clear.assert_called_once_with(Path("/fake/root"))

    async def test_fix_all_calls_correct_check_sequences(self) -> None:
        """fix_all calls fix_quality, then type_check/quality/format/markdown, then tests, then phase B."""
        ok: dict[str, object] = {"status": "success", "total_errors": 0}
        validate_result = json.dumps({"status": "success"})

        with patch(
            "cortex.tools.execution.pre_commit_tools.execute_pre_commit_checks",
            new_callable=AsyncMock,
            return_value=ok,
        ) as mock_exec:
            with patch(
                "cortex.tools.validation.operations.validate_impl",
                new_callable=AsyncMock,
                return_value=validate_result,
            ):
                _ = await run_composite_workflow(operation="fix_all")

        assert mock_exec.await_count == 4
        calls = mock_exec.call_args_list
        assert calls[0][1]["checks"] == ["fix_quality"]
        assert calls[1][1]["checks"] == ["type_check", "quality", "format", "markdown"]
        assert calls[2][1]["checks"] == ["tests"]
        assert calls[3][1].get("phase") == "B"

    @staticmethod
    def _poll_test_payloads() -> tuple[dict[str, object], dict[str, object], str]:
        fix: dict[str, object] = {"status": "success", "files_modified": []}
        full: dict[str, object] = {
            "status": "success",
            "results": {"type_check": {"success": False, "output": "error: no attr"}},
        }
        val = json.dumps({"status": "success"})
        return fix, full, val

    @staticmethod
    def _poll_test_patches():
        """Return context manager + mock_poll for detached-job poll test."""
        stub: dict[str, object] = {"job_id": "abc123", "status": "started"}
        fix, full, val = TestAgentWorkflowFixAll._poll_test_payloads()

        @contextmanager
        def _ctx():
            with (
                patch(
                    "cortex.tools.execution.pre_commit_tools.execute_pre_commit_checks",
                    new_callable=AsyncMock,
                    side_effect=[fix, stub, stub, stub],
                ),
                patch(
                    "cortex.tools.validation.operations.validate_impl",
                    new_callable=AsyncMock,
                    return_value=val,
                ),
                patch(
                    "cortex.core.usage_context.get_current_project_root",
                    return_value=Path("/fake/root"),
                ),
                patch(
                    "cortex.tools.execution.pre_commit_detached.clear_all_cached_results"
                ),
                patch(
                    "cortex.tools.execution.pre_commit_detached.poll_job_to_completion",
                    new_callable=AsyncMock,
                    return_value=full,
                ) as mp,
            ):
                yield mp

        return _ctx()

    async def test_fix_all_polls_detached_jobs_to_completion(self) -> None:
        """fix_all polls job stubs to completion so quality_verify has output."""
        from pathlib import Path

        with self._poll_test_patches() as mock_poll:
            result = await run_composite_workflow(operation="fix_all")

        out = json.loads(result)
        assert out["status"] == "success"
        assert mock_poll.await_count == 3
        assert mock_poll.call_args_list[0][0] == (Path("/fake/root"), "abc123")
