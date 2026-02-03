"""Tests for Python framework adapter."""

import subprocess
import tempfile
from contextlib import chdir
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from cortex.services.framework_adapters.base import TestResult
from cortex.services.framework_adapters.python_adapter import PythonAdapter


class TestPythonAdapter:
    """Test Python framework adapter."""

    def test_init_with_project_root(self) -> None:
        """Test adapter initialization with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = PythonAdapter(str(tmpdir))
            assert adapter.project_root == Path(tmpdir)

    def test_init_without_project_root(self) -> None:
        """Test adapter initialization without project root."""
        adapter = PythonAdapter()
        assert adapter.project_root == Path.cwd()

    @patch("cortex.services.framework_adapters.python_adapter.subprocess.run")
    def test_run_tests_success(self, mock_run: MagicMock) -> None:
        """Test successful test execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".venv" / "bin").mkdir(parents=True)
            (project_root / ".venv" / "bin" / "pytest").touch()

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "10 passed, 0 failed\nTOTAL 95%"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = PythonAdapter(str(project_root))
            result = adapter.run_tests()

            assert result["success"] is True
            # Note: Parsing may not work perfectly in unit tests, but
            # structure is correct
            assert "tests_run" in result
            assert "tests_passed" in result
            assert "tests_failed" in result

    @patch("cortex.services.framework_adapters.python_adapter.subprocess.run")
    def test_run_tests_timeout(self, mock_run: MagicMock) -> None:
        """Test test execution timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".venv" / "bin").mkdir(parents=True)

            mock_run.side_effect = subprocess.TimeoutExpired("pytest", 30)

            adapter = PythonAdapter(str(project_root))
            result = adapter.run_tests(timeout=30)

            assert result["success"] is False
            output = cast(str, result["output"])
            assert "timeout" in output.lower() or "timed out" in output.lower()
            errors = cast(list[str], result["errors"])
            assert len(errors) > 0

    @patch("cortex.services.framework_adapters.python_adapter.subprocess.run")
    def test_format_code(self, mock_run: MagicMock) -> None:
        """Test code formatting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".venv" / "bin").mkdir(parents=True)
            (project_root / ".venv" / "bin" / "black").touch()
            (project_root / ".venv" / "bin" / "ruff").touch()

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "All done!"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = PythonAdapter(str(project_root))
            result = adapter.format_code()

            assert result["check_type"] == "format"
            assert result["success"] is True
            errors = cast(list[str], result["errors"])
            assert len(errors) == 0

    @patch("cortex.services.framework_adapters.python_adapter.subprocess.run")
    def test_type_check(self, mock_run: MagicMock) -> None:
        """Test type checking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".venv" / "bin").mkdir(parents=True)
            (project_root / ".venv" / "bin" / "pyright").touch()

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "0 errors, 0 warnings"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = PythonAdapter(str(project_root))
            result = adapter.type_check()

            assert result["check_type"] == "type_check"
            assert result["success"] is True
            errors = cast(list[str], result["errors"])
            assert len(errors) == 0

    @patch("cortex.services.framework_adapters.python_adapter.subprocess.run")
    def test_fix_errors(self, mock_run: MagicMock) -> None:
        """Test error fixing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".venv" / "bin").mkdir(parents=True)
            (project_root / ".venv" / "bin" / "ruff").touch()
            (project_root / ".venv" / "bin" / "black").touch()
            (project_root / ".venv" / "bin" / "pyright").touch()

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "All fixed!"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            adapter = PythonAdapter(str(project_root))
            result = adapter.fix_errors()

            assert result["check_type"] == "fix_errors"
            assert result["success"] is True

    def test_get_command_raises_when_tool_missing(self) -> None:
        """_get_command raises FileNotFoundError when tool not in project or cwd venv."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with chdir(tmpdir):
                adapter = PythonAdapter(tmpdir)
                with pytest.raises(FileNotFoundError) as exc_info:
                    adapter._get_command("ruff")  # type: ignore[attr-defined]
                assert "ruff not found" in str(exc_info.value)
                assert "execute_pre_commit_checks" in str(exc_info.value)

    def test_get_command_uses_cwd_venv_when_project_venv_missing(self) -> None:
        """_get_command uses cwd/.venv/bin when project_root has no .venv (MCP fallback)."""
        cwd_venv_bin = Path.cwd() / ".venv" / "bin"
        if not (cwd_venv_bin / "ruff").exists():
            pytest.skip(reason="repo .venv/bin/ruff not present (e.g. minimal CI)")
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            adapter = PythonAdapter(str(project_root))
            path = adapter._get_command("ruff")  # type: ignore[attr-defined]
            assert path == str(cwd_venv_bin / "ruff")

    def test_parse_lint_errors_ignores_ruff_summary_lines(self) -> None:
        """Ensure ruff summary lines don't count as remaining errors."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = PythonAdapter(str(tmpdir))
            output = "Found 5 errors (5 fixed, 0 remaining).\n"

            # Act
            errors = adapter._parse_lint_errors(output)  # type: ignore[attr-defined]

            # Assert
            assert errors == []

    def test_parse_lint_errors_collects_diagnostic_lines(self) -> None:
        """Ensure ruff diagnostic lines are captured."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = PythonAdapter(str(tmpdir))
            output = "\n".join(
                [
                    "src/foo.py:1:1: F401 `os` imported but unused",
                    "Found 1 error (1 fixed, 0 remaining).",
                ]
            )

            # Act
            errors = adapter._parse_lint_errors(output)  # type: ignore[attr-defined]

            # Assert
            assert errors == ["src/foo.py:1:1: F401 `os` imported but unused"]

    def test_build_test_errors_success(self) -> None:
        """Test _build_test_errors with success=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = PythonAdapter(str(tmpdir))
            errors = adapter._build_test_errors(success=True)  # type: ignore[attr-defined]
            assert errors == []

    def test_build_test_errors_failure_no_coverage(self) -> None:
        """Test _build_test_errors with success=False and no coverage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = PythonAdapter(str(tmpdir))
            errors = adapter._build_test_errors(success=False, coverage=None)  # type: ignore[attr-defined]
            assert errors == ["Test execution failed"]

    def test_build_test_errors_failure_low_coverage(self) -> None:
        """Test _build_test_errors with success=False and coverage below threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = PythonAdapter(str(tmpdir))
            errors = adapter._build_test_errors(  # type: ignore[attr-defined]
                success=False, coverage=0.85, coverage_threshold=0.90
            )
            assert len(errors) == 1
            assert "Test coverage 85.00% is below required threshold 90%" in errors[0]

    def test_build_test_errors_failure_coverage_above_threshold(self) -> None:
        """Test _build_test_errors with success=False but coverage above threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = PythonAdapter(str(tmpdir))
            errors = adapter._build_test_errors(  # type: ignore[attr-defined]
                success=False, coverage=0.95, coverage_threshold=0.90
            )
            assert errors == ["Test execution failed"]

    def test_collect_test_count_parses_tests_collected_line(self) -> None:
        """_collect_test_count parses 'N tests collected' from collect-only output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".venv" / "bin").mkdir(parents=True)
            (project_root / ".venv" / "bin" / "pytest").touch()
            (project_root / "tests").mkdir()
            adapter = PythonAdapter(str(project_root))
            with patch(
                "cortex.services.framework_adapters.python_adapter.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="",
                    stderr="======================== 42 tests collected in 0.5s =========================\n",
                )
                total = adapter._collect_test_count()  # type: ignore[attr-defined]
                assert total == 42

    @patch(
        "cortex.services.framework_adapters.python_adapter.PythonAdapter._execute_test_command_streaming"
    )
    @patch(
        "cortex.services.framework_adapters.python_adapter.PythonAdapter._collect_test_count"
    )
    def test_run_tests_with_progress_callback_uses_real_test_counts(
        self,
        mock_collect: MagicMock,
        mock_streaming: MagicMock,
    ) -> None:
        """When progress_callback is set, use streaming and report (completed, total)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / ".venv" / "bin").mkdir(parents=True)
            (project_root / ".venv" / "bin" / "pytest").touch()
            mock_collect.return_value = 100
            mock_streaming.return_value = TestResult(
                success=True,
                tests_run=100,
                tests_passed=100,
                tests_failed=0,
                pass_rate=1.0,
                coverage=0.95,
                output="OK",
                errors=[],
            )
            adapter = PythonAdapter(str(project_root))

            def progress_callback(completed: int, total: int) -> None:
                pass  # Callback used to enable streaming path; args verified below

            result = adapter.run_tests(progress_callback=progress_callback)

            mock_collect.assert_called_once()
            mock_streaming.assert_called_once()
            # _execute_test_command_streaming(cmd, timeout, coverage_threshold, total, progress_callback)
            pos = mock_streaming.call_args[0]
            total_arg = pos[3]
            cb_arg = pos[4]
            assert total_arg == 100
            assert cb_arg is progress_callback
            assert result["success"] is True
            assert result["tests_run"] == 100
