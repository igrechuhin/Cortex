"""Tests for Python adapter parsing helpers."""

from typing import cast

from cortex.services.framework_adapters.python_adapter_parsing import (
    build_test_errors,
    parse_coverage,
    parse_lint_errors,
    parse_pytest_output,
    parse_test_counts,
)


class TestParseLintErrors:
    """Tests for parse_lint_errors."""

    def test_ignores_ruff_summary_lines(self) -> None:
        """Ensure ruff summary lines don't count as remaining errors."""
        output = "Found 5 errors (5 fixed, 0 remaining).\n"
        errors = parse_lint_errors(output)
        assert errors == []

    def test_collects_diagnostic_lines(self) -> None:
        """Ensure ruff diagnostic lines are captured."""
        output = "\n".join(
            [
                "src/foo.py:1:1: F401 `os` imported but unused",
                "Found 1 error (1 fixed, 0 remaining).",
            ]
        )
        errors = parse_lint_errors(output)
        assert errors == ["src/foo.py:1:1: F401 `os` imported but unused"]


class TestBuildTestErrors:
    """Tests for build_test_errors."""

    def test_success(self) -> None:
        """Test build_test_errors with success=True."""
        errors = build_test_errors(success=True)
        assert errors == []

    def test_failure_no_coverage(self) -> None:
        """Test build_test_errors with success=False and no coverage."""
        errors = build_test_errors(success=False, coverage=None)
        assert errors == ["Test execution failed"]

    def test_failure_low_coverage(self) -> None:
        """Test build_test_errors with success=False and coverage below threshold."""
        errors = build_test_errors(
            success=False, coverage=0.85, coverage_threshold=0.90
        )
        assert len(errors) == 1
        assert "Test coverage 85.00% is below required threshold 90%" in errors[0]

    def test_failure_coverage_above_threshold(self) -> None:
        """Test build_test_errors with success=False but coverage above threshold."""
        errors = build_test_errors(
            success=False, coverage=0.95, coverage_threshold=0.90
        )
        assert errors == ["Test execution failed"]


class TestParseCoverage:
    """Tests for parse_coverage."""

    def test_total_coverage_format(self) -> None:
        """parse_coverage parses 'Total coverage: XX.XX%' format."""
        output = "Required test coverage of 95% reached. Total coverage: 91.23%"
        coverage = parse_coverage(output)
        assert coverage is not None
        assert abs(coverage - 0.9123) < 0.0001 if coverage else False

    def test_returns_none_when_no_match(self) -> None:
        """parse_coverage returns None when no percentage found."""
        assert parse_coverage("no coverage here") is None


class TestParseTestCounts:
    """Tests for parse_test_counts."""

    def test_uses_only_pytest_summary_line_with_timing(self) -> None:
        """parse_test_counts uses only lines with ' in '; skipped is not failed."""
        summary = (
            "=========== 3698 passed, 2 skipped, 20 warnings in 57.17s ============"
        )
        passed, failed = parse_test_counts(summary)
        assert passed == 3698
        assert failed == 0

    def test_ignores_stray_failed_line_without_timing(self) -> None:
        """parse_test_counts ignores lines with '2 failed' that lack timing."""
        output = (
            "Some assertion message: 2 failed\n"
            "=========== 3698 passed, 2 skipped, 20 warnings in 57.17s ============"
        )
        passed, failed = parse_test_counts(output)
        assert passed == 3698
        assert failed == 0


class TestParsePytestOutput:
    """Tests for parse_pytest_output."""

    def test_includes_failed_test_identifier(self) -> None:
        """parse_pytest_output surfaces FAILED summary line in errors."""
        from cortex.services.framework_adapters.base import TestResult

        output = "\n".join(
            [
                "============================= test session starts ==============================",
                "platform darwin -- Python 3.13.7, pytest-9.0.2",
                "FAILED tests/unit/test_foo.py::TestFoo::test_bar - AssertionError: boom",
                "1 failed, 0 passed in 1.23s",
                "TOTAL 95%",
            ]
        )
        result: TestResult = parse_pytest_output(
            output, success=False, coverage_threshold=0.90
        )
        errors = cast(list[str], result["errors"])
        assert any("tests/unit/test_foo.py::TestFoo::test_bar" in e for e in errors)

    def test_coverage_89_5_accepted_with_warning(self) -> None:
        """parse_pytest_output accepts 89.5%+ with warning and success=True."""
        from cortex.services.framework_adapters.base import TestResult

        output = (
            "=========== 10 passed in 1.00s ============\n"
            "Required test coverage of 90% reached. Total coverage: 89.50%"
        )
        result: TestResult = parse_pytest_output(
            output, success=True, coverage_threshold=0.90
        )
        assert result["success"] is True
        assert result["coverage"] is not None
        cov = cast(float, result["coverage"])
        assert cov < 0.90
        assert any("89.50" in w and "90%" in w for w in result.warnings)

    def test_zero_tests_run(self) -> None:
        """parse_pytest_output sets pass_rate 0 when tests_run is 0."""
        from cortex.services.framework_adapters.base import TestResult

        result: TestResult = parse_pytest_output(
            "no summary line", success=False, coverage_threshold=0.90
        )
        assert result["tests_run"] == 0
        assert result["pass_rate"] == 0.0
