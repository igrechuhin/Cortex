"""PHP Framework Adapter

Adapter for PHP projects (PHPUnit/Pest, PHPStan/Psalm, Pint/PHP-CS-Fixer, PHPCS).
Test results and coverage come from JUnit/Clover XML reports, and static analysis
from JSON output -- never from scraping console text.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from cortex.services.language_detector import LanguageDetector, LanguageInfo

from .base import (
    CheckResult,
    CoverageGap,
    FrameworkAdapter,
    ProgressCallback,
    TestResult,
)
from .php_parsing import parse_clover, parse_junit

ErrorExtractor = Callable[[object], list[str]]


def _empty_test_result(output: str, errors: list[str]) -> TestResult:
    """Build a zero-count failing TestResult."""
    return TestResult(
        success=False,
        tests_run=0,
        tests_passed=0,
        tests_failed=0,
        pass_rate=0.0,
        coverage=None,
        output=output,
        errors=errors,
    )


def _check(
    check_type: str, success: bool, output: str, errors: list[str]
) -> CheckResult:
    """Build a CheckResult with no warnings or modified files."""
    return CheckResult(
        check_type=check_type,
        success=success,
        output=output,
        errors=errors,
        warnings=[],
        files_modified=[],
    )


class PhpAdapter(FrameworkAdapter):
    """Adapter for PHP projects."""

    @classmethod
    def detect(cls, path: Path) -> LanguageInfo | None:
        """Detect if path is a PHP project. Reuses LanguageDetector."""
        info = LanguageDetector(str(path)).detect_language()
        if info is not None and info.language == "php":
            return info
        return None

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize PHP adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)
        self._info = LanguageDetector(str(self.project_root)).detect_language()

    def _tool_path(self, tool: str) -> str | None:
        """Resolve a PHP tool from vendor/bin, falling back to PATH."""
        vendor = self.project_root / "vendor" / "bin" / tool
        if vendor.exists():
            return str(vendor)
        return shutil.which(tool)

    def _run(
        self, cmd: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run a command in the project root."""
        return subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
        progress_callback: ProgressCallback | None = None,
        include_slow_tests: bool = False,
    ) -> TestResult:
        """Run PHPUnit/Pest and parse the JUnit and Clover XML reports."""
        runner = self._info.test_framework if self._info else None
        binary = self._tool_path(runner or "phpunit") or self._tool_path("pest")
        if binary is None:
            return _empty_test_result(
                "PHPUnit/Pest not found in vendor/bin or PATH",
                ["PHP test runner not installed"],
            )
        with tempfile.TemporaryDirectory() as tmp:
            junit = Path(tmp) / "junit.xml"
            clover = Path(tmp) / "clover.xml"
            cmd = [binary, "--log-junit", str(junit), "--coverage-clover", str(clover)]
            if max_failures is not None:
                cmd.append("--stop-on-failure")
            result = self._try_run(cmd, timeout)
            if isinstance(result, TestResult):
                return result
            return self._build_test_result(
                junit,
                clover,
                result.stdout + result.stderr,
                coverage_threshold,
                result.returncode,
            )

    def _try_run(
        self, cmd: list[str], timeout: int | None
    ) -> subprocess.CompletedProcess[str] | TestResult:
        """Run the test command, returning a failed TestResult if it never ran."""
        try:
            return self._run(cmd, timeout=timeout)
        except subprocess.TimeoutExpired:
            return _empty_test_result(
                "Test execution timed out", ["Test execution exceeded timeout"]
            )
        except OSError as e:
            return _empty_test_result(str(e), [str(e)])

    def _build_test_result(
        self,
        junit: Path,
        clover: Path,
        output: str,
        coverage_threshold: float,
        returncode: int,
    ) -> TestResult:
        """Assemble a TestResult from the XML reports produced by the run."""
        counts = parse_junit(junit)
        if counts is None:
            return _empty_test_result(
                output, ["PHPUnit produced no JUnit report; see output"]
            )
        coverage, gaps = parse_clover(clover, self.project_root)
        total = counts.passed + counts.failed
        return TestResult(
            success=returncode == 0 and counts.failed == 0,
            tests_run=total,
            tests_passed=counts.passed,
            tests_failed=counts.failed,
            skipped_tests=counts.skipped,
            pass_rate=(counts.passed / total) if total > 0 else 0.0,
            coverage=coverage,
            coverage_gaps=_top_gaps(gaps, coverage, coverage_threshold),
            uncovered_files=_zero_coverage(gaps),
            output=output,
            errors=counts.failures,
        )

    def fix_errors(
        self,
        error_types: Sequence[str] | None = None,
        auto_fix: bool = True,
        strict_mode: bool = False,
    ) -> CheckResult:
        """Fix formatting via the detected PHP formatter."""
        if error_types and "formatting" not in error_types:
            return _check("fix_errors", True, "", [])
        if not auto_fix:
            return _check("fix_errors", True, "auto_fix disabled", [])
        formatted = self.format_code()
        return _check(
            "fix_errors", formatted.success, formatted.output, formatted.errors
        )

    def format_code(self) -> CheckResult:
        """Format code using Pint, PHP-CS-Fixer, or phpcbf."""
        fixer_args = {
            "pint": [],
            "php-cs-fixer": ["fix"],
            "phpcbf": [],
        }
        for tool, args in fixer_args.items():
            binary = self._tool_path(tool)
            if binary is None:
                continue
            return self._run_check("format", [binary, *args], f"{tool} failed")
        return _check("format", True, "No PHP formatter installed; skipped", [])

    def type_check(self) -> CheckResult:
        """Run PHPStan (or Psalm) and parse its JSON output."""
        phpstan = self._tool_path("phpstan")
        if phpstan is not None:
            cmd = [phpstan, "analyse", "--no-progress", "--error-format=json"]
            return self._run_static_analysis("type_check", cmd, keyed_file_errors)
        psalm = self._tool_path("psalm")
        if psalm is not None:
            return self._run_static_analysis(
                "type_check",
                [psalm, "--output-format=json", "--no-progress"],
                psalm_errors,
            )
        return _check("type_check", True, "No PHP static analyser installed", [])

    def lint_code(self) -> CheckResult:
        """Run PHP_CodeSniffer and parse its JSON report."""
        phpcs = self._tool_path("phpcs")
        if phpcs is None:
            return _check("lint", True, "phpcs not installed; skipped", [])
        return self._run_static_analysis(
            "lint", [phpcs, "--report=json"], keyed_file_errors
        )

    def _run_check(self, check_type: str, cmd: list[str], failure: str) -> CheckResult:
        """Run a command and map its exit code onto a CheckResult."""
        try:
            result = self._run(cmd)
        except (OSError, subprocess.SubprocessError) as e:
            return _check(check_type, False, str(e), [str(e)])
        output = result.stdout + result.stderr
        ok = result.returncode == 0
        return _check(check_type, ok, output, [] if ok else [failure])

    def _run_static_analysis(
        self, check_type: str, cmd: list[str], extract: ErrorExtractor
    ) -> CheckResult:
        """Run a JSON-reporting analyser and extract its findings."""
        try:
            result = self._run(cmd)
        except (OSError, subprocess.SubprocessError) as e:
            return _check(check_type, False, str(e), [str(e)])
        output = result.stdout + result.stderr
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            if result.returncode == 0:
                return _check(check_type, True, output, [])
            return _check(check_type, False, output, [f"{cmd[0]} failed"])
        errors = extract(payload)
        return _check(check_type, not errors, output, errors)


def keyed_file_errors(payload: object) -> list[str]:
    """Extract ``file:line: message`` from PHPStan/phpcs JSON (shared shape).

    Both report ``{"files": {path: {"messages": [{"line": n, "message": s}]}}}``.
    """
    if not isinstance(payload, dict):
        return []
    files = cast(dict[str, object], payload).get("files")
    if not isinstance(files, dict):
        return []
    errors: list[str] = []
    for path, entry in cast(dict[str, object], files).items():
        for msg in _messages(entry):
            errors.append(
                f"{path}:{_field(msg, 'line', '?')}: {_field(msg, 'message')}"
            )
    return errors


def _messages(entry: object) -> list[dict[str, object]]:
    """Return the ``messages`` list of a keyed-file entry, or empty."""
    if not isinstance(entry, dict):
        return []
    messages = cast(dict[str, object], entry).get("messages")
    if not isinstance(messages, list):
        return []
    return [
        cast(dict[str, object], m)
        for m in cast(list[object], messages)
        if isinstance(m, dict)
    ]


def _field(item: dict[str, object], key: str, default: str = "") -> str:
    """Read a JSON field as a string, falling back to a default."""
    value = item.get(key, default)
    return str(value)


def psalm_errors(payload: object) -> list[str]:
    """Extract ``file:line: message`` strings from a Psalm JSON report."""
    if not isinstance(payload, list):
        return []
    issues = [
        cast(dict[str, object], i)
        for i in cast(list[object], payload)
        if isinstance(i, dict)
    ]
    return [_psalm_line(i) for i in issues]


def _psalm_line(issue: dict[str, object]) -> str:
    """Format one Psalm issue as ``file:line: message``."""
    where = f"{_field(issue, 'file_name', '?')}:{_field(issue, 'line_from', '?')}"
    return f"{where}: {_field(issue, 'message')}"


def _top_gaps(
    gaps: list[CoverageGap], coverage: float | None, threshold: float
) -> list[CoverageGap]:
    """Return the worst-covered files when overall coverage is below threshold."""
    if coverage is None or coverage >= threshold:
        return []
    ranked = sorted(gaps, key=lambda g: g.lines_uncovered, reverse=True)
    return ranked[:10]


def _zero_coverage(gaps: list[CoverageGap]) -> list[CoverageGap]:
    """Return files with no covered lines, smallest first."""
    zero = [g for g in gaps if g.coverage == 0.0]
    return sorted(zero, key=lambda g: g.lines_total)
