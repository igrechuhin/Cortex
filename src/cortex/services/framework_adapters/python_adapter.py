"""Python Framework Adapter

Adapter for Python projects using pytest, ruff, pyright, and black.
"""

import subprocess
from collections.abc import Sequence

from .base import CheckResult, FrameworkAdapter, TestResult


class PythonAdapter(FrameworkAdapter):
    """Adapter for Python projects."""

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize Python adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)
        self.venv_bin = self.project_root / ".venv" / "bin"

    def _get_command(self, tool: str) -> str:
        """Get full path to tool command."""
        venv_tool = self.venv_bin / tool
        if venv_tool.exists():
            return str(venv_tool)
        return tool

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
    ) -> TestResult:
        """Run pytest test suite.

        Args:
            timeout: Maximum time in seconds for test execution.
            coverage_threshold: Minimum coverage percentage required.
            max_failures: Maximum number of failures before stopping.

        Returns:
            TestResult with test execution details.
        """
        cmd = self._build_test_command(coverage_threshold, max_failures)
        return self._execute_test_command(cmd, timeout)

    def _build_test_command(
        self, coverage_threshold: float, max_failures: int | None
    ) -> list[str]:
        """Build pytest command with options."""
        cmd = [
            self._get_command("pytest"),
            "-v",
            "--cov=src",
            "--cov-report=term",
            f"--cov-fail-under={int(coverage_threshold * 100)}",
        ]
        if max_failures:
            cmd.extend(["--maxfail", str(max_failures)])
        return cmd

    def _execute_test_command(self, cmd: list[str], timeout: int | None) -> TestResult:
        """Execute test command and handle results."""
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
            return self._create_timeout_result()
        except Exception as e:
            return self._create_error_result(str(e))

    def _create_timeout_result(self) -> TestResult:
        """Create test result for timeout."""
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

    def _create_error_result(self, error: str) -> TestResult:
        """Create test result for error."""
        return TestResult(
            success=False,
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            pass_rate=0.0,
            coverage=None,
            output=error,
            errors=[error],
        )

    def fix_errors(
        self,
        error_types: Sequence[str] | None = None,
        auto_fix: bool = True,
        strict_mode: bool = False,
    ) -> CheckResult:
        """Fix errors using ruff and pyright.

        Args:
            error_types: Types of errors to fix (e.g., ['formatting', 'linting']).
            auto_fix: Whether to automatically fix errors.
            strict_mode: Whether to treat warnings as errors.

        Returns:
            CheckResult with fix operation details.
        """
        files_modified: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        output_parts: list[str] = []

        self._fix_linting_errors(
            error_types, files_modified, errors, warnings, output_parts
        )
        self._fix_formatting_errors(error_types, files_modified, errors, output_parts)
        self._check_type_errors(errors, output_parts)

        return CheckResult(
            check_type="fix_errors",
            success=len(errors) == 0,
            output="\n".join(output_parts),
            errors=errors,
            warnings=warnings,
            files_modified=list(set(files_modified)),
        )

    def _fix_linting_errors(
        self,
        error_types: Sequence[str] | None,
        files_modified: list[str],
        errors: list[str],
        warnings: list[str],
        output_parts: list[str],
    ) -> None:
        """Fix linting errors."""
        if not error_types or "linting" in error_types:
            lint_result = self._run_ruff_fix()
            output_parts.append(lint_result["output"])
            files_modified.extend(lint_result["files_modified"])
            errors.extend(lint_result["errors"])
            warnings.extend(lint_result["warnings"])

    def _fix_formatting_errors(
        self,
        error_types: Sequence[str] | None,
        files_modified: list[str],
        errors: list[str],
        output_parts: list[str],
    ) -> None:
        """Fix formatting errors."""
        if not error_types or "formatting" in error_types:
            format_result = self.format_code()
            output_parts.append(format_result["output"])
            files_modified.extend(format_result["files_modified"])
            errors.extend(format_result["errors"])

    def _check_type_errors(self, errors: list[str], output_parts: list[str]) -> None:
        """Check type errors."""
        type_result = self.type_check()
        output_parts.append(type_result["output"])
        if type_result["errors"]:
            errors.extend(type_result["errors"])

    def format_code(self) -> CheckResult:
        """Format code using black and ruff import sorting.

        Returns:
            CheckResult with formatting operation details.
        """
        files_modified: list[str] = []
        errors: list[str] = []
        output_parts: list[str] = []

        self._run_black_formatting(errors, output_parts)
        self._run_ruff_import_sorting(errors, output_parts)

        return CheckResult(
            check_type="format",
            success=len(errors) == 0,
            output="\n".join(output_parts),
            errors=errors,
            warnings=[],
            files_modified=files_modified,
        )

    def _run_black_formatting(self, errors: list[str], output_parts: list[str]) -> None:
        """Run black formatter."""
        try:
            result = subprocess.run(
                [self._get_command("black"), "."],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )
            output_parts.append(result.stdout)
            if result.returncode != 0:
                errors.append("Black formatting failed")
        except Exception as e:
            errors.append(f"Black formatting error: {e}")

    def _run_ruff_import_sorting(
        self, errors: list[str], output_parts: list[str]
    ) -> None:
        """Run ruff import sorting."""
        try:
            result = subprocess.run(
                [self._get_command("ruff"), "check", "--fix", "--select", "I", "."],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )
            output_parts.append(result.stdout)
            if result.returncode != 0:
                errors.append("Ruff import sorting failed")
        except Exception as e:
            errors.append(f"Ruff import sorting error: {e}")

    def type_check(self) -> CheckResult:
        """Run pyright type checker.

        Returns:
            CheckResult with type checking details.
        """
        try:
            result = subprocess.run(
                [self._get_command("pyright"), "src/", "tests/"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )
            output = result.stdout + result.stderr
            errors = self._parse_type_errors(output)
            return CheckResult(
                check_type="type_check",
                success=len(errors) == 0,
                output=output,
                errors=errors,
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

    def lint_code(self) -> CheckResult:
        """Run ruff linter.

        Returns:
            CheckResult with linting details.
        """
        return self._run_ruff_fix()

    def _run_ruff_fix(self) -> CheckResult:
        """Run ruff with auto-fix."""
        try:
            result = subprocess.run(
                [self._get_command("ruff"), "check", "--fix", "."],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )
            output = result.stdout + result.stderr
            errors = self._parse_lint_errors(output)
            return CheckResult(
                check_type="lint",
                success=len(errors) == 0,
                output=output,
                errors=errors,
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

    def _parse_test_output(self, output: str, success: bool) -> TestResult:
        """Parse pytest output to extract test results."""
        tests_passed, tests_failed = self._parse_test_counts(output)
        coverage = self._parse_coverage(output)
        errors = self._build_test_errors(success)

        tests_run = tests_passed + tests_failed
        pass_rate = (tests_passed / tests_run * 100.0) if tests_run > 0 else 0.0

        return TestResult(
            success=success and tests_failed == 0,
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            pass_rate=pass_rate,
            coverage=coverage,
            output=output,
            errors=errors,
        )

    def _parse_test_counts(self, output: str) -> tuple[int, int]:
        """Parse test passed/failed counts from output."""
        tests_passed = 0
        tests_failed = 0

        for line in output.split("\n"):
            if not self._is_test_summary_line(line):
                continue

            parts = line.split()
            tests_passed = (
                self._extract_count_from_line(parts, "passed") or tests_passed
            )
            tests_failed = (
                self._extract_count_from_line(parts, "failed") or tests_failed
            )

        return tests_passed, tests_failed

    def _is_test_summary_line(self, line: str) -> bool:
        """Check if line contains test summary with passed/failed counts."""
        return "passed" in line and "failed" in line

    def _extract_count_from_line(self, parts: list[str], keyword: str) -> int | None:
        """Extract count value for given keyword from line parts."""
        for i, part in enumerate(parts):
            if part != keyword:
                continue

            try:
                return int(parts[i - 1])
            except (ValueError, IndexError):
                pass

        return None

    def _parse_coverage(self, output: str) -> float | None:
        """Parse coverage percentage from output."""
        for line in output.split("\n"):
            if "TOTAL" in line and "%" in line:
                try:
                    coverage_str = line.split()[-1].replace("%", "")
                    return float(coverage_str) / 100.0
                except (ValueError, IndexError):
                    pass
        return None

    def _build_test_errors(self, success: bool) -> list[str]:
        """Build error list for test results."""
        errors: list[str] = []
        if not success:
            errors.append("Test execution failed")
        return errors

    def _parse_type_errors(self, output: str) -> list[str]:
        """Parse pyright output for type errors."""
        errors: list[str] = []
        for line in output.split("\n"):
            if "error" in line.lower() and "warning" not in line.lower():
                errors.append(line.strip())
        return errors

    def _parse_lint_errors(self, output: str) -> list[str]:
        """Parse ruff output for linting errors."""
        errors: list[str] = []
        for line in output.split("\n"):
            if "error" in line.lower() or "E" in line[:5]:
                errors.append(line.strip())
        return errors
