"""Pre-commit checks pipeline.

Extracted from pre_commit_tools to keep that file under 400 lines.
"""

from collections.abc import Callable

from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.tools.pre_commit_helpers_models import (
    CheckStats,
    PreCommitCheck,
    QualityCheckResult,
)
from cortex.tools.pre_commit_pipeline_processors import (
    process_fix_errors_check,
    process_format_check,
    process_quality_check,
    process_script_based_checks,
    process_synapse_format_check,
    process_synapse_lint_check,
    process_tests_check,
    process_type_check,
)
from cortex.tools.pre_commit_pipeline_quality import check_function_lengths

# Re-export for tests (reportPrivateUsage)
_check_function_lengths = check_function_lengths


def _run_non_test_checks(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Run fix_errors, quality, format, synapse scripts, script-based, and type checks."""
    process_fix_errors_check(adapter, checks_to_perform, strict_mode, results, stats)
    process_quality_check(adapter, language, checks_to_perform, results, stats)
    process_format_check(adapter, checks_to_perform, results, stats)
    process_synapse_format_check(adapter, language, checks_to_perform, results, stats)
    process_synapse_lint_check(adapter, language, checks_to_perform, results, stats)
    process_script_based_checks(
        adapter,
        language,
        checks_to_perform,
        results,
        stats,
    )
    process_type_check(adapter, checks_to_perform, results, stats)


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
) -> None:
    """Run all check processors in order (mutates results and stats)."""
    _run_non_test_checks(
        adapter, language, checks_to_perform, strict_mode, results, stats
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
