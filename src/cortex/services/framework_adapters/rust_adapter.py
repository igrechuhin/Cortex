"""Rust Framework Adapter

Adapter for Rust projects using cargo fmt, cargo clippy, cargo check, cargo test.
"""

import re
import subprocess
from collections.abc import Sequence

from .base import CheckResult, FrameworkAdapter, ProgressCallback, TestResult

_RUST_ERROR_RE = re.compile(r"^error(\[E\d+\])?:\s+", re.IGNORECASE)
_RUST_WARNING_RE = re.compile(r"^warning(\[W\d+\]|\s+\(.*\))?:\s+", re.IGNORECASE)


class RustAdapter(FrameworkAdapter):
    """Adapter for Rust projects."""

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize Rust adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)

    def _run_cargo(
        self, args: list[str], timeout: int | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run cargo command in project root."""
        cmd = ["cargo", *args]
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
        """Run test suite via cargo test."""
        args = ["test"]
        if max_failures is not None:
            args.extend(["--", f"--max-failures={max_failures}"])
        try:
            result = self._run_cargo(args, timeout=timeout)
            output = result.stdout + result.stderr
            return self._parse_test_output(output, result.returncode == 0)
        except subprocess.TimeoutExpired:
            return self._timeout_test_result()
        except Exception as e:
            return self._error_test_result(str(e))

    def _parse_test_output(self, output: str, success: bool) -> TestResult:
        """Parse cargo test output."""
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
        """Extract passed/failed counts from cargo test output."""
        passed, failed = 0, 0
        for line in reversed(output.splitlines()):
            line_lower = line.lower()
            if "test result:" in line_lower and "passed" in line_lower:
                parts = line.split()
                for i, part in enumerate(parts):
                    clean = part.rstrip(".,;")
                    if clean == "passed" and i > 0:
                        try:
                            passed = int(parts[i - 1])
                        except (ValueError, IndexError):
                            pass
                    if clean == "failed" and i > 0:
                        try:
                            failed = int(parts[i - 1])
                        except (ValueError, IndexError):
                            pass
                if passed > 0 or failed > 0:
                    break
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
        """Fix errors using cargo fmt and cargo fix."""
        files_modified: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        output_parts: list[str] = []

        if not error_types or "formatting" in error_types:
            fmt_r = self.format_code()
            output_parts.append(fmt_r.output)
            files_modified.extend(fmt_r.files_modified)
            errors.extend(fmt_r.errors)

        if not error_types or "linting" in error_types:
            fix_r = self._run_cargo_fix()
            output_parts.append(fix_r.output)
            files_modified.extend(fix_r.files_modified)
            errors.extend(fix_r.errors)
            warnings.extend(fix_r.warnings)

        return CheckResult(
            check_type="fix_errors",
            success=len(errors) == 0,
            output="\n".join(output_parts),
            errors=errors,
            warnings=warnings,
            files_modified=list(set(files_modified)),
        )

    def _run_cargo_fix(self) -> CheckResult:
        """Run cargo fix --allow-dirty --allow-staged."""
        try:
            result = self._run_cargo(["fix", "--allow-dirty", "--allow-staged"])
            output = result.stdout + result.stderr
            errs, warns = self._parse_rust_output(output)
            return CheckResult(
                check_type="lint",
                success=len(errs) == 0,
                output=output,
                errors=errs,
                warnings=warns,
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

    def format_code(self) -> CheckResult:
        """Format code using cargo fmt."""
        try:
            result = self._run_cargo(["fmt"])
            out = result.stdout + result.stderr
            return CheckResult(
                check_type="format",
                success=result.returncode == 0,
                output=out,
                errors=[] if result.returncode == 0 else ["cargo fmt failed"],
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
        """Run type checker via cargo check."""
        try:
            result = self._run_cargo(["check"])
            output = result.stdout + result.stderr
            errs, warns = self._parse_rust_output(output)
            return CheckResult(
                check_type="type_check",
                success=len(errs) == 0,
                output=output,
                errors=errs,
                warnings=warns,
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

    def lint_code(self) -> CheckResult:
        """Run linter via cargo clippy."""
        try:
            result = self._run_cargo(["clippy", "--", "-D", "warnings"])
            output = result.stdout + result.stderr
            errs, warns = self._parse_rust_output(output)
            return CheckResult(
                check_type="lint",
                success=len(errs) == 0,
                output=output,
                errors=errs,
                warnings=warns,
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

    def _parse_rust_output(self, output: str) -> tuple[list[str], list[str]]:
        """Parse rustc/clippy output into errors and warnings."""
        errors: list[str] = []
        warnings: list[str] = []
        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if _RUST_ERROR_RE.match(line_stripped):
                errors.append(line_stripped)
            elif _RUST_WARNING_RE.match(line_stripped):
                warnings.append(line_stripped)
        return errors, warnings
