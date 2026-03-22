"""Parsing helpers for Python framework adapter.

Pure functions for parsing pytest, coverage, type-check, and lint output.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

from cortex.services.framework_adapters.base import COVERAGE_ACCEPT_MIN, TestResult

RUFF_DIAGNOSTIC_RE = re.compile(r"^.+?:\d+:\d+:\s+[A-Z]{1,6}\d{1,4}\b")
TESTS_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected", re.IGNORECASE)
# Match any pytest line that reports an individual test outcome, including
# xdist/parallel formats. We do not rely on a specific prefix/suffix shape,
# only that a result token appears somewhere on the line.
PYTEST_RESULT_LINE_RE = re.compile(
    r"\b(PASSED|FAILED|SKIPPED|ERROR|XPASS|XFAIL)\b", re.IGNORECASE
)


def extract_count_from_line(parts: list[str], keyword: str) -> int | None:
    """Extract count value for given keyword from line parts."""
    for i, part in enumerate(parts):
        part_clean = part.rstrip(".,;")
        if part_clean != keyword:
            continue

        try:
            count_str = parts[i - 1]
            return int(count_str)
        except (ValueError, IndexError):
            pass

    return None


def parse_test_counts(output: str) -> tuple[int, int, int]:
    """Parse passed, failed, and skipped counts from pytest session summary."""
    tests_passed = 0
    tests_failed = 0
    tests_skipped = 0

    lines = output.split("\n")
    for line in reversed(lines):
        line_lower = line.lower()
        if " in " not in line_lower:
            continue
        if not ("passed" in line_lower or "failed" in line_lower):
            continue
        if not any(c.isdigit() for c in line):
            continue
        parts = line.split()
        passed_count = extract_count_from_line(parts, "passed")
        failed_count = extract_count_from_line(parts, "failed")
        skipped_count = extract_count_from_line(parts, "skipped")
        if passed_count is not None:
            tests_passed = passed_count
        if failed_count is not None:
            tests_failed = failed_count
        if skipped_count is not None:
            tests_skipped = skipped_count
        if passed_count is not None:
            break

    return tests_passed, tests_failed, tests_skipped


def _read_cached_skipped_count(cache_path: Path) -> int | None:
    """Load previous skipped_tests from cache file, or None."""
    try:
        raw_text = cache_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        raw_obj: object = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw_obj, dict):
        return None
    data = cast(dict[str, object], raw_obj)
    val_obj = data.get("skipped_tests")
    if isinstance(val_obj, int) and val_obj >= 0:
        return val_obj
    return None


def _persist_skipped_count_cache(cache_path: Path, skipped_tests: int) -> None:
    """Write skipped_tests count to cache (best effort)."""
    try:
        _ = cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"skipped_tests": skipped_tests}, indent=2) + "\n"
        _ = cache_path.write_text(payload, encoding="utf-8")
    except OSError:
        pass


def merge_skip_trend_warnings(
    skipped_tests: int,
    project_root: Path | None,
    existing_warnings: list[str],
) -> list[str]:
    """Append warning if skipped count rose vs last run; persist count under .cortex/.cache."""
    warnings = list(existing_warnings)
    if project_root is None:
        return warnings
    cache_path = project_root / ".cortex" / ".cache" / "last_pytest_skipped_count.json"
    previous = _read_cached_skipped_count(cache_path) if cache_path.is_file() else None
    if previous is not None and skipped_tests > previous:
        tail = "(not a failure; ref: cleanup-skipped-legacy-tests)."
        msg = f"Skipped test count increased from {previous} to {skipped_tests} " + tail
        warnings.append(msg)
    _persist_skipped_count_cache(cache_path, skipped_tests)
    return warnings


def _pytest_errors_and_pass_rate(
    output: str,
    tests_passed: int,
    tests_failed: int,
    coverage: float | None,
    coverage_threshold: float,
    actual_success: bool,
) -> tuple[list[str], float]:
    """Build errors list and pass_rate from pytest output fragment."""
    errors = build_test_errors(actual_success, coverage, coverage_threshold)
    if tests_failed > 0:
        for line in extract_failed_test_lines(output):
            if line not in errors:
                errors.append(line)
    tests_run = tests_passed + tests_failed
    pass_rate = (tests_passed / tests_run) if tests_run > 0 else 0.0
    return errors, pass_rate


def _build_test_result_payload(
    output: str,
    actual_success: bool,
    tests_run: int,
    tests_passed: int,
    tests_failed: int,
    skipped_tests: int,
    pass_rate: float,
    coverage: float | None,
    errors: list[str],
    warnings: list[str],
) -> TestResult:
    """Assemble TestResult from parsed pytest fields."""
    return TestResult(
        success=actual_success,
        tests_run=tests_run,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        skipped_tests=skipped_tests,
        pass_rate=pass_rate,
        coverage=coverage,
        output=output,
        errors=errors,
        warnings=warnings,
    )


def extract_failed_test_lines(output: str) -> list[str]:
    """Extract FAILED summary lines from pytest output."""
    failed: list[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line.startswith("FAILED "):
            continue
        if "====" in line or "======" in line:
            continue
        failed.append(line)
    return failed


def parse_coverage(output: str) -> float | None:
    """Parse coverage percentage from pytest/coverage output."""
    for line in output.split("\n"):
        if "TOTAL" in line and "%" in line:
            try:
                parts = line.split()
                for part in reversed(parts):
                    if "%" in part:
                        coverage_str = part.replace("%", "")
                        return float(coverage_str) / 100.0
            except (ValueError, IndexError):
                pass
        if "Total coverage:" in line and "%" in line:
            try:
                coverage_part = line.split("Total coverage:")[-1].strip()
                coverage_str = coverage_part.split("%")[0].strip()
                return float(coverage_str) / 100.0
            except (ValueError, IndexError):
                pass
    return None


def build_test_errors(
    success: bool,
    coverage: float | None = None,
    coverage_threshold: float = 0.90,
) -> list[str]:
    """Build error list for test results."""
    errors: list[str] = []
    if not success:
        if coverage is not None and coverage < coverage_threshold:
            threshold_pct = coverage_threshold * 100
            msg = (
                f"Test coverage {coverage * 100:.2f}% is below "
                + f"required threshold {threshold_pct:.0f}%"
            )
            errors.append(msg)
        else:
            errors.append("Test execution failed")
    return errors


def coverage_accept_and_warning(
    coverage: float | None,
    coverage_threshold: float,
) -> tuple[bool, list[str]]:
    """Return (coverage_met, warnings). Accept 89.5%+ with warning."""
    coverage_met = coverage is not None and coverage >= COVERAGE_ACCEPT_MIN
    warning: list[str] = []
    if (
        coverage is not None
        and coverage >= COVERAGE_ACCEPT_MIN
        and coverage < coverage_threshold
    ):
        warning = [
            f"Coverage {coverage * 100:.2f}% is below 90%; "
            + "90%+ required for CI/release."
        ]
    return coverage_met, warning


def parse_type_errors(output: str) -> list[str]:
    """Parse pyright output for type errors."""
    errors: list[str] = []
    for line in output.split("\n"):
        if "error" in line.lower() and "warning" not in line.lower():
            errors.append(line.strip())
    return errors


def parse_lint_errors(output: str) -> list[str]:
    """Parse ruff output for linting errors."""
    errors: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.lower().startswith("error:"):
            errors.append(line)
            continue

        if RUFF_DIAGNOSTIC_RE.match(line):
            errors.append(line)

    return errors


def should_report_progress(completed: int, total: int, every_n: int = 50) -> bool:
    """True if we should report progress (every N tests or at completion)."""
    return completed % every_n == 0 or completed >= total


def is_pytest_result_line(line: str) -> bool:
    """Check if line contains pytest PASSED/FAILED/SKIPPED/ERROR result."""
    return PYTEST_RESULT_LINE_RE.search(line) is not None


def parse_tests_collected(output: str) -> int | None:
    """Run reversed scan for tests collected line; return total count or None."""
    for line in reversed(output.splitlines()):
        match = TESTS_COLLECTED_RE.search(line)
        if match:
            return int(match.group(1))
    return None


def parse_pytest_output(
    output: str,
    success: bool,
    coverage_threshold: float = 0.90,
    project_root: Path | None = None,
) -> TestResult:
    """Parse pytest output to TestResult. Used by PythonAdapter."""
    _ = success
    tp, tf, skipped_tests = parse_test_counts(output)
    coverage = parse_coverage(output)
    tests_run = tp + tf
    cov_ok, cov_warn = coverage_accept_and_warning(coverage, coverage_threshold)
    actual_ok = (tf == 0 and tests_run > 0) and cov_ok
    errors, pass_rate = _pytest_errors_and_pass_rate(
        output, tp, tf, coverage, coverage_threshold, actual_ok
    )
    warns = merge_skip_trend_warnings(skipped_tests, project_root, cov_warn)
    return _build_test_result_payload(
        output,
        actual_ok,
        tests_run,
        tp,
        tf,
        skipped_tests,
        pass_rate,
        coverage,
        errors,
        warns,
    )
