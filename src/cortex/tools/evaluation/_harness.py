"""
Phase 57: ToolEvaluationHarness and load_eval_tasks.

Extracted for Phase 9.1.4 file size compliance.
"""

from __future__ import annotations

from pathlib import Path

from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker
from cortex.tools.evaluation.evaluation_task_loader import (
    build_eval_tasks,
    load_eval_task_dicts,
)

from ._aggregation import AggregatedEvents, AnalysisAccumulator
from ._models import (
    EvalAnalysis,
    EvalSuiteResult,
    EvalTask,
    EvalTaskResult,
    EvalTaskStatus,
)


def _validate_eval_task(rec: dict[str, object]) -> EvalTask | None:
    """Validate one raw dict into EvalTask; return None on error."""
    try:
        return EvalTask.model_validate(rec)
    except Exception:
        return None


async def load_eval_tasks(
    project_root: Path, task_ids: list[str] | None = None
) -> list[EvalTask]:
    """Load evaluation tasks from .cortex/evals/tasks/*.json."""
    evals_dir = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR) / "evals"
    tasks_dir = evals_dir / "tasks"
    if not tasks_dir.is_dir():
        return []

    selected_ids = set(task_ids or [])
    records = load_eval_task_dicts(tasks_dir)
    return build_eval_tasks(records, selected_ids, _validate_eval_task)


class ToolEvaluationHarness:
    """Harness that aggregates metrics from UsageTracker (no workflow replay)."""

    def __init__(self, project_root: Path, tracker: UsageTracker | None) -> None:
        self._project_root = project_root
        self._tracker = tracker

    async def _collect_events_for_task(self, task: EvalTask) -> AggregatedEvents:
        """Collect usage events for all expected tools in a task."""
        if self._tracker is None:
            return AggregatedEvents(events=[])

        events: list[ToolUsageEvent] = []
        limit_per_tool = 200
        for tool_name in task.expected_tools:
            tool_events = await self._tracker.search_usage(
                start_date=None,
                end_date=None,
                tool_name=tool_name,
                success=None,
                limit=limit_per_tool,
                query=task.usage_query,
            )
            events.extend(tool_events)
        return AggregatedEvents(events=events)

    def _unavailable_result(self, task: EvalTask) -> EvalTaskResult:
        """Build a result payload when the tracker is unavailable."""
        return EvalTaskResult(
            task_id=task.id,
            task_name=task.name,
            category=task.category,
            status=EvalTaskStatus.UNAVAILABLE,
            total_calls=0,
            successful_calls=0,
            failed_calls=0,
            success_rate=0.0,
            avg_duration_ms=0.0,
            total_duration_ms=0.0,
            error_types={},
            evaluated_tools=task.expected_tools,
        )

    def _status_for_aggregated_events(self, agg: AggregatedEvents) -> EvalTaskStatus:
        if agg.total_calls == 0:
            return EvalTaskStatus.NO_DATA
        if agg.failed_calls == 0:
            return EvalTaskStatus.SUCCESS
        if agg.successful_calls == 0:
            return EvalTaskStatus.MIXED
        return EvalTaskStatus.MIXED

    def _result_from_aggregated_events(
        self,
        task: EvalTask,
        agg: AggregatedEvents,
    ) -> EvalTaskResult:
        status = self._status_for_aggregated_events(agg)
        return EvalTaskResult(
            task_id=task.id,
            task_name=task.name,
            category=task.category,
            status=status,
            total_calls=agg.total_calls,
            successful_calls=agg.successful_calls,
            failed_calls=agg.failed_calls,
            success_rate=agg.success_rate,
            avg_duration_ms=agg.avg_duration_ms,
            total_duration_ms=agg.total_duration_ms,
            error_types=agg.error_types,
            evaluated_tools=task.expected_tools,
            tool_metrics=agg.tool_metrics(),
        )

    async def run_task(self, task: EvalTask) -> EvalTaskResult:
        """Run a single evaluation task and compute metrics from usage data."""
        if self._tracker is None:
            return self._unavailable_result(task)
        agg = await self._collect_events_for_task(task)
        return self._result_from_aggregated_events(task, agg)

    async def run_suite(self, suite: list[EvalTask]) -> EvalSuiteResult:
        """Run all tasks in a suite and aggregate results."""
        from datetime import UTC, datetime

        generated_at = datetime.now(UTC).isoformat()
        results: list[EvalTaskResult] = []
        for task in suite:
            results.append(await self.run_task(task))
        return EvalSuiteResult(generated_at=generated_at, tasks=results)

    def analyze_results(self, suite: EvalSuiteResult) -> EvalAnalysis:
        """Analyze a completed suite and compute high-level metrics."""
        from cortex.tools.evaluation import evaluation_helpers as _eval_helpers

        total_tasks = len(suite.tasks)
        if total_tasks == 0:
            return _eval_helpers.empty_eval_analysis()
        acc = AnalysisAccumulator()
        for result in suite.tasks:
            acc.add_result(result)
        overall_success_rate = acc.total_success_rate / float(total_tasks)
        average_calls_per_task = (
            float(acc.total_calls) / float(total_tasks) if total_tasks else 0.0
        )
        return _eval_helpers.build_eval_analysis(
            acc.category_success,
            acc.error_counter,
            acc.tasks_with_no_data,
            acc.tasks_unavailable,
            total_tasks,
            overall_success_rate,
            average_calls_per_task,
            suite,
        )
