"""Pre-commit checks pipeline.

Extracted from pre_commit_tools to keep that file under 400 lines.
"""

from collections.abc import Callable

from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.tools.execution.pre_commit_helpers_models import (
    CheckStats,
    PreCommitCheck,
    QualityCheckResult,
)
from cortex.tools.execution.pre_commit_pipeline_processors import (
    process_fix_errors_check,
    process_format_check,
    process_quality_check,
    process_script_based_checks,
    process_synapse_format_check,
    process_synapse_lint_check,
    process_tests_check,
    process_type_check,
)


def _run_non_test_checks(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    phase_callback: Callable[[int, int], None] | None = None,
    total_checks: int = 0,
) -> int:
    """Run fix_errors, quality, format, synapse scripts, script-based, and type checks.

    Returns the number of non-test checks completed (for progress tracking).
    """
    completed = 0

    def _tick() -> None:
        nonlocal completed
        completed += 1
        if phase_callback is not None and total_checks > 0:
            phase_callback(completed, total_checks)

    process_fix_errors_check(adapter, checks_to_perform, strict_mode, results, stats)
    _tick()
    process_quality_check(adapter, language, checks_to_perform, results, stats)
    _tick()
    process_format_check(adapter, checks_to_perform, results, stats)
    _tick()
    process_synapse_format_check(adapter, language, checks_to_perform, results, stats)
    _tick()
    process_synapse_lint_check(adapter, language, checks_to_perform, results, stats)
    _tick()
    process_script_based_checks(
        adapter,
        language,
        checks_to_perform,
        results,
        stats,
    )
    _tick()
    process_type_check(adapter, checks_to_perform, results, stats)
    _tick()
    return completed


def run_checks_pipeline(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    timeout: int | None,
    coverage_threshold: float,
    progress_callback: Callable[[int, int], None] | None,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    include_slow_tests: bool = False,
    phase_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Run all check processors in order (mutates results and stats).

    Args:
        phase_callback: Optional (completed, total) callback fired after each
            non-test check completes, used as a heartbeat to keep the MCP
            connection alive during long-running pipelines.
    """
    # 7 non-test processor slots + 1 for tests = total_checks
    total_checks = 8
    _ = _run_non_test_checks(
        adapter,
        language,
        checks_to_perform,
        strict_mode,
        results,
        stats,
        phase_callback=phase_callback,
        total_checks=total_checks,
    )
    process_tests_check(
        adapter,
        checks_to_perform,
        timeout,
        coverage_threshold,
        results,
        stats,
        progress_callback,
        include_slow_tests,
    )
