"""Tests for pre-commit tools."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.tools.pre_commit_tools import execute_pre_commit_checks


class TestExecutePreCommitChecks:
    """Test execute_pre_commit_checks tool."""

    @pytest.mark.asyncio
    async def test_detect_language_error_when_no_language_detected(self) -> None:
        """Test error when language cannot be detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result_json = await execute_pre_commit_checks(
                checks=["fix_errors"],
                project_root=str(tmpdir),
            )
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert "Could not detect project language" in result["error"]

    @pytest.mark.asyncio
    async def test_error_for_unsupported_language(self) -> None:
        """Test error for unsupported language."""
        result_json = await execute_pre_commit_checks(
            checks=["fix_errors"],
            language="rust",
        )
        result = json.loads(result_json)

        assert result["status"] == "error"
        assert "not yet supported" in result["error"]

    @pytest.mark.asyncio
    async def test_success_with_python_project(self) -> None:
        """Test success with Python project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter

                mock_fix_result = {
                    "check_type": "fix_errors",
                    "success": True,
                    "output": "Fixed errors",
                    "errors": [],
                    "warnings": [],
                    "files_modified": [],
                }
                mock_adapter.fix_errors.return_value = mock_fix_result

                result_json = await execute_pre_commit_checks(
                    checks=["fix_errors"],
                    project_root=str(project_root),
                )
                result = json.loads(result_json)

                assert result["status"] == "success"
                assert result["language"] == "python"
                assert "fix_errors" in result["checks_performed"]
                assert result["total_errors"] == 0

    @pytest.mark.asyncio
    async def test_execute_all_checks_by_default(self) -> None:
        """Test that all checks are executed when checks parameter is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter

                mock_result = {
                    "check_type": "test",
                    "success": True,
                    "output": "Success",
                    "errors": [],
                    "warnings": [],
                    "files_modified": [],
                }
                mock_adapter.fix_errors.return_value = mock_result
                mock_adapter.format_code.return_value = mock_result
                mock_adapter.type_check.return_value = mock_result
                mock_adapter.lint_code.return_value = mock_result
                mock_adapter.run_tests.return_value = {
                    "success": True,
                    "tests_run": 10,
                    "tests_passed": 10,
                    "tests_failed": 0,
                    "pass_rate": 100.0,
                    "coverage": 0.95,
                    "output": "All tests passed",
                    "errors": [],
                }

                result_json = await execute_pre_commit_checks(
                    checks=None,
                    project_root=str(project_root),
                )
                result = json.loads(result_json)

                assert result["status"] == "success"
                assert len(result["checks_performed"]) == 5
                assert "fix_errors" in result["checks_performed"]
                assert "format" in result["checks_performed"]
                assert "type_check" in result["checks_performed"]
                assert "quality" in result["checks_performed"]
                assert "tests" in result["checks_performed"]

    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        """Test error handling in tool."""
        with patch("cortex.tools.pre_commit_tools.get_project_root") as mock_root:
            mock_root.side_effect = Exception("Test error")

            result_json = await execute_pre_commit_checks(checks=["fix_errors"])
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert "Test error" in result["error"]
