"""
Phase 57: Evaluation-Driven Tool Improvement

Core evaluation models, harness, and MCP tool for running an evaluation suite
over existing usage analytics data. This is the first iteration that focuses on:

- Pydantic v2 models for evaluation tasks and results
- A ToolEvaluationHarness that aggregates metrics from UsageTracker
- A run_tool_evaluation MCP tool that loads tasks from .cortex/evals/tasks
  and writes suite + analysis results to .cortex/.cache/evals/last_suite.json

Later iterations (same phase) will layer on automated tool description
optimization and A/B testing, but those are intentionally out of scope for
this initial implementation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import (
    CortexResourceType,
    get_cache_path,
    get_cortex_path,
)
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import UsageTracker
from cortex.server import mcp
from cortex.tools import usage_analytics
from cortex.tools.phase5_evaluation_anomalies_helpers import (
    get_session_tool_anomalies_payload as _get_session_tool_anomalies_payload,
)
from cortex.tools.phase5_evaluation_anomalies_helpers import (
    unavailable_session_anomalies_response,
)
from cortex.tools.phase5_evaluation_task_loader import (
    build_eval_tasks,
    load_eval_task_dicts,
)


class EvalTaskCategory(str, Enum):
    """Workflow category for an evaluation task."""

    CONTEXT = "context"
    PRE_COMMIT = "pre_commit"
    PLAN = "plan"
    MEMORY_BANK = "memory_bank"
    OTHER = "other"


class EvalTaskStatus(str, Enum):
    """Status of a single evaluation task result."""

    SUCCESS = "success"
    MIXED = "mixed"
    NO_DATA = "no_data"
    UNAVAILABLE = "unavailable"


class EvalTask(BaseModel):
    """Single evaluation task definition grounded in a real workflow."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Stable identifier for this evaluation task")
    name: str = Field(description="Human-readable task name")
    description: str = Field(description="Detailed task description")
    category: EvalTaskCategory = Field(
        default=EvalTaskCategory.OTHER,
        description="High-level workflow category for the task",
    )
    expected_tools: list[str] = Field(
        default_factory=list,
        description="List of MCP tools that should be involved in this task",
    )
    expected_outcome: str = Field(
        description="What success looks like for this task (free-form summary)"
    )
    token_budget_baseline: int | None = Field(
        default=None,
        ge=0,
        description="Expected token budget for this task, if known",
    )
    common_failure_modes: list[str] = Field(
        default_factory=list,
        description="Known or anticipated failure modes for this task",
    )
    usage_query: str | None = Field(
        default=None,
        description=(
            "Optional query string used to filter historical usage events when "
            "computing metrics (e.g., by tool name, error substring, or summary)."
        ),
    )


class ToolTaskMetrics(BaseModel):
    """Per-tool metrics within a single evaluation task."""

    model_config = ConfigDict(extra="forbid")

    calls: int = Field(ge=0, description="Number of calls for this tool")
    successful: int = Field(ge=0, description="Number of successful calls")
    failed: int = Field(ge=0, description="Number of failed calls")


class EvalTaskResult(BaseModel):
    """Computed metrics for a single evaluation task."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_name: str
    category: str
    status: EvalTaskStatus
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    total_input_tokens: int = Field(
        default=0,
        ge=0,
        description="Total input tokens consumed (0 when usage events lack token data)",
    )
    total_output_tokens: int = Field(
        default=0,
        ge=0,
        description="Total output tokens consumed (0 when usage events lack token data)",
    )
    error_types: dict[str, int] = Field(default_factory=dict)
    evaluated_tools: list[str] = Field(default_factory=list)
    tool_metrics: dict[str, ToolTaskMetrics] = Field(
        default_factory=dict,
        description="Per-tool call and success counts for dashboard aggregation",
    )


def _empty_eval_results() -> list[EvalTaskResult]:
    """Typed default factory for EvalSuiteResult.tasks."""
    return []


def _empty_category_success() -> dict[str, list[float]]:
    """Typed default factory for category_success accumulator."""
    return {}


def _empty_error_counter() -> dict[str, ErrorPattern]:
    """Typed default factory for error_counter accumulator."""
    return {}


class EvalSuiteResult(BaseModel):
    """Aggregate results for an evaluation suite run."""

    model_config = ConfigDict(extra="forbid")

    generated_at: str = Field(
        description="ISO 8601 timestamp when the suite was evaluated"
    )
    tasks: list[EvalTaskResult] = Field(default_factory=_empty_eval_results)


class ErrorPattern(BaseModel):
    """Aggregated error pattern across tasks and tools."""

    model_config = ConfigDict(extra="forbid")

    error_type: str
    count: int
    affected_tools: list[str]


class ToolCombination(BaseModel):
    """Tool usage pattern: set of tools used together in tasks."""

    model_config = ConfigDict(extra="forbid")

    tools: list[str] = Field(description="Tool names that co-occur in tasks")
    task_count: int = Field(ge=0, description="Number of tasks using this combination")


def _empty_tool_combinations() -> list[ToolCombination]:
    """Typed default factory for EvalAnalysis.top_tool_combinations."""
    return []


class EvalAnalysis(BaseModel):
    """High-level analysis of an evaluation suite."""

    model_config = ConfigDict(extra="forbid")

    overall_success_rate: float
    total_tasks: int
    tasks_with_no_data: int
    tasks_unavailable: int
    average_calls_per_task: float
    average_tokens_per_task: float = Field(
        default=0.0,
        ge=0,
        description="Average input+output tokens per task (0 when usage lacks token data)",
    )
    token_consumption_by_category: dict[str, float] = Field(
        default_factory=dict,
        description="Average tokens per task by category (empty when no token data)",
    )
    top_error_patterns: list[ErrorPattern]
    success_rate_by_category: dict[str, float]
    top_tool_combinations: list[ToolCombination] = Field(
        default_factory=_empty_tool_combinations,
        description="Most common tool sets used together across tasks",
    )


class ABWinner(str, Enum):
    """Winner of an A/B comparison (baseline vs optimized)."""

    baseline = "baseline"
    optimized = "optimized"
    tie = "tie"


class OptimizationRunWinner(str, Enum):
    """Winner or status of an optimization run (includes baseline-only)."""

    baseline = "baseline"
    optimized = "optimized"
    tie = "tie"
    baseline_only = "baseline_only"


class ABComparisonResult(BaseModel):
    """Result of comparing baseline vs optimized evaluation analyses (A/B)."""

    model_config = ConfigDict(extra="forbid")

    winner: ABWinner
    success_rate_delta: float = Field(
        description="optimized minus baseline overall_success_rate"
    )
    total_error_count_baseline: int = 0
    total_error_count_optimized: int = 0
    error_count_delta: int = Field(
        description="optimized total errors minus baseline (negative = fewer errors)"
    )


class OptimizationRunRecord(BaseModel):
    """Single optimization run for history persistence."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    generated_at: str = Field(description="ISO 8601 timestamp")
    baseline_success_rate: float = 0.0
    optimized_success_rate: float | None = None
    winner: OptimizationRunWinner = OptimizationRunWinner.baseline_only
    success_rate_delta: float | None = None
    total_error_count_baseline: int = 0
    total_error_count_optimized: int | None = None


class RunToolEvaluationPayload(BaseModel):
    """JSON-serializable payload for run_tool_evaluation response."""

    model_config = ConfigDict(extra="forbid")

    status: OperationStatus = OperationStatus.SUCCESS
    project_root: str = Field(description="Project root path")
    tasks_loaded: int = Field(ge=0, description="Number of tasks loaded")
    generated_at: str = Field(description="Suite generation timestamp")
    cache_file: str = Field(description="Path to last_suite.json")
    suite: dict[str, object] = Field(
        description="Suite result as JSON-serializable dict"
    )
    analysis: dict[str, object] = Field(
        description="Analysis result as JSON-serializable dict"
    )
    dashboard_path: str | None = Field(
        default=None, description="Relative path to dashboard.md"
    )


@dataclass(slots=True)
class _AggregatedEvents:
    """Internal helper for aggregating ToolUsageEvent metrics."""

    events: list[ToolUsageEvent]

    @property
    def total_calls(self) -> int:
        return len(self.events)

    @property
    def successful_calls(self) -> int:
        return sum(1 for e in self.events if e.success)

    @property
    def failed_calls(self) -> int:
        return sum(1 for e in self.events if not e.success)

    @property
    def success_rate(self) -> float:
        return (
            float(self.successful_calls) / float(self.total_calls)
            if self.total_calls
            else 0.0
        )

    @property
    def avg_duration_ms(self) -> float:
        if not self.events:
            return 0.0
        durations = [e.duration_ms for e in self.events]
        return float(sum(durations) / len(durations))

    @property
    def total_duration_ms(self) -> float:
        return float(sum(e.duration_ms for e in self.events))

    @property
    def error_types(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.events:
            if e.error_type:
                out[e.error_type] = out.get(e.error_type, 0) + 1
        return out

    def tool_metrics(self) -> dict[str, ToolTaskMetrics]:
        """Per-tool call and success counts for dashboard aggregation."""
        by_tool: dict[str, list[ToolUsageEvent]] = {}
        for e in self.events:
            by_tool.setdefault(e.tool_name, []).append(e)
        out: dict[str, ToolTaskMetrics] = {}
        for name, evs in by_tool.items():
            successful = sum(1 for e in evs if e.success)
            out[name] = ToolTaskMetrics(
                calls=len(evs),
                successful=successful,
                failed=len(evs) - successful,
            )
        return out


@dataclass(slots=True)
class _AnalysisAccumulator:
    """Accumulator for evaluation analysis metrics."""

    total_success_rate: float = 0.0
    total_calls: int = 0
    tasks_with_no_data: int = 0
    tasks_unavailable: int = 0
    category_success: dict[str, list[float]] = field(
        default_factory=_empty_category_success
    )
    error_counter: dict[str, ErrorPattern] = field(default_factory=_empty_error_counter)

    def add_result(self, result: EvalTaskResult) -> None:
        """Update aggregate metrics and error counters for a single task."""
        self.total_success_rate += result.success_rate
        self.total_calls += result.total_calls
        if result.status == EvalTaskStatus.NO_DATA:
            self.tasks_with_no_data += 1
        if result.status == EvalTaskStatus.UNAVAILABLE:
            self.tasks_unavailable += 1

        self.category_success.setdefault(result.category, []).append(
            result.success_rate
        )

        for err_type, count in result.error_types.items():
            existing = self.error_counter.get(err_type)
            tools: set[str] = (
                set(existing.affected_tools) if existing is not None else set()
            )
            tools.update(result.evaluated_tools)
            total_count = (existing.count if existing is not None else 0) + count
            self.error_counter[err_type] = ErrorPattern(
                error_type=err_type,
                count=total_count,
                affected_tools=sorted(tools),
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

    async def _collect_events_for_task(self, task: EvalTask) -> _AggregatedEvents:
        """Collect usage events for all expected tools in a task."""
        if self._tracker is None:
            return _AggregatedEvents(events=[])

        events: list[ToolUsageEvent] = []
        # Use a reasonable per-tool cap to keep evaluation bounded.
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
        return _AggregatedEvents(events=events)

    def _unavailable_result(self, task: EvalTask) -> EvalTaskResult:
        """Build a result payload when the tracker is unavailable."""
        return EvalTaskResult(
            task_id=task.id,
            task_name=task.name,
            category=task.category.value,
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

    def _status_for_aggregated_events(self, agg: _AggregatedEvents) -> EvalTaskStatus:
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
        agg: _AggregatedEvents,
    ) -> EvalTaskResult:
        status = self._status_for_aggregated_events(agg)
        return EvalTaskResult(
            task_id=task.id,
            task_name=task.name,
            category=task.category.value,
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
        generated_at = datetime.now(UTC).isoformat()
        results: list[EvalTaskResult] = []
        for task in suite:
            results.append(await self.run_task(task))
        return EvalSuiteResult(generated_at=generated_at, tasks=results)

    def analyze_results(self, suite: EvalSuiteResult) -> EvalAnalysis:
        """Analyze a completed suite and compute high-level metrics."""
        from cortex.tools import phase5_evaluation_helpers as _eval_helpers

        total_tasks = len(suite.tasks)
        if total_tasks == 0:
            return _eval_helpers.empty_eval_analysis()
        acc = _AnalysisAccumulator()
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


def _total_error_count(analysis: EvalAnalysis) -> int:
    """Sum of error counts across all top error patterns."""
    return sum(p.count for p in analysis.top_error_patterns)


def compare_ab_analyses(
    baseline: EvalAnalysis, optimized: EvalAnalysis
) -> ABComparisonResult:
    """Compare baseline vs optimized analysis for A/B tool description testing.

    Winner is chosen by: higher overall_success_rate wins; if tie, fewer
    total errors wins; else tie.
    """
    success_rate_delta = optimized.overall_success_rate - baseline.overall_success_rate
    total_baseline = _total_error_count(baseline)
    total_optimized = _total_error_count(optimized)
    error_delta = total_optimized - total_baseline

    if success_rate_delta > 0:
        winner = ABWinner.optimized
    elif success_rate_delta < 0:
        winner = ABWinner.baseline
    else:
        if error_delta < 0:
            winner = ABWinner.optimized
        elif error_delta > 0:
            winner = ABWinner.baseline
        else:
            winner = ABWinner.tie

    return ABComparisonResult(
        winner=winner,
        success_rate_delta=success_rate_delta,
        total_error_count_baseline=total_baseline,
        total_error_count_optimized=total_optimized,
        error_count_delta=error_delta,
    )


async def _get_usage_tracker(root: Path) -> UsageTracker | None:
    """Resolve UsageTracker via existing usage_analytics helper."""
    return await usage_analytics._get_tracker(root)  # type: ignore[attr-defined]


@mcp.tool(annotations=read_only_annotations("Tool Evaluation"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def run_tool_evaluation(
    task_ids: list[str] | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Run the evaluation suite for MCP tools and return metrics."""
    root = await resolve_project_root_async(None, ctx)
    if ctx is not None:
        await log_client(
            ctx,
            "info",
            "run_tool_evaluation: starting",
            logger_name=__name__,
        )

    tracker = await _get_usage_tracker(root)
    tasks = await load_eval_tasks(root, task_ids)

    harness = ToolEvaluationHarness(project_root=root, tracker=tracker)
    suite = await harness.run_suite(tasks)
    analysis = harness.analyze_results(suite)

    await _persist_latest_suite(root, suite, analysis)
    dashboard_path = await _write_evaluation_dashboard(root, analysis, suite)
    payload = _build_evaluation_payload(root, tasks, suite, analysis)
    payload = payload.model_copy(
        update={"dashboard_path": str(dashboard_path.relative_to(root))}
    )
    return json.dumps(payload.model_dump(mode="json"), indent=2)


async def _write_evaluation_dashboard(
    root: Path,
    analysis: EvalAnalysis,
    suite: EvalSuiteResult,
) -> Path:
    """Write evaluation dashboard Markdown report next to last_suite.json.

    Args:
        root: Project root path
        analysis: Evaluation analysis
        suite: Evaluation suite results

    Returns:
        Path to written dashboard file
    """
    from cortex.tools.phase5_evaluation_dashboard_helpers import (
        generate_evaluation_dashboard,
    )

    dashboard_content = generate_evaluation_dashboard(analysis, suite)
    cache_dir = get_cache_path(root, CortexResourceType.CACHE.value)
    dashboard_path = cache_dir / "evals" / "dashboard.md"
    # Create directory if it doesn't exist; return value intentionally unused
    # pyright: ignore[reportUnusedCallResult]
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    _ = dashboard_path.write_text(dashboard_content, encoding="utf-8")
    return dashboard_path


async def _persist_latest_suite(
    root: Path,
    suite: EvalSuiteResult,
    analysis: EvalAnalysis,
) -> None:
    """Persist latest evaluation suite and analysis to cache."""
    cache_key = "evals/last_suite.json"
    await write_cache_json(
        root,
        cache_key,
        {
            "suite": suite.model_dump(mode="json"),
            "analysis": analysis.model_dump(mode="json"),
        },
    )


def _build_evaluation_payload(
    root: Path,
    tasks: list[EvalTask],
    suite: EvalSuiteResult,
    analysis: EvalAnalysis,
) -> RunToolEvaluationPayload:
    """Build JSON-serializable payload for run_tool_evaluation."""
    cache_path = get_cache_path(root, "evals") / "last_suite.json"
    return RunToolEvaluationPayload(
        status=OperationStatus.SUCCESS,
        project_root=str(root),
        tasks_loaded=len(tasks),
        generated_at=suite.generated_at,
        cache_file=str(cache_path),
        suite=cast(dict[str, object], suite.model_dump(mode="json")),
        analysis=cast(dict[str, object], analysis.model_dump(mode="json")),
    )


async def _persist_error_patterns(root: Path, analysis: EvalAnalysis) -> None:
    """Persist top error patterns to a dedicated cache file.

    This complements the full suite payload by providing a lightweight view
    that other tools (or external dashboards) can consume without loading the
    entire evaluation result.
    """
    cache_key = "evals/error_patterns.json"
    await write_cache_json(
        root,
        cache_key,
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_patterns": len(analysis.top_error_patterns),
            "patterns": [
                pattern.model_dump(mode="json")
                for pattern in analysis.top_error_patterns
            ],
        },
    )


_OPTIMIZATION_HISTORY_KEY = "evals/optimization_history.json"


async def load_optimization_history(
    root: Path,
) -> list[OptimizationRunRecord]:
    """Load optimization run history from cache; returns empty list if missing."""
    raw = await read_cache_json(root, _OPTIMIZATION_HISTORY_KEY)
    if not raw or not isinstance(raw, dict) or "runs" not in raw:
        return []
    runs_raw = raw.get("runs")
    if not isinstance(runs_raw, list):
        return []
    runs: list[dict[str, object]] = cast(list[dict[str, object]], runs_raw)
    records: list[OptimizationRunRecord] = []
    for item in runs:
        try:
            records.append(OptimizationRunRecord.model_validate(item))
        except Exception:
            continue
    return records


async def append_optimization_record(root: Path, record: OptimizationRunRecord) -> None:
    """Append a single optimization run record to history and persist."""
    history = await load_optimization_history(root)
    history.append(record)
    await write_cache_json(
        root,
        _OPTIMIZATION_HISTORY_KEY,
        {"runs": [r.model_dump(mode="json") for r in history]},
    )


def _parse_optimized_analysis(json_str: str | None) -> EvalAnalysis | None:
    """Parse optimized_analysis_json into EvalAnalysis or return None."""
    if not json_str or not json_str.strip():
        return None
    try:
        optimized_dict = json.loads(json_str)
        return EvalAnalysis.model_validate(optimized_dict)
    except (json.JSONDecodeError, Exception):
        return None


def _build_optimization_record(
    baseline_analysis: EvalAnalysis,
    optimized_analysis: EvalAnalysis | None,
    run_id: str,
    generated_at: str,
) -> OptimizationRunRecord:
    """Build OptimizationRunRecord for baseline-only or A/B comparison."""
    total_errors_baseline = _total_error_count(baseline_analysis)
    if optimized_analysis is None:
        return OptimizationRunRecord(
            run_id=run_id,
            generated_at=generated_at,
            baseline_success_rate=baseline_analysis.overall_success_rate,
            optimized_success_rate=None,
            winner=OptimizationRunWinner.baseline_only,
            success_rate_delta=None,
            total_error_count_baseline=total_errors_baseline,
            total_error_count_optimized=None,
        )
    comparison = compare_ab_analyses(baseline_analysis, optimized_analysis)
    return OptimizationRunRecord(
        run_id=run_id,
        generated_at=generated_at,
        baseline_success_rate=baseline_analysis.overall_success_rate,
        optimized_success_rate=optimized_analysis.overall_success_rate,
        winner=OptimizationRunWinner(comparison.winner.value),
        success_rate_delta=comparison.success_rate_delta,
        total_error_count_baseline=comparison.total_error_count_baseline,
        total_error_count_optimized=comparison.total_error_count_optimized,
    )


def _build_optimization_workflow_payload(
    root: Path,
    run_id: str,
    baseline_analysis: EvalAnalysis,
    record: OptimizationRunRecord,
    history: list[OptimizationRunRecord],
) -> str:
    """Build JSON payload string for run_tool_optimization_workflow response."""
    payload = {
        "status": "success",
        "project_root": str(root),
        "run_id": run_id,
        "baseline_success_rate": baseline_analysis.overall_success_rate,
        "record": record.model_dump(mode="json"),
        "history_runs_count": len(history),
        "cache_file": str(get_cache_path(root, "evals") / "optimization_history.json"),
    }
    return json.dumps(payload, indent=2)


@mcp.tool(annotations=read_only_annotations("Tool Error Pattern Analysis"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def analyze_error_patterns(
    task_ids: list[str] | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Analyze error patterns across evaluation tasks and cache the results.

    This tool runs the same evaluation harness as ``run_tool_evaluation`` but
    focuses on the aggregated error patterns. It writes a compact JSON payload
    to ``.cortex/.cache/evals/error_patterns.json`` and returns a summary
    payload including the top patterns.
    """
    root = await resolve_project_root_async(None, ctx)
    if ctx is not None:
        await log_client(
            ctx,
            "info",
            "analyze_error_patterns: starting",
            logger_name=__name__,
        )

    tracker = await _get_usage_tracker(root)
    tasks = await load_eval_tasks(root, task_ids)

    harness = ToolEvaluationHarness(project_root=root, tracker=tracker)
    suite = await harness.run_suite(tasks)
    analysis = harness.analyze_results(suite)

    await _persist_error_patterns(root, analysis)
    cache_path = get_cache_path(root, "evals") / "error_patterns.json"
    payload = {
        "status": "success",
        "project_root": str(root),
        "tasks_loaded": len(tasks),
        "generated_at": suite.generated_at,
        "cache_file": str(cache_path),
        "total_patterns": len(analysis.top_error_patterns),
        "error_patterns": [
            pattern.model_dump(mode="json") for pattern in analysis.top_error_patterns
        ],
    }
    return json.dumps(payload, indent=2)


@mcp.tool(annotations=read_only_annotations("Session Tool Anomalies"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def get_session_tool_anomalies(
    hours: int = 24,
    ctx: MCPContext | None = None,
) -> str:
    """Compare session tool usage to expected patterns and flag anomalies.

    For use in end-of-session analysis: lists tools used in the last N hours,
    and flags tools with retries or errors. Call this from the Analyze prompt
    to add a Tool use anomalies subsection to the report.
    """
    root = await resolve_project_root_async(None, ctx)
    if ctx is not None:
        await log_client(
            ctx,
            "info",
            "get_session_tool_anomalies: starting",
            logger_name=__name__,
        )
    tracker = await _get_usage_tracker(root)
    if tracker is None:
        return unavailable_session_anomalies_response(hours)
    payload = await _get_session_tool_anomalies_payload(root, tracker, hours)
    return json.dumps(payload.model_dump(mode="json"), indent=2)


@mcp.tool(annotations=read_only_annotations("Tool Optimization Workflow"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def run_tool_optimization_workflow(
    task_ids: list[str] | None = None,
    optimized_analysis_json: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Run evaluation baseline and optionally compare with optimized run (A/B).

    Runs the evaluation suite to get baseline metrics, then either records
    a baseline-only entry or compares with provided optimized analysis and
    appends the result to .cortex/.cache/evals/optimization_history.json.
    """
    root = await resolve_project_root_async(None, ctx)
    if ctx is not None:
        await log_client(
            ctx,
            "info",
            "run_tool_optimization_workflow: starting",
            logger_name=__name__,
        )
    tracker = await _get_usage_tracker(root)
    tasks = await load_eval_tasks(root, task_ids)
    harness = ToolEvaluationHarness(project_root=root, tracker=tracker)
    suite = await harness.run_suite(tasks)
    baseline_analysis = harness.analyze_results(suite)
    run_id = f"run-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    generated_at = datetime.now(UTC).isoformat()
    optimized_analysis = _parse_optimized_analysis(optimized_analysis_json)
    record = _build_optimization_record(
        baseline_analysis, optimized_analysis, run_id, generated_at
    )
    await append_optimization_record(root, record)
    history = await load_optimization_history(root)
    return _build_optimization_workflow_payload(
        root, run_id, baseline_analysis, record, history
    )
