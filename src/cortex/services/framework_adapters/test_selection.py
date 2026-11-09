"""Validation and result handling shared by explicitly selected test runs."""

import re

from .base import TestResult
from .python_adapter_parsing import extract_failed_test_lines, parse_test_counts
from .swift_test_diagnostics import SwiftTestOutcome, SwiftTestStatus


def validate_test_filter(test_filter: object) -> None:
    """Reject empty selections and control characters before subprocess execution."""
    if not isinstance(test_filter, str) or not test_filter.strip():
        raise ValueError("test_filter must be a non-empty string")
    if len(test_filter) > 4096 or any(
        ord(char) < 32 or ord(char) == 127 for char in test_filter
    ):
        raise ValueError("test_filter must be at most 4096 characters without controls")


def selected_test_result(result: TestResult) -> TestResult:
    """Never describe subset coverage as a project-wide coverage verdict."""
    result.coverage = None
    result.coverage_gaps = []
    result.uncovered_files = []
    if result.tests_run == 0:
        result.success = False
        result.errors.append("test_filter selected no runnable tests")
    return result


def selected_pytest_command(command: list[str], test_filter: str) -> list[str]:
    """Replace global coverage flags with one explicit pytest selection."""
    validate_test_filter(test_filter)
    return [arg for arg in command if not arg.startswith("--cov")] + [
        "--no-cov",
        "-k",
        test_filter,
    ]


def validate_swift_test_filter(test_filter: str, is_package: bool) -> None:
    """Reject invalid expressions or unsupported Swift execution modes."""
    validate_test_filter(test_filter)
    try:
        _ = re.compile(test_filter)
    except re.error as exc:
        raise ValueError(
            f"Invalid Swift test_filter regular expression: {exc}"
        ) from exc
    if not is_package:
        raise ValueError("test_filter is supported only for Swift Package Manager")


def swift_test_arguments(test_filter: str | None) -> list[str]:
    """Keep full-suite coverage separate from selected-test execution."""
    if test_filter is not None:
        return ["test", "--no-parallel", "--filter", test_filter]
    return ["test", "--enable-code-coverage", "--no-parallel"]


def selected_swift_result(
    output: str, outcome: SwiftTestOutcome, counts: tuple[int, int]
) -> TestResult:
    """Classify a Swift selection without consulting global coverage files."""
    passed, failed = counts
    success = outcome.status == SwiftTestStatus.PASSED and failed == 0
    total = passed + failed
    return selected_test_result(
        TestResult(
            success=success,
            tests_run=total,
            tests_passed=passed,
            tests_failed=failed,
            pass_rate=passed / total if total else 0.0,
            coverage=None,
            output=output,
            errors=[] if success else [outcome.diagnostic],
        )
    )


def selected_pytest_result(output: str, returncode: int) -> TestResult:
    """Parse subset execution independently of the global coverage contract."""
    passed, failed, skipped = parse_test_counts(output)
    total = passed + failed
    errors = extract_failed_test_lines(output)
    if returncode != 0:
        errors.append(f"Selected pytest run exited {returncode}")
    return selected_test_result(
        TestResult(
            success=returncode == 0 and failed == 0 and total > 0,
            tests_run=total,
            tests_passed=passed,
            tests_failed=failed,
            skipped_tests=skipped,
            pass_rate=passed / total if total else 0.0,
            coverage=None,
            output=output,
            errors=errors,
        )
    )
