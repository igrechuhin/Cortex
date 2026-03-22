"""Individual check processors for the pre-commit pipeline.

Extracted from pre_commit_pipeline to keep that file under 400 lines.
"""

from collections.abc import Callable
from pathlib import Path

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
from cortex.tools.execution.pre_commit_pipeline_quality import (
    execute_quality,
)
from cortex.tools.execution.pre_commit_synapse import run_synapse_script


def process_fix_errors_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    strict_mode: bool,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process fix_errors check if requested."""
    if PreCommitCheck.FIX_ERRORS in checks_to_perform:
        fix_result = _execute_fix_errors(adapter, strict_mode)
        results[PreCommitCheck.FIX_ERRORS.value] = fix_result
        stats.checks_performed.append(PreCommitCheck.FIX_ERRORS.value)
        stats.total_errors += len(fix_result.errors)
        stats.total_warnings += len(fix_result.warnings)
        stats.files_modified.extend(fix_result.files_modified)


def process_format_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process format check if requested."""
    if PreCommitCheck.FORMAT in checks_to_perform:
        format_result = adapter.format_code()
        results[PreCommitCheck.FORMAT.value] = format_result
        stats.checks_performed.append(PreCommitCheck.FORMAT.value)
        stats.total_errors += len(format_result.errors)
        stats.files_modified.extend(format_result.files_modified)


def process_synapse_format_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process synapse script formatting (matches CI Black check)."""
    if PreCommitCheck.SYNAPSE_FORMAT not in checks_to_perform:
        return
    project_root = Path(adapter.project_root)
    result = run_synapse_script(
        project_root,
        language,
        "check_formatting.py",
        PreCommitCheck.SYNAPSE_FORMAT.value,
    )
    results[PreCommitCheck.SYNAPSE_FORMAT.value] = result
    stats.checks_performed.append(PreCommitCheck.SYNAPSE_FORMAT.value)
    stats.total_errors += len(result.errors)


def process_synapse_lint_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process synapse script linting (matches CI Ruff check)."""
    if PreCommitCheck.SYNAPSE_LINT not in checks_to_perform:
        return
    project_root = Path(adapter.project_root)
    result = run_synapse_script(
        project_root,
        language,
        "check_linting.py",
        PreCommitCheck.SYNAPSE_LINT.value,
    )
    results[PreCommitCheck.SYNAPSE_LINT.value] = result
    stats.checks_performed.append(PreCommitCheck.SYNAPSE_LINT.value)
    stats.total_errors += len(result.errors)


def process_script_based_checks(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Run format_ci_parity, spelling, test_naming, check_async_tests."""
    process_format_ci_parity_check(adapter, language, checks_to_perform, results, stats)
    process_spelling_check(adapter, language, checks_to_perform, results, stats)
    process_test_naming_check(adapter, language, checks_to_perform, results, stats)
    process_async_tests_check(adapter, language, checks_to_perform, results, stats)


def process_format_ci_parity_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process format_ci_parity check (runs synapse script)."""
    if PreCommitCheck.FORMAT_CI_PARITY not in checks_to_perform:
        return
    project_root = Path(adapter.project_root)
    result = run_synapse_script(
        project_root,
        language,
        "check_formatting_ci_parity.py",
        PreCommitCheck.FORMAT_CI_PARITY.value,
    )
    results[PreCommitCheck.FORMAT_CI_PARITY.value] = result
    stats.checks_performed.append(PreCommitCheck.FORMAT_CI_PARITY.value)
    stats.total_errors += len(result.errors)


def process_spelling_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process spelling check (runs synapse script)."""
    if PreCommitCheck.SPELLING not in checks_to_perform:
        return
    project_root = Path(adapter.project_root)
    result = run_synapse_script(
        project_root,
        language,
        "check_spelling.py",
        PreCommitCheck.SPELLING.value,
    )
    results[PreCommitCheck.SPELLING.value] = result
    stats.checks_performed.append(PreCommitCheck.SPELLING.value)
    stats.total_errors += len(result.errors)


def process_test_naming_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process test_naming check (runs synapse script)."""
    if PreCommitCheck.TEST_NAMING not in checks_to_perform:
        return
    project_root = Path(adapter.project_root)
    result = run_synapse_script(
        project_root,
        language,
        "check_test_naming.py",
        PreCommitCheck.TEST_NAMING.value,
    )
    results[PreCommitCheck.TEST_NAMING.value] = result
    stats.checks_performed.append(PreCommitCheck.TEST_NAMING.value)
    stats.total_errors += len(result.errors)


def process_async_tests_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process check_async_tests (runs synapse script, before tests)."""
    if PreCommitCheck.CHECK_ASYNC_TESTS not in checks_to_perform:
        return
    project_root = Path(adapter.project_root)
    result = run_synapse_script(
        project_root,
        language,
        "check_async_tests.py",
        PreCommitCheck.CHECK_ASYNC_TESTS.value,
    )
    results[PreCommitCheck.CHECK_ASYNC_TESTS.value] = result
    stats.checks_performed.append(PreCommitCheck.CHECK_ASYNC_TESTS.value)
    stats.total_errors += len(result.errors)


def process_type_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process type_check check if requested."""
    if PreCommitCheck.TYPE_CHECK in checks_to_perform:
        type_result = adapter.type_check()
        results[PreCommitCheck.TYPE_CHECK.value] = type_result
        stats.checks_performed.append(PreCommitCheck.TYPE_CHECK.value)
        stats.total_errors += len(type_result.errors)


def process_quality_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process quality check if requested."""
    if PreCommitCheck.QUALITY in checks_to_perform:
        quality_result = execute_quality(adapter, language)
        results[PreCommitCheck.QUALITY.value] = quality_result
        stats.checks_performed.append(PreCommitCheck.QUALITY.value)
        stats.total_errors += len(quality_result.errors)


def process_tests_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    timeout: int | None,
    coverage_threshold: float,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    progress_callback: Callable[[int, int], None] | None = None,
    include_slow_tests: bool = False,
) -> None:
    """Process tests check if requested."""
    if PreCommitCheck.TESTS in checks_to_perform:
        test_result = _execute_tests(
            adapter,
            timeout,
            coverage_threshold,
            progress_callback,
            include_slow_tests,
        )
        results[PreCommitCheck.TESTS.value] = test_result
        stats.checks_performed.append(PreCommitCheck.TESTS.value)
        stats.total_warnings += len(test_result.warnings)
        if not test_result.success:
            stats.total_errors += len(test_result.errors)


def _execute_fix_errors(
    adapter: FrameworkAdapter,
    strict_mode: bool,
) -> CheckResult:
    """Execute fix_errors check."""
    return adapter.fix_errors(
        error_types=None,
        auto_fix=True,
        strict_mode=strict_mode,
    )


def _execute_tests(
    adapter: FrameworkAdapter,
    timeout: int | None,
    coverage_threshold: float,
    progress_callback: Callable[[int, int], None] | None = None,
    include_slow_tests: bool = False,
) -> TestResult:
    """Execute tests check. By default excludes slow tests for fast commit runs."""
    return adapter.run_tests(
        timeout=timeout,
        coverage_threshold=coverage_threshold,
        max_failures=None,
        progress_callback=progress_callback,
        include_slow_tests=include_slow_tests,
    )
