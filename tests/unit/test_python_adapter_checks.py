"""Tests for python_adapter_checks.py exception-handling branches."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from cortex.services.framework_adapters.python_adapter_checks import (
    run_black_formatting,
    run_ruff_fix,
    run_ruff_import_sorting,
    type_check_pyright_only,
    type_check_via_script,
)


def _get_cmd(name: str) -> str:
    return name


class TestRunBlackFormattingExceptions:
    """Exception branches for run_black_formatting."""

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_timeout_appends_timed_out_message(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = subprocess.TimeoutExpired("black", 60)
        errors: list[str] = []
        output_parts: list[str] = []
        # Act
        run_black_formatting(Path("/tmp"), _get_cmd, errors, output_parts)
        # Assert
        assert len(errors) == 1
        assert "timed out" in errors[0]

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_oserror_appends_formatting_error(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = OSError("no such file")
        errors: list[str] = []
        output_parts: list[str] = []
        # Act
        run_black_formatting(Path("/tmp"), _get_cmd, errors, output_parts)
        # Assert
        assert len(errors) == 1
        assert "Black formatting error" in errors[0]

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_unexpected_exception_appends_unexpected_message(
        self, mock_run: MagicMock
    ) -> None:
        # Arrange
        mock_run.side_effect = RuntimeError("boom")
        errors: list[str] = []
        output_parts: list[str] = []
        # Act
        run_black_formatting(Path("/tmp"), _get_cmd, errors, output_parts)
        # Assert
        assert len(errors) == 1
        assert "Unexpected black error" in errors[0]


class TestRunRuffImportSortingExceptions:
    """Exception branches for run_ruff_import_sorting."""

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_timeout_appends_timed_out_message(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = subprocess.TimeoutExpired("ruff", 60)
        errors: list[str] = []
        output_parts: list[str] = []
        # Act
        run_ruff_import_sorting(Path("/tmp"), _get_cmd, errors, output_parts)
        # Assert
        assert len(errors) == 1
        assert "timed out" in errors[0]

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_oserror_appends_sorting_error(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = OSError("no such file")
        errors: list[str] = []
        output_parts: list[str] = []
        # Act
        run_ruff_import_sorting(Path("/tmp"), _get_cmd, errors, output_parts)
        # Assert
        assert len(errors) == 1
        assert "Ruff import sorting error" in errors[0]

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_unexpected_exception_appends_unexpected_message(
        self, mock_run: MagicMock
    ) -> None:
        # Arrange
        mock_run.side_effect = RuntimeError("boom")
        errors: list[str] = []
        output_parts: list[str] = []
        # Act
        run_ruff_import_sorting(Path("/tmp"), _get_cmd, errors, output_parts)
        # Assert
        assert len(errors) == 1
        assert "Unexpected ruff import sorting error" in errors[0]


class TestTypeCheckViaScriptExceptions:
    """Exception branches for type_check_via_script."""

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_timeout_returns_failure(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = subprocess.TimeoutExpired("python", 300)
        # Act
        result = type_check_via_script(
            Path("/tmp"), Path("/tmp/.venv/bin"), Path("/script.py"), lambda s: []
        )
        # Assert
        assert result.success is False
        assert any("timed out" in e.lower() for e in result.errors)

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_oserror_returns_failure(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = OSError("no such file")
        # Act
        result = type_check_via_script(
            Path("/tmp"), Path("/tmp/.venv/bin"), Path("/script.py"), lambda s: []
        )
        # Assert
        assert result.success is False
        assert result.check_type == "type_check"

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_unexpected_exception_labels_error(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = RuntimeError("unexpected")
        # Act
        result = type_check_via_script(
            Path("/tmp"), Path("/tmp/.venv/bin"), Path("/script.py"), lambda s: []
        )
        # Assert
        assert result.success is False
        assert any("Unexpected type-check runner error" in e for e in result.errors)


class TestTypeCheckPyrightOnlyExceptions:
    """Exception branches for type_check_pyright_only."""

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_timeout_returns_failure(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = subprocess.TimeoutExpired("pyright", 300)
        # Act
        result = type_check_pyright_only(Path("/tmp"), _get_cmd, lambda s: [])
        # Assert
        assert result.success is False
        assert any("Pyright timed out" in e for e in result.errors)

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_oserror_returns_failure(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = OSError("not found")
        # Act
        result = type_check_pyright_only(Path("/tmp"), _get_cmd, lambda s: [])
        # Assert
        assert result.success is False
        assert result.check_type == "type_check"

    @patch("cortex.services.framework_adapters.python_adapter_checks.subprocess.run")
    def test_unexpected_exception_labels_error(self, mock_run: MagicMock) -> None:
        # Arrange
        mock_run.side_effect = RuntimeError("unexpected")
        # Act
        result = type_check_pyright_only(Path("/tmp"), _get_cmd, lambda s: [])
        # Assert
        assert result.success is False
        assert any("Unexpected pyright error" in e for e in result.errors)


class TestRunRuffFixExceptions:
    """Exception branches for run_ruff_fix."""

    @patch(
        "cortex.services.framework_adapters.python_adapter_checks.execute_ruff_fix_command"
    )
    def test_timeout_returns_lint_error(self, mock_fix: MagicMock) -> None:
        # Arrange
        mock_fix.side_effect = subprocess.TimeoutExpired("ruff", 300)
        # Act
        result = run_ruff_fix(Path("/tmp"), _get_cmd, lambda s: [])
        # Assert
        assert result.success is False
        assert result.check_type == "lint"
        assert any("timed out" in e.lower() and "300" in e for e in result.errors)

    @patch(
        "cortex.services.framework_adapters.python_adapter_checks.execute_ruff_fix_command"
    )
    def test_oserror_returns_lint_error(self, mock_fix: MagicMock) -> None:
        # Arrange
        mock_fix.side_effect = OSError("not found")
        # Act
        result = run_ruff_fix(Path("/tmp"), _get_cmd, lambda s: [])
        # Assert
        assert result.success is False
        assert result.check_type == "lint"

    @patch(
        "cortex.services.framework_adapters.python_adapter_checks.execute_ruff_fix_command"
    )
    def test_unexpected_exception_labels_error(self, mock_fix: MagicMock) -> None:
        # Arrange
        mock_fix.side_effect = RuntimeError("boom")
        # Act
        result = run_ruff_fix(Path("/tmp"), _get_cmd, lambda s: [])
        # Assert
        assert result.success is False
        assert any("Unexpected ruff fix error" in e for e in result.errors)
