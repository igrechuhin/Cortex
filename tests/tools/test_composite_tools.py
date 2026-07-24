"""Tests for composite tools (run_composite_workflow dispatcher).

Composite tool chains multiple operations. Plan: agent-skills-and-composability Step 2,
tool consolidation.
"""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.composite_tools import run_composite_workflow


# Patches autofix, run_quality_gate, run_docs_gate, and validate_impl for fix_all tests.
@contextmanager
def _patch_fix_all_mocks(
    fix_result: dict[str, object],
    gate_result: dict[str, object],
    docs_result: dict[str, object],
    validate_result: str,
):
    with (
        patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.autofix",
            new_callable=AsyncMock,
            return_value=fix_result,
        ),
        patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_quality_gate",
            new_callable=AsyncMock,
            return_value=gate_result,
        ),
        patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_docs_gate",
            new_callable=AsyncMock,
            return_value=docs_result,
        ),
        patch(
            "cortex.tools.validation.operations.validate_impl",
            new_callable=AsyncMock,
            return_value=validate_result,
        ),
    ):
        yield


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
        """autofix() not called when run_quality_gate() passes (preflight_passed=True)."""
        pre_result = {
            "status": "success",
            "preflight_passed": True,
            "total_errors": 0,
        }
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_quality_gate",
            new_callable=AsyncMock,
            return_value=pre_result,
        ) as mock_gate:
            result = await run_composite_workflow(operation="quality_check")
            mock_gate.assert_awaited_once()
        out = json.loads(result)
        assert out["status"] == "success"
        assert out["pre_commit_result"] == pre_result
        assert out["fix_applied"] is False

    async def test_quality_check_calls_autofix_when_pre_has_errors(self) -> None:
        """autofix() called when run_quality_gate() returns preflight_passed=False."""
        pre_result = {"status": "error", "preflight_passed": False, "total_errors": 2}
        fix_result: dict[str, object] = {
            "status": "success",
            "files_modified": ["a.py"],
        }
        with patch(
            "cortex.tools.execution.pre_commit_zero_arg_tools.run_quality_gate",
            new_callable=AsyncMock,
            return_value=pre_result,
        ):
            with patch(
                "cortex.tools.execution.pre_commit_zero_arg_tools.autofix",
                new_callable=AsyncMock,
                return_value=fix_result,
            ) as mock_fix:
                result = await run_composite_workflow(operation="quality_check")
                mock_fix.assert_awaited_once()
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
        fix_result: dict[str, object] = {
            "status": "success",
            "files_modified": ["a.py"],
        }
        gate_result: dict[str, object] = {
            "status": "success",
            "preflight_passed": True,
            "total_errors": 0,
        }
        docs_result: dict[str, object] = {
            "status": "success",
            "docs_phase_passed": True,
        }
        validate_result = json.dumps({"status": "success", "valid": True})

        with _patch_fix_all_mocks(
            fix_result, gate_result, docs_result, validate_result
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
        """run_composite_workflow() with no args defaults to fix_all (some MCP bridges send {})."""
        ok: dict[str, object] = {"status": "success", "preflight_passed": True}
        docs_ok: dict[str, object] = {"status": "success", "docs_phase_passed": True}
        validate_result = json.dumps({"status": "success"})

        with _patch_fix_all_mocks(ok, ok, docs_ok, validate_result):
            result = await run_composite_workflow()

        out = json.loads(result)
        assert out["status"] == "success"
        assert "quality_fix" in out
        assert "tests" in out

    async def test_fix_all_calls_each_zero_arg_tool(self) -> None:
        """fix_all calls autofix, run_quality_gate (×2), run_docs_gate, then validate (×2)."""
        ok: dict[str, object] = {"status": "success", "preflight_passed": True}
        docs_ok: dict[str, object] = {"status": "success", "docs_phase_passed": True}
        validate_result = json.dumps({"status": "success"})

        with (
            patch(
                "cortex.tools.execution.pre_commit_zero_arg_tools.autofix",
                new_callable=AsyncMock,
                return_value=ok,
            ) as mock_fix,
            patch(
                "cortex.tools.execution.pre_commit_zero_arg_tools.run_quality_gate",
                new_callable=AsyncMock,
                return_value=ok,
            ) as mock_gate,
            patch(
                "cortex.tools.execution.pre_commit_zero_arg_tools.run_docs_gate",
                new_callable=AsyncMock,
                return_value=docs_ok,
            ) as mock_docs,
            patch(
                "cortex.tools.validation.operations.validate_impl",
                new_callable=AsyncMock,
                return_value=validate_result,
            ),
        ):
            _ = await run_composite_workflow(operation="fix_all")

        mock_fix.assert_awaited_once()
        assert mock_gate.await_count == 2  # verify + tests
        mock_docs.assert_awaited_once()
