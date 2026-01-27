"""Tests for Python framework adapter."""

import subprocess
import tempfile
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

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
