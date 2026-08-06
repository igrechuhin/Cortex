"""
Phase 57: Evaluation-Driven Tool Improvement.

Core evaluation models, harness, and MCP tools for running an evaluation suite
over existing usage analytics data. Split into submodules for Phase 9.1.4
file size compliance (each file <400 lines).

Public API: run_tool_evaluation, run_full_evaluation_payload, load_eval_tasks,
compare_ab_analyses, analyze_error_patterns, get_session_tool_anomalies,
run_tool_optimization_workflow, load_optimization_history, append_optimization_record.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from cortex.core.constants import MCP_TOOL_TIMEOUT_COMPLEX
from cortex.core.context_logging import MCPContext, log_client
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.project_root_resolver import resolve_project_root_async

from ._agentic_models import (
    AgenticScorecard,
    AgenticSkipReason,
    AgenticSummary,
    AgenticTaskResult,
    EvalTaskKind,
    ToolFeedbackRecord,
    UnpairedReason,
)
from ._agentic_suite import AgenticSuiteOutcome, run_agentic_suite
from ._harness import ToolEvaluationHarness, load_eval_tasks
from ._models import (
    ABComparisonResult,
    ABWinner,
    ErrorPattern,
    EvalAnalysis,
    EvalRunMode,
    EvalSuiteResult,
    EvalTask,
    EvalTaskCategory,
    EvalTaskResult,
    EvalTaskStatus,
    ExecutionExpectSpec,
    ExecutionExpectType,
    ExecutionResultEntry,
    ExecutionSpec,
    ExecutionSummary,
    OptimizationRunRecord,
    OptimizationRunWinner,
    ToolCombination,
    ToolTaskMetrics,
)
from ._optimization import (
    append_optimization_record,
    build_optimization_record,
    build_optimization_workflow_payload,
    compare_ab_analyses,
    load_optimization_history,
    parse_optimized_analysis,
)
from ._payload_models import RunToolEvaluationPayload
from ._run_impl import analyze_error_patterns_impl, run_tool_evaluation_impl


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def run_tool_evaluation(
    task_ids: list[str] | None = None,
    mode: str = "full",
    category: EvalTaskCategory | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Run the evaluation suite for MCP tools and return metrics.

    USE WHEN: User wants to run evals, user needs tool evaluation
    results, user requests eval suite, user wants pass/fail metrics
    before or after tool changes.

    EXAMPLES: 'run_tool_evaluation(mode="fast")', 'run evals in full
    mode', 'run_tool_evaluation(mode="focused", category="context")'.

    RETURNS: JSON with status, tasks_loaded, suite (per-task results),
    analysis (success rate, top error patterns), cache_file path, and
    optional dashboard_path.

    Modes: "fast" (10 tasks, <30s), "full" (all tasks), "focused"
    (filter by category). Project root is resolved internally.

    Args:
        task_ids: Optional list of task IDs to run; if None, all tasks
            for the selected mode are run.
        mode: "fast" (10 execution tasks, <30s), "full" (all tasks),
            "focused" (filter by category), "agentic" (agent-in-the-loop
            tool-selection eval; requires the optional `anthropic` extra and
            ANTHROPIC_API_KEY, and reports a typed skip otherwise).
            Default: "full".
        category: When mode is "focused", only tasks with this category
            are run. Ignored for "fast" and "full".
    """
    root = await resolve_project_root_async(None, ctx)
    if ctx is not None:
        await log_client(
            ctx,
            "info",
            "run_tool_evaluation: starting",
            logger_name=__name__,
        )
    run_mode = EvalRunMode(mode)
    return await run_tool_evaluation_impl(root, task_ids, run_mode, category)


async def run_full_evaluation_payload(root: Path) -> dict[str, object]:
    """Run full eval and return payload dict (for benchmark_model)."""
    return json.loads(
        await run_tool_evaluation_impl(root, None, EvalRunMode.FULL, None)
    )


@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_COMPLEX)
async def analyze_error_patterns(
    task_ids: list[str] | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Analyze error patterns across evaluation tasks and cache the results.

    USE WHEN: User wants error pattern analysis, user needs top eval
    failures, user requests error aggregation, user wants to improve
    tools based on failure patterns.

    EXAMPLES: 'analyze error patterns', 'get top eval error patterns',
    'analyze_error_patterns(task_ids=["task-1", "task-2"])'.

    RETURNS: JSON with status, total_patterns, patterns (list with
    pattern, count, task_ids), cache_path. Writes
    .cortex/.cache/evals/error_patterns.json for dashboards.

    Runs the same harness as run_tool_evaluation but focuses on
    aggregated error patterns. Project root is resolved internally.

    Args:
        task_ids: Optional list of task IDs to include; if None, all
            tasks are run and analyzed.
    """
    root = await resolve_project_root_async(None, ctx)
    if ctx is not None:
        await log_client(
            ctx, "info", "analyze_error_patterns: starting", logger_name=__name__
        )
    return await analyze_error_patterns_impl(root, task_ids)


async def get_session_tool_anomalies(
    hours: int = 24,
    ctx: MCPContext | None = None,
) -> str:
    """Session tool anomalies (pruned from MCP tool list). Use query_usage instead.

    Previously an MCP tool; pruned for tool-count reduction. Use
    query_usage(query_type="anomalies", hours=hours) for the same behavior.
    Kept as a callable for tests and any internal use.
    """
    from cortex.tools.usage.query_operations import query_usage

    return await query_usage(query_type="anomalies", hours=hours, ctx=ctx)


async def run_tool_optimization_workflow(
    task_ids: list[str] | None = None,
    optimized_analysis_json: str | None = None,
    ctx: MCPContext | None = None,
) -> str:
    """Evaluation baseline + A/B comparison (pruned from MCP tool list).

    Previously an MCP tool; pruned for tool-count reduction. For usage-based
    optimization use query_usage(query_type="unused") and
    query_usage(query_type="recommendations"). Kept as callable for tests
    and programmatic eval-baseline/A/B use.
    """
    from ._harness import ToolEvaluationHarness, load_eval_tasks
    from ._run_impl import get_usage_tracker

    root = await resolve_project_root_async(None, ctx)
    if ctx is not None:
        await log_client(
            ctx,
            "info",
            "run_tool_optimization_workflow: starting",
            logger_name=__name__,
        )
    tracker = await get_usage_tracker(root)
    tasks = await load_eval_tasks(root, task_ids)
    harness = ToolEvaluationHarness(project_root=root, tracker=tracker)
    suite = await harness.run_suite(tasks)
    baseline_analysis = harness.analyze_results(suite)
    run_id = f"run-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    generated_at = datetime.now(UTC).isoformat()
    optimized_analysis = parse_optimized_analysis(optimized_analysis_json)
    record = build_optimization_record(
        baseline_analysis, optimized_analysis, run_id, generated_at
    )
    await append_optimization_record(root, record)
    history = await load_optimization_history(root)
    return build_optimization_workflow_payload(
        root, run_id, baseline_analysis, record, history
    )


__all__ = [
    "ABComparisonResult",
    "AgenticScorecard",
    "AgenticSkipReason",
    "AgenticSummary",
    "AgenticSuiteOutcome",
    "AgenticTaskResult",
    "EvalTaskKind",
    "ToolFeedbackRecord",
    "UnpairedReason",
    "run_agentic_suite",
    "ABWinner",
    "EvalAnalysis",
    "EvalRunMode",
    "EvalSuiteResult",
    "EvalTask",
    "EvalTaskCategory",
    "EvalTaskResult",
    "EvalTaskStatus",
    "ErrorPattern",
    "ExecutionExpectSpec",
    "ExecutionExpectType",
    "ExecutionResultEntry",
    "ExecutionSpec",
    "ExecutionSummary",
    "OptimizationRunRecord",
    "OptimizationRunWinner",
    "RunToolEvaluationPayload",
    "ToolCombination",
    "ToolTaskMetrics",
    "ToolEvaluationHarness",
    "analyze_error_patterns",
    "append_optimization_record",
    "compare_ab_analyses",
    "get_session_tool_anomalies",
    "load_eval_tasks",
    "load_optimization_history",
    "run_full_evaluation_payload",
    "run_tool_evaluation",
    "run_tool_optimization_workflow",
]
