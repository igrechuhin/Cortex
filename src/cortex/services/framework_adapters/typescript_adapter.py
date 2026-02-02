"""TypeScript Framework Adapter

Adapter for TypeScript/JavaScript projects using prettier, eslint, and tsc.
"""

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

from .base import CheckResult, FrameworkAdapter, ProgressCallback, TestResult

_ESLINT_LINE_RE = re.compile(r"^.+?:\d+:\d+:\s+(error|warning)\s+", re.IGNORECASE)
_TSC_ERROR_RE = re.compile(r"error\s+TS\d+", re.IGNORECASE)


class TypeScriptAdapter(FrameworkAdapter):
    """Adapter for TypeScript/JavaScript projects."""

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize TypeScript adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)
        self._npx_prefix = ["npx", "--no-install"]

    def _run_npx(
        self, args: list[str], cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run npx command in project root."""
        cwd = cwd or self.project_root
        return subprocess.run(
            [*self._npx_prefix, *args],
            cwd=cwd,
            capture_output=True,
            text=True,
        )

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> TestResult:
        """Run test suite via npm test.

        Args:
            timeout: Maximum time in seconds for test execution.
            coverage_threshold: Minimum coverage percentage required.
            max_failures: Maximum number of failures before stopping.
            progress_callback: Unused; for API compatibility.

        Returns:
            TestResult with test execution details.
        """
        cmd = ["npm", "test", "--", "--passWithNoTests"]
        if max_failures is not None:
            cmd.extend(["--maxWorkers=1", f"--bail={max_failures}"])
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout + result.stderr
            return self._parse_test_output(output, result.returncode == 0)
        except subprocess.TimeoutExpired:
            return self._timeout_test_result()
        except Exception as e:
            return self._error_test_result(str(e))

    def _parse_test_output(self, output: str, success: bool) -> TestResult:
        """Parse npm test / Jest / Vitest-style output."""
        passed, failed = self._extract_test_counts(output)
        total = passed + failed
        pass_rate = (passed / total) if total > 0 else 0.0
        coverage = self._extract_coverage(output)
        errors: list[str] = []
        if not success:
            errors.append("Test execution failed")
        if coverage is not None and coverage < 0.90:
            errors.append(f"Coverage {coverage * 100:.2f}% is below threshold 90%")
        return TestResult(
            success=success and len(errors) == 0,
            tests_run=total,
            tests_passed=passed,
            tests_failed=failed,
            pass_rate=pass_rate,
            coverage=coverage,
            output=output,
            errors=errors,
        )

    def _extract_test_counts(self, output: str) -> tuple[int, int]:
        """Extract passed/failed counts from test output."""
        passed, failed = 0, 0
        for line in reversed(output.splitlines()):
            line_lower = line.lower()
            if ("passed" in line_lower or "failed" in line_lower) and any(
                c.isdigit() for c in line
            ):
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

    def _extract_coverage(self, output: str) -> float | None:
        """Extract coverage percentage from output."""
        for line in output.split("\n"):
            if "%" in line and ("coverage" in line.lower() or "stmts" in line):
                parts = line.split()
                for part in reversed(parts):
                    if "%" in part:
                        try:
                            pct = float(part.replace("%", "")) / 100.0
                            if 0 <= pct <= 1:
                                return pct
                        except ValueError:
                            pass
        return None

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
        """Fix errors using eslint and prettier.

        Args:
            error_types: Types of errors to fix (e.g. ['formatting', 'linting']).
            auto_fix: Whether to automatically fix errors.
            strict_mode: Whether to treat warnings as errors.

        Returns:
            CheckResult with fix operation details.
        """
        files_modified: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        output_parts: list[str] = []

        if not error_types or "linting" in error_types:
            lint_r = self._run_eslint_fix()
            output_parts.append(lint_r.output)
            files_modified.extend(lint_r.files_modified)
            errors.extend(lint_r.errors)
            warnings.extend(lint_r.warnings)

        if not error_types or "formatting" in error_types:
            fmt_r = self.format_code()
            output_parts.append(fmt_r.output)
            files_modified.extend(fmt_r.files_modified)
            errors.extend(fmt_r.errors)

        return CheckResult(
            check_type="fix_errors",
            success=len(errors) == 0,
            output="\n".join(output_parts),
            errors=errors,
            warnings=warnings,
            files_modified=list(set(files_modified)),
        )

    def format_code(self) -> CheckResult:
        """Format code using Prettier.

        Returns:
            CheckResult with formatting operation details.
        """
        try:
            result = self._run_npx(
                ["prettier", "--write", ".", "--ignore-path", ".gitignore"]
            )
            out = result.stdout + result.stderr
            return CheckResult(
                check_type="format",
                success=result.returncode == 0,
                output=out,
                errors=[] if result.returncode == 0 else ["Prettier formatting failed"],
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
        """Run TypeScript compiler in noEmit mode.

        Returns:
            CheckResult with type checking details.
        """
        try:
            result = self._run_npx(["tsc", "--noEmit"])
            output = result.stdout + result.stderr
            errs = self.parse_tsc_errors(output)
            return CheckResult(
                check_type="type_check",
                success=len(errs) == 0,
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

    def parse_tsc_errors(self, output: str) -> list[str]:
        """Extract type errors from tsc output."""
        errors: list[str] = []
        for line in output.splitlines():
            if _TSC_ERROR_RE.search(line):
                errors.append(line.strip())
        return errors

    def lint_code(self) -> CheckResult:
        """Run ESLint.

        Returns:
            CheckResult with linting details.
        """
        return self._run_eslint_fix()

    def _run_eslint_fix(self) -> CheckResult:
        """Run ESLint with --fix and build CheckResult."""
        try:
            result = self._run_npx(
                ["eslint", ".", "--ext", ".ts,.tsx,.js,.jsx", "--fix"]
            )
            output = result.stdout + result.stderr
            errs, warns = self.parse_eslint_output(output)
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

    def parse_eslint_output(self, output: str) -> tuple[list[str], list[str]]:
        """Parse ESLint output into errors and warnings."""
        errors: list[str] = []
        warnings: list[str] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            match = _ESLINT_LINE_RE.match(line)
            if match:
                kind = match.group(1).lower()
                if kind == "error":
                    errors.append(line)
                else:
                    warnings.append(line)
        return errors, warnings
