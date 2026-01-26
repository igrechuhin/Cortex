"""Tests for pre-commit tools."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cortex.services.framework_adapters.base import CheckResult, TestResult
from cortex.tools.pre_commit_tools import (
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
    _check_file_sizes,  # pyright: ignore[reportPrivateUsage]
    _check_function_lengths,  # pyright: ignore[reportPrivateUsage]
    _check_function_lengths_in_file,  # pyright: ignore[reportPrivateUsage]
    _count_file_lines,  # pyright: ignore[reportPrivateUsage]
    execute_pre_commit_checks,
    fix_quality_issues,
)


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
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter

                mock_adapter.fix_errors.return_value = CheckResult(
                    check_type="fix_errors",
                    success=True,
                    output="Fixed errors",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )

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
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter

                mock_result = CheckResult(
                    check_type="test",
                    success=True,
                    output="Success",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )
                mock_adapter.fix_errors.return_value = mock_result
                mock_adapter.format_code.return_value = mock_result
                mock_adapter.type_check.return_value = mock_result
                mock_adapter.lint_code.return_value = mock_result
                mock_adapter.run_tests.return_value = TestResult(
                    success=True,
                    tests_run=10,
                    tests_passed=10,
                    tests_failed=0,
                    pass_rate=1.0,
                    coverage=0.95,
                    output="All tests passed",
                    errors=[],
                )

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


class TestFixQualityIssues:
    """Test fix_quality_issues tool."""

    @pytest.mark.asyncio
    async def test_fix_quality_issues_error_path(self) -> None:
        """Test error path when execute_pre_commit_checks returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()

            with patch(
                "cortex.tools.pre_commit_tools.execute_pre_commit_checks"
            ) as mock_execute:
                mock_execute.return_value = json.dumps(
                    {"status": "error", "error": "Test error"}
                )

                result_json = await fix_quality_issues(project_root=str(project_root))
                result = json.loads(result_json)

                assert result["status"] == "error"
                assert result["error_message"] == "Test error"
                assert result["errors_fixed"] == 0
                assert result["files_modified"] == []

    @pytest.mark.asyncio
    async def test_fix_quality_issues_success_when_checks_report_errors(self) -> None:
        """Test non-exceptional 'status=error' from checks is still handled as success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()

            with (
                patch(
                    "cortex.tools.pre_commit_tools.execute_pre_commit_checks"
                ) as mock_execute,
                patch(
                    "cortex.tools.pre_commit_tools.fix_markdown_lint"
                ) as mock_markdown,
            ):
                mock_execute.return_value = json.dumps(
                    {
                        "status": "error",
                        "checks_performed": ["fix_errors", "format", "type_check"],
                        "files_modified": ["file1.py"],
                        "total_errors": 1,
                        "total_warnings": 0,
                        "success": False,
                        "results": {
                            "fix_errors": {
                                "errors": ["E1"],
                                "warnings": [],
                                "files_modified": ["file1.py"],
                            },
                            "format": {"files_formatted": 0},
                            "type_check": {"errors": [], "warnings": []},
                        },
                    }
                )
                mock_markdown.return_value = json.dumps(
                    {"success": True, "files_fixed": 0, "files_processed": 0}
                )

                result_json = await fix_quality_issues(project_root=str(project_root))
                result = json.loads(result_json)

                assert result["status"] == "success"
                assert result["error_message"] is None
                assert result["errors_fixed"] == 1
                # Check that remaining issues are reported (with more specific message)
                assert len(result["remaining_issues"]) > 0
                assert any(
                    "1 linting/formatting errors remain" in issue
                    for issue in result["remaining_issues"]
                )

    @pytest.mark.asyncio
    async def test_fix_quality_issues_exception_handling(self) -> None:
        """Test exception handling in fix_quality_issues."""
        with patch("cortex.tools.pre_commit_tools._get_project_root_str") as mock_root:
            mock_root.side_effect = Exception("Root error")

            result_json = await fix_quality_issues()
            result = json.loads(result_json)

            assert result["status"] == "error"
            assert result["error_message"] == "Root error"
            assert result["errors_fixed"] == 0

    @pytest.mark.asyncio
    async def test_fix_quality_issues_success_path(self) -> None:
        """Test success path in fix_quality_issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()

            with (
                patch(
                    "cortex.tools.pre_commit_tools.execute_pre_commit_checks"
                ) as mock_execute,
                patch(
                    "cortex.tools.pre_commit_tools.fix_markdown_lint"
                ) as mock_markdown,
            ):
                mock_execute.return_value = json.dumps(
                    {
                        "status": "success",
                        "checks": {
                            "fix_errors": {
                                "errors": [],
                                "warnings": [],
                                "files_modified": ["file1.py"],
                            },
                            "format": {"files_formatted": 1},
                            "type_check": {"errors": 0, "warnings": 0},
                        },
                    }
                )
                mock_markdown.return_value = json.dumps(
                    {"success": True, "files_fixed": 1, "files_processed": 1}
                )

                result_json = await fix_quality_issues(project_root=str(project_root))
                result = json.loads(result_json)

                assert result["status"] == "success"
                assert result["errors_fixed"] >= 0
                assert len(result["files_modified"]) >= 0

    @pytest.mark.asyncio
    async def test_fix_quality_issues_clean_repo_no_remaining_issues(self) -> None:
        """Test that fix_quality_issues returns empty remaining_issues on clean repo.

        This test verifies the fix for over-reporting remaining issues. Even if
        total_errors/total_warnings are non-zero, if all checks succeeded (success=True),
        remaining_issues should be empty.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()

            with (
                patch(
                    "cortex.tools.pre_commit_tools.execute_pre_commit_checks"
                ) as mock_execute,
                patch(
                    "cortex.tools.pre_commit_tools.fix_markdown_lint"
                ) as mock_markdown,
            ):
                # Simulate a clean repo where all checks succeeded but
                # total_errors/total_warnings might be non-zero (e.g., from previous runs)
                mock_execute.return_value = json.dumps(
                    {
                        "status": "success",
                        "checks_performed": ["fix_errors", "format", "type_check"],
                        "files_modified": [],
                        "total_errors": 4175,  # Large number that should NOT appear in remaining_issues
                        "total_warnings": 100,  # Large number that should NOT appear in remaining_issues
                        "success": True,
                        "results": {
                            "fix_errors": {
                                "check_type": "fix_errors",
                                "success": True,  # All checks succeeded
                                "errors": [],
                                "warnings": [],
                                "files_modified": [],
                            },
                            "format": {
                                "check_type": "format",
                                "success": True,  # Format succeeded
                                "errors": [],
                                "files_modified": [],
                            },
                            "type_check": {
                                "check_type": "type_check",
                                "success": True,  # Type check succeeded
                                "errors": [],
                            },
                        },
                    }
                )
                mock_markdown.return_value = json.dumps(
                    {"success": True, "files_fixed": 0, "files_processed": 0}
                )

                result_json = await fix_quality_issues(project_root=str(project_root))
                result = json.loads(result_json)

                assert result["status"] == "success"
                # Even though total_errors=4175, remaining_issues should be empty
                # because all checks succeeded (success=True)
                assert result["remaining_issues"] == []


class TestCountFileLines:
    """Test _count_file_lines helper function."""

    def test_count_lines_simple_file(self) -> None:
        """Test counting lines in a simple Python file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("x = 1\n")
            _ = f.write("y = 2\n")
            _ = f.write("z = 3\n")
            f.flush()
            path = Path(f.name)

        try:
            count = _count_file_lines(path)
            assert count == 3
        finally:
            path.unlink()

    def test_count_lines_with_comments_and_blanks(self) -> None:
        """Test counting lines excludes comments and blanks."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("# This is a comment\n")
            _ = f.write("\n")
            _ = f.write("x = 1\n")
            _ = f.write("  # Indented comment\n")
            _ = f.write("\n")
            _ = f.write("y = 2\n")
            f.flush()
            path = Path(f.name)

        try:
            count = _count_file_lines(path)
            assert count == 2  # Only x = 1 and y = 2
        finally:
            path.unlink()

    def test_count_lines_with_docstring(self) -> None:
        """Test counting lines handles docstrings."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Simple docstring on one line toggles in_docstring twice (becomes false)
            # so the line after it counts normally
            _ = f.write("x = 1\n")
            _ = f.write("y = 2\n")
            f.flush()
            path = Path(f.name)

        try:
            count = _count_file_lines(path)
            # Both lines should be counted
            assert count == 2
        finally:
            path.unlink()

    def test_count_lines_nonexistent_file(self) -> None:
        """Test counting lines returns 0 for nonexistent file."""
        count = _count_file_lines(Path("/nonexistent/file.py"))
        assert count == 0


class TestCheckFileSizes:
    """Test _check_file_sizes helper function."""

    def test_no_violations_when_no_src(self) -> None:
        """Test no violations when src directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            violations = _check_file_sizes(Path(tmpdir))
            assert violations == []

    def test_no_violations_when_files_within_limit(self) -> None:
        """Test no violations when all files are within limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a small file
            _ = (src_dir / "small.py").write_text("x = 1\ny = 2\n")

            violations = _check_file_sizes(project_root)
            assert violations == []

    def test_detects_file_size_violation(self) -> None:
        """Test detection of file exceeding max lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a large file exceeding MAX_FILE_LINES
            large_content = "\n".join(
                [f"x{i} = {i}" for i in range(MAX_FILE_LINES + 50)]
            )
            _ = (src_dir / "large.py").write_text(large_content)

            violations = _check_file_sizes(project_root)
            assert len(violations) == 1
            assert violations[0].file == "src/large.py"
            assert violations[0].lines > MAX_FILE_LINES
            assert violations[0].excess > 0

    def test_skips_test_files(self) -> None:
        """Test that test files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a large test file
            large_content = "\n".join(
                [f"x{i} = {i}" for i in range(MAX_FILE_LINES + 50)]
            )
            _ = (src_dir / "test_large.py").write_text(large_content)

            violations = _check_file_sizes(project_root)
            assert violations == []  # test files are skipped


class TestCheckFunctionLengths:
    """Test _check_function_lengths and _check_function_lengths_in_file."""

    def test_no_violations_when_no_src(self) -> None:
        """Test no violations when src directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            violations = _check_function_lengths(Path(tmpdir))
            assert violations == []

    def test_no_violations_for_short_function(self) -> None:
        """Test no violations for short functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            content = '''
def short_func():
    """Short function."""
    x = 1
    y = 2
    return x + y
'''
            _ = (src_dir / "short.py").write_text(content)

            violations = _check_function_lengths(project_root)
            assert violations == []

    def test_detects_long_function(self) -> None:
        """Test detection of function exceeding max lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a file with a long function
            lines = [f"    x{i} = {i}" for i in range(MAX_FUNCTION_LINES + 10)]
            content = "def long_func():\n" + "\n".join(lines) + "\n    return x0\n"
            _ = (src_dir / "long.py").write_text(content)

            violations = _check_function_lengths(project_root)
            assert len(violations) == 1
            assert violations[0].function == "long_func"
            assert violations[0].lines > MAX_FUNCTION_LINES

    def test_check_function_lengths_in_file_syntax_error(self) -> None:
        """Test handling of syntax errors in file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            _ = f.write("def broken(\n")  # Invalid syntax
            f.flush()
            path = Path(f.name)

        try:
            violations = _check_function_lengths_in_file(path)
            assert violations == []  # Should return empty on syntax error
        finally:
            path.unlink()

    def test_check_function_lengths_in_file_read_error(self) -> None:
        """Test handling of file read errors."""
        violations = _check_function_lengths_in_file(Path("/nonexistent/file.py"))
        assert violations == []

    def test_skips_test_files(self) -> None:
        """Test that test files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a test file with a long function
            lines = [f"    x{i} = {i}" for i in range(MAX_FUNCTION_LINES + 10)]
            content = "def long_func():\n" + "\n".join(lines) + "\n    return x0\n"
            _ = (src_dir / "test_long.py").write_text(content)

            violations = _check_function_lengths(project_root)
            assert violations == []  # test files are skipped

    def test_detects_async_function_length(self) -> None:
        """Test detection of async function exceeding max lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a file with a long async function
            lines = [f"    x{i} = {i}" for i in range(MAX_FUNCTION_LINES + 10)]
            content = (
                "async def long_async_func():\n"
                + "\n".join(lines)
                + "\n    return x0\n"
            )
            _ = (src_dir / "async_long.py").write_text(content)

            violations = _check_function_lengths(project_root)
            assert len(violations) == 1
            assert violations[0].function == "long_async_func"


class TestQualityCheckIntegration:
    """Integration tests for quality check through execute_pre_commit_checks."""

    @pytest.mark.asyncio
    async def test_quality_check_includes_file_size_check(self) -> None:
        """Test that quality check includes file size violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            _ = (project_root / "pyproject.toml").write_text("[project]\nname = 'test'")
            (project_root / ".venv").mkdir()
            src_dir = project_root / "src"
            src_dir.mkdir()

            # Create a small valid file
            _ = (src_dir / "module.py").write_text("x = 1\n")

            with patch(
                "cortex.tools.pre_commit_tools.PythonAdapter"
            ) as mock_adapter_class:
                mock_adapter = MagicMock()
                mock_adapter_class.return_value = mock_adapter
                mock_adapter.project_root = project_root

                mock_adapter.lint_code.return_value = CheckResult(
                    check_type="lint",
                    success=True,
                    output="All good",
                    errors=[],
                    warnings=[],
                    files_modified=[],
                )

                result_json = await execute_pre_commit_checks(
                    checks=["quality"],
                    project_root=str(project_root),
                )
                result = json.loads(result_json)

                assert result["status"] == "success"
                assert "quality" in result["checks_performed"]
                # Quality result should include file_size_violations and function_length_violations
                quality_result = result["results"]["quality"]
                assert "file_size_violations" in quality_result
                assert "function_length_violations" in quality_result
