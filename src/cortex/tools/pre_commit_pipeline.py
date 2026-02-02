"""Pre-commit checks pipeline.

Extracted from pre_commit_tools to keep that file under 400 lines.
"""

from collections.abc import Callable
from pathlib import Path

from cortex.core.constants import MAX_FILE_LINES, MAX_FUNCTION_LINES
from cortex.services.framework_adapters.base import (
    CheckResult,
    FrameworkAdapter,
    TestResult,
)
from cortex.tools.pre_commit_helpers import (
    CheckStats,
    FileSizeViolation,
    FunctionLengthViolation,
    PreCommitCheck,
    QualityCheckResult,
    check_file_sizes,
    check_function_lengths_in_file,
)
from cortex.tools.pre_commit_synapse import run_synapse_script


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
) -> None:
    """Run all check processors in order (mutates results and stats)."""
    _process_fix_errors_check(adapter, checks_to_perform, strict_mode, results, stats)
    _process_quality_check(adapter, language, checks_to_perform, results, stats)
    _process_format_check(adapter, checks_to_perform, results, stats)
    _process_format_ci_parity_check(
        adapter, language, checks_to_perform, results, stats
    )
    _process_type_check(adapter, checks_to_perform, results, stats)
    _process_test_naming_check(adapter, language, checks_to_perform, results, stats)
    _process_tests_check(
        adapter,
        checks_to_perform,
        timeout,
        coverage_threshold,
        results,
        stats,
        progress_callback,
    )


def _process_fix_errors_check(
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


def _process_format_check(
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


def _process_format_ci_parity_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process format_ci_parity check if requested (runs synapse script)."""
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


def _process_test_naming_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process test_naming check if requested (runs synapse script)."""
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


def _process_type_check(
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


def _process_quality_check(
    adapter: FrameworkAdapter,
    language: str,
    checks_to_perform: list[PreCommitCheck],
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
) -> None:
    """Process quality check if requested."""
    if PreCommitCheck.QUALITY in checks_to_perform:
        quality_result = _execute_quality(adapter, language)
        results[PreCommitCheck.QUALITY.value] = quality_result
        stats.checks_performed.append(PreCommitCheck.QUALITY.value)
        stats.total_errors += len(quality_result.errors)


def _process_tests_check(
    adapter: FrameworkAdapter,
    checks_to_perform: list[PreCommitCheck],
    timeout: int | None,
    coverage_threshold: float,
    results: dict[str, CheckResult | TestResult | QualityCheckResult],
    stats: CheckStats,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Process tests check if requested."""
    if PreCommitCheck.TESTS in checks_to_perform:
        test_result = _execute_tests(
            adapter, timeout, coverage_threshold, progress_callback
        )
        results[PreCommitCheck.TESTS.value] = test_result
        stats.checks_performed.append(PreCommitCheck.TESTS.value)
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


def _check_function_lengths(project_root: Path) -> list[FunctionLengthViolation]:
    """Check all Python files for function length violations."""
    violations: list[FunctionLengthViolation] = []
    src_dir = project_root / "src"

    if not src_dir.exists():
        return violations

    for py_file in src_dir.glob("**/*.py"):
        if "__pycache__" in str(py_file) or py_file.name.startswith("test_"):
            continue
        file_violations = check_function_lengths_in_file(py_file)
        for func_name, logical_lines, start_line in file_violations:
            try:
                relative_path = str(py_file.relative_to(project_root))
            except ValueError:
                relative_path = str(py_file)
            violations.append(
                FunctionLengthViolation(
                    file=relative_path,
                    function=func_name,
                    line=start_line,
                    lines=logical_lines,
                    max_lines=MAX_FUNCTION_LINES,
                    excess=logical_lines - MAX_FUNCTION_LINES,
                )
            )

    return violations


def _build_quality_errors(
    lint_errors: list[str],
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
) -> list[str]:
    """Build error messages for quality check."""
    errors = list(lint_errors)
    for v in file_violations:
        msg = f"File size violation: {v.file} has {v.lines} lines "
        msg += f"(max: {v.max_lines}, excess: {v.excess})"
        errors.append(msg)
    for v in func_violations:
        msg = f"Function length violation: {v.file}:{v.function}() at line "
        msg += f"{v.line} has {v.lines} lines "
        msg += f"(max: {v.max_lines}, excess: {v.excess})"
        errors.append(msg)
    return errors


def _build_quality_output(
    lint_output: str,
    file_violations: list[FileSizeViolation],
    func_violations: list[FunctionLengthViolation],
) -> str:
    """Build output message for quality check."""
    parts = [lint_output]
    if file_violations:
        parts.append(
            f"\nFile size violations: {len(file_violations)} file(s) "
            + f"exceed {MAX_FILE_LINES} lines"
        )
    if func_violations:
        parts.append(
            f"\nFunction length violations: {len(func_violations)} "
            + f"function(s) exceed {MAX_FUNCTION_LINES} lines"
        )
    return "\n".join(parts)


def _execute_quality(adapter: FrameworkAdapter, language: str) -> QualityCheckResult:
    """Execute quality check: linting; for Python only, file sizes and function lengths."""
    lint_result = adapter.lint_code()
    project_root = adapter.project_root
    file_violations: list[FileSizeViolation] = []
    func_violations: list[FunctionLengthViolation] = []
    if language == "python":
        file_violations = check_file_sizes(project_root)
        func_violations = _check_function_lengths(project_root)

    errors = _build_quality_errors(lint_result.errors, file_violations, func_violations)
    output = _build_quality_output(lint_result.output, file_violations, func_violations)
    success = (
        lint_result.success and len(file_violations) == 0 and len(func_violations) == 0
    )

    return QualityCheckResult(
        check_type="quality",
        success=success,
        output=output,
        errors=errors,
        warnings=list(lint_result.warnings),
        files_modified=list(lint_result.files_modified),
        file_size_violations=file_violations,
        function_length_violations=func_violations,
    )


def _execute_tests(
    adapter: FrameworkAdapter,
    timeout: int | None,
    coverage_threshold: float,
    progress_callback: Callable[[int, int], None] | None = None,
) -> TestResult:
    """Execute tests check."""
    return adapter.run_tests(
        timeout=timeout,
        coverage_threshold=coverage_threshold,
        max_failures=None,
        progress_callback=progress_callback,
    )
