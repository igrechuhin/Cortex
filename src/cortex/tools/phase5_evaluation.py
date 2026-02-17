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

# pyright: reportUnknownVariableType=false
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.cache_json_access import write_cache_json
from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_annotations import read_only_annotations
from cortex.core.mcp_stability import (
    ensure_usage_context,
    mcp_tool_wrapper,
)
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


class EvalTask(BaseModel):
    """Single evaluation task definition grounded in a real workflow.

    The initial implementation deliberately keeps this schema small and focused.
    Future iterations can extend it via the `metadata` field without breaking
    callers or persisted JSON.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(description="Stable identifier for this evaluation task")
    name: str = Field(description="Human-readable task name")
    description: str = Field(description="Detailed task description")
    category: Literal["context", "pre_commit", "plan", "memory_bank", "other"] = Field(
        default="other",
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


class EvalTaskResult(BaseModel):
    """Computed metrics for a single evaluation task."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_name: str
    category: str
    status: Literal["success", "mixed", "no_data", "unavailable"]
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    error_types: dict[str, int] = Field(default_factory=dict)
    evaluated_tools: list[str] = Field(default_factory=list)


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


class EvalAnalysis(BaseModel):
    """High-level analysis of an evaluation suite."""

    model_config = ConfigDict(extra="forbid")

    overall_success_rate: float
    total_tasks: int
    tasks_with_no_data: int
    tasks_unavailable: int
    average_calls_per_task: float
    top_error_patterns: list[ErrorPattern]
    success_rate_by_category: dict[str, float]


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
        if result.status == "no_data":
            self.tasks_with_no_data += 1
        if result.status == "unavailable":
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


def _load_eval_task_dicts(tasks_dir: Path) -> list[dict[str, Any]]:
    """Load raw task dicts from all JSON files under tasks_dir."""
    records: list[dict[str, Any]] = []
    for path in sorted(tasks_dir.glob("*.json")):
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not raw_text.strip():
            continue
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            continue

        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            sequence: list[object] = data
            for item_obj in sequence:
                if isinstance(item_obj, dict):
                    item: dict[str, Any] = item_obj
                    items.append(item)
        elif isinstance(data, dict):
            item_single: dict[str, Any] = data
            items.append(item_single)
        records.extend(items)
    return records


def _build_eval_tasks(
    records: list[dict[str, Any]], selected_ids: set[str]
) -> list[EvalTask]:
    """Validate raw task dicts into EvalTask models and apply ID filter."""
    tasks: list[EvalTask] = []
    for rec in records:
        try:
            task = EvalTask.model_validate(rec)
        except Exception:
            continue
        if selected_ids and task.id not in selected_ids:
            continue
        tasks.append(task)
    return tasks


async def _load_eval_tasks(
    project_root: Path, task_ids: list[str] | None = None
) -> list[EvalTask]:
    """Load evaluation tasks from .cortex/evals/tasks/*.json."""
    evals_dir = get_cortex_path(project_root, CortexResourceType.CORTEX_DIR) / "evals"
    tasks_dir = evals_dir / "tasks"
    if not tasks_dir.is_dir():
        return []

    selected_ids = set(task_ids or [])
    records = _load_eval_task_dicts(tasks_dir)
    return _build_eval_tasks(records, selected_ids)


class ToolEvaluationHarness:
    """Evaluation harness that aggregates metrics from UsageTracker.

    This harness does not attempt to replay full agent workflows. Instead, it
    uses historical ToolUsageEvent data for the tools referenced in each task
    to compute success rates, error patterns, and latency.
    """

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
            category=task.category,
            status="unavailable",
            total_calls=0,
            successful_calls=0,
            failed_calls=0,
            success_rate=0.0,
            avg_duration_ms=0.0,
            total_duration_ms=0.0,
            error_types={},
            evaluated_tools=task.expected_tools,
        )

    def _status_for_aggregated_events(
        self, agg: _AggregatedEvents
    ) -> Literal["success", "mixed", "no_data", "unavailable"]:
        if agg.total_calls == 0:
            return "no_data"
        if agg.failed_calls == 0:
            return "success"
        if agg.successful_calls == 0:
            return "mixed"
        return "mixed"

    def _result_from_aggregated_events(
        self,
        task: EvalTask,
        agg: _AggregatedEvents,
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
        total_tasks = len(suite.tasks)
        if total_tasks == 0:
            return EvalAnalysis(
                overall_success_rate=0.0,
                total_tasks=0,
                tasks_with_no_data=0,
                tasks_unavailable=0,
                average_calls_per_task=0.0,
                top_error_patterns=[],
                success_rate_by_category={},
            )
        acc = _AnalysisAccumulator()
        for result in suite.tasks:
            acc.add_result(result)
        overall_success_rate = acc.total_success_rate / float(total_tasks)
        average_calls_per_task = (
            float(acc.total_calls) / float(total_tasks) if total_tasks else 0.0
        )
        return EvalAnalysis(
            overall_success_rate=overall_success_rate,
            total_tasks=total_tasks,
            tasks_with_no_data=acc.tasks_with_no_data,
            tasks_unavailable=acc.tasks_unavailable,
            average_calls_per_task=average_calls_per_task,
            top_error_patterns=_top_error_patterns(acc.error_counter),
            success_rate_by_category=_compute_success_rate_by_category(
                acc.category_success
            ),
        )


def _compute_success_rate_by_category(
    category_success: dict[str, list[float]],
) -> dict[str, float]:
    """Compute average success rate for each category."""
    out: dict[str, float] = {}
    for category, rates in category_success.items():
        if not rates:
            continue
        out[category] = sum(rates) / float(len(rates))
    return out


def _top_error_patterns(
    error_counter: dict[str, ErrorPattern],
    limit: int = 10,
) -> list[ErrorPattern]:
    """Return top-N error patterns sorted by count descending."""
    patterns_sorted = sorted(
        error_counter.values(), key=lambda p: p.count, reverse=True
    )
    return patterns_sorted[:limit]


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
    tasks = await _load_eval_tasks(root, task_ids)

    harness = ToolEvaluationHarness(project_root=root, tracker=tracker)
    suite = await harness.run_suite(tasks)
    analysis = harness.analyze_results(suite)

    await _persist_latest_suite(root, suite, analysis)
    payload = _build_evaluation_payload(root, tasks, suite, analysis)
    return json.dumps(payload, indent=2)


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
) -> dict[str, Any]:
    """Build JSON-serializable payload for run_tool_evaluation."""
    cache_path = get_cache_path(root, "evals") / "last_suite.json"
    return {
        "status": "success",
        "project_root": str(root),
        "tasks_loaded": len(tasks),
        "generated_at": suite.generated_at,
        "cache_file": str(cache_path),
        "suite": suite.model_dump(mode="json"),
        "analysis": analysis.model_dump(mode="json"),
    }


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
    tasks = await _load_eval_tasks(root, task_ids)

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
