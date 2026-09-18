"""Run helpers for pre-commit check execution (checks execution, response building).

Extracted from the retired pre_commit_tools.py to keep call sites within file-size limits.
"""

import asyncio
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import cast

from cortex.core.context_logging import (
    LogLevel,
    MCPContext,
    log_client,
)
from cortex.core.models import ModelDict, OperationStatus
from cortex.core.progress_types import (
    QualityGateProgress,
    report_structured_progress,
)
from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
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

_HEARTBEAT_MAX_DOTS = 500


async def _async_sleep(seconds: float) -> None:
    """Delegate to ``asyncio.sleep`` (separate symbol for tests to monkeypatch)."""
    await asyncio.sleep(seconds)


def _run_coroutine_threadsafe(
    coro: Coroutine[object, object, object],
    loop: asyncio.AbstractEventLoop,
) -> Future[object]:
    """Delegate to asyncio.run_coroutine_threadsafe for test monkeypatching."""
    return asyncio.run_coroutine_threadsafe(coro, loop)


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
    check completes, preventing some MCP clients from recreating the client during
    long-running pipelines.
    """
    if ctx is None:
        return None

    def report(completed: int, total: int) -> None:
        progress = QualityGateProgress(
            tool="quality_gate",
            phase="quality_gate",
            message=f"Completed check {completed}/{total}",
            checks_completed=completed,
            checks_total=total,
            current_check="non_test_checks",
        )
        _ = _run_coroutine_threadsafe(
            report_structured_progress(ctx, progress, completed, total),
            loop,
        )

    return report


async def heartbeat_loop(ctx: MCPContext, interval: float) -> None:
    """Send periodic log heartbeats to keep MCP connection alive.

    Each tick sends one additional dot via ctx.log (debug level) so liveness
    is visible as plain text without numeric progress fields.
    """
    dot_count = 0
    while True:
        await _async_sleep(interval)
        dot_count = min(dot_count + 1, _HEARTBEAT_MAX_DOTS)
        await log_client(ctx, LogLevel.DEBUG, "." * dot_count)
