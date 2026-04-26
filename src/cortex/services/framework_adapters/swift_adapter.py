"""Swift Framework Adapter

Adapter for Swift projects using Swift Package Manager: swift format,
swift build (type check / lint), swift test.
"""

import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from cortex.config.swift_coverage_config import load_swift_coverage_config
from cortex.services.language_detector import LanguageDetector, LanguageInfo

from .base import (
    CheckResult,
    CoverageGap,
    FrameworkAdapter,
    ProgressCallback,
    TestResult,
)
from .python_adapter_parsing import build_test_errors, coverage_accept_and_warning
from .swift_coverage import (
    FileCoverageEntry,
    build_coverage_gaps,
    build_swift_llvm_cov_ignore_regex,
    build_uncovered_files,
    compile_swift_coverage_exclude_regexes,
    default_profdata_path,
    find_package_tests_executable,
    llvm_cov_export_per_file,
    merge_profraw_to_profdata,
    parse_llvm_cov_report_line_coverage_fraction,
    pick_codecov_json_file,
    read_swift_codecov_json_per_file,
)
from .swift_test_diagnostics import (
    SwiftTestOutcome,
    SwiftTestStatus,
    build_swift_test_harness_errors,
    interpret_swift_test_output,
    stderr_tail,
)
from .swift_test_logging import SwiftTestLogRecord, write_swift_test_log

# Matches XCTest summary: "Executed N tests, with M failures"
_XCTEST_SUMMARY_RE = re.compile(
    r"Executed\s+(?P<total>\d+)\s+tests?,\s+with\s+(?P<failed>\d+)\s+failures?",
    re.IGNORECASE,
)

# Matches Swift Testing grand-total: "Test run with N test(s) passed" (exit 0)
# or "Test run with N test(s) ... passed" with optional middle text.
# This line is the authoritative count for mixed XCTest + Swift Testing suites.
_SWIFT_TESTING_SUMMARY_RE = re.compile(
    r"Test run with\s+(?P<total>\d+)\s+tests?\b.*?passed",
    re.IGNORECASE | re.DOTALL,
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
        self._swift_coverage_cfg = load_swift_coverage_config(self.project_root)
        self._swift_cov_extra_filename_re = compile_swift_coverage_exclude_regexes(
            list(self._swift_coverage_cfg.exclude_filename_regex_patterns)
        )

    def has_package_swift(self) -> bool:
        """Return True if Package.swift exists in project root."""
        return (self.project_root / "Package.swift").is_file()

    def _run_swift(
        self,
        args: list[str],
        timeout: int | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run swift command in project root.

        Captures raw bytes and decodes with ``errors="replace"`` so that binary
        content in test output (e.g. PNG snapshot bytes starting with 0x89) does
        not raise ``UnicodeDecodeError`` and crash the quality gate.

        ``extra_env`` is merged over ``os.environ`` for the child process. Used
        by ``run_tests`` to disable MLX Metal by default (SIGBUS workaround on
        Apple Silicon when ``swift test`` output is captured).
        """
        cmd = ["swift", *args]
        env: dict[str, str] | None = None
        if extra_env:
            env = {**os.environ, **extra_env}
        raw = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=False,
            timeout=timeout,
            env=env,
        )
        stdout = raw.stdout.decode("utf-8", errors="replace") if raw.stdout else ""
        stderr = raw.stderr.decode("utf-8", errors="replace") if raw.stderr else ""
        return subprocess.CompletedProcess(
            args=raw.args,
            returncode=raw.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    @staticmethod
    def _swift_test_env() -> dict[str, str]:
        """Return env overrides for ``swift test`` subprocess.

        Disables MLX Metal by default (``MLX_DISABLE_METAL=1``) to avoid
        intermittent SIGBUS when ``swift test`` output is captured on Apple
        Silicon. Set ``SWIFT_TEST_ALLOW_METAL=1`` in the parent env to opt out.
        """
        if os.getenv("SWIFT_TEST_ALLOW_METAL", "").lower() in {"1", "true", "yes"}:
            return {}
        return {"MLX_DISABLE_METAL": "1"}

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
        progress_callback: ProgressCallback | None = None,
        include_slow_tests: bool = False,
    ) -> TestResult:
        """Run test suite via swift test.

        Uses :func:`interpret_swift_test_output` as the authoritative
        pass/fail classifier — the exit code is NOT trusted because
        SwiftPM exits non-zero on post-run harness signals (e.g. SIGBUS
        from XCTest teardown on Apple Silicon when stdio is piped), even
        when every test passed. A full :file:`.cortex/.session/logs/swift-test-<ts>.log`
        transcript is written for every invocation so users can share the
        exact failure shape with the maintainers.
        """
        if not self.has_package_swift():
            return self._error_test_result(
                "No Package.swift found; not a Swift Package Manager project"
            )
        return self._run_tests_with_logging(timeout, coverage_threshold)

    def _run_tests_with_logging(
        self,
        timeout: int | None,
        coverage_threshold: float,
    ) -> TestResult:
        """Execute ``swift test`` and classify its outcome from the output."""
        extra_env = self._swift_test_env()
        argv = ["swift", "test", "--enable-code-coverage"]
        start = time.monotonic()
        try:
            result = self._run_swift(
                ["test", "--enable-code-coverage"],
                timeout=timeout,
                extra_env=extra_env,
            )
        except subprocess.TimeoutExpired as exc:
            self._handle_swift_test_timeout(exc, argv, extra_env, start)
            return self._timeout_test_result()
        except Exception as e:
            return self._error_test_result(str(e))
        return self._classify_and_finalize(
            result,
            argv,
            extra_env,
            start,
            timeout,
            coverage_threshold,
        )

    def _classify_and_finalize(  # noqa: PLR0913
        self,
        result: subprocess.CompletedProcess[str],
        argv: list[str],
        extra_env: dict[str, str] | None,
        start: float,
        timeout: int | None,
        coverage_threshold: float,
    ) -> TestResult:
        """Interpret ``swift test`` output, write the log, and finalize the gate result."""
        outcome = interpret_swift_test_output(
            result.stdout, result.stderr, result.returncode
        )
        self._log_swift_test_run(
            argv=argv,
            extra_env=extra_env,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed=time.monotonic() - start,
            outcome=outcome,
        )
        return self._build_completed_process_test_result(
            result, outcome, timeout, coverage_threshold
        )

    def _build_completed_process_test_result(
        self,
        result: subprocess.CompletedProcess[str],
        outcome: SwiftTestOutcome,
        timeout: int | None,
        coverage_threshold: float,
    ) -> TestResult:
        """Build final gate TestResult from subprocess output + interpreted outcome."""
        output = result.stdout + result.stderr
        passed, failed = self.extract_test_counts(output)
        actual_ok, coverage, errors, gaps, effective_warnings, uncovered = (
            self._build_swift_test_outcome_details(
                outcome.status == SwiftTestStatus.PASSED,
                timeout,
                coverage_threshold,
                failed,
                output,
                result.returncode,
                stderr_tail(result.stderr),
                outcome,
            )
        )
        return self._make_test_result(
            passed,
            failed,
            actual_ok,
            coverage,
            gaps,
            uncovered,
            output,
            errors,
            effective_warnings,
        )

    def _handle_swift_test_timeout(
        self,
        exc: subprocess.TimeoutExpired,
        argv: list[str],
        extra_env: dict[str, str] | None,
        start: float,
    ) -> None:
        """Log a timed-out ``swift test`` before returning the timeout result."""
        elapsed = time.monotonic() - start
        stdout = (
            (exc.stdout or b"").decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            (exc.stderr or b"").decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        outcome = SwiftTestOutcome(
            status=SwiftTestStatus.HARNESS_FAILURE,
            diagnostic=f"swift test exceeded timeout after {elapsed:.1f}s",
        )
        self._log_swift_test_run(
            argv=argv,
            extra_env=extra_env,
            returncode=-1,
            stdout=stdout,
            stderr=stderr,
            elapsed=elapsed,
            outcome=outcome,
        )

    def _log_swift_test_run(  # noqa: PLR0913
        self,
        argv: list[str],
        extra_env: dict[str, str] | None,
        returncode: int,
        stdout: str,
        stderr: str,
        elapsed: float,
        outcome: SwiftTestOutcome,
    ) -> None:
        """Persist a comprehensive swift test transcript for user attachments.

        Best-effort: any subprocess failure during codecov-dir resolution is
        swallowed so logging never breaks the gate.
        """
        codecov_dir: Path | None = None
        try:
            bin_path = self._resolve_swift_bin_path(None)
            if bin_path is not None:
                codecov_dir = bin_path / "codecov"
        except Exception:
            codecov_dir = None
        _ = write_swift_test_log(
            project_root=self.project_root,
            record=SwiftTestLogRecord(
                argv=argv,
                cwd=self.project_root,
                extra_env=extra_env,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                outcome=outcome,
                elapsed_seconds=elapsed,
                codecov_dir=codecov_dir,
            ),
        )

    def _llvm_cov_report_argv(self, binary: Path, profdata: Path) -> list[str]:
        """Build argv for ``llvm-cov report`` (macOS uses ``xcrun``)."""
        ignore = build_swift_llvm_cov_ignore_regex(
            list(self._swift_coverage_cfg.exclude_filename_regex_patterns)
        )
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
    ) -> tuple[float | None, bool, list[FileCoverageEntry]]:
        """Return ``(fraction, collected, per_file)`` after ``swift test``.

        ``collected`` is True only when SwiftPM artifacts exist and a numeric
        line-coverage value was derived (JSON export or ``llvm-cov report``).
        ``per_file`` is populated only when the JSON path succeeds.
        """
        bin_path = self._resolve_swift_bin_path(timeout)
        if bin_path is None:
            return None, False, []
        # Merge *.profraw → default.profdata when SwiftPM skipped the merge
        # (happens with mixed XCTest + Swift Testing targets).
        _ = merge_profraw_to_profdata(bin_path, timeout)
        profdata = default_profdata_path(bin_path)
        if not profdata.is_file():
            return None, False, []
        frac, per_file = self._coverage_from_json(profdata.parent)
        if frac is not None:
            return frac, True, per_file
        # JSON absent — try llvm-cov export first (gives both fraction + per-file).
        exe = find_package_tests_executable(bin_path)
        if exe is not None:
            export_per_file = llvm_cov_export_per_file(
                exe, profdata, self._swift_cov_extra_filename_re, timeout
            )
            if export_per_file:
                total = sum(e.lines_total for e in export_per_file)
                if total > 0:
                    covered = sum(e.lines_covered for e in export_per_file)
                    return covered / total, True, export_per_file
        frac = self._coverage_from_llvm_cov(bin_path, profdata, timeout)
        if frac is None:
            return None, False, []
        return frac, True, []

    def _resolve_swift_bin_path(self, timeout: int | None) -> Path | None:
        """Resolve SwiftPM bin path via ``swift build --show-bin-path``."""
        bin_path_res = self._run_swift(["build", "--show-bin-path"], timeout=timeout)
        if bin_path_res.returncode != 0:
            return None
        bin_text = (bin_path_res.stdout + bin_path_res.stderr).strip()
        if not bin_text:
            return None
        return Path(bin_text.splitlines()[-1].strip())

    def _coverage_from_json(
        self, codecov_dir: Path
    ) -> tuple[float | None, list[FileCoverageEntry]]:
        """Read coverage fraction and per-file entries from JSON export."""
        json_path = pick_codecov_json_file(codecov_dir)
        if json_path is None:
            return None, []
        per_file = read_swift_codecov_json_per_file(
            json_path, self._swift_cov_extra_filename_re
        )
        if not per_file:
            return None, []
        total = sum(e.lines_total for e in per_file)
        if total <= 0:
            return None, per_file
        covered = sum(e.lines_covered for e in per_file)
        return covered / total, per_file

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

    def _build_swift_test_outcome_details(  # noqa: PLR0913
        self,
        tests_ok: bool,
        timeout: int | None,
        coverage_threshold: float,
        failed: int,
        output: str,
        returncode: int,
        stderr_tail_text: str,
        outcome: SwiftTestOutcome | None,
    ) -> tuple[
        bool, float | None, list[str], list[CoverageGap], list[str], list[CoverageGap]
    ]:
        """Compute verdict, errors, gaps, warnings, and uncovered files for swift test output."""
        actual_ok, coverage, warnings, per_file = self._coverage_gate_outcome(
            tests_ok, timeout, coverage_threshold
        )
        errors = self._build_swift_test_errors(
            actual_ok,
            coverage,
            coverage_threshold,
            tests_ok,
            failed,
            output,
            returncode,
            stderr_tail_text,
            outcome,
        )
        gaps = self._build_coverage_gaps(per_file, coverage, coverage_threshold)
        uncovered = build_uncovered_files(per_file)
        effective_warnings = self._append_teardown_warning(
            warnings, outcome, tests_ok, returncode
        )
        return actual_ok, coverage, errors, gaps, effective_warnings, uncovered

    @staticmethod
    def _append_teardown_warning(
        warnings: list[str],
        outcome: SwiftTestOutcome | None,
        tests_ok: bool,
        returncode: int,
    ) -> list[str]:
        """Append a post-run-signal caveat when swift test passed under teardown crash."""
        effective = list(warnings)
        if outcome is not None and outcome.teardown_signal is not None and tests_ok:
            effective.append(
                f"swift test exited {returncode} after all tests passed "
                + f"(post-run signal {outcome.teardown_signal}); treated as success"
            )
        return effective

    @staticmethod
    def _make_test_result(  # noqa: PLR0913
        passed: int,
        failed: int,
        actual_ok: bool,
        coverage: float | None,
        gaps: list[CoverageGap],
        uncovered: list[CoverageGap],
        output: str,
        errors: list[str],
        warnings: list[str],
    ) -> TestResult:
        """Assemble the final ``TestResult`` from parsed counts and gate outcome."""
        total = passed + failed
        pass_rate = (passed / total) if total > 0 else 0.0
        return TestResult(
            success=actual_ok and len(errors) == 0,
            tests_run=total,
            tests_passed=passed,
            tests_failed=failed,
            pass_rate=pass_rate,
            coverage=coverage,
            coverage_gaps=gaps,
            uncovered_files=uncovered,
            output=output,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _build_swift_test_errors(  # noqa: PLR0913
        actual_ok: bool,
        coverage: float | None,
        coverage_threshold: float,
        tests_ok: bool,
        failed: int,
        output: str,
        returncode: int,
        stderr_tail_text: str,
        outcome: SwiftTestOutcome | None = None,
    ) -> list[str]:
        """Build test-phase error list, promoting harness failures over generic text.

        When ``swift test`` exits non-zero AND :func:`interpret_swift_test_output`
        classifies the run as anything other than PASSED, surface the
        classified diagnostic (linker failure, compile error, post-run signal,
        unknown harness failure) so fix-path subagents can route accurately.
        When outcome is PASSED, the gate should consider the tests green —
        any non-zero returncode is a post-run harness quirk, not a test
        failure.
        """
        errors = build_test_errors(actual_ok, coverage, coverage_threshold)
        if tests_ok:
            return errors
        if outcome is not None:
            tail = stderr_tail_text.splitlines()[-5:] if stderr_tail_text else []
            tail_text = " | ".join(line.strip() for line in tail if line.strip())
            message = outcome.diagnostic
            if tail_text:
                message = f"{message} — {tail_text}"
            return [message]
        if failed == 0:
            return build_swift_test_harness_errors(output, returncode, stderr_tail_text)
        return errors

    @staticmethod
    def _build_coverage_gaps(
        per_file: list[FileCoverageEntry],
        coverage: float | None,
        threshold: float,
    ) -> list[CoverageGap]:
        """Build top coverage gaps when below threshold."""
        return build_coverage_gaps(per_file, coverage, threshold)

    def _coverage_gate_outcome(
        self,
        tests_ok: bool,
        timeout: int | None,
        coverage_threshold: float,
    ) -> tuple[bool, float | None, list[str], list[FileCoverageEntry]]:
        """Evaluate test+coverage gate; return (ok, coverage, warnings, per_file)."""
        if not tests_ok:
            return False, None, [], []
        frac, collected, per_file = self._collect_line_coverage_fraction(timeout)
        if not collected or frac is None:
            return True, None, [], []
        cov_ok, cov_warn = coverage_accept_and_warning(frac, coverage_threshold)
        return cov_ok, frac, cov_warn, per_file

    def extract_test_counts(self, output: str) -> tuple[int, int]:
        """Extract passed/failed counts from swift test output.

        For mixed XCTest + Swift Testing suites, Swift Testing emits the
        authoritative grand total: ``Test run with N tests ... passed``.
        When that line is present it is used directly and XCTest per-suite
        failure counts are summed separately (they are not included in the
        Swift Testing summary line).

        For XCTest-only suites the last ``Executed N tests, with M failures``
        line is the grand-total aggregate.  When the run crashes before the
        aggregate line is written we fall back to the last seen per-bundle
        total, which is the best available partial count.
        """
        # Prefer Swift Testing grand total when present (mixed suites).
        swift_testing_match = _SWIFT_TESTING_SUMMARY_RE.search(output)
        if swift_testing_match:
            total = int(swift_testing_match.group("total"))
            # XCTest failure lines still report individual bundle failures;
            # sum them to get the overall failed count.
            failed = sum(
                int(m.group("failed")) for m in _XCTEST_SUMMARY_RE.finditer(output)
            )
            return max(total - failed, 0), failed

        # XCTest-only: use the last summary line (grand-total aggregate).
        last_total: int = 0
        last_failed: int = 0
        found_summary = False
        for m in _XCTEST_SUMMARY_RE.finditer(output):
            last_total, last_failed = int(m.group("total")), int(m.group("failed"))
            found_summary = True

        if found_summary:
            passed = last_total - last_failed
            return max(passed, 0), last_failed

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
