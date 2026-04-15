"""Tests for Phase 57 Step 2 execution-based evaluation harness."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from cortex.managers.initialization import get_project_root
from cortex.tools.evaluation import (
    EvalRunMode,
    EvalTask,
    EvalTaskCategory,
    ExecutionExpectSpec,
    ExecutionExpectType,
    ExecutionSpec,
)
from cortex.tools.evaluation.evaluation_execution import (
    ExecutionResult,
    build_execution_summary,
    run_execution_suite,
    run_one_execution,
)
from cortex.tools.evaluation.evaluation_execution_registry import get_tool_invoker


def _task_without_execution() -> EvalTask:
    return EvalTask(
        id="no-exec",
        name="No execution",
        description="Usage-only task",
        category=EvalTaskCategory.OTHER,
        expected_tools=["load_context"],
        expected_outcome="Context loaded.",
    )


def _task_with_execution(
    task_id: str = "exec-1",
    tool: str = "get_structure_info",
    expect_type: ExecutionExpectType = ExecutionExpectType.CONTAINS,
    substring: str = "structure_info",
) -> EvalTask:
    return EvalTask(
        id=task_id,
        name="Exec task",
        description="Task with execution spec",
        category=EvalTaskCategory.OTHER,
        expected_tools=[tool],
        expected_outcome="Tool returns expected output.",
        execution=ExecutionSpec(
            tool=tool,
            arguments={},
            expect=ExecutionExpectSpec(type=expect_type, substring=substring),
        ),
    )


@pytest.mark.asyncio
async def test_run_one_execution_skipped_when_no_spec() -> None:
    """run_one_execution returns skipped when task has no execution spec."""
    task = _task_without_execution()
    result = await run_one_execution(task)
    assert result.skipped
    assert result.passed
    assert "no execution spec" in result.message


@pytest.mark.asyncio
async def test_run_one_execution_passes_with_contains() -> None:
    """run_one_execution passes when tool output contains expected substring."""
    task = _task_with_execution()
    with patch(
        "cortex.tools.evaluation.evaluation_execution._invoke_tool",
        new_callable=AsyncMock,
        return_value='{"success": true, "structure_info": {}}',
    ):
        result = await run_one_execution(task)
    assert not result.skipped
    assert result.passed
    assert "contains" in result.message.lower() or "substring" in result.message.lower()


@pytest.mark.asyncio
async def test_run_one_execution_fails_when_substring_missing() -> None:
    """run_one_execution fails when output does not contain expected substring."""
    task = _task_with_execution(substring="nonexistent_key")
    with patch(
        "cortex.tools.evaluation.evaluation_execution._invoke_tool",
        new_callable=AsyncMock,
        return_value='{"success": true}',
    ):
        result = await run_one_execution(task)
    assert not result.skipped
    assert not result.passed
    assert (
        "missing" in result.message.lower() or "nonexistent" in result.message.lower()
    )


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_run_execution_suite_fast_mode_limits_tasks() -> None:
    """run_execution_suite in fast mode runs at most fast_cap tasks with execution."""
    project_root = get_project_root()
    from cortex.tools.evaluation import load_eval_tasks

    tasks = await load_eval_tasks(project_root, task_ids=None)
    results = await run_execution_suite(tasks, mode=EvalRunMode.FAST, fast_cap=10)
    assert len(results) <= 10
    run_count = sum(1 for r in results if not r.skipped)
    assert run_count <= 10


@pytest.mark.asyncio
async def test_run_execution_suite_focused_mode_filters_by_category() -> None:
    """run_execution_suite in focused mode only runs tasks in the given category."""
    tasks = [
        _task_with_execution(task_id="a").model_copy(
            update={"category": EvalTaskCategory.CONTEXT}
        ),
        _task_with_execution(task_id="b").model_copy(
            update={"category": EvalTaskCategory.PRE_COMMIT}
        ),
    ]
    with patch(
        "cortex.tools.evaluation.evaluation_execution._invoke_tool",
        new_callable=AsyncMock,
        return_value='{"structure_info": {}}',
    ):
        results = await run_execution_suite(
            tasks, mode=EvalRunMode.FOCUSED, category=EvalTaskCategory.CONTEXT
        )
    assert len(results) == 1
    assert results[0].task_id == "a"


def test_build_execution_summary() -> None:
    """build_execution_summary aggregates passed/failed/skipped counts."""
    results = [
        ExecutionResult("t1", True, "ok", 10.0, False),
        ExecutionResult("t2", False, "fail", 5.0, False),
        ExecutionResult("t3", True, "skipped", 0.0, True),
    ]
    summary = build_execution_summary(results)
    assert summary.execution_passed == 1
    assert summary.execution_failed == 1
    assert summary.execution_skipped == 1
    assert summary.execution_total_run == 2
    assert len(summary.results) == 3


def test_get_tool_invoker_returns_invoker_for_registered_tool() -> None:
    """get_tool_invoker returns a callable for get_structure_info."""
    invoker = get_tool_invoker("get_structure_info")
    assert invoker is not None


def test_get_tool_invoker_returns_none_for_unknown_tool() -> None:
    """get_tool_invoker returns None for unregistered tool."""
    invoker = get_tool_invoker("nonexistent_tool_xyz")
    assert invoker is None
