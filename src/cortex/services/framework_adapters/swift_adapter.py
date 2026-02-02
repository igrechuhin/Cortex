"""Swift Framework Adapter

Adapter for Swift projects using Swift Package Manager: swift format,
swift build (type check / lint), swift test.
"""

import re
import subprocess
from collections.abc import Sequence

from .base import CheckResult, FrameworkAdapter, ProgressCallback, TestResult

_SWIFT_ERROR_LINE_RE = re.compile(r"error:\s+.*|\.swift:\d+:\d+:\s+error:", re.I)


class SwiftAdapter(FrameworkAdapter):
    """Adapter for Swift projects (Swift Package Manager)."""

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize Swift adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)

    def _has_package_swift(self) -> bool:
        """Return True if Package.swift exists in project root."""
        return (self.project_root / "Package.swift").is_file()

    def _run_swift(
        self, args: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run swift command in project root."""
        cmd = ["swift", *args]
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
    ) -> TestResult:
        """Run test suite via swift test."""
        if not self._has_package_swift():
            return self._error_test_result(
                "No Package.swift found; not a Swift Package Manager project"
            )
        try:
            result = self._run_swift(["test"], timeout=timeout)
            output = result.stdout + result.stderr
            return self._parse_test_output(output, result.returncode == 0)
        except subprocess.TimeoutExpired:
            return self._timeout_test_result()
        except Exception as e:
            return self._error_test_result(str(e))

    def _parse_test_output(self, output: str, success: bool) -> TestResult:
        """Parse swift test output."""
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
        """Extract passed/failed counts from swift test output."""
        passed, failed = 0, 0
        for line in output.splitlines():
            line_lower = line.lower()
            if "passed" in line_lower or "failed" in line_lower:
                parts = line.replace(",", " ").split()
                for i, part in enumerate(parts):
                    if part == "passed" and i > 0:
                        try:
                            passed = int(parts[i - 1])
                        except ValueError:
                            pass
                    if part == "failed" and i > 0:
                        try:
                            failed = int(parts[i - 1])
                        except ValueError:
                            pass
        if passed == 0 and failed == 0 and "test" in output.lower():
            if "passed" in output.lower():
                passed = 1
            elif "failed" in output.lower() or "error:" in output:
                failed = 1
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
        if not self._has_package_swift():
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
        if not self._has_package_swift():
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
