"""Tests for Phase 57 evaluation framework (run_tool_evaluation)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import HandlerKind
from cortex.managers.usage_models import ToolUsageEvent
from cortex.tools.phase5_evaluation import (
    ABComparisonResult,
    ABWinner,
    ErrorPattern,
    EvalAnalysis,
    EvalSuiteResult,
    EvalTask,
    EvalTaskCategory,
    EvalTaskResult,
    EvalTaskStatus,
    OptimizationRunRecord,
    OptimizationRunWinner,
    ToolEvaluationHarness,
    ToolTaskMetrics,
    analyze_error_patterns,
    append_optimization_record,
    compare_ab_analyses,
    get_session_tool_anomalies,
    load_eval_tasks,
    load_optimization_history,
    run_tool_evaluation,
    run_tool_optimization_workflow,
)
from cortex.tools.phase5_evaluation_anomalies_helpers import (
    aggregate_session_tool_anomalies,
)
from cortex.tools.phase5_evaluation_dashboard_helpers import (
    aggregate_tool_metrics,
    format_token_efficiency,
    generate_evaluation_dashboard,
)


@pytest.mark.asyncio
async def test_load_eval_tasks_from_core_workflows() -> None:
    """load_eval_tasks loads tasks from .cortex/evals/tasks/core_workflows.json."""
    project_root = Path(__file__).resolve().parents[2]
    tasks = await load_eval_tasks(project_root, task_ids=None)

    # We expect at least a handful of tasks from the seeded core_workflows.json.
    assert len(tasks) >= 5
    ids = {t.id for t in tasks}
    assert "context-bugfix-validation-module" in ids
    assert "memory-validate-memory-bank-files" in ids


@pytest.mark.asyncio
async def test_load_eval_tasks_filters_by_task_ids() -> None:
    """load_eval_tasks respects task_ids filter."""
    project_root = Path(__file__).resolve().parents[2]

    target_id = "context-add-new-mcp-tool"
    tasks = await load_eval_tasks(project_root, task_ids=[target_id])

    assert tasks
    ids = {t.id for t in tasks}
    assert ids == {target_id}


@pytest.mark.asyncio
async def test_load_eval_tasks_returns_empty_when_tasks_dir_missing(
    tmp_path: Path,
) -> None:
    """load_eval_tasks returns empty list when evals/tasks directory is missing."""
    project_root = tmp_path

    with patch(
        "cortex.tools.phase5_evaluation.get_cortex_path",
        return_value=project_root / ".cortex",
    ):
        tasks = await load_eval_tasks(project_root, task_ids=None)

    assert tasks == []


def test_analyze_results_aggregates_basic_metrics() -> None:
    """ToolEvaluationHarness.analyze_results computes high-level metrics."""
    # Build a small synthetic suite with two tasks and known metrics.
    t1 = EvalTaskResult(
        task_id="t1",
        task_name="Task 1",
        category=EvalTaskCategory.CONTEXT,
        status=EvalTaskStatus.SUCCESS,
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
        category=EvalTaskCategory.PRE_COMMIT,
        status=EvalTaskStatus.MIXED,
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
    expected_rate = (0.8 + 0.6) / 2.0
    assert abs(analysis.overall_success_rate - expected_rate) <= expected_rate * 1e-6
    assert analysis.tasks_with_no_data == 0
    assert analysis.tasks_unavailable == 0
    expected_avg_calls = (10 + 5) / 2.0
    assert (
        abs(analysis.average_calls_per_task - expected_avg_calls)
        <= expected_avg_calls * 1e-6
    )

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
async def test_run_suite_reproducibility_same_tracker_data() -> None:
    """Same tasks and same tracker data produce the same suite metrics (reproducibility)."""
    project_root = Path(__file__).resolve().parents[2]
    events_load_context = [
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-17T12:00:00Z",
            duration_ms=50.0,
            success=True,
        ),
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-17T12:01:00Z",
            duration_ms=60.0,
            success=False,
            error_type="ValueError",
        ),
    ]
    events_pre_commit = [
        ToolUsageEvent(
            tool_name="execute_pre_commit_checks",
            timestamp="2026-02-17T12:02:00Z",
            duration_ms=200.0,
            success=True,
        ),
    ]
    mock_tracker = AsyncMock()

    async def search_usage(
        start_date: str | None = None,
        end_date: str | None = None,
        tool_name: str | None = None,
        success: bool | None = None,
        limit: int = 200,
        query: str | None = None,
    ) -> list[ToolUsageEvent]:
        if tool_name == "load_context":
            return list(events_load_context)
        if tool_name == "execute_pre_commit_checks":
            return list(events_pre_commit)
        return []

    mock_tracker.search_usage = search_usage

    tasks = [
        EvalTask(
            id="ctx-1",
            name="Context task",
            description="Load context",
            category=EvalTaskCategory.CONTEXT,
            expected_tools=["load_context"],
            expected_outcome="ok",
        ),
        EvalTask(
            id="pre-1",
            name="Pre-commit task",
            description="Run checks",
            category=EvalTaskCategory.PRE_COMMIT,
            expected_tools=["execute_pre_commit_checks"],
            expected_outcome="ok",
        ),
    ]
    harness = ToolEvaluationHarness(project_root=project_root, tracker=mock_tracker)

    suite1 = await harness.run_suite(tasks)
    suite2 = await harness.run_suite(tasks)

    assert len(suite1.tasks) == len(suite2.tasks) == 2
    for i in range(2):
        r1, r2 = suite1.tasks[i], suite2.tasks[i]
        assert r1.task_id == r2.task_id
        assert r1.total_calls == r2.total_calls
        assert r1.successful_calls == r2.successful_calls
        assert r1.failed_calls == r2.failed_calls
        assert r1.status == r2.status
        assert abs(r1.success_rate - r2.success_rate) <= r2.success_rate * 1e-9
    assert suite1.generated_at != suite2.generated_at


@pytest.mark.asyncio
async def test_run_tool_evaluation_uses_harness_and_writes_cache() -> None:
    """run_tool_evaluation wires together task loading, harness, and cache writes."""
    project_root = Path("/project")

    fake_tasks = [
        EvalTask(
            id="t1",
            name="Task 1",
            description="Test task 1",
            category=EvalTaskCategory.CONTEXT,
            expected_tools=["load_context"],
            expected_outcome="ok",
        ),
        EvalTask(
            id="t2",
            name="Task 2",
            description="Test task 2",
            category=EvalTaskCategory.PRE_COMMIT,
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
                category=EvalTaskCategory.CONTEXT,
                status=EvalTaskStatus.SUCCESS,
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
            "cortex.tools.phase5_evaluation.load_eval_tasks",
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
            "cortex.tools.phase5_evaluation._write_evaluation_dashboard",
            new_callable=AsyncMock,
            return_value=Path("/project/.cortex/evals/dashboard.md"),
        ),
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
async def test_analyze_error_patterns_persists_error_cache() -> None:
    """analyze_error_patterns writes a compact error_patterns cache file."""
    project_root = Path("/project")

    fake_tasks = [
        EvalTask(
            id="t1",
            name="Task 1",
            description="Test task 1",
            category=EvalTaskCategory.CONTEXT,
            expected_tools=["load_context"],
            expected_outcome="ok",
        )
    ]

    suite = EvalSuiteResult(
        generated_at="2026-02-17T00:00:00Z",
        tasks=[
            EvalTaskResult(
                task_id="t1",
                task_name="Task 1",
                category=EvalTaskCategory.CONTEXT,
                status=EvalTaskStatus.MIXED,
                total_calls=2,
                successful_calls=1,
                failed_calls=1,
                success_rate=0.5,
                avg_duration_ms=10.0,
                total_duration_ms=20.0,
                error_types={"ValueError": 1},
                evaluated_tools=["load_context"],
            )
        ],
    )
    analysis = EvalAnalysis(
        overall_success_rate=0.5,
        total_tasks=1,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=2.0,
        top_error_patterns=[
            ErrorPattern(
                error_type="ValueError",
                count=1,
                affected_tools=["load_context"],
            )
        ],
        success_rate_by_category={"context": 0.5},
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
            "cortex.tools.phase5_evaluation.load_eval_tasks",
            new_callable=AsyncMock,
            return_value=fake_tasks,
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.run_suite",
            new_callable=AsyncMock,
            return_value=suite,
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.analyze_results",
            new=MagicMock(return_value=analysis),
        ),
        patch(
            "cortex.tools.phase5_evaluation.write_cache_json",
            new_callable=AsyncMock,
        ) as mock_write_cache,
    ):
        raw = await analyze_error_patterns(task_ids=None, ctx=None)

    data = json.loads(raw)
    assert data["status"] == "success"
    assert data["tasks_loaded"] == len(fake_tasks)
    assert data["generated_at"] == suite.generated_at
    assert data["total_patterns"] == 1

    # The error patterns cache should be written once to the expected key.
    _ = mock_write_cache.assert_awaited_once()
    args, _ = mock_write_cache.call_args
    assert args[1] == "evals/error_patterns.json"

    # Return payload includes error_patterns with expected shape.
    assert "error_patterns" in data
    assert len(data["error_patterns"]) == 1
    assert data["error_patterns"][0]["error_type"] == "ValueError"
    assert data["error_patterns"][0]["count"] == 1
    assert data["error_patterns"][0]["affected_tools"] == ["load_context"]


@pytest.mark.asyncio
async def test_analyze_error_patterns_empty_suite_returns_zero_patterns() -> None:
    """analyze_error_patterns returns zero patterns when suite has no tasks."""
    project_root = Path("/project")
    empty_suite = EvalSuiteResult(
        generated_at="2026-02-21T00:00:00Z",
        tasks=[],
    )
    empty_analysis = EvalAnalysis(
        overall_success_rate=0.0,
        total_tasks=0,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=0.0,
        top_error_patterns=[],
        success_rate_by_category={},
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
        ),
        patch(
            "cortex.tools.phase5_evaluation.load_eval_tasks",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.run_suite",
            new_callable=AsyncMock,
            return_value=empty_suite,
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.analyze_results",
            new=MagicMock(return_value=empty_analysis),
        ),
        patch(
            "cortex.tools.phase5_evaluation.write_cache_json",
            new_callable=AsyncMock,
        ),
    ):
        raw = await analyze_error_patterns(task_ids=None, ctx=None)

    data = json.loads(raw)
    assert data["status"] == "success"
    assert data["tasks_loaded"] == 0
    assert data["total_patterns"] == 0
    assert data["error_patterns"] == []


@pytest.mark.asyncio
async def test_analyze_error_patterns_passes_task_ids_to_load_tasks() -> None:
    """analyze_error_patterns passes task_ids to load_eval_tasks."""
    project_root = Path("/project")
    empty_suite = EvalSuiteResult(
        generated_at="2026-02-21T00:00:00Z",
        tasks=[],
    )
    empty_analysis = EvalAnalysis(
        overall_success_rate=0.0,
        total_tasks=0,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=0.0,
        top_error_patterns=[],
        success_rate_by_category={},
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
        ),
        patch(
            "cortex.tools.phase5_evaluation.load_eval_tasks",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_load,
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.run_suite",
            new_callable=AsyncMock,
            return_value=empty_suite,
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.analyze_results",
            new=MagicMock(return_value=empty_analysis),
        ),
        patch(
            "cortex.tools.phase5_evaluation.write_cache_json",
            new_callable=AsyncMock,
        ),
    ):
        await analyze_error_patterns(task_ids=["t1", "t2"], ctx=None)

    _ = mock_load.assert_awaited_once()
    assert mock_load.call_args[0][1] == ["t1", "t2"]


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
                    handler_kind=HandlerKind.TOOL,
                ),
                ToolUsageEvent(
                    tool_name="load_context",
                    timestamp="2026-02-17T00:00:01Z",
                    duration_ms=20.0,
                    success=False,
                    error_type="ValueError",
                    handler_kind=HandlerKind.TOOL,
                ),
            ]

    task = EvalTask(
        id="t-metrics",
        name="Task Metrics",
        description="Test task metrics aggregation",
        category=EvalTaskCategory.CONTEXT,
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
    assert abs(result.avg_duration_ms - 15.0) <= 15.0 * 1e-6
    assert abs(result.total_duration_ms - 30.0) <= 30.0 * 1e-6
    assert result.error_types == {"ValueError": 1}
    assert result.evaluated_tools == ["load_context"]
    assert "load_context" in result.tool_metrics
    m = result.tool_metrics["load_context"]
    assert m.calls == 2
    assert m.successful == 1
    assert m.failed == 1


def test_aggregate_tool_metrics_sums_across_tasks() -> None:
    """aggregate_tool_metrics sums per-tool calls and success/failed across tasks."""
    t1 = EvalTaskResult(
        task_id="t1",
        task_name="T1",
        category=EvalTaskCategory.CONTEXT,
        status=EvalTaskStatus.SUCCESS,
        total_calls=5,
        successful_calls=4,
        failed_calls=1,
        success_rate=0.8,
        avg_duration_ms=0.0,
        total_duration_ms=0.0,
        error_types={},
        evaluated_tools=["load_context"],
        tool_metrics={
            "load_context": ToolTaskMetrics(calls=5, successful=4, failed=1),
        },
    )
    t2 = EvalTaskResult(
        task_id="t2",
        task_name="T2",
        category=EvalTaskCategory.CONTEXT,
        status=EvalTaskStatus.SUCCESS,
        total_calls=3,
        successful_calls=3,
        failed_calls=0,
        success_rate=1.0,
        avg_duration_ms=0.0,
        total_duration_ms=0.0,
        error_types={},
        evaluated_tools=["load_context", "manage_file"],
        tool_metrics={
            "load_context": ToolTaskMetrics(calls=2, successful=2, failed=0),
            "manage_file": ToolTaskMetrics(calls=1, successful=1, failed=0),
        },
    )
    suite = EvalSuiteResult(
        generated_at="2026-02-21T00:00:00Z",
        tasks=[t1, t2],
    )
    agg = aggregate_tool_metrics(suite)
    assert agg["load_context"] == (7, 6, 1)
    assert agg["manage_file"] == (1, 1, 0)


def test_format_token_efficiency_empty_when_no_token_data() -> None:
    """format_token_efficiency returns no lines when average_tokens and by_category are zero/empty."""
    analysis = EvalAnalysis(
        overall_success_rate=0.8,
        total_tasks=2,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=3.0,
        average_tokens_per_task=0.0,
        token_consumption_by_category={},
        top_error_patterns=[],
        success_rate_by_category={"context": 0.8},
    )
    lines = format_token_efficiency(analysis)
    assert lines == []


def test_format_token_efficiency_section_when_token_data_present() -> None:
    """format_token_efficiency returns Token Efficiency Trends section when token data exists."""
    analysis = EvalAnalysis(
        overall_success_rate=0.8,
        total_tasks=2,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=3.0,
        average_tokens_per_task=1500.0,
        token_consumption_by_category={"context": 2000.0, "pre_commit": 1000.0},
        top_error_patterns=[],
        success_rate_by_category={"context": 0.8},
    )
    lines = format_token_efficiency(analysis)
    assert any("Token Efficiency Trends" in line for line in lines)
    assert any("1,500" in line or "1500" in line for line in lines)
    assert any("context" in line and "2,000" in line for line in lines)
    assert any("pre_commit" in line and "1,000" in line for line in lines)


def test_generate_evaluation_dashboard_includes_token_efficiency_when_available() -> (
    None
):
    """generate_evaluation_dashboard includes Token Efficiency Trends when analysis has token data."""
    suite = EvalSuiteResult(
        generated_at="2026-02-21T12:00:00Z",
        tasks=[
            EvalTaskResult(
                task_id="t1",
                task_name="Task 1",
                category=EvalTaskCategory.CONTEXT,
                status=EvalTaskStatus.SUCCESS,
                total_calls=1,
                successful_calls=1,
                failed_calls=0,
                success_rate=1.0,
                avg_duration_ms=0.0,
                total_duration_ms=0.0,
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
        average_tokens_per_task=1200.0,
        token_consumption_by_category={"context": 1200.0},
        top_error_patterns=[],
        success_rate_by_category={"context": 1.0},
    )
    dashboard = generate_evaluation_dashboard(analysis, suite)
    assert "## Token Efficiency Trends" in dashboard
    assert "1,200" in dashboard or "1200" in dashboard


@pytest.mark.asyncio
async def test_run_tool_evaluation_generates_dashboard(tmp_path: Path) -> None:
    """run_tool_evaluation generates dashboard.md file alongside last_suite.json."""
    project_root = tmp_path
    evals_dir = project_root / ".cortex" / "evals" / "tasks"
    _ = evals_dir.mkdir(parents=True, exist_ok=True)

    # Create a minimal task file
    task_file = evals_dir / "test_tasks.json"
    _ = task_file.write_text(
        json.dumps(
            [
                {
                    "id": "test-task",
                    "name": "Test Task",
                    "description": "Test description",
                    "category": "other",
                    "expected_tools": ["load_context"],
                    "expected_outcome": "Success",
                }
            ]
        )
    )

    cache_dir = project_root / ".cortex" / ".cache" / "evals"
    _ = cache_dir.mkdir(parents=True, exist_ok=True)

    with (
        patch(
            "cortex.tools.phase5_evaluation.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=project_root,
        ),
        patch(
            "cortex.tools.phase5_evaluation._get_usage_tracker",
            new_callable=AsyncMock,
        ) as mock_tracker,
        patch(
            "cortex.tools.phase5_evaluation.load_eval_tasks",
            new_callable=AsyncMock,
            return_value=[
                EvalTask(
                    id="test-task",
                    name="Test Task",
                    description="Test description",
                    category=EvalTaskCategory.OTHER,
                    expected_tools=["load_context"],
                    expected_outcome="Success",
                )
            ],
        ),
        patch(
            "cortex.tools.phase5_evaluation._persist_latest_suite",
            new_callable=AsyncMock,
        ),
    ):
        # Mock usage tracker to return empty events (no data scenario)
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.search_usage = AsyncMock(return_value=[])
        mock_tracker.return_value = mock_tracker_instance

        result_str = await run_tool_evaluation(task_ids=["test-task"])
        result = json.loads(result_str)

        # Verify dashboard path is in response
        assert "dashboard_path" in result
        dashboard_path = project_root / result["dashboard_path"]
        assert dashboard_path.exists()
        assert dashboard_path.name == "dashboard.md"
        assert dashboard_path.parent.name == "evals"

        # Verify dashboard content
        content = dashboard_path.read_text(encoding="utf-8")
        assert "# Evaluation Dashboard" in content
        assert "## Overall Metrics" in content
        assert "Overall Tool Effectiveness Score" in content


@pytest.mark.asyncio
async def test_run_tool_evaluation_dashboard_includes_top_tools_sections(
    tmp_path: Path,
) -> None:
    """Dashboard includes Top 5 Tools by Usage and by Improvement when suite has tool_metrics."""
    project_root = tmp_path
    evals_dir = project_root / ".cortex" / "evals" / "tasks"
    _ = evals_dir.mkdir(parents=True, exist_ok=True)
    _ = (evals_dir / "test_tasks.json").write_text(
        json.dumps(
            [
                {
                    "id": "t1",
                    "name": "Task 1",
                    "description": "Desc",
                    "category": "context",
                    "expected_tools": ["load_context"],
                    "expected_outcome": "OK",
                }
            ]
        )
    )
    _ = (project_root / ".cortex" / ".cache" / "evals").mkdir(
        parents=True, exist_ok=True
    )

    suite_with_tool_metrics = EvalSuiteResult(
        generated_at="2026-02-21T12:00:00Z",
        tasks=[
            EvalTaskResult(
                task_id="t1",
                task_name="Task 1",
                category=EvalTaskCategory.CONTEXT,
                status=EvalTaskStatus.SUCCESS,
                total_calls=10,
                successful_calls=8,
                failed_calls=2,
                success_rate=0.8,
                avg_duration_ms=5.0,
                total_duration_ms=50.0,
                error_types={},
                evaluated_tools=["load_context", "manage_file"],
                tool_metrics={
                    "load_context": ToolTaskMetrics(calls=8, successful=7, failed=1),
                    "manage_file": ToolTaskMetrics(calls=2, successful=1, failed=1),
                },
            ),
        ],
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
        ),
        patch(
            "cortex.tools.phase5_evaluation.load_eval_tasks",
            new_callable=AsyncMock,
            return_value=[
                EvalTask(
                    id="t1",
                    name="Task 1",
                    description="Desc",
                    category=EvalTaskCategory.CONTEXT,
                    expected_tools=["load_context"],
                    expected_outcome="OK",
                )
            ],
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.run_suite",
            new_callable=AsyncMock,
            return_value=suite_with_tool_metrics,
        ),
        patch(
            "cortex.tools.phase5_evaluation._persist_latest_suite",
            new_callable=AsyncMock,
        ),
    ):
        result_str = await run_tool_evaluation(task_ids=["t1"])
        result = json.loads(result_str)
        dashboard_path = project_root / result["dashboard_path"]
        content = dashboard_path.read_text(encoding="utf-8")

    assert "## Top 5 Tools by Usage" in content
    assert "## Top 5 Tools by Improvement Needed" in content
    assert "load_context" in content
    assert "manage_file" in content


def test_compare_ab_analyses_optimized_wins_by_success_rate() -> None:
    """compare_ab_analyses returns optimized when success rate is higher."""
    baseline = EvalAnalysis(
        overall_success_rate=0.7,
        total_tasks=10,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=5.0,
        top_error_patterns=[],
        success_rate_by_category={},
    )
    optimized = EvalAnalysis(
        overall_success_rate=0.9,
        total_tasks=10,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=5.0,
        top_error_patterns=[],
        success_rate_by_category={},
    )
    result = compare_ab_analyses(baseline, optimized)
    assert isinstance(result, ABComparisonResult)
    assert result.winner == ABWinner.optimized
    assert abs(result.success_rate_delta - 0.2) <= 1e-9
    assert result.total_error_count_baseline == 0
    assert result.total_error_count_optimized == 0
    assert result.error_count_delta == 0


def test_compare_ab_analyses_baseline_wins_when_success_rate_lower() -> None:
    """compare_ab_analyses returns baseline when optimized success rate is lower."""
    baseline = EvalAnalysis(
        overall_success_rate=0.9,
        total_tasks=10,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=5.0,
        top_error_patterns=[],
        success_rate_by_category={},
    )
    optimized = EvalAnalysis(
        overall_success_rate=0.6,
        total_tasks=10,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=5.0,
        top_error_patterns=[],
        success_rate_by_category={},
    )
    result = compare_ab_analyses(baseline, optimized)
    assert result.winner == ABWinner.baseline
    assert abs(result.success_rate_delta - (-0.3)) <= 1e-9


def test_compare_ab_analyses_tie_breaks_by_error_count() -> None:
    """When success rates tie, fewer total errors wins."""
    baseline = EvalAnalysis(
        overall_success_rate=0.8,
        total_tasks=5,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=4.0,
        top_error_patterns=[
            ErrorPattern(error_type="ErrA", count=3, affected_tools=["t1"]),
        ],
        success_rate_by_category={},
    )
    optimized = EvalAnalysis(
        overall_success_rate=0.8,
        total_tasks=5,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=4.0,
        top_error_patterns=[
            ErrorPattern(error_type="ErrA", count=1, affected_tools=["t1"]),
        ],
        success_rate_by_category={},
    )
    result = compare_ab_analyses(baseline, optimized)
    assert result.winner == ABWinner.optimized
    assert result.success_rate_delta == 0.0
    assert result.total_error_count_baseline == 3
    assert result.total_error_count_optimized == 1
    assert result.error_count_delta == -2


def test_compare_ab_analyses_tie_when_equal() -> None:
    """When success rates and error counts match, winner is tie."""
    analysis = EvalAnalysis(
        overall_success_rate=0.75,
        total_tasks=4,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=3.0,
        top_error_patterns=[
            ErrorPattern(error_type="X", count=2, affected_tools=["a"]),
        ],
        success_rate_by_category={},
    )
    result = compare_ab_analyses(analysis, analysis)
    assert result.winner == ABWinner.tie
    assert result.success_rate_delta == 0.0
    assert result.error_count_delta == 0


def test_aggregate_session_tool_anomalies_empty() -> None:
    """aggregate_session_tool_anomalies returns empty lists for no events."""
    result = aggregate_session_tool_anomalies([])
    assert result.tools_used == []
    assert result.high_retry_tools == []
    assert result.high_error_tools == []


def test_aggregate_session_tool_anomalies_flags_retries_and_errors() -> None:
    """aggregate_session_tool_anomalies flags tools with retries or errors."""
    events = [
        ToolUsageEvent(
            tool_name="load_context",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=10.0,
            success=True,
            retry_count=0,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:01:00Z",
            duration_ms=5.0,
            success=False,
            error_type="ValueError",
            retry_count=2,
        ),
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:02:00Z",
            duration_ms=5.0,
            success=True,
            retry_count=1,
        ),
    ]
    result = aggregate_session_tool_anomalies(events)
    assert len(result.tools_used) == 2
    by_name = {t.tool_name: t for t in result.tools_used}
    assert by_name["load_context"].calls == 1
    assert by_name["load_context"].retries == 0
    assert by_name["load_context"].errors == 0
    assert by_name["manage_file"].calls == 2
    assert by_name["manage_file"].retries == 3
    assert by_name["manage_file"].errors == 1
    assert "manage_file" in result.high_retry_tools
    assert "manage_file" in result.high_error_tools
    assert "load_context" not in result.high_retry_tools
    assert "load_context" not in result.high_error_tools


@pytest.mark.asyncio
async def test_get_session_tool_anomalies_unavailable() -> None:
    """get_session_tool_anomalies (redirects to query_usage) returns unavailable when tracker is None."""
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        result_str = await get_session_tool_anomalies(hours=24)
    result = json.loads(result_str)
    assert result["status"] == "unavailable"
    assert result["session_window_hours"] == 24
    assert "message" in result


@pytest.mark.asyncio
async def test_get_session_tool_anomalies_success() -> None:
    """get_session_tool_anomalies (redirects to query_usage) returns tools_used and anomalies when tracker has events."""
    mock_events = [
        ToolUsageEvent(
            tool_name="query_usage",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=10.0,
            success=True,
            retry_count=0,
        ),
    ]
    mock_tracker = MagicMock()
    mock_tracker.search_usage = AsyncMock(return_value=mock_events)

    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=mock_tracker,
        ),
    ):
        result_str = await get_session_tool_anomalies(hours=24)
    result = json.loads(result_str)
    assert result["status"] == "success"
    assert result["session_window_hours"] == 24
    assert result["total_events"] == 1
    assert len(result["tools_used"]) == 1
    assert result["tools_used"][0]["tool_name"] == "query_usage"
    assert result["tools_used"][0]["calls"] == 1
    assert result["tools_used"][0]["retries"] == 0
    assert result["tools_used"][0]["errors"] == 0
    assert "high_retry_tools" in result
    assert "high_error_tools" in result


@pytest.mark.asyncio
async def test_load_optimization_history_empty_when_missing(tmp_path: Path) -> None:
    """load_optimization_history returns empty list when cache file is missing."""
    with patch(
        "cortex.tools.phase5_evaluation.read_cache_json",
        new_callable=AsyncMock,
        return_value=None,
    ):
        history = await load_optimization_history(tmp_path)
    assert history == []


@pytest.mark.asyncio
async def test_load_optimization_history_parses_runs(tmp_path: Path) -> None:
    """load_optimization_history parses runs from cache."""
    raw = {
        "runs": [
            {
                "run_id": "run-1",
                "generated_at": "2026-02-21T12:00:00Z",
                "baseline_success_rate": 0.8,
                "optimized_success_rate": None,
                "winner": "baseline_only",
                "success_rate_delta": None,
                "total_error_count_baseline": 5,
                "total_error_count_optimized": None,
            },
        ]
    }
    with patch(
        "cortex.tools.phase5_evaluation.read_cache_json",
        new_callable=AsyncMock,
        return_value=raw,
    ):
        history = await load_optimization_history(tmp_path)
    assert len(history) == 1
    assert history[0].run_id == "run-1"
    assert history[0].baseline_success_rate == 0.8
    assert history[0].winner == OptimizationRunWinner.baseline_only


@pytest.mark.asyncio
async def test_append_optimization_record_persists(tmp_path: Path) -> None:
    """append_optimization_record appends a record and writes cache."""
    record = OptimizationRunRecord(
        run_id="run-test",
        generated_at="2026-02-21T12:00:00Z",
        baseline_success_rate=0.7,
        optimized_success_rate=None,
        winner=OptimizationRunWinner.baseline_only,
        success_rate_delta=None,
        total_error_count_baseline=2,
        total_error_count_optimized=None,
    )
    write_calls: list[tuple[Path, str, object]] = []

    async def capture_write(root: Path, key: str, data: object) -> None:
        write_calls.append((root, key, data))
        return None

    with (
        patch(
            "cortex.tools.phase5_evaluation.read_cache_json",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "cortex.tools.phase5_evaluation.write_cache_json",
            side_effect=capture_write,
        ),
    ):
        await append_optimization_record(tmp_path, record)

    assert len(write_calls) == 1
    assert write_calls[0][1] == "evals/optimization_history.json"
    raw_payload = write_calls[0][2]
    assert isinstance(raw_payload, dict)
    assert "runs" in raw_payload
    runs = cast(list[dict[str, object]], raw_payload["runs"])
    assert len(runs) == 1
    assert "run_id" in runs[0]
    assert runs[0]["run_id"] == "run-test"


@pytest.mark.asyncio
async def test_run_tool_optimization_workflow_baseline_only() -> None:
    """run_tool_optimization_workflow records baseline_only when no optimized run."""
    project_root = Path("/project")
    baseline_analysis = EvalAnalysis(
        overall_success_rate=0.75,
        total_tasks=5,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=4.0,
        top_error_patterns=[],
        success_rate_by_category={"context": 0.75},
    )
    suite = EvalSuiteResult(
        generated_at="2026-02-21T12:00:00Z",
        tasks=[],
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
            "cortex.tools.phase5_evaluation.load_eval_tasks",
            new_callable=AsyncMock,
            return_value=[
                EvalTask(
                    id="t1",
                    name="T1",
                    description="D",
                    category=EvalTaskCategory.CONTEXT,
                    expected_tools=[],
                    expected_outcome="ok",
                )
            ],
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.run_suite",
            new_callable=AsyncMock,
            return_value=suite,
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.analyze_results",
            return_value=baseline_analysis,
        ),
        patch(
            "cortex.tools.phase5_evaluation.append_optimization_record",
            new_callable=AsyncMock,
        ) as mock_append,
        patch(
            "cortex.tools.phase5_evaluation.load_optimization_history",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result_str = await run_tool_optimization_workflow(
            task_ids=None, optimized_analysis_json=None, ctx=None
        )

    data = json.loads(result_str)
    assert data["status"] == "success"
    assert "run_id" in data
    assert data["baseline_success_rate"] == 0.75
    assert data["record"]["winner"] == "baseline_only"
    assert data["history_runs_count"] == 0
    _ = mock_append.assert_awaited_once()
    call_record = mock_append.call_args[0][1]
    assert call_record.winner == OptimizationRunWinner.baseline_only
    assert call_record.baseline_success_rate == 0.75


@pytest.mark.asyncio
async def test_run_tool_optimization_workflow_with_ab_comparison() -> None:
    """run_tool_optimization_workflow compares and records when optimized_analysis given."""
    project_root = Path("/project")
    baseline_analysis = EvalAnalysis(
        overall_success_rate=0.7,
        total_tasks=5,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=4.0,
        top_error_patterns=[
            ErrorPattern(error_type="E", count=3, affected_tools=["t1"]),
        ],
        success_rate_by_category={},
    )
    optimized_analysis = EvalAnalysis(
        overall_success_rate=0.9,
        total_tasks=5,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=4.0,
        top_error_patterns=[],
        success_rate_by_category={},
    )
    suite = EvalSuiteResult(
        generated_at="2026-02-21T12:00:00Z",
        tasks=[],
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
            "cortex.tools.phase5_evaluation.load_eval_tasks",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.run_suite",
            new_callable=AsyncMock,
            return_value=suite,
        ),
        patch(
            "cortex.tools.phase5_evaluation.ToolEvaluationHarness.analyze_results",
            return_value=baseline_analysis,
        ),
        patch(
            "cortex.tools.phase5_evaluation.append_optimization_record",
            new_callable=AsyncMock,
        ) as mock_append,
        patch(
            "cortex.tools.phase5_evaluation.load_optimization_history",
            new_callable=AsyncMock,
            return_value=[
                OptimizationRunRecord(
                    run_id="run-prev",
                    generated_at="2026-02-20T00:00:00Z",
                    baseline_success_rate=0.5,
                    winner=OptimizationRunWinner.baseline_only,
                )
            ],
        ),
    ):
        optimized_json = optimized_analysis.model_dump(mode="json")
        result_str = await run_tool_optimization_workflow(
            task_ids=None,
            optimized_analysis_json=json.dumps(optimized_json),
            ctx=None,
        )

    data = json.loads(result_str)
    assert data["status"] == "success"
    assert data["record"]["winner"] == "optimized"
    assert abs(data["record"]["success_rate_delta"] - 0.2) <= 1e-9
    assert data["history_runs_count"] == 1
    _ = mock_append.assert_awaited_once()
    call_record = mock_append.call_args[0][1]
    assert call_record.winner == OptimizationRunWinner.optimized
    assert call_record.baseline_success_rate == 0.7
    assert call_record.optimized_success_rate == 0.9
