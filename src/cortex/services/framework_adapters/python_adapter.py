"""Python Framework Adapter

Adapter for Python projects using pytest, ruff, pyright, and black.
"""

import os
import re
import subprocess
import threading
from collections.abc import Sequence
from pathlib import Path

from cortex.core.path_resolver import (
    CortexResourceType,
    get_cortex_path,
    get_venv_bin_path,
)
from cortex.services.language_detector import LanguageDetector, LanguageInfo

from .base import CheckResult, FrameworkAdapter, ProgressCallback, TestResult

_RUFF_DIAGNOSTIC_RE = re.compile(r"^.+?:\d+:\d+:\s+[A-Z]{1,6}\d{1,4}\b")
_TESTS_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected", re.IGNORECASE)
_PYTEST_RESULT_LINE_RE = re.compile(
    r"\s+(PASSED|FAILED|SKIPPED|ERROR)\s+\[", re.IGNORECASE
)
_PROGRESS_REPORT_EVERY_N_TESTS = 50
_PROGRESS_HEARTBEAT_SECONDS = (
    20  # Report progress when pytest is silent (e.g. long test)
)


def _should_report_progress(completed: int, total: int) -> bool:
    """True if we should report progress (every N tests or at completion)."""
    return completed % _PROGRESS_REPORT_EVERY_N_TESTS == 0 or completed >= total


class PythonAdapter(FrameworkAdapter):
    """Adapter for Python projects."""

    @classmethod
    def detect(cls, path: Path) -> LanguageInfo | None:
        """Detect if path is a Python project. Reuses LanguageDetector."""
        info = LanguageDetector(str(path)).detect_language()
        if info is not None and info.language == "python":
            return info
        return None

    def __init__(self, project_root: str | None = None) -> None:
        """Initialize Python adapter.

        Args:
            project_root: Path to project root directory.
        """
        super().__init__(project_root)
        self.venv_bin = get_venv_bin_path(self.project_root)
        self._xdist_available: bool = False

    def _get_command(self, tool: str) -> str:
        """Get full path to tool command. Never relies on PATH (MCP-safe).

        Tries project_root/.venv/bin/<tool>, then cwd/.venv/bin/<tool>.
        Raises FileNotFoundError with clear message if neither exists.
        """
        venv_tool = self.venv_bin / tool
        if venv_tool.exists():
            return str(venv_tool)
        cwd_venv = get_venv_bin_path(Path.cwd()) / tool
        if cwd_venv.exists():
            return str(cwd_venv)
        expected = str(venv_tool)
        msg = (
            f"{tool} not found at {expected} or at {cwd_venv}. "
            + "Ensure .venv is set up (e.g. uv sync) and run from project root or "
            + "pass project_root to execute_pre_commit_checks."
        )
        raise FileNotFoundError(msg)

    def run_tests(
        self,
        timeout: int | None = None,
        coverage_threshold: float = 0.90,
        max_failures: int | None = None,
        progress_callback: ProgressCallback | None = None,
        include_slow_tests: bool = False,
    ) -> TestResult:
        """Run pytest test suite.

        Uses pytest-xdist -n auto when available for parallel runs (commit pipeline
        and CI). Set CORTEX_PYTEST_PARALLEL=0 to disable parallel (e.g. for debugging).

        Args:
            timeout: Maximum time in seconds for test execution.
            coverage_threshold: Minimum coverage percentage required.
            max_failures: Maximum number of failures before stopping.
            progress_callback: Optional (completed, total) for real test progress.
            include_slow_tests: If False (default), run with -m "not slow" so
                slow integration tests are excluded and the run finishes quickly.

        Returns:
            TestResult with test execution details.
        """
        cmd = self._build_test_command(
            coverage_threshold, max_failures, include_slow_tests
        )
        if progress_callback is not None:
            total = self._collect_test_count(include_slow_tests)
            if total is not None and total > 0:
                return self._execute_test_command_streaming(
                    cmd, timeout, coverage_threshold, total, progress_callback
                )
        return self._execute_test_command(cmd, timeout, coverage_threshold)

    def _pytest_parallel_requested(self) -> bool:
        """Return True if parallel test runs are allowed (default True when xdist used).

        Parallel (-n auto) is used when this returns True and xdist is available.
        Set CORTEX_PYTEST_PARALLEL=0 or false or no to disable (e.g. for debugging).
        """
        val = os.environ.get("CORTEX_PYTEST_PARALLEL", "").strip().lower()
        if val in ("0", "false", "no"):
            return False
        return True

    def _has_pytest_xdist(self) -> bool:
        """Return True if pytest-xdist is installed so we can use -n auto."""
        try:
            result = subprocess.run(
                [
                    self._get_command("pytest"),
                    "tests/",
                    "-n",
                    "auto",
                    "--collect-only",
                    "-q",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = (result.stdout or "") + (result.stderr or "")
            self._xdist_available = (
                result.returncode == 0 and "unrecognized arguments" not in out
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._xdist_available = False
        return self._xdist_available

    def _build_test_command(
        self,
        coverage_threshold: float,
        max_failures: int | None,
        include_slow_tests: bool = False,
    ) -> list[str]:
        """Build pytest command with options (matches CI when include_slow_tests)."""
        cmd = [
            self._get_command("pytest"),
            "tests/",  # Match CI: tests/
            "-v",
            "--cov=src/cortex",  # Match CI: --cov=src/cortex
            "--cov-report=xml",  # Match CI: --cov-report=xml
            "--cov-report=term",  # Also include terminal report
            f"--cov-fail-under={int(coverage_threshold * 100)}",  # Match CI:
            # --cov-fail-under=90
        ]
        if self._pytest_parallel_requested() and self._has_pytest_xdist():
            cmd.extend(["-n", "auto"])  # Parallel workers for faster runs
        if not include_slow_tests:
            cmd.extend(["-m", "not slow"])
        if max_failures:
            cmd.extend(["--maxfail", str(max_failures)])
        return cmd

    def _collect_test_count(self, include_slow_tests: bool = False) -> int | None:
        """Run pytest --collect-only -q and return total test count."""
        collect_cmd = [
            self._get_command("pytest"),
            "tests/",
            "--collect-only",
            "-q",
        ]
        if not include_slow_tests:
            collect_cmd.extend(["-m", "not slow"])
        try:
            result = subprocess.run(
                collect_cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            combined = result.stdout + result.stderr
            for line in reversed(combined.splitlines()):
                match = _TESTS_COLLECTED_RE.search(line)
                if match:
                    return int(match.group(1))
        except (subprocess.TimeoutExpired, ValueError):
            pass
        return None

    def _collect_streaming_output(
        self,
        proc: subprocess.Popen[str],
        total: int,
        progress_callback: ProgressCallback,
    ) -> list[str]:
        """Read proc stdout line by line and report test progress; return lines.

        When pytest is silent (e.g. one long test), a heartbeat thread still
        reports progress every _PROGRESS_HEARTBEAT_SECONDS so the UI does not
        appear stuck (e.g. around 300/3704 when a slow test runs).
        """
        lines: list[str] = []
        completed = 0
        completed_ref: list[int] = [0]
        stop_heartbeat = threading.Event()

        def heartbeat() -> None:
            while not stop_heartbeat.wait(timeout=_PROGRESS_HEARTBEAT_SECONDS):
                progress_callback(completed_ref[0], total)
            progress_callback(completed_ref[0], total)

        assert proc.stdout is not None
        heart = threading.Thread(target=heartbeat, daemon=True)
        heart.start()
        try:
            for line in proc.stdout:
                lines.append(line)
                if _PYTEST_RESULT_LINE_RE.search(line):
                    completed += 1
                    completed_ref[0] = completed
                    if _should_report_progress(completed, total):
                        progress_callback(completed, total)
            return lines
        finally:
            stop_heartbeat.set()
            heart.join(timeout=2.0)

    def _start_streaming_process(self, cmd: list[str]) -> subprocess.Popen[str]:
        """Start pytest process for streaming output."""
        return subprocess.Popen(
            cmd,
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def _execute_test_command_streaming(
        self,
        cmd: list[str],
        timeout: int | None,
        coverage_threshold: float,
        total: int,
        progress_callback: ProgressCallback,
    ) -> TestResult:
        """Run pytest with Popen, stream output, report (completed, total)."""
        proc: subprocess.Popen[str] | None = None
        try:
            proc = self._start_streaming_process(cmd)
            lines = self._collect_streaming_output(proc, total, progress_callback)
            wait_timeout = timeout if timeout else 3600
            _ = proc.wait(timeout=wait_timeout)  # noqa: F841
            output = "".join(lines)
            if proc.returncode == 0 and total > 0:
                # Ensure final 100% progress update even if no per-test lines matched.
                progress_callback(total, total)
            return self._parse_test_output(
                output, proc.returncode == 0, coverage_threshold
            )
        except subprocess.TimeoutExpired:
            if proc is not None and proc.poll() is None:
                proc.kill()
            return self._create_timeout_result()
        except Exception as e:
            return self._create_error_result(str(e))

    def _execute_test_command(
        self, cmd: list[str], timeout: int | None, coverage_threshold: float = 0.90
    ) -> TestResult:
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
            return self._parse_test_output(
                output, result.returncode == 0, coverage_threshold
            )
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
        """Fix errors using ruff and formatting tools.

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
            output_parts.append(lint_result.output)
            files_modified.extend(lint_result.files_modified)
            errors.extend(lint_result.errors)
            warnings.extend(lint_result.warnings)

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
            output_parts.append(format_result.output)
            files_modified.extend(format_result.files_modified)
            errors.extend(format_result.errors)

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
        """Run black formatter on src/ and tests/ (matches CI workflow)."""
        try:
            result = subprocess.run(
                [self._get_command("black"), "src/", "tests/"],
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
        """Run ruff import sorting on src/ and tests/ (matches CI workflow)."""
        try:
            result = subprocess.run(
                [
                    self._get_command("ruff"),
                    "check",
                    "--fix",
                    "--select",
                    "I",
                    "src/",
                    "tests/",
                ],
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
        """Run type checker matching CI scope (src, tests, synapse scripts).

        Uses .cortex/synapse/scripts/python/check_types.py when present so scope
        matches CI step 'Type check (tests and scripts)'; otherwise falls back
        to pyright src/ tests/.
        """
        script_path = (
            get_cortex_path(self.project_root, CortexResourceType.SYNAPSE)
            / "scripts"
            / "python"
            / "check_types.py"
        )
        if script_path.exists():
            return self._type_check_via_script(script_path)
        return self._type_check_pyright_only()

    def _type_check_result(
        self, success: bool, output: str, errors: list[str]
    ) -> CheckResult:
        """Build a type_check CheckResult."""
        return CheckResult(
            check_type="type_check",
            success=success,
            output=output,
            errors=errors,
            warnings=[],
            files_modified=[],
        )

    def _type_check_via_script(self, script_path: Path) -> CheckResult:
        """Run check_types.py so scope matches CI (src + tests + synapse scripts)."""
        try:
            python_bin = (
                str(self.venv_bin / "python")
                if (self.venv_bin / "python").exists()
                else "python3"
            )
            result = subprocess.run(
                [python_bin, str(script_path)],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )
            output = result.stdout + result.stderr
            errors = self._parse_type_errors(output) if result.returncode != 0 else []
            err_list = (
                errors
                if errors
                else ([output.strip()] if result.returncode != 0 else [])
            )
            return self._type_check_result(result.returncode == 0, output, err_list)
        except subprocess.TimeoutExpired:
            return self._type_check_result(
                False,
                "check_types.py timed out (300s)",
                ["Type check script timed out"],
            )
        except Exception as e:
            return self._type_check_result(False, str(e), [str(e)])

    def _type_check_pyright_only(self) -> CheckResult:
        """Fallback: pyright on src/ and tests/ when check_types.py is missing."""
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
        """Run ruff with auto-fix, then verify no errors remain.

        Uses pyproject.toml rule set (E, F, I, B, UP) - matches CI workflow.
        """
        try:
            # Step 1: Auto-fix errors
            fix_output = self._execute_ruff_fix_command()

            # Step 2: Verify no errors remain (matches CI workflow exactly)
            verify_output = self._execute_ruff_verify_command()
            verify_errors = self._parse_lint_errors(verify_output)

            # Combine outputs
            combined_output = (
                f"{fix_output}\n\n--- Verification (matches CI) ---\n{verify_output}"
            )

            # If verification found errors, those are the real errors
            if verify_errors:
                return self._create_lint_result(combined_output, verify_errors)

            # If fix step had errors but verification passed, that's OK
            # (errors were fixed)
            return self._create_lint_result(combined_output, [])
        except Exception as e:
            return self._create_lint_error_result(str(e))

    def _execute_ruff_fix_command(self) -> str:
        """Execute ruff check with --fix to auto-fix errors.

        Uses pyproject.toml rule set (E, F, I, B, UP).
        """
        result = subprocess.run(
            [
                self._get_command("ruff"),
                "check",
                "--fix",
                "src/",
                "tests/",
            ],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        return result.stdout + result.stderr

    def _execute_ruff_verify_command(self) -> str:
        """Execute ruff check without --fix to verify no errors remain.

        Uses pyproject.toml rule set - matches CI workflow.
        """
        result = subprocess.run(
            [
                self._get_command("ruff"),
                "check",
                "src/",
                "tests/",
            ],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        # Check return code - non-zero means errors remain
        if result.returncode != 0:
            # Add explicit error message if return code indicates failure
            error_msg = (
                f"Ruff verification failed (exit code {result.returncode}). "
                "Unfixable errors remain after auto-fix."
            )
            return f"{result.stdout}{result.stderr}\n{error_msg}"
        return result.stdout + result.stderr

    def _create_lint_result(self, output: str, errors: list[str]) -> CheckResult:
        """Create lint check result from output and errors."""
        return CheckResult(
            check_type="lint",
            success=len(errors) == 0,
            output=output,
            errors=errors,
            warnings=[],
            files_modified=[],
        )

    def _create_lint_error_result(self, error_msg: str) -> CheckResult:
        """Create lint check result for error case."""
        return CheckResult(
            check_type="lint",
            success=False,
            output=error_msg,
            errors=[error_msg],
            warnings=[],
            files_modified=[],
        )

    def _parse_test_output(
        self, output: str, success: bool, coverage_threshold: float = 0.90
    ) -> TestResult:
        """Parse pytest output to extract test results."""
        tests_passed, tests_failed = self._parse_test_counts(output)
        coverage = self._parse_coverage(output)

        # Determine actual success based on test results AND coverage
        # threshold. Return code can be non-zero due to coverage threshold,
        # but tests may still pass
        tests_run = tests_passed + tests_failed
        tests_passed_check = tests_failed == 0 and tests_run > 0

        # CRITICAL: Coverage must meet threshold (matches CI behavior)
        coverage_met = coverage is not None and coverage >= coverage_threshold

        # Success requires BOTH: tests passed AND coverage threshold met
        actual_success = tests_passed_check and coverage_met

        # Build errors if tests failed OR coverage threshold not met
        errors = self._build_test_errors(
            not actual_success, coverage, coverage_threshold
        )

        # `TestResult.pass_rate` is a ratio in [0, 1] (not a percentage).
        pass_rate = (tests_passed / tests_run) if tests_run > 0 else 0.0

        return TestResult(
            success=actual_success,
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

        lines = output.split("\n")
        # Search from the end for pytest's actual summary line (has timing " in X.XXs ")
        for line in reversed(lines):
            line_lower = line.lower()
            # Pytest summary always includes timing (e.g. " in 57.17s " or " in 0:01:00 ")
            if " in " not in line_lower:
                continue
            if not ("passed" in line_lower or "failed" in line_lower):
                continue
            if not any(c.isdigit() for c in line):
                continue
            parts = line.split()
            passed_count = self._extract_count_from_line(parts, "passed")
            failed_count = self._extract_count_from_line(parts, "failed")
            if passed_count is not None:
                tests_passed = passed_count
            if failed_count is not None:
                tests_failed = failed_count
            if passed_count is not None:
                break

        return tests_passed, tests_failed

    def _is_test_summary_line(self, line: str) -> bool:
        """Check if line contains test summary with passed/failed counts."""
        line_lower = line.lower()
        # Check for test summary - contains passed/failed and has numbers
        return ("passed" in line_lower or "failed" in line_lower) and any(
            char.isdigit() for char in line
        )

    def _extract_count_from_line(self, parts: list[str], keyword: str) -> int | None:
        """Extract count value for given keyword from line parts."""
        for i, part in enumerate(parts):
            # Handle keywords with or without trailing comma/punctuation
            part_clean = part.rstrip(".,;")
            if part_clean != keyword:
                continue

            try:
                # Get the number before the keyword
                count_str = parts[i - 1]
                return int(count_str)
            except (ValueError, IndexError):
                pass

        return None

    def _parse_coverage(self, output: str) -> float | None:
        """Parse coverage percentage from output."""
        # Look for coverage percentage in multiple formats
        for line in output.split("\n"):
            # Format 1: "TOTAL ... XX.XX%"
            if "TOTAL" in line and "%" in line:
                try:
                    # Find the percentage value (last number with %)
                    parts = line.split()
                    for part in reversed(parts):
                        if "%" in part:
                            coverage_str = part.replace("%", "")
                            return float(coverage_str) / 100.0
                except (ValueError, IndexError):
                    pass
            # Format 2: "Required test coverage of XX% reached. Total coverage: YY.YY%"
            if "Total coverage:" in line and "%" in line:
                try:
                    # Extract percentage after "Total coverage:"
                    coverage_part = line.split("Total coverage:")[-1].strip()
                    coverage_str = coverage_part.split("%")[0].strip()
                    return float(coverage_str) / 100.0
                except (ValueError, IndexError):
                    pass
        return None

    def _build_test_errors(
        self,
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
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Ruff emits summary lines like:
            # - "Found N errors (M fixed, K remaining)."
            # Those should not be counted as "remaining errors".
            if line.lower().startswith("error:"):
                errors.append(line)
                continue

            if _RUFF_DIAGNOSTIC_RE.match(line):
                errors.append(line)

        return errors
