"""Phase 57 extension: Model benchmark and comparison for eval-guided upgrades.

Runs the full evaluation suite and stores results keyed by model name for
historical comparison. Supports the model upgrade playbook (docs/guides/model-upgrade-playbook.md).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.models import OperationStatus
from cortex.core.path_resolver import get_cache_path
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.core.pydantic_extra import EXTRA_FORBID

logger = logging.getLogger(__name__)

_MODEL_BENCHMARKS_KEY = "evals/model_benchmarks.json"


class ModelBenchmarkRecord(BaseModel):
    """Single benchmark run for one model (stored for historical comparison)."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    model_name: str = Field(
        description="Model identifier (e.g. claude-sonnet-4, current)"
    )
    generated_at: str = Field(description="ISO 8601 timestamp of the run")
    overall_success_rate: float = Field(
        ge=0, le=1, description="Harness overall success rate"
    )
    execution_passed: int = Field(ge=0, description="Execution-based tasks passed")
    execution_failed: int = Field(ge=0, description="Execution-based tasks failed")
    execution_skipped: int = Field(ge=0, description="Execution-based tasks skipped")
    execution_total_run: int = Field(ge=0, description="Execution-based tasks run")
    execution_pass_rate: float = Field(
        ge=0, le=1, description="Execution pass rate (passed / total_run or 0)"
    )
    tasks_loaded: int = Field(ge=0, description="Number of eval tasks loaded")
    analysis: dict[str, object] = Field(
        default_factory=dict,
        description="Full analysis dict from run_tool_evaluation",
    )
    execution_summary: dict[str, object] = Field(
        default_factory=dict,
        description="Execution summary dict for per-task comparison",
    )


class ModelBenchmarkComparison(BaseModel):
    """Comparison of current run vs a baseline run."""

    model_config = ConfigDict(extra=EXTRA_FORBID)

    baseline_model: str = Field(description="Model name of the baseline run")
    baseline_generated_at: str = Field(description="Baseline run timestamp")
    current_model: str = Field(description="Model name of the current run")
    current_generated_at: str = Field(description="Current run timestamp")
    success_rate_delta: float = Field(
        description="Current overall_success_rate minus baseline"
    )
    execution_pass_rate_delta: float = Field(
        description="Current execution_pass_rate minus baseline"
    )
    regressions: list[str] = Field(
        default_factory=list,
        description="Task IDs that passed in baseline but failed in current",
    )
    improvements: list[str] = Field(
        default_factory=list,
        description="Task IDs that failed in baseline but passed in current",
    )


def _execution_pass_rate(record: ModelBenchmarkRecord) -> float:
    """Compute execution pass rate from record (for comparison)."""
    if record.execution_total_run <= 0:
        return 0.0
    return record.execution_passed / float(record.execution_total_run)


def _to_int(val: object) -> int:
    """Coerce value to int for cache dict values."""
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, float):
        return int(val)
    return 0


def _task_result_map(execution_summary: dict[str, object]) -> dict[str, bool]:
    """Build task_id -> passed from execution_summary.results."""
    results_raw = execution_summary.get("results")
    if not isinstance(results_raw, list):
        return {}
    results = cast(list[object], results_raw)
    out: dict[str, bool] = {}
    for raw in results:
        if not isinstance(raw, dict):
            continue
        item = cast(dict[str, object], raw)
        if "task_id" not in item or "passed" not in item:
            continue
        tid = item.get("task_id")
        passed = item.get("passed")
        if isinstance(tid, str) and isinstance(passed, bool):
            out[tid] = passed
    return out


def _build_comparison(
    baseline: ModelBenchmarkRecord,
    current: ModelBenchmarkRecord,
) -> ModelBenchmarkComparison:
    """Build comparison report between baseline and current run."""
    baseline_pass_rate = _execution_pass_rate(baseline)
    current_pass_rate = _execution_pass_rate(current)
    baseline_map = _task_result_map(baseline.execution_summary)
    current_map = _task_result_map(current.execution_summary)

    regressions: list[str] = []
    improvements: list[str] = []

    for task_id, base_passed in baseline_map.items():
        cur_passed = current_map.get(task_id, False)
        if base_passed and not cur_passed:
            regressions.append(task_id)
        if not base_passed and cur_passed:
            improvements.append(task_id)

    for task_id, cur_passed in current_map.items():
        if task_id not in baseline_map and cur_passed:
            improvements.append(task_id)

    return ModelBenchmarkComparison(
        baseline_model=baseline.model_name,
        baseline_generated_at=baseline.generated_at,
        current_model=current.model_name,
        current_generated_at=current.generated_at,
        success_rate_delta=current.overall_success_rate - baseline.overall_success_rate,
        execution_pass_rate_delta=current_pass_rate - baseline_pass_rate,
        regressions=regressions,
        improvements=improvements,
    )


async def _load_benchmarks(root: Path) -> list[ModelBenchmarkRecord]:
    """Load benchmark history from cache; return empty list if missing."""
    raw = await read_cache_json(root, _MODEL_BENCHMARKS_KEY)
    if not raw or not isinstance(raw, dict) or "benchmarks" not in raw:
        return []
    benches_raw = raw.get("benchmarks")
    if not isinstance(benches_raw, list):
        return []
    benches = cast(list[object], benches_raw)
    records: list[ModelBenchmarkRecord] = []
    for raw_item in benches:
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, object], raw_item)
        try:
            records.append(ModelBenchmarkRecord.model_validate(item))
        except Exception as e:
            logger.debug("_load_benchmarks: skip invalid record: %s", e)
            continue
    return records


async def _save_benchmarks(root: Path, records: list[ModelBenchmarkRecord]) -> None:
    """Persist benchmark list to cache."""
    await write_cache_json(
        root,
        _MODEL_BENCHMARKS_KEY,
        {"benchmarks": [r.model_dump(mode="json") for r in records]},
    )


async def _run_full_eval(root: Path) -> dict[str, object]:
    """Run full evaluation suite and return payload dict."""
    from cortex.tools.evaluation import run_full_evaluation_payload

    return await run_full_evaluation_payload(root)


def _parse_execution_counts(
    exec_summary: dict[str, object],
) -> tuple[int, int, int, int]:
    """Return (execution_passed, execution_failed, execution_skipped, execution_total_run)."""
    return (
        _to_int(exec_summary.get("execution_passed", 0)),
        _to_int(exec_summary.get("execution_failed", 0)),
        _to_int(exec_summary.get("execution_skipped", 0)),
        _to_int(exec_summary.get("execution_total_run", 0)),
    )


def _parse_payload_analysis_meta(
    payload: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], float, int, str]:
    """Return (analysis, exec_summary, overall_success_rate, tasks_loaded, generated_at)."""
    raw_analysis: object = payload.get("analysis")
    analysis = (
        cast(dict[str, object], raw_analysis) if isinstance(raw_analysis, dict) else {}
    )
    raw_exec: object = payload.get("execution_summary")
    exec_summary = (
        cast(dict[str, object], raw_exec) if isinstance(raw_exec, dict) else {}
    )
    raw_overall: object = analysis.get("overall_success_rate", 0.0)
    overall = float(raw_overall) if isinstance(raw_overall, (int, float)) else 0.0
    raw_tasks: object = payload.get("tasks_loaded", 0)
    tasks_loaded = int(raw_tasks) if isinstance(raw_tasks, (int, float)) else 0
    raw_ts: object = payload.get("generated_at", datetime.now(UTC).isoformat())
    generated_at = str(raw_ts) if raw_ts is not None else datetime.now(UTC).isoformat()
    return analysis, exec_summary, overall, tasks_loaded, generated_at


def _payload_to_record(
    model_name: str,
    payload: dict[str, object],
) -> ModelBenchmarkRecord:
    """Build ModelBenchmarkRecord from run_tool_evaluation payload."""
    analysis, exec_summary, overall, tasks_loaded, generated_at = (
        _parse_payload_analysis_meta(payload)
    )
    execution_passed, execution_failed, execution_skipped, execution_total_run = (
        _parse_execution_counts(exec_summary)
    )
    execution_pass_rate = (
        execution_passed / float(execution_total_run)
        if execution_total_run > 0
        else 0.0
    )
    return ModelBenchmarkRecord(
        model_name=model_name,
        generated_at=generated_at,
        overall_success_rate=overall,
        execution_passed=execution_passed,
        execution_failed=execution_failed,
        execution_skipped=execution_skipped,
        execution_total_run=execution_total_run,
        execution_pass_rate=execution_pass_rate,
        tasks_loaded=tasks_loaded,
        analysis=analysis,
        execution_summary=exec_summary,
    )


async def benchmark_model(
    model_name: str,
    baseline_model_name: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Run the full evaluation suite and store results for model upgrade comparison.

    Unpublished from MCP tool list (2026-03-02). Use run_tool_evaluation + manual
    store/compare for model benchmarks. Kept as callable for tests and internal use.

    USE WHEN: (Internal use) User wants to benchmark a model, user needs eval-guided
    model upgrade, user requests comparison with baseline, user wants
    to store eval results by model name.

    EXAMPLES: 'benchmark_model(model_name="claude-sonnet-4")',
    'benchmark model current vs baseline', 'run model benchmark with
    baseline claude-sonnet-3'.

    RETURNS: JSON with status, model_name, baseline_model_name (if
    set), record (success rate, task counts), history_runs_count,
    cache_file. Optionally includes comparison when baseline_model_name
    is set (regressions, improvements).

    Runs run_tool_evaluation(mode='full'), stores the result keyed by
    model_name in .cortex/.cache/evals/model_benchmarks.json. See
    docs/guides/model-upgrade-playbook.md. Project root resolved internally.

    Args:
        model_name: Identifier for this model (e.g. claude-sonnet-4,
            current). Used to store and retrieve benchmark runs.
        baseline_model_name: If set, the most recent stored run with
            this name is used to generate a comparison report
            (regressions, improvements).
    """
    root = await resolve_project_root_async(None, ctx)
    if ctx is not None:
        await log_client(
            ctx,
            "info",
            "benchmark_model: starting full eval",
            logger_name=__name__,
        )

    payload = await _run_full_eval(root)
    record = _payload_to_record(model_name, payload)
    history = await _load_benchmarks(root)
    history.append(record)
    await _save_benchmarks(root, history)

    out = _build_benchmark_output(
        root, model_name, record, history, baseline_model_name
    )
    return json.dumps(out, indent=2)


def _add_comparison(
    out: dict[str, object],
    history: list[ModelBenchmarkRecord],
    record: ModelBenchmarkRecord,
    baseline_model_name: str,
) -> None:
    """Set out['comparison'] or out['comparison_note'] when baseline is requested."""
    baseline_run = next(
        (r for r in reversed(history[:-1]) if r.model_name == baseline_model_name),
        None,
    )
    if baseline_run is not None:
        out["comparison"] = _build_comparison(baseline_run, record).model_dump(
            mode="json"
        )
    else:
        out["comparison"] = None
        out["comparison_note"] = (
            f"No baseline run found for model {baseline_model_name!r}"
        )


def _build_benchmark_output(
    root: Path,
    model_name: str,
    record: ModelBenchmarkRecord,
    history: list[ModelBenchmarkRecord],
    baseline_model_name: str | None,
) -> dict[str, object]:
    """Build JSON-serializable output dict for benchmark_model."""
    cache_file = str(get_cache_path(root, "evals") / "model_benchmarks.json")
    out: dict[str, object] = {
        "status": OperationStatus.SUCCESS.value,
        "project_root": str(root),
        "model_name": model_name,
        "generated_at": record.generated_at,
        "overall_success_rate": record.overall_success_rate,
        "execution_pass_rate": record.execution_pass_rate,
        "execution_passed": record.execution_passed,
        "execution_failed": record.execution_failed,
        "execution_total_run": record.execution_total_run,
        "tasks_loaded": record.tasks_loaded,
        "cache_file": cache_file,
        "history_count": len(history),
    }
    if baseline_model_name:
        _add_comparison(out, history, record, baseline_model_name)
    return out
