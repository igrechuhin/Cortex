"""Pre-commit checks pipeline.

Extracted from pre_commit_tools to keep that file under 400 lines.
"""

from collections.abc import Callable

from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.services.framework_adapters.selected_checks import selected_source_checks
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

    _run_standard_non_test_processors(
        adapter, language, checks_to_perform, strict_mode, results, stats, _tick
    )
    return completed


def _run_standard_non_test_processors(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    tick: Callable[[], None],
) -> None:
    process_fix_errors_check(adapter, checks_to_perform, strict_mode, results, stats)
    tick()
    process_quality_check(adapter, language, checks_to_perform, results, stats)
    tick()
    process_format_check(adapter, checks_to_perform, results, stats)
    tick()
    process_synapse_format_check(adapter, language, checks_to_perform, results, stats)
    tick()
    process_synapse_lint_check(adapter, language, checks_to_perform, results, stats)
    tick()
    process_script_based_checks(adapter, language, checks_to_perform, results, stats)
    tick()
    process_type_check(adapter, checks_to_perform, results, stats)
    tick()


def _run_tests_step(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    timeout: int | None,
    coverage_threshold: float,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    progress_callback: Callable[[int, int], None] | None,
    include_slow_tests: bool,
    test_filter: str | None = None,
) -> None:
    process_tests_check(
        adapter,
        checks_to_perform,
        timeout,
        coverage_threshold,
        results,
        stats,
        progress_callback,
        include_slow_tests,
        **({"test_filter": test_filter} if test_filter is not None else {}),
    )


# fmt: off
def run_checks_pipeline(adapter: FrameworkAdapter, language: str, checks_to_perform: list[PreCommitCheck], strict_mode: bool, timeout: int | None, coverage_threshold: float, progress_callback: Callable[[int, int], None] | None, results: dict[str, CheckResult | TestResult | QualityCheckResult], stats: CheckStats, include_slow_tests: bool = False, phase_callback: Callable[[int, int], None] | None = None, test_filter: str | None = None) -> None:
# fmt: on
    """Run all check processors in order."""
    _run_non_test_phase(
        adapter,
        language,
        checks_to_perform,
        strict_mode,
        results,
        stats,
        phase_callback,
        timeout=timeout,
        **({"test_filter": test_filter} if test_filter is not None else {}),
    )
    _run_tests_phase(
        adapter,
        checks_to_perform,
        timeout,
        coverage_threshold,
        results,
        stats,
        progress_callback,
        include_slow_tests,
        **({"test_filter": test_filter} if test_filter is not None else {}),
    )


def _run_non_test_phase(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    phase_callback: Callable[[int, int], None] | None,
    test_filter: str | None = None,
    timeout: int | None = None,
) -> None:
    if test_filter is not None:
        checks_to_perform = _run_selected_source_checks(
            adapter, checks_to_perform, results, stats, timeout
        )
    _ = _run_non_test_checks(
        adapter,
        language,
        checks_to_perform,
        strict_mode,
        results,
        stats,
        phase_callback=phase_callback,
        total_checks=8,
    )


def _run_selected_source_checks(
    adapter: FrameworkAdapter,
    checks: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    timeout: int | None = None,
) -> list[PreCommitCheck]:
    """Replace automatic source mutations with equivalent read-only validations."""
    replacements = (PreCommitCheck.FIX_ERRORS, PreCommitCheck.FORMAT)
    if any(check in checks for check in replacements):
        lint, formatting = selected_source_checks(adapter, timeout=timeout)
        for check, result in zip(replacements, (lint, formatting), strict=True):
            if check in checks:
                results[check.value] = result
                stats.checks_performed.append(check.value)
                stats.total_errors += len(result.errors)
                stats.total_warnings += len(result.warnings)
    return [check for check in checks if check not in replacements]


def _run_tests_phase(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    timeout: int | None,
    coverage_threshold: float,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    progress_callback: Callable[[int, int], None] | None,
    include_slow_tests: bool,
    test_filter: str | None = None,
) -> None:
    _run_tests_step(
        adapter,
        checks_to_perform,
        timeout,
        coverage_threshold,
        results,
        stats,
        progress_callback,
        include_slow_tests,
        **({"test_filter": test_filter} if test_filter is not None else {}),
    )
