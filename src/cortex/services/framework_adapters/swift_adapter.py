"""Swift Framework Adapter

Adapter for Swift projects using Swift Package Manager: swift format,
swift build (type check / lint), swift test.
"""

import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from cortex.services.language_detector import LanguageDetector, LanguageInfo

from .base import CheckResult, FrameworkAdapter, ProgressCallback, TestResult
from .python_adapter_parsing import build_test_errors, coverage_accept_and_warning
from .swift_coverage import (
    default_profdata_path,
    find_package_tests_executable,
    parse_llvm_cov_report_line_coverage_fraction,
    pick_codecov_json_file,
    read_swift_codecov_json_fraction,
)

# Matches XCTest summary: "Executed N tests, with M failures"
_XCTEST_SUMMARY_RE = re.compile(
    r"Executed\s+(?P<total>\d+)\s+tests?,\s+with\s+(?P<failed>\d+)\s+failures?",
    re.IGNORECASE,
)

_SWIFT_ERROR_LINE_RE = re.compile(r"error:\s+.*|\.swift:\d+:\d+:\s+error:", re.I)


class SwiftAdapter(FrameworkAdapter):
    """Adapter for Swift projects (Swift Package Manager)."""

    @classmethod
    def detect(cls, path: Path) -> LanguageInfo | None:
        """Detect if path is a Swift project. Reuses LanguageDetector."""
        info = LanguageDetector(str(path)).detect_language()
        if info is not None and info.language == "swift":
            return info
        return None

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize Swift adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)

    def has_package_swift(self) -> bool:
        """Return True if Package.swift exists in project root."""
        return (self.project_root / "Package.swift").is_file()

    def _run_swift(
        self, args: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run swift command in project root.

        Captures raw bytes and decodes with ``errors="replace"`` so that binary
        content in test output (e.g. PNG snapshot bytes starting with 0x89) does
        not raise ``UnicodeDecodeError`` and crash the quality gate.
        """
        cmd = ["swift", *args]
        raw = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=False,
            timeout=timeout,
        )
        stdout = raw.stdout.decode("utf-8", errors="replace") if raw.stdout else ""
        stderr = raw.stderr.decode("utf-8", errors="replace") if raw.stderr else ""
        return subprocess.CompletedProcess(
            args=raw.args,
            returncode=raw.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
        progress_callback: ProgressCallback | None = None,
        include_slow_tests: bool = False,
    ) -> TestResult:
        """Run test suite via swift test."""
        if not self.has_package_swift():
            return self._error_test_result(
                "No Package.swift found; not a Swift Package Manager project"
            )
        try:
            result = self._run_swift(
                ["test", "--enable-code-coverage"],
                timeout=timeout,
            )
            output = result.stdout + result.stderr
            return self._finalize_swift_test_result(
                output,
                result.returncode == 0,
                timeout=timeout,
                coverage_threshold=coverage_threshold,
            )
        except subprocess.TimeoutExpired:
            return self._timeout_test_result()
        except Exception as e:
            return self._error_test_result(str(e))

    def _llvm_cov_report_argv(self, binary: Path, profdata: Path) -> list[str]:
        """Build argv for ``llvm-cov report`` (macOS uses ``xcrun``)."""
        ignore = r"\.build|Tests"
        tail = [
            "report",
            str(binary),
            f"-instr-profile={profdata}",
            f"-ignore-filename-regex={ignore}",
        ]
        if sys.platform == "darwin":
            return ["xcrun", "llvm-cov", *tail]
        return ["llvm-cov", *tail]

    def _collect_line_coverage_fraction(
        self, timeout: int | None
    ) -> tuple[float | None, bool]:
        """Return ``(fraction, collected)`` after a successful ``swift test`` run.

        ``collected`` is True only when SwiftPM artifacts exist and a numeric
        line-coverage value was derived (JSON export or ``llvm-cov report``).
        """
        bin_path = self._resolve_swift_bin_path(timeout)
        if bin_path is None:
            return None, False
        profdata = default_profdata_path(bin_path)
        if not profdata.is_file():
            return None, False
        frac = self._coverage_from_json(profdata.parent)
        if frac is not None:
            return frac, True
        frac = self._coverage_from_llvm_cov(bin_path, profdata, timeout)
        if frac is None:
            return None, False
        return frac, True

    def _resolve_swift_bin_path(self, timeout: int | None) -> Path | None:
        """Resolve SwiftPM bin path via ``swift build --show-bin-path``."""
        bin_path_res = self._run_swift(["build", "--show-bin-path"], timeout=timeout)
        if bin_path_res.returncode != 0:
            return None
        bin_text = (bin_path_res.stdout + bin_path_res.stderr).strip()
        if not bin_text:
            return None
        return Path(bin_text.splitlines()[-1].strip())

    def _coverage_from_json(self, codecov_dir: Path) -> float | None:
        """Read coverage fraction from JSON export if available."""
        json_path = pick_codecov_json_file(codecov_dir)
        if json_path is None:
            return None
        return read_swift_codecov_json_fraction(json_path)

    def _coverage_from_llvm_cov(
        self,
        bin_path: Path,
        profdata: Path,
        timeout: int | None,
    ) -> float | None:
        """Read coverage fraction via ``llvm-cov report`` fallback path."""
        exe = find_package_tests_executable(bin_path)
        if exe is None:
            return None
        argv = self._llvm_cov_report_argv(exe, profdata)
        raw = subprocess.run(
            argv,
            cwd=self.project_root,
            capture_output=True,
            text=False,
            timeout=timeout,
        )
        report = ""
        if raw.stdout:
            report += raw.stdout.decode("utf-8", errors="replace")
        if raw.stderr:
            report += raw.stderr.decode("utf-8", errors="replace")
        if raw.returncode != 0:
            return None
        return parse_llvm_cov_report_line_coverage_fraction(report)

    def _finalize_swift_test_result(
        self,
        output: str,
        tests_ok: bool,
        timeout: int | None,
        coverage_threshold: float,
    ) -> TestResult:
        """Parse ``swift test`` output and apply coverage threshold when data exists."""
        passed, failed = self._extract_test_counts(output)
        total = passed + failed
        pass_rate = (passed / total) if total > 0 else 0.0
        actual_ok, coverage, warnings = self._coverage_gate_outcome(
            tests_ok, timeout, coverage_threshold
        )

        errors = build_test_errors(
            actual_ok,
            coverage,
            coverage_threshold,
        )
        return TestResult(
            success=actual_ok and len(errors) == 0,
            tests_run=total,
            tests_passed=passed,
            tests_failed=failed,
            pass_rate=pass_rate,
            coverage=coverage,
            output=output,
            errors=errors,
            warnings=warnings,
        )

    def _coverage_gate_outcome(
        self,
        tests_ok: bool,
        timeout: int | None,
        coverage_threshold: float,
    ) -> tuple[bool, float | None, list[str]]:
        """Evaluate test+coverage gate and return (ok, coverage, warnings)."""
        if not tests_ok:
            return False, None, []
        frac, collected = self._collect_line_coverage_fraction(timeout)
        if not collected or frac is None:
            return True, None, []
        cov_ok, cov_warn = coverage_accept_and_warning(frac, coverage_threshold)
        return cov_ok, frac, cov_warn

    def _extract_test_counts(self, output: str) -> tuple[int, int]:
        """Extract passed/failed counts from swift test output.

        Parses the XCTest summary line:
          ``Executed N tests, with M failures (0 unexpected) in ...``
        and accumulates counts across multiple summary lines (parallel suites).
        Falls back to a heuristic scan if no summary line is found.
        """
        total_from_summary = 0
        failed_from_summary = 0
        found_summary = False
        for m in _XCTEST_SUMMARY_RE.finditer(output):
            total_from_summary = max(total_from_summary, int(m.group("total")))
            failed_from_summary += int(m.group("failed"))
            found_summary = True

        if found_summary:
            passed = total_from_summary - failed_from_summary
            return max(passed, 0), failed_from_summary

        # Fallback: output was truncated or format is unexpected.
        if "test" in output.lower():
            if "passed" in output.lower():
                return 1, 0
            if "failed" in output.lower() or "error:" in output:
                return 0, 1
        return 0, 0

    def _timeout_test_result(self) -> TestResult:
        """Build test result for timeout."""
        return TestResult(
            success=False,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output="Test execution timed out",
            errors=["Test execution exceeded timeout"],
        )

    def _error_test_result(self, message: str) -> TestResult:
        """Build test result for error."""
        return TestResult(
            success=False,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output=message,
            errors=[message],
        )

    def fix_errors(
        self,
        error_types: Sequence[str] | None = None,
        auto_fix: bool = True,
        strict_mode: bool = False,
    ) -> CheckResult:
        """Fix errors using swift format."""
        if not error_types or "formatting" in error_types:
            fmt_r = self.format_code()
            return CheckResult(
                check_type="fix_errors",
                success=fmt_r.success,
                output=fmt_r.output,
                errors=fmt_r.errors,
                warnings=fmt_r.warnings,
                files_modified=fmt_r.files_modified,
            )
        return CheckResult(
            check_type="fix_errors",
            success=True,
            output="",
            errors=[],
            warnings=[],
            files_modified=[],
        )

    def format_code(self) -> CheckResult:
        """Format code using swift format."""
        if not self.has_package_swift():
            return CheckResult(
                check_type="format",
                success=False,
                output="No Package.swift found",
                errors=["No Package.swift found"],
                warnings=[],
                files_modified=[],
            )
        try:
            result = self._run_swift(["format", "-r", "."])
            out = result.stdout + result.stderr
            return CheckResult(
                check_type="format",
                success=result.returncode == 0,
                output=out,
                errors=[] if result.returncode == 0 else ["swift format failed"],
                warnings=[],
                files_modified=[],
            )
        except Exception as e:
            return CheckResult(
                check_type="format",
                success=False,
                output=str(e),
                errors=[str(e)],
                warnings=[],
                files_modified=[],
            )

    def type_check(self) -> CheckResult:
        """Run type checker via swift build."""
        if not self.has_package_swift():
            return CheckResult(
                check_type="type_check",
                success=False,
                output="No Package.swift found",
                errors=["No Package.swift found"],
                warnings=[],
                files_modified=[],
            )
        try:
            result = self._run_swift(["build"])
            output = result.stdout + result.stderr
            errs = self._parse_build_errors(output) if result.returncode != 0 else []
            return CheckResult(
                check_type="type_check",
                success=result.returncode == 0,
                output=output,
                errors=errs,
                warnings=[],
                files_modified=[],
            )
        except Exception as e:
            return CheckResult(
                check_type="type_check",
                success=False,
                output=str(e),
                errors=[str(e)],
                warnings=[],
                files_modified=[],
            )

    def _parse_build_errors(self, output: str) -> list[str]:
        """Extract error lines from swift build output."""
        errors: list[str] = []
        for line in output.splitlines():
            s = line.strip()
            if s and _SWIFT_ERROR_LINE_RE.search(s):
                errors.append(s)
        return errors

    def lint_code(self) -> CheckResult:
        """Run linter via swift build (build catches many issues)."""
        return self.type_check()
