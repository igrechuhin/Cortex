"""Python Framework Adapter

Adapter for Python projects using pytest, ruff, pyright, and black.
"""

import os
import subprocess
import threading
from collections.abc import Sequence
from pathlib import Path

from cortex.core.path_resolver import get_venv_bin_path
from cortex.services.language_detector import LanguageDetector, LanguageInfo

from .base import (
    CheckResult,
    FrameworkAdapter,
    ProgressCallback,
    TestResult,
)
from .python_adapter_checks import (
    get_type_check_script_path,
    run_black_formatting,
    run_ruff_fix,
    run_ruff_import_sorting,
    type_check_pyright_only,
    type_check_via_script,
)
from .python_adapter_parsing import (
    is_pytest_result_line,
    parse_lint_errors,
    parse_pytest_output,
    parse_tests_collected,
    parse_type_errors,
    should_report_progress,
)

_PROGRESS_REPORT_EVERY_N_TESTS = 50
_PROGRESS_HEARTBEAT_SECONDS = 20


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
        """Initialize Python adapter."""
        super().__init__(project_root)
        self.venv_bin = get_venv_bin_path(self.project_root)
        self._xdist_available: bool = False

    def _get_command(self, tool: str) -> str:
        """Get full path to tool command. Never relies on PATH (MCP-safe)."""
        venv_tool = self.venv_bin / tool
        if venv_tool.exists():
            return str(venv_tool)
        cwd_venv = get_venv_bin_path(Path.cwd()) / tool
        if cwd_venv.exists():
            return str(cwd_venv)
        msg = (
            f"{tool} not found at {venv_tool} or at {cwd_venv}. "
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
        """Run pytest test suite."""
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
        """Return True if parallel test runs are allowed."""
        val = os.environ.get("CORTEX_PYTEST_PARALLEL", "").strip().lower()
        if val in ("0", "false", "no"):
            return False
        return True

    def _has_pytest_xdist(self) -> bool:
        """Return True if pytest-xdist is installed."""
        try:
            python_exe = self._get_command("python")
            result = subprocess.run(
                [
                    python_exe,
                    "-m",
                    "pytest",
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
        """Build pytest command with options."""
        python_exe = self._get_command("python")
        cmd = [
            python_exe,
            "-m",
            "pytest",
            "tests/",
            "-v",
            "--cov=src/cortex",
            "--cov-report=xml",
            "--cov-report=term",
            f"--cov-fail-under={int(coverage_threshold * 100)}",
        ]
        if self._pytest_parallel_requested() and self._has_pytest_xdist():
            cmd.extend(["-n", "auto"])
        if not include_slow_tests:
            cmd.extend(["-m", "not slow"])
        if max_failures:
            cmd.extend(["--maxfail", str(max_failures)])
        return cmd

    def _collect_test_count(self, include_slow_tests: bool = False) -> int | None:
        """Run pytest --collect-only -q and return total test count."""
        python_exe = self._get_command("python")
        collect_cmd = [
            python_exe,
            "-m",
            "pytest",
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
            return parse_tests_collected(combined)
        except subprocess.TimeoutExpired:
            pass
        return None

    def _collect_streaming_output(
        self,
        proc: subprocess.Popen[str],
        total: int,
        progress_callback: ProgressCallback,
    ) -> list[str]:
        """Read proc stdout line by line and report test progress; return lines."""
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
                if is_pytest_result_line(line):
                    completed += 1
                    completed_ref[0] = completed
                    if should_report_progress(
                        completed, total, _PROGRESS_REPORT_EVERY_N_TESTS
                    ):
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

    def _complete_streaming_test_run(
        self,
        proc: subprocess.Popen[str],
        timeout: int | None,
        coverage_threshold: float,
        total: int,
        progress_callback: ProgressCallback,
    ) -> TestResult:
        """Collect streamed output, wait for process, parse pytest result."""
        lines = self._collect_streaming_output(proc, total, progress_callback)
        wait_timeout = timeout if timeout else 3600
        _ = proc.wait(timeout=wait_timeout)  # noqa: F841
        output = "".join(lines)
        if proc.returncode == 0 and total > 0:
            progress_callback(total, total)
        return parse_pytest_output(
            output,
            proc.returncode == 0,
            coverage_threshold,
            self.project_root,
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
            return self._complete_streaming_test_run(
                proc, timeout, coverage_threshold, total, progress_callback
            )
        except subprocess.TimeoutExpired:
            if proc is not None and proc.poll() is None:
                proc.kill()
            return self._create_timeout_result()
        except (OSError, subprocess.SubprocessError) as e:
            return self._create_error_result(str(e))
        except Exception as e:
            return self._create_error_result(
                f"Unexpected error during streaming test execution: {e}"
            )

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
            return parse_pytest_output(
                output,
                result.returncode == 0,
                coverage_threshold,
                self.project_root,
            )
        except subprocess.TimeoutExpired:
            return self._create_timeout_result()
        except (OSError, subprocess.SubprocessError) as e:
            return self._create_error_result(str(e))
        except Exception as e:
            return self._create_error_result(
                f"Unexpected error during test execution: {e}"
            )

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
        """Fix errors using ruff and formatting tools."""
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
        """Format code using black and ruff import sorting."""
        files_modified: list[str] = []
        errors: list[str] = []
        output_parts: list[str] = []

        run_black_formatting(self.project_root, self._get_command, errors, output_parts)
        run_ruff_import_sorting(
            self.project_root, self._get_command, errors, output_parts
        )

        return CheckResult(
            check_type="format",
            success=len(errors) == 0,
            output="\n".join(output_parts),
            errors=errors,
            warnings=[],
            files_modified=files_modified,
        )

    def type_check(self) -> CheckResult:
        """Run type checker matching CI scope."""
        script_path = get_type_check_script_path(self.project_root)
        if script_path.exists():
            return type_check_via_script(
                self.project_root,
                self.venv_bin,
                script_path,
                parse_type_errors,
            )
        return type_check_pyright_only(
            self.project_root, self._get_command, parse_type_errors
        )

    def lint_code(self) -> CheckResult:
        """Run ruff linter."""
        return self._run_ruff_fix()

    def _run_ruff_fix(self) -> CheckResult:
        """Run ruff with auto-fix, then verify no errors remain."""
        return run_ruff_fix(self.project_root, self._get_command, parse_lint_errors)
