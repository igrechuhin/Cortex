"""Tests for Phase 57 evaluation framework (run_tool_evaluation)."""

# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.phase5_evaluation import (
    EvalAnalysis,
    EvalSuiteResult,
    EvalTask,
    EvalTaskResult,
    ToolEvaluationHarness,
    _load_eval_tasks,
    run_tool_evaluation,
)


@pytest.mark.asyncio
async def test_load_eval_tasks_from_core_workflows() -> None:
    """_load_eval_tasks loads tasks from .cortex/evals/tasks/core_workflows.json."""
    project_root = Path(__file__).resolve().parents[2]
    tasks = await _load_eval_tasks(project_root, task_ids=None)

    # We expect at least a handful of tasks from the seeded core_workflows.json.
    assert len(tasks) >= 5
    ids = {t.id for t in tasks}
    assert "context-bugfix-validation-module" in ids
    assert "memory-validate-memory-bank-files" in ids


@pytest.mark.asyncio
async def test_load_eval_tasks_filters_by_task_ids() -> None:
    """_load_eval_tasks respects task_ids filter."""
    project_root = Path(__file__).resolve().parents[2]

    target_id = "context-add-new-mcp-tool"
    tasks = await _load_eval_tasks(project_root, task_ids=[target_id])

    assert tasks
    ids = {t.id for t in tasks}
    assert ids == {target_id}


@pytest.mark.asyncio
async def test_load_eval_tasks_returns_empty_when_tasks_dir_missing(
    tmp_path: Path,
) -> None:
    """_load_eval_tasks returns empty list when evals/tasks directory is missing."""
    project_root = tmp_path

    with patch(
        "cortex.tools.phase5_evaluation.get_cortex_path",
        return_value=project_root / ".cortex",
    ):
        tasks = await _load_eval_tasks(project_root, task_ids=None)

    assert tasks == []


def test_analyze_results_aggregates_basic_metrics() -> None:
    """ToolEvaluationHarness.analyze_results computes high-level metrics."""
    # Build a small synthetic suite with two tasks and known metrics.
    t1 = EvalTaskResult(
        task_id="t1",
        task_name="Task 1",
        category="context",
        status="success",
        total_calls=10,
        successful_calls=8,
        failed_calls=2,
        success_rate=0.8,
        avg_duration_ms=5.0,
        total_duration_ms=50.0,
        error_types={"ValueError": 2},
        evaluated_tools=["load_context"],
    )
    t2 = EvalTaskResult(
        task_id="t2",
        task_name="Task 2",
        category="pre_commit",
        status="mixed",
        total_calls=5,
        successful_calls=3,
        failed_calls=2,
        success_rate=0.6,
        avg_duration_ms=10.0,
        total_duration_ms=50.0,
        error_types={"TypeError": 1},
        evaluated_tools=["execute_pre_commit_checks"],
    )
    suite = EvalSuiteResult(
        generated_at="2026-02-17T00:00:00Z",
        tasks=[t1, t2],
    )
    harness = ToolEvaluationHarness(project_root=Path("/tmp"), tracker=None)

    analysis = harness.analyze_results(suite)

    assert isinstance(analysis, EvalAnalysis)
    assert analysis.total_tasks == 2
    # Overall success rate is the mean of per-task success rates.
    assert pytest.approx(analysis.overall_success_rate, rel=1e-6) == (0.8 + 0.6) / 2.0
    assert analysis.tasks_with_no_data == 0
    assert analysis.tasks_unavailable == 0
    assert pytest.approx(analysis.average_calls_per_task, rel=1e-6) == (10 + 5) / 2.0

    # Error patterns should include both error types with correct counts.
    patterns = {p.error_type: p for p in analysis.top_error_patterns}
    assert patterns["ValueError"].count == 2
    assert patterns["TypeError"].count == 1
    assert "context" in analysis.success_rate_by_category
    assert "pre_commit" in analysis.success_rate_by_category


def test_analyze_results_handles_empty_suite() -> None:
    """analyze_results returns zeroed metrics when there are no tasks."""
    suite = EvalSuiteResult(
        generated_at="2026-02-17T00:00:00Z",
        tasks=[],
    )
    harness = ToolEvaluationHarness(project_root=Path("/tmp"), tracker=None)

    analysis = harness.analyze_results(suite)

    assert isinstance(analysis, EvalAnalysis)
    assert analysis.total_tasks == 0
    assert analysis.overall_success_rate == 0.0
    assert analysis.tasks_with_no_data == 0
    assert analysis.tasks_unavailable == 0
    assert analysis.average_calls_per_task == 0.0
    assert analysis.top_error_patterns == []
    assert analysis.success_rate_by_category == {}


@pytest.mark.asyncio
async def test_run_tool_evaluation_uses_harness_and_writes_cache() -> None:
    """run_tool_evaluation wires together task loading, harness, and cache writes."""
    project_root = Path("/project")

    fake_tasks = [
        EvalTask(
            id="t1",
            name="Task 1",
            description="Test task 1",
            category="context",
            expected_tools=["load_context"],
            expected_outcome="ok",
        ),
        EvalTask(
            id="t2",
            name="Task 2",
            description="Test task 2",
            category="pre_commit",
            expected_tools=["execute_pre_commit_checks"],
            expected_outcome="ok",
        ),
    ]

    suite = EvalSuiteResult(
        generated_at="2026-02-17T00:00:00Z",
        tasks=[
            EvalTaskResult(
                task_id="t1",
                task_name="Task 1",
                category="context",
                status="success",
                total_calls=1,
                successful_calls=1,
                failed_calls=0,
                success_rate=1.0,
                avg_duration_ms=1.0,
                total_duration_ms=1.0,
                error_types={},
                evaluated_tools=["load_context"],
            )
        ],
    )
    analysis = EvalAnalysis(
        overall_success_rate=1.0,
        total_tasks=1,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=1.0,
        top_error_patterns=[],
        success_rate_by_category={"context": 1.0},
    )

    with (
        patch(
            "cortex.tools.phase5_evaluation.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=project_root,
        ),
        patch(
            "cortex.tools.phase5_evaluation._get_usage_tracker",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "cortex.tools.phase5_evaluation._load_eval_tasks",
            new_callable=AsyncMock,
            return_value=fake_tasks,
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.run_suite",
            new_callable=AsyncMock,
            return_value=suite,
        ) as mock_run_suite,
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.analyze_results",
            new=MagicMock(return_value=analysis),
        ) as mock_analyze,
        patch(
            "cortex.tools.phase5_evaluation.write_cache_json",
            new_callable=AsyncMock,
        ) as mock_write_cache,
    ):
        result = await run_tool_evaluation(task_ids=None, ctx=None)

    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tasks_loaded"] == len(fake_tasks)
    assert data["suite"]["generated_at"] == suite.generated_at
    assert data["analysis"]["total_tasks"] == analysis.total_tasks

    _ = mock_run_suite.assert_awaited_once()
    _ = mock_analyze.assert_called_once()
    _ = mock_write_cache.assert_awaited_once()
    args, _ = mock_write_cache.call_args
    # Second positional argument is the relative cache key.
    assert args[1] == "evals/last_suite.json"


@pytest.mark.asyncio
async def test_run_task_uses_usage_tracker_metrics() -> None:
    """ToolEvaluationHarness.run_task computes metrics from UsageTracker events."""

    class DummyTracker:
        async def search_usage(
            self,
            start_date: str | None = None,
            end_date: str | None = None,
            tool_name: str | None = None,
            success: bool | None = None,
            limit: int | None = None,
            query: str | None = None,
        ) -> list[ToolUsageEvent]:
            assert tool_name == "load_context"
            return [
                ToolUsageEvent(
                    tool_name="load_context",
                    timestamp="2026-02-17T00:00:00Z",
                    duration_ms=10.0,
                    success=True,
                    error_type=None,
                    handler_kind="tool",
                ),
                ToolUsageEvent(
                    tool_name="load_context",
                    timestamp="2026-02-17T00:00:01Z",
                    duration_ms=20.0,
                    success=False,
                    error_type="ValueError",
                    handler_kind="tool",
                ),
            ]

    task = EvalTask(
        id="t-metrics",
        name="Task Metrics",
        description="Test task metrics aggregation",
        category="context",
        expected_tools=["load_context"],
        expected_outcome="ok",
    )

    harness = ToolEvaluationHarness(
        project_root=Path("/project"),
        tracker=DummyTracker(),  # type: ignore[arg-type]
    )

    result = await harness.run_task(task)

    assert result.task_id == "t-metrics"
    assert result.total_calls == 2
    assert result.successful_calls == 1
    assert result.failed_calls == 1
    assert result.status == "mixed"
    assert pytest.approx(result.avg_duration_ms, rel=1e-6) == 15.0
    assert pytest.approx(result.total_duration_ms, rel=1e-6) == 30.0
    assert result.error_types == {"ValueError": 1}
    assert result.evaluated_tools == ["load_context"]
