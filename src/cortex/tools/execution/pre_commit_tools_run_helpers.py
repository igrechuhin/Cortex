"""Run helpers for execute_pre_commit_checks (checks execution, response building).

Extracted to keep pre_commit_tools.py under 400 lines.
"""

import asyncio
from collections.abc import Callable
from typing import cast

from cortex.core.context_logging import MCPContext, report_progress_safe
from cortex.core.models import ModelDict, OperationStatus
from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.services.language_detector import LanguageInfo
from cortex.tools.execution.pre_commit_connection import (
    log_connection_health_after_tests,
    log_connection_health_before_tests,
    log_test_execution_error,
)
from cortex.tools.execution.pre_commit_eval import run_eval_fast_check
from cortex.tools.execution.pre_commit_helpers import ensure_json_serializable_for_mcp
from cortex.tools.execution.pre_commit_helpers_models import (
    CheckStats,
    PreCommitCheck,
    PreCommitResult,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_helpers_remaining import (
    truncate_large_logs_in_data,
)
from cortex.tools.execution.pre_commit_pipeline import run_checks_pipeline

_HEARTBEAT_INTERVAL_SECONDS = 10


def execute_all_checks(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    progress_callback: Callable[[int, int], None] | None = None,
    phase_callback: Callable[[int, int], None] | None = None,
) -> tuple[dict[str, CheckResult | TestResult | QualityCheckResult], CheckStats]:
    """Execute all requested checks (sync, runs off event loop via to_thread)."""
    results: dict[str, CheckResult | TestResult | QualityCheckResult] = {}
    stats = CheckStats(
        total_errors=0,
        total_warnings=0,
        files_modified=[],
        checks_performed=[],
    )
    run_checks_pipeline(
        adapter,
        language,
        checks_to_perform,
        strict_mode,
        timeout,
        coverage_threshold,
        progress_callback,
        results,
        stats,
        phase_callback=phase_callback,
    )
    return results, stats


def build_pre_commit_response(
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    detected_language: str,
) -> ModelDict:
    """Build response dict (FastMCP serializes to JSON)."""
    total_errors = stats.total_errors
    success = total_errors == 0
    response = PreCommitResult(
        status=OperationStatus.SUCCESS if success else OperationStatus.ERROR,
        language=detected_language,
        checks_performed=stats.checks_performed,
        results=results,
        total_errors=total_errors,
        total_warnings=stats.total_warnings,
        files_modified=list(set(stats.files_modified)),
        success=success,
    )
    data = response.model_dump(mode="json")
    compact = truncate_large_logs_in_data(data)
    return ensure_json_serializable_for_mcp(cast(ModelDict, compact))


def make_phase_progress_callback(
    ctx: MCPContext | None, loop: asyncio.AbstractEventLoop
) -> Callable[[int, int], None] | None:
    """Build (completed_checks, total_checks) callback for per-check heartbeats.

    Keeps the MCP connection alive by sending progress after each non-test
    check completes, preventing Cursor from recreating the client during
    long-running pipelines.
    """
    if ctx is None:
        return None

    def report(completed: int, total: int) -> None:
        _ = asyncio.run_coroutine_threadsafe(
            report_progress_safe(ctx, float(completed), float(total)), loop
        )

    return report


def make_test_progress_callback(
    ctx: MCPContext | None, loop: asyncio.AbstractEventLoop
) -> Callable[[int, int], None] | None:
    """Build (completed, total) callback that reports test counts to MCP.

    This uses completed/total tests directly so that all progress
    notifications for execute_pre_commit_checks use a single, consistent
    scheme: number of tests completed out of total tests.
    """
    if ctx is None:
        return None

    def report(completed: int, total: int) -> None:
        _ = asyncio.run_coroutine_threadsafe(
            report_progress_safe(ctx, float(completed), float(total)), loop
        )

    return report


def _callbacks_for_ctx(
    ctx: MCPContext,
    loop: asyncio.AbstractEventLoop,
    checks_to_perform: list[PreCommitCheck],
    language: str,
) -> tuple[
    Callable[[int, int], None] | None,
    Callable[[int, int], None] | None,
]:
    """Build phase and optional test progress callbacks when ctx is set."""
    phase_cb = make_phase_progress_callback(ctx, loop)
    progress_callback = None
    if PreCommitCheck.TESTS in checks_to_perform and language == "python":
        progress_callback = make_test_progress_callback(ctx, loop)
    return phase_cb, progress_callback


async def _heartbeat_loop(ctx: MCPContext, interval: float) -> None:
    """Send periodic progress heartbeats to keep MCP connection alive.

    Runs as a background task alongside the pipeline. Uses a fixed
    total of 500 and increments progress each tick so Cursor sees
    continuous activity even during long subprocess calls (pytest
    collection, typecheck, etc.).
    """
    tick = 0
    total = 500
    while True:
        await asyncio.sleep(interval)
        tick = min(tick + 1, total)
        await report_progress_safe(ctx, float(tick), float(total))


def _setup_heartbeat_and_callbacks(
    ctx: MCPContext | None,
    checks_to_perform: list[PreCommitCheck],
    language: str,
) -> tuple[
    Callable[[int, int], None] | None,
    Callable[[int, int], None] | None,
    asyncio.Task[None] | None,
]:
    """Build progress/phase callbacks and start heartbeat task when ctx is set."""
    if ctx is None:
        return None, None, None
    loop = asyncio.get_running_loop()
    phase_cb, progress_callback = _callbacks_for_ctx(
        ctx, loop, checks_to_perform, language
    )
    heartbeat = asyncio.create_task(_heartbeat_loop(ctx, _HEARTBEAT_INTERVAL_SECONDS))
    return progress_callback, phase_cb, heartbeat


async def run_all_checks_off_loop(
    adapter: FrameworkAdapter,
    language_info: LanguageInfo,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> tuple[dict[str, CheckResult | TestResult | QualityCheckResult], CheckStats]:
    """Run checks off event loop with heartbeat and progress callbacks."""
    progress_callback, phase_cb, heartbeat = _setup_heartbeat_and_callbacks(
        ctx, checks_to_perform, language_info.language
    )
    try:
        results, stats = await asyncio.to_thread(
            execute_all_checks,
            adapter,
            language_info.language,
            checks_to_perform,
            strict_mode,
            timeout,
            coverage_threshold,
            progress_callback,
            phase_cb,
        )
    finally:
        if heartbeat is not None:
            _ = heartbeat.cancel()
    await merge_eval_fast_if_requested(checks_to_perform, results, stats, ctx)
    return results, stats


async def merge_eval_fast_if_requested(
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    ctx: MCPContext | None,
) -> None:
    """If eval_fast requested, run it and merge into results/stats."""
    if PreCommitCheck.EVAL_FAST not in checks_to_perform:
        return
    eval_result = await run_eval_fast_check(ctx)
    results[PreCommitCheck.EVAL_FAST.value] = eval_result
    stats.checks_performed.append(PreCommitCheck.EVAL_FAST.value)
    if not eval_result.success:
        stats.total_errors += len(eval_result.errors)


async def run_checks_with_connection_monitoring(
    adapter: FrameworkAdapter,
    language_info: LanguageInfo,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    ctx: MCPContext | None,
) -> tuple[dict[str, CheckResult | TestResult | QualityCheckResult], CheckStats]:
    """Run checks with connection stability monitoring for tests."""
    health_before = (
        await log_connection_health_before_tests()
        if PreCommitCheck.TESTS in checks_to_perform
        else None
    )
    try:
        return await run_all_checks_off_loop(
            adapter,
            language_info,
            checks_to_perform,
            strict_mode,
            timeout,
            coverage_threshold,
            ctx,
        )
    except Exception as e:
        if PreCommitCheck.TESTS in checks_to_perform:
            log_test_execution_error(e, health_before)
        raise
    finally:
        if PreCommitCheck.TESTS in checks_to_perform:
            await log_connection_health_after_tests(health_before)
