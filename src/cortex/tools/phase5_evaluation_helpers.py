"""Phase 57: Analysis helpers for evaluation suite (extracted for file size limits)."""

from __future__ import annotations

from cortex.tools.phase5_evaluation._models import (
    ErrorPattern,
    EvalAnalysis,
    EvalSuiteResult,
    EvalTaskResult,
    ToolCombination,
)


def compute_success_rate_by_category(
    category_success: dict[str, list[float]],
) -> dict[str, float]:
    """Compute average success rate for each category."""
    out: dict[str, float] = {}
    for category, rates in category_success.items():
        if not rates:
            continue
        out[category] = sum(rates) / float(len(rates))
    return out


def compute_tokens_by_category(
    tasks: list[EvalTaskResult],
) -> dict[str, float]:
    """Compute average token consumption (input+output) per task by category."""
    by_cat: dict[str, list[int]] = {}
    for r in tasks:
        tokens = r.total_input_tokens + r.total_output_tokens
        by_cat.setdefault(r.category, []).append(tokens)
    out: dict[str, float] = {}
    for category, values in by_cat.items():
        if not values:
            continue
        out[category] = float(sum(values)) / float(len(values))
    return out


def compute_top_tool_combinations(
    suite: EvalSuiteResult,
    limit: int = 10,
) -> list[ToolCombination]:
    """Compute most common tool sets (co-occurrence) across tasks."""
    key_to_count: dict[tuple[str, ...], int] = {}
    for result in suite.tasks:
        if not result.evaluated_tools:
            continue
        key = tuple(sorted(result.evaluated_tools))
        key_to_count[key] = key_to_count.get(key, 0) + 1
    sorted_keys = sorted(
        key_to_count.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:limit]
    return [ToolCombination(tools=list(k), task_count=c) for k, c in sorted_keys]


def top_error_patterns(
    error_counter: dict[str, ErrorPattern],
    limit: int = 10,
) -> list[ErrorPattern]:
    """Return top-N error patterns sorted by count descending."""
    patterns_sorted = sorted(
        error_counter.values(), key=lambda p: p.count, reverse=True
    )
    return patterns_sorted[:limit]


def empty_eval_analysis() -> EvalAnalysis:
    """Return zeroed EvalAnalysis for an empty suite."""
    return EvalAnalysis(
        overall_success_rate=0.0,
        total_tasks=0,
        tasks_with_no_data=0,
        tasks_unavailable=0,
        average_calls_per_task=0.0,
        average_tokens_per_task=0.0,
        token_consumption_by_category={},
        top_error_patterns=[],
        success_rate_by_category={},
        top_tool_combinations=[],
    )


def build_eval_analysis(
    category_success: dict[str, list[float]],
    error_counter: dict[str, ErrorPattern],
    tasks_with_no_data: int,
    tasks_unavailable: int,
    total_tasks: int,
    overall_success_rate: float,
    average_calls_per_task: float,
    suite: EvalSuiteResult,
) -> EvalAnalysis:
    """Build EvalAnalysis from accumulator state and suite (avoids long analyze_results)."""
    total_tokens = sum(
        r.total_input_tokens + r.total_output_tokens for r in suite.tasks
    )
    average_tokens_per_task = (
        float(total_tokens) / float(total_tasks) if total_tasks else 0.0
    )
    token_by_cat = compute_tokens_by_category(suite.tasks)
    return EvalAnalysis(
        overall_success_rate=overall_success_rate,
        total_tasks=total_tasks,
        tasks_with_no_data=tasks_with_no_data,
        tasks_unavailable=tasks_unavailable,
        average_calls_per_task=average_calls_per_task,
        average_tokens_per_task=average_tokens_per_task,
        token_consumption_by_category=token_by_cat,
        top_error_patterns=top_error_patterns(error_counter),
        success_rate_by_category=compute_success_rate_by_category(category_success),
        top_tool_combinations=compute_top_tool_combinations(suite),
    )
