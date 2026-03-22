"""Tests for Python adapter parsing helpers."""

import logging
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from cortex.services.framework_adapters.python_adapter_parsing import (
    build_test_errors,
    merge_skip_trend_warnings,
    parse_coverage,
    parse_lint_errors,
    parse_pytest_output,
    parse_test_counts,
    parse_type_errors,
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


class TestParseTypeErrors:
    """Tests for parse_type_errors."""

    def test_captures_pyright_error_line(self) -> None:
        """Canonical pyright error line is captured."""
        line = (
            "src/foo.py:10:5 - error: Name 'x' is not defined "
            "(reportUndefinedVariable)"
        )
        assert parse_type_errors(line) == [line]

    def test_ignores_warning_lines(self) -> None:
        """Warning diagnostics are not treated as errors."""
        line = "src/foo.py:10:5 - warning: something"
        assert parse_type_errors(line) == []

    def test_ignores_summary_line(self) -> None:
        """Pyright summary lines do not match the diagnostic pattern."""
        assert parse_type_errors("0 errors, 0 warnings") == []

    def test_ignores_empty_input(self) -> None:
        assert parse_type_errors("") == []

    def test_multiple_errors(self) -> None:
        """Only error-shaped lines are returned when mixed with warnings."""
        output = "\n".join(
            [
                "src/a.py:1:1 - error: first (reportX)",
                "src/b.py:2:2 - error: second (reportY)",
                "src/c.py:3:3 - warning: skip me",
            ]
        )
        assert parse_type_errors(output) == [
            "src/a.py:1:1 - error: first (reportX)",
            "src/b.py:2:2 - error: second (reportY)",
        ]

    def test_does_not_capture_informational_lines(self) -> None:
        """Version header lines are ignored."""
        assert parse_type_errors("Pyright (1.1.400)") == []

    def test_error_in_string_literal_context(self) -> None:
        """Lines with 'error' only in a code snippet lack the pyright shape."""
        line = '  print("error")'
        assert parse_type_errors(line) == []

    def test_captures_leading_whitespace_pyright_line(self) -> None:
        """Indented pyright output still matches path:line:col - error:."""
        line = (
            "  /path/to/file.py:1:1 - error: Import could not be resolved "
            "(reportMissingModuleSource)"
        )
        assert parse_type_errors(line) == [line.strip()]


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
        passed, failed, skipped = parse_test_counts(summary)
        assert passed == 3698
        assert failed == 0
        assert skipped == 2

    def test_ignores_stray_failed_line_without_timing(self) -> None:
        """parse_test_counts ignores lines with '2 failed' that lack timing."""
        output = (
            "Some assertion message: 2 failed\n"
            "=========== 3698 passed, 2 skipped, 20 warnings in 57.17s ============"
        )
        passed, failed, skipped = parse_test_counts(output)
        assert passed == 3698
        assert failed == 0
        assert skipped == 2


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
        assert result["skipped_tests"] == 0

    def test_skipped_tests_parsed(self) -> None:
        """parse_pytest_output records skipped_tests from summary line."""
        from cortex.services.framework_adapters.base import TestResult

        output = (
            "=========== 10 passed, 3 skipped, 1 warning in 1.00s ============\n"
            "Required test coverage of 90% reached. Total coverage: 92.00%"
        )
        result: TestResult = parse_pytest_output(
            output, success=True, coverage_threshold=0.90
        )
        assert result["skipped_tests"] == 3
        assert result["success"] is True


class TestMergeSkipTrendWarnings:
    """Tests for merge_skip_trend_warnings."""

    def test_warns_when_skip_count_increases(self, tmp_path: Path) -> None:
        """Emits warning when new skipped count exceeds cached value."""
        root = tmp_path / "proj"
        cache = root / ".cortex" / ".cache" / "last_pytest_skipped_count.json"
        cache.parent.mkdir(parents=True)
        _ = cache.write_text('{"skipped_tests": 2}\n', encoding="utf-8")
        w = merge_skip_trend_warnings(5, root, [])
        assert len(w) == 1
        assert "increased from 2 to 5" in w[0]

    def test_no_warning_on_first_or_equal_run(self, tmp_path: Path) -> None:
        """No warning when cache missing or count did not increase."""
        root = tmp_path / "proj2"
        assert merge_skip_trend_warnings(3, root, ["keep"]) == ["keep"]
        w2 = merge_skip_trend_warnings(3, root, [])
        assert w2 == []


class TestPersistSkippedCountCache:
    """Tests for skip-count cache persistence (via merge_skip_trend_warnings)."""

    def test_cache_write_failure_logs_debug(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """OSError on cache write emits debug log with cache path."""
        root = tmp_path / "proj"
        cache_path = root / ".cortex" / ".cache" / "last_pytest_skipped_count.json"
        with caplog.at_level(logging.DEBUG):
            with patch.object(Path, "write_text", side_effect=OSError("eperm")):
                _ = merge_skip_trend_warnings(2, root, [])
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "Cache write failed" in joined
        assert str(cache_path) in joined

    def test_cache_write_failure_does_not_raise(self, tmp_path: Path) -> None:
        """Cache write failure is swallowed; caller does not see OSError."""
        root = tmp_path / "proj2"
        with patch.object(Path, "write_text", side_effect=OSError("eperm")):
            out = merge_skip_trend_warnings(2, root, [])
        assert out == []
