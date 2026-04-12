"""
Phase 57: Run implementation and cache/persist helpers.

Extracted for Phase 9.1.4 file size compliance.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from cortex.core.cache_json_access import write_cache_json
from cortex.core.models._enums import OperationStatus
from cortex.core.path_resolver import CortexResourceType, get_cache_path
from cortex.managers.usage_tracker import UsageTracker
from cortex.tools.usage import usage_analytics

from ._harness import ToolEvaluationHarness, load_eval_tasks
from ._models import (
    EvalAnalysis,
    EvalRunMode,
    EvalSuiteResult,
    EvalTask,
    RunToolEvaluationPayload,
)

logger = logging.getLogger(__name__)


async def get_usage_tracker(root: Path) -> UsageTracker | None:
    """Resolve UsageTracker via existing usage_analytics helper."""
    return await usage_analytics.get_usage_tracker(root)


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


async def _write_evaluation_dashboard(
    root: Path,
    analysis: EvalAnalysis,
    suite: EvalSuiteResult,
    tracker: UsageTracker | None,
) -> Path:
    """Write evaluation dashboard Markdown next to last_suite.json."""
    from cortex.tools.evaluation.evaluation_dashboard_helpers import (
        generate_evaluation_dashboard,
    )
    from cortex.tools.usage.redundancy_helpers import (
        RedundancyPayload,
        get_redundancy_payload,
    )

    redundancy: RedundancyPayload | None = None
    if tracker is not None:
        try:
            redundancy = await get_redundancy_payload(root, tracker, days=30)
        except Exception as e:
            logger.debug(
                "_write_evaluation_dashboard: get_redundancy_payload failed: %s", e
            )
    dashboard_content = generate_evaluation_dashboard(
        analysis, suite, redundancy=redundancy
    )
    cache_dir = get_cache_path(root, CortexResourceType.CACHE.value)
    dashboard_path = cache_dir / "evals" / "dashboard.md"
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    _ = dashboard_path.write_text(dashboard_content, encoding="utf-8")
    return dashboard_path


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


async def persist_error_patterns(root: Path, analysis: EvalAnalysis) -> None:
    """Persist top error patterns to evals/error_patterns.json (package-internal)."""
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


async def analyze_error_patterns_impl(root: Path, task_ids: list[str] | None) -> str:
    """Run harness, persist error patterns, return JSON payload (package-internal)."""
    from cortex.core.path_resolver import get_cache_path

    tracker = await get_usage_tracker(root)
    tasks = await load_eval_tasks(root, task_ids)
    harness = ToolEvaluationHarness(project_root=root, tracker=tracker)
    suite = await harness.run_suite(tasks)
    analysis = harness.analyze_results(suite)
    await persist_error_patterns(root, analysis)
    cache_path = get_cache_path(root, "evals") / "error_patterns.json"
    payload = {
        "status": OperationStatus.SUCCESS.value,
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


async def run_tool_evaluation_impl(
    root: Path,
    task_ids: list[str] | None,
    mode: EvalRunMode,
    category: str | None,
) -> str:
    """Run evaluation suite and execution harness; return JSON payload."""
    from cortex.tools.evaluation.evaluation_execution import (
        build_execution_summary,
        run_execution_suite,
    )

    tracker = await get_usage_tracker(root)
    tasks = await load_eval_tasks(root, task_ids)
    harness = ToolEvaluationHarness(project_root=root, tracker=tracker)
    suite = await harness.run_suite(tasks)
    analysis = harness.analyze_results(suite)
    exec_results = await run_execution_suite(
        tasks, mode=mode, category=category, fast_cap=10
    )
    execution_summary = build_execution_summary(exec_results)
    await _persist_latest_suite(root, suite, analysis)
    dashboard_path = await _write_evaluation_dashboard(root, analysis, suite, tracker)
    payload = _build_evaluation_payload(root, tasks, suite, analysis)
    payload = payload.model_copy(
        update={
            "dashboard_path": str(dashboard_path.relative_to(root)),
            "execution_summary": execution_summary,
        }
    )
    return json.dumps(payload.model_dump(mode="json"), indent=2)
