"""
Phase 57: Optimization history and A/B comparison helpers.

Extracted for Phase 9.1.4 file size compliance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.core.path_resolver import get_cache_path

from ._models import (
    ABComparisonResult,
    ABWinner,
    EvalAnalysis,
    OptimizationRunRecord,
    OptimizationRunWinner,
)

_OPTIMIZATION_HISTORY_KEY = "evals/optimization_history.json"


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


def parse_optimized_analysis(json_str: str | None) -> EvalAnalysis | None:
    """Parse optimized_analysis_json into EvalAnalysis or return None."""
    if not json_str or not json_str.strip():
        return None
    try:
        optimized_dict = json.loads(json_str)
        return EvalAnalysis.model_validate(optimized_dict)
    except (json.JSONDecodeError, Exception):
        return None


def build_optimization_record(
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


def build_optimization_workflow_payload(
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
