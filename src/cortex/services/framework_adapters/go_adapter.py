"""Go Framework Adapter

Adapter for Go projects using go fmt, go vet, go build, go test.
"""

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from cortex.services.language_detector import LanguageDetector, LanguageInfo

from .base import CheckResult, FrameworkAdapter, ProgressCallback, TestResult

_GO_VET_LINE_RE = re.compile(r"^[^\s]+\.go:\d+:\d+:\s+.+$")


class GoAdapter(FrameworkAdapter):
    """Adapter for Go projects."""

    @classmethod
    def detect(cls, path: Path) -> LanguageInfo | None:
        """Detect if path is a Go project. Reuses LanguageDetector."""
        info = LanguageDetector(str(path)).detect_language()
        if info is not None and info.language == "go":
            return info
        return None

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize Go adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)

    def _run_go(
        self, args: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run go command in project root."""
        cmd = ["go", *args]
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
        """Run test suite via go test."""
        args = ["test", "./..."]
        if max_failures is not None:
            args.extend(["-count=1", "-failfast"])
        try:
            result = self._run_go(args, timeout=timeout)
            output = result.stdout + result.stderr
            return self._parse_test_output(output, result.returncode == 0)
        except subprocess.TimeoutExpired:
            return self._timeout_test_result()
        except Exception as e:
            return self._error_test_result(str(e))

    def _parse_test_output(self, output: str, success: bool) -> TestResult:
        """Parse go test output."""
        passed, failed = self._extract_test_counts(output)
        total = passed + failed
        pass_rate = (passed / total) if total > 0 else 0.0
        errors: list[str] = []
        if not success:
            errors.append("Test execution failed")
        return TestResult(
            success=success and len(errors) == 0,
            tests_run=total,
            tests_passed=passed,
            tests_failed=failed,
            pass_rate=pass_rate,
            coverage=None,
            output=output,
            errors=errors,
        )

    def _extract_test_counts(self, output: str) -> tuple[int, int]:
        """Extract passed/failed counts from go test output."""
        passed, failed = 0, 0
        for line in output.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("--- PASS:"):
                passed += 1
            elif line_stripped.startswith("--- FAIL:"):
                failed += 1
        if passed == 0 and failed == 0 and ("FAIL" in output or "ok" in output):
            if "FAIL" in output and "ok " not in output.split()[-1:]:
                failed = 1
            elif "ok " in output:
                passed = 1
        return passed, failed

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
        """Fix errors using go fmt."""
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
        """Format code using go fmt."""
        try:
            result = self._run_go(["fmt", "./..."])
            out = result.stdout + result.stderr
            return CheckResult(
                check_type="format",
                success=result.returncode == 0,
                output=out,
                errors=[] if result.returncode == 0 else ["go fmt failed"],
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
        """Run type checker via go build."""
        try:
            result = self._run_go(["build", "./..."])
            output = result.stdout + result.stderr
            errs = self._parse_go_build_output(output) if result.returncode != 0 else []
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

    def _parse_go_build_output(self, output: str) -> list[str]:
        """Extract error lines from go build output."""
        errors: list[str] = []
        for line in output.splitlines():
            line_stripped = line.strip()
            if _GO_VET_LINE_RE.match(line_stripped) or (
                line_stripped and "error" in line_stripped.lower()
            ):
                errors.append(line_stripped)
        return errors

    def lint_code(self) -> CheckResult:
        """Run linter via go vet."""
        try:
            result = self._run_go(["vet", "./..."])
            output = result.stdout + result.stderr
            errs = self._parse_go_vet_output(output)
            return CheckResult(
                check_type="lint",
                success=len(errs) == 0,
                output=output,
                errors=errs,
                warnings=[],
                files_modified=[],
            )
        except Exception as e:
            return CheckResult(
                check_type="lint",
                success=False,
                output=str(e),
                errors=[str(e)],
                warnings=[],
                files_modified=[],
            )

    def _parse_go_vet_output(self, output: str) -> list[str]:
        """Extract error lines from go vet output."""
        errors: list[str] = []
        for line in output.splitlines():
            line_stripped = line.strip()
            if _GO_VET_LINE_RE.match(line_stripped):
                errors.append(line_stripped)
        return errors
