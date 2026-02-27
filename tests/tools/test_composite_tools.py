"""Tests for composite tools (run_composite_workflow dispatcher).

Composite tool chains multiple operations. Plan: agent-skills-and-composability Step 2,
tool consolidation.
"""

import json
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
            "cortex.tools.session_dispatcher.session",
            new_callable=AsyncMock,
            return_value=json.dumps(brief_data),
        ):
            with patch(
                "cortex.tools.phase4_optimization_handlers.load_context",
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
            "cortex.tools.session_dispatcher.session",
            new_callable=AsyncMock,
            return_value=json.dumps(brief_data),
        ):
            with patch(
                "cortex.tools.phase4_optimization_handlers.load_context",
                new_callable=AsyncMock,
                return_value=json.dumps(context_data),
            ) as mock_load:
                await run_composite_workflow(operation="quick_start")
                mock_load.assert_awaited_once()
                call_kwargs = mock_load.call_args[1]
                assert call_kwargs["token_budget"] == 10000

    async def test_quick_start_general_task_when_no_description(self) -> None:
        """run_composite_workflow quick_start uses 'general task' when task_description empty."""
        brief_data = {"status": "success"}
        context_data = {"status": "success"}
        with patch(
            "cortex.tools.session_dispatcher.session",
            new_callable=AsyncMock,
            return_value=json.dumps(brief_data),
        ):
            with patch(
                "cortex.tools.phase4_optimization_handlers.load_context",
                new_callable=AsyncMock,
                return_value=json.dumps(context_data),
            ) as mock_load:
                await run_composite_workflow(
                    operation="quick_start", task_description=""
                )
                call_kwargs = mock_load.call_args[1]
                assert call_kwargs["task_description"] == "general task"


@pytest.mark.asyncio
class TestAgentWorkflowQualityCheck:
    """Tests for run_composite_workflow(operation='quality_check')."""

    async def test_quality_check_skips_fix_when_pre_passes(self) -> None:
        """fix_quality_issues not called when execute_pre_commit_checks passes."""
        pre_result = {
            "status": "success",
            "total_errors": 0,
            "total_warnings": 0,
        }
        with patch(
            "cortex.tools.pre_commit_tools.execute_pre_commit_checks",
            new_callable=AsyncMock,
            return_value=pre_result,
        ):
            with patch(
                "cortex.tools.pre_commit_tools.fix_quality_issues",
                new_callable=AsyncMock,
            ) as mock_fix:
                result = await run_composite_workflow(operation="quality_check")
                mock_fix.assert_not_awaited()
        out = json.loads(result)
        assert out["status"] == "success"
        assert out["pre_commit_result"] == pre_result
        assert out["fix_applied"] is False

    async def test_quality_check_calls_fix_when_pre_has_errors(self) -> None:
        """fix_quality_issues called when execute_pre_commit_checks has errors."""
        pre_result = {"status": "error", "total_errors": 2}
        fix_result = {"status": "success", "files_modified": ["a.py"]}
        with patch(
            "cortex.tools.pre_commit_tools.execute_pre_commit_checks",
            new_callable=AsyncMock,
            return_value=pre_result,
        ):
            with patch(
                "cortex.tools.pre_commit_tools.fix_quality_issues",
                new_callable=AsyncMock,
                return_value=json.dumps(fix_result),
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
            "cortex.tools.validation_operations.validate",
            new_callable=AsyncMock,
            side_effect=[json.dumps(pre_val), json.dumps(post_val)],
        ):
            with patch(
                "cortex.tools.file_crud_operations.manage_file",
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
            "cortex.tools.validation_operations.validate",
            new_callable=AsyncMock,
            side_effect=[json.dumps(pre_val), json.dumps(post_val)],
        ) as mock_validate:
            with patch(
                "cortex.tools.file_crud_operations.manage_file",
                new_callable=AsyncMock,
                return_value=json.dumps(file_result),
            ):
                await run_composite_workflow(
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
        assert "file_name" in out["message"].lower()
