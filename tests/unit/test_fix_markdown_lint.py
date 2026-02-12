"""
Unit tests for cortex.tools.markdown_operations.py script.
"""

import json

# Import the MCP tool functions (private functions are tested)
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# pyright: reportPrivateUsage=false
from cortex.core.models import GitCommandResult
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.tools.markdown_lint_responses import create_empty_success_response
from cortex.tools.markdown_operations import (
    _find_markdownlint_command,
    _get_all_markdown_files,  # type: ignore[reportPrivateUsage]
    _get_modified_markdown_files,
    _run_command,
    _run_markdownlint_fix,
)


class TestRunCommand:
    """Test _run_command function."""

    @pytest.mark.asyncio
    async def test_run_command_success(self):
        """Test successful command execution."""
        # Arrange
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(b"output", b""))
        mock_process.returncode = 0

        async def mock_create_subprocess(*args: object, **kwargs: object) -> Mock:
            """Mock create_subprocess_exec."""
            return mock_process

        with patch(
            "cortex.tools.markdown_operations.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ):
            # Act
            result = await _run_command(["test", "command"])

            # Assert
            assert result.success is True
            assert result.stdout == "output"
            assert result.stderr == ""
            assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_run_command_failure(self):
        """Test command execution failure."""
        # Arrange
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"error message"))
        mock_process.returncode = 1

        async def mock_create_subprocess(*args: object, **kwargs: object) -> Mock:
            """Mock create_subprocess_exec."""
            return mock_process

        with patch(
            "cortex.tools.markdown_operations.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ):
            # Act
            result = await _run_command(["test", "command"])

            # Assert
            assert result.success is False
            assert result.stdout == ""
            assert result.stderr == "error message"
            assert result.returncode == 1

    @pytest.mark.asyncio
    async def test_run_command_timeout(self):
        """Test command timeout handling."""

        # Arrange - Create mock that raises TimeoutError (Python 3.13+
        # asyncio.timeout raises TimeoutError)
        async def slow_subprocess(*args: object, **kwargs: object) -> Mock:
            """Mock that simulates a long-running process."""
            raise TimeoutError("Operation timed out")

        with patch(
            "cortex.tools.markdown_operations.asyncio.create_subprocess_exec",
            side_effect=slow_subprocess,
        ):
            # Act
            result = await _run_command(["test", "command"], timeout=5)

            # Assert
            assert result.success is False
            assert result.error is not None
            assert "timed out" in result.error
            assert result.returncode == -1

    @pytest.mark.asyncio
    async def test_run_command_exception(self):
        """Test command execution exception handling."""
        # Arrange
        with patch(
            "cortex.tools.markdown_operations.asyncio.create_subprocess_exec",
            side_effect=Exception("Test error"),
        ):
            # Act
            result = await _run_command(["test", "command"])

            # Assert
            assert result.success is False
            assert result.error is not None
            assert "Test error" in result.error
            assert result.returncode == -1


class TestGetModifiedMarkdownFiles:
    """Test _get_modified_markdown_files function."""

    @pytest.mark.asyncio
    async def test_get_modified_files_from_diff(self, tmp_path: Path):
        """Test getting modified files from git diff."""
        # Arrange
        project_root = tmp_path
        diff_output = "file1.md\nfile2.mdc\nfile3.txt"

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = [
                GitCommandResult(
                    success=True, stdout=diff_output, stderr="", returncode=0
                ),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
            ]

            # Act
            files = await _get_modified_markdown_files(project_root)

            # Assert
            assert len(files) == 2
            assert any("file1.md" in str(f) for f in files)
            assert any("file2.mdc" in str(f) for f in files)
            assert not any("file3.txt" in str(f) for f in files)

    @pytest.mark.asyncio
    async def test_get_modified_files_from_cached(self, tmp_path: Path):
        """Test getting staged files from git diff --cached."""
        # Arrange
        project_root = tmp_path
        cached_output = "staged1.md\nstaged2.mdc"

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = [
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
                GitCommandResult(
                    success=True, stdout=cached_output, stderr="", returncode=0
                ),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
            ]

            # Act
            files = await _get_modified_markdown_files(project_root)

            # Assert
            assert len(files) == 2
            assert any("staged1.md" in str(f) for f in files)
            assert any("staged2.mdc" in str(f) for f in files)

    @pytest.mark.asyncio
    async def test_get_modified_files_include_untracked(self, tmp_path: Path):
        """Test including untracked files."""
        # Arrange
        project_root = tmp_path
        status_output = "?? untracked1.md\n?? untracked2.mdc\n M modified.txt"

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = [
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
                GitCommandResult(
                    success=True, stdout=status_output, stderr="", returncode=0
                ),
            ]

            # Act
            files = await _get_modified_markdown_files(
                project_root, include_untracked=True
            )

            # Assert
            assert len(files) == 2
            assert any("untracked1.md" in str(f) for f in files)
            assert any("untracked2.mdc" in str(f) for f in files)

    @pytest.mark.asyncio
    async def test_get_modified_files_no_files(self, tmp_path: Path):
        """Test when no modified files exist."""
        # Arrange
        project_root = tmp_path

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = [
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
            ]

            # Act
            files = await _get_modified_markdown_files(project_root)

            # Assert
            assert len(files) == 0

    @pytest.mark.asyncio
    async def test_get_modified_files_deduplicates(self, tmp_path: Path):
        """Test that duplicate files are deduplicated."""
        # Arrange
        project_root = tmp_path
        diff_output = "file1.md"
        cached_output = "file1.md"

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = [
                GitCommandResult(
                    success=True, stdout=diff_output, stderr="", returncode=0
                ),
                GitCommandResult(
                    success=True, stdout=cached_output, stderr="", returncode=0
                ),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
            ]

            # Act
            files = await _get_modified_markdown_files(project_root)

            # Assert
            assert len(files) == 1
            assert "file1.md" in str(files[0])


class TestCheckMarkdownlintAvailable:
    """Test _find_markdownlint_command function."""

    @pytest.mark.asyncio
    async def test_markdownlint_available(self):
        """Test when markdownlint is available via PATH."""
        # Arrange
        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=True,
                stdout="markdownlint-cli2 version 1.0.0",
                stderr="",
                returncode=0,
            )

            # Act
            result = await _find_markdownlint_command()

            # Assert
            assert result == ["markdownlint-cli2"]
            mock_run.assert_called_once_with(["markdownlint-cli2", "--version"])

    @pytest.mark.asyncio
    async def test_markdownlint_available_via_npx(self):
        """Test when markdownlint is available via npx."""
        # Arrange
        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            # First call fails (not in PATH), second succeeds (npx)
            mock_run.side_effect = [
                GitCommandResult(
                    success=False,
                    stdout="",
                    stderr="command not found",
                    returncode=127,
                    error="command not found",
                ),
                GitCommandResult(
                    success=True,
                    stdout="markdownlint-cli2 version 1.0.0",
                    stderr="",
                    returncode=0,
                ),
            ]

            # Act
            result = await _find_markdownlint_command()

            # Assert
            assert result == ["npx", "--yes", "markdownlint-cli2"]
            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_markdownlint_not_available(self):
        """Test when markdownlint is not available."""
        # Arrange
        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            # Both calls fail
            mock_run.return_value = GitCommandResult(
                success=False,
                stdout="",
                stderr="command not found",
                returncode=127,
                error="command not found",
            )

            # Act
            result = await _find_markdownlint_command()

            # Assert
            assert result is None
            assert mock_run.call_count == 2  # Should try both markdownlint-cli2 and npx


class TestRunMarkdownlintFix:
    """Test _run_markdownlint_fix function."""

    @pytest.mark.asyncio
    async def test_run_markdownlint_fix_success(self, tmp_path: Path):
        """Test successful markdownlint fix."""
        # Arrange
        project_root = tmp_path
        file_path = tmp_path / "test.md"
        _ = file_path.write_text("# Test\n\nContent")

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=True, stdout="Fixed: test.md", stderr="", returncode=0
            )

            # Act
            result = await _run_markdownlint_fix(
                file_path, project_root, ["markdownlint-cli2"], dry_run=False
            )

            # Assert
            assert result.fixed is True
            assert result.file == "test.md"
            assert result.error_message is None
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_markdownlint_fix_dry_run(self, tmp_path: Path):
        """Test markdownlint dry run (no fix)."""
        # Arrange
        project_root = tmp_path
        file_path = tmp_path / "test.md"
        _ = file_path.write_text("# Test\n\nContent")

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=True,
                stdout="test.md: 5:1 MD022/blanks-around-headings",
                stderr="",
                returncode=0,
            )

            # Act
            result = await _run_markdownlint_fix(
                file_path, project_root, ["markdownlint-cli2"], dry_run=True
            )

            # Assert
            assert result.fixed is False  # Dry run doesn't fix
            assert result.file == "test.md"
            assert len(result.errors) > 0
            mock_run.assert_called_once()
            # Verify --fix was not included in command
            call_args = mock_run.call_args[0][0]
            assert "--fix" not in call_args

    @pytest.mark.asyncio
    async def test_run_markdownlint_fix_with_errors(self, tmp_path: Path):
        """Test markdownlint with unfixable errors."""
        # Arrange
        project_root = tmp_path
        file_path = tmp_path / "test.md"
        _ = file_path.write_text("# Test\n\nContent")

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=False,
                stdout="",
                stderr="test.md: 1:1 MD036/no-emphasis-as-heading",
                returncode=1,
                error="markdownlint failed",
            )

            # Act
            result = await _run_markdownlint_fix(
                file_path, project_root, ["markdownlint-cli2"], dry_run=False
            )

            # Assert
            assert result.fixed is False
            assert result.file == "test.md"
            assert result.error_message is not None
            assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_run_markdownlint_fix_timeout(self, tmp_path: Path):
        """Test markdownlint timeout handling."""
        # Arrange
        project_root = tmp_path
        file_path = tmp_path / "test.md"
        _ = file_path.write_text("# Test\n\nContent")

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=False,
                error="Command timed out after 60s",
                stdout="",
                stderr="",
                returncode=-1,
            )

            # Act
            result = await _run_markdownlint_fix(
                file_path, project_root, ["markdownlint-cli2"], dry_run=False
            )

            # Assert
            assert result.fixed is False
            assert result.error_message is not None
            assert "timed out" in result.error_message

    @pytest.mark.asyncio
    async def test_run_markdownlint_fix_parses_errors(self, tmp_path: Path):
        """Test that markdownlint errors are parsed correctly."""
        # Arrange
        project_root = tmp_path
        file_path = tmp_path / "test.md"
        _ = file_path.write_text("# Test\n\nContent")

        stderr_output = (
            "test.md: 1:1 MD022/blanks-around-headings\n"
            "test.md: 3:1 MD032/blanks-around-lists"
        )

        with patch(
            "cortex.tools.markdown_operations._run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=False,
                stdout="",
                stderr=stderr_output,
                returncode=1,
                error="markdownlint failed",
            )

            # Act
            result = await _run_markdownlint_fix(
                file_path, project_root, ["markdownlint-cli2"], dry_run=False
            )

            # Assert
            assert len(result.errors) == 2
            assert any("MD022" in e for e in result.errors)
            assert any("MD032" in e for e in result.errors)


class TestFixMarkdownLintTool:
    """Test fix_markdown_lint MCP tool."""

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_success(self, tmp_path: Path):
        """Test successful markdown lint fixing."""
        # Arrange
        from cortex.tools.markdown_operations import fix_markdown_lint

        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test\n\nContent")

        with (
            patch(
                "cortex.tools.markdown_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.markdown_operations._run_command",
                new_callable=AsyncMock,
            ) as mock_run,
            patch(
                "cortex.tools.markdown_operations._find_markdownlint_command",
                new_callable=AsyncMock,
                return_value=["markdownlint-cli2"],
            ),
        ):
            mock_run.side_effect = [
                GitCommandResult(
                    success=True, stdout="", stderr="", returncode=0
                ),  # git check
                GitCommandResult(
                    success=True, stdout="test.md", stderr="", returncode=0
                ),  # git diff
                GitCommandResult(
                    success=True, stdout="", stderr="", returncode=0
                ),  # git diff cached
                GitCommandResult(
                    success=True, stdout="Fixed", stderr="", returncode=0
                ),  # markdownlint
            ]

            # Act
            result_str = await fix_markdown_lint()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert result["files_processed"] == 1
            assert result["files_fixed"] == 1

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_not_git_repo(self, tmp_path: Path):
        """Test error when not in git repository."""
        # Arrange
        from cortex.tools.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.markdown_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.markdown_operations._run_command",
                new_callable=AsyncMock,
                return_value=GitCommandResult(
                    success=False,
                    stdout="",
                    stderr="",
                    returncode=128,
                    error="not a git repository",
                ),
            ),
        ):
            # Act
            result_str = await fix_markdown_lint()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is False
            assert "git repository" in result["error_message"]

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_not_git_repo_with_none_project_root_includes_hint(
        self, tmp_path: Path
    ):
        """When project_root is None and git check fails, error includes MCP hint."""
        from cortex.tools.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.markdown_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.markdown_operations._run_command",
                new_callable=AsyncMock,
                return_value=GitCommandResult(
                    success=False,
                    stdout="",
                    stderr="",
                    returncode=128,
                    error="not a git repository",
                ),
            ),
        ):
            result_str = await fix_markdown_lint()
            result = json.loads(result_str)
            assert result["success"] is False
            assert "Not in a git repository" in result["error_message"]
            assert (
                "MCP client" in result["error_message"]
                or "workspace" in result["error_message"]
            )

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_markdownlint_not_available(self, tmp_path: Path):
        """Test error when markdownlint-cli2 is not available."""
        # Arrange
        from cortex.tools.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.markdown_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.markdown_operations._run_command",
                new_callable=AsyncMock,
            ) as mock_run,
            patch(
                "cortex.tools.markdown_operations._find_markdownlint_command",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_run.side_effect = [
                GitCommandResult(
                    success=True, stdout="", stderr="", returncode=0
                ),  # git check
            ]

            # Act
            result_str = await fix_markdown_lint()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is False
            assert "markdownlint-cli2" in result["error_message"]

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_no_files(self, tmp_path: Path):
        """Test when no modified files found."""
        # Arrange
        from cortex.tools.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.markdown_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.markdown_operations._run_command",
                new_callable=AsyncMock,
            ) as mock_run,
            patch(
                "cortex.tools.markdown_operations._find_markdownlint_command",
                new_callable=AsyncMock,
                return_value=["markdownlint-cli2"],
            ),
            patch(
                "cortex.tools.markdown_operations._get_modified_markdown_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            mock_run.return_value = GitCommandResult(
                success=True, stdout="", stderr="", returncode=0
            )

            # Act
            result_str = await fix_markdown_lint()
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert result["files_processed"] == 0

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_exception(self, tmp_path: Path):
        """Test exception handling (e.g. from validation or later step)."""
        from cortex.tools.markdown_operations import fix_markdown_lint

        with patch(
            "cortex.tools.markdown_operations._validate_markdown_prerequisites",
            new_callable=AsyncMock,
            side_effect=ValueError("Test error"),
        ):
            result_str = await fix_markdown_lint()
            result = json.loads(result_str)
            assert result["success"] is False
            assert "Test error" in result["error_message"]

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_check_all_files_caps_list(self, tmp_path: Path):
        """Test that check_all_files=True caps files at MARKDOWN_LINT_MAX_FILES."""
        # Arrange
        from cortex.core.constants import MARKDOWN_LINT_MAX_FILES_WHEN_CHECK_ALL
        from cortex.tools.markdown_operations import fix_markdown_lint

        excess = 100
        many_files = [
            tmp_path / f"f{i}.md"
            for i in range(MARKDOWN_LINT_MAX_FILES_WHEN_CHECK_ALL + excess)
        ]
        for p in many_files:
            _ = p.write_text("# x\n")
        run_markdownlint_with_cache_called_with: list[list[Path]] = []

        async def capture_run_markdownlint_with_cache(
            root_path: Path,
            files: list[Path],
            markdownlint_cmd: list[str],
            config_path: Path | None,
            dry_run: bool,
            ctx: object = None,
        ) -> str:
            run_markdownlint_with_cache_called_with.append(files)
            return create_empty_success_response()

        with (
            patch(
                "cortex.tools.markdown_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.markdown_operations._validate_markdown_prerequisites",
                new_callable=AsyncMock,
                return_value=(None, ["markdownlint-cli2"], None),
            ),
            patch(
                "cortex.tools.markdown_operations._get_markdown_files_to_process",
                new_callable=AsyncMock,
                return_value=many_files,
            ),
            patch(
                "cortex.tools.markdown_operations._run_markdownlint_with_cache",
                side_effect=capture_run_markdownlint_with_cache,
            ),
        ):
            # Act
            result_str = await fix_markdown_lint(check_all_files=True)
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            assert len(run_markdownlint_with_cache_called_with) == 1
            passed_files = run_markdownlint_with_cache_called_with[0]
            assert len(passed_files) == MARKDOWN_LINT_MAX_FILES_WHEN_CHECK_ALL


class TestFixMarkdownLintContextLogging:
    """Test fix_markdown_lint Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, fix_markdown_lint logs start and completion."""
        # Arrange
        from cortex.tools.markdown_operations import fix_markdown_lint

        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.markdown_operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.markdown_operations.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.markdown_operations._run_command",
                new_callable=AsyncMock,
            ) as mock_run,
            patch(
                "cortex.tools.markdown_operations._find_markdownlint_command",
                new_callable=AsyncMock,
                return_value=["markdownlint-cli2"],
            ),
            patch(
                "cortex.tools.markdown_operations._get_markdown_files_to_process",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            mock_run.return_value = GitCommandResult(
                success=True, stdout="", stderr="", returncode=0
            )

            # Act
            result_str = await fix_markdown_lint(ctx=mock_ctx)
            result = json.loads(result_str)

            # Assert
            assert result["success"] is True
            args_list = [c[0] for c in mock_log.call_args_list]
            levels_and_messages = [(a[1], a[2]) for a in args_list]
            assert ("info", "fix_markdown_lint: starting") in levels_and_messages
            assert ("info", "fix_markdown_lint: completed") in levels_and_messages

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_calls_log_client_error_on_exception_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When impl raises and ctx is passed, fix_markdown_lint logs error."""
        from cortex.tools.markdown_operations import fix_markdown_lint

        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.markdown_operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.markdown_operations._validate_markdown_prerequisites",
                new_callable=AsyncMock,
                side_effect=ValueError("Test error"),
            ),
        ):
            result_str = await fix_markdown_lint(ctx=mock_ctx)
            result = json.loads(result_str)
            assert result["success"] is False
            assert any(
                c[0][1] == "error" and "fix_markdown_lint: failed:" in str(c[0][2])
                for c in mock_log.call_args_list
                if len(c[0]) >= 3
            )


class TestHelperFunctions:
    """Test helper functions in markdown_operations."""

    def test_parse_git_output(self, tmp_path: Path):
        """Test _parse_git_output helper."""
        from cortex.tools.markdown_operations import (
            _parse_git_output,  # type: ignore[reportPrivateUsage]
        )

        files: list[Path] = []
        stdout = "file1.md\nfile2.md\nfile3.txt"
        _parse_git_output(stdout, tmp_path, files)

        assert len(files) == 2
        assert any("file1.md" in str(f) for f in files)
        assert any("file2.md" in str(f) for f in files)

    def test_parse_untracked_files(self, tmp_path: Path):
        """Test _parse_untracked_files helper."""
        from cortex.tools.markdown_operations import (
            _parse_untracked_files,  # type: ignore[reportPrivateUsage]
        )

        files: list[Path] = []
        stdout = "?? file1.md\n?? file2.mdc\n?? file3.txt"
        _parse_untracked_files(stdout, tmp_path, files)

        assert len(files) == 2
        assert any("file1.md" in str(f) for f in files)
        assert any("file2.mdc" in str(f) for f in files)

    def test_parse_markdownlint_errors(self):
        """Test _parse_markdownlint_errors helper."""
        from cortex.tools.markdown_operations import (
            _parse_markdownlint_errors,  # type: ignore[reportPrivateUsage]
        )

        stderr = "file.md: 1:1 MD022\nmarkdownlint-cli2 version\nfile.md: 2:1 MD032"
        errors = _parse_markdownlint_errors(stderr)

        assert len(errors) == 2
        assert any("MD022" in e for e in errors)


class TestFixMarkdownLintErrorHandling:
    """Test error handling improvements for Phase 59 (connection closed fix)."""

    @pytest.mark.asyncio
    async def test_get_all_markdown_files_handles_thread_exception(
        self, tmp_path: Path
    ):
        """Test that _get_all_markdown_files handles exceptions from thread execution."""
        from cortex.tools.markdown_operations import (
            _get_all_markdown_files,  # type: ignore[reportPrivateUsage]
        )

        with (
            patch(
                "cortex.tools.markdown_operations.asyncio.to_thread",
                new_callable=AsyncMock,
                side_effect=OSError("File system error"),
            ) as mock_thread,
            patch(
                "cortex.tools.markdown_operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
        ):
            # Act
            result = await _get_all_markdown_files(tmp_path)

            # Assert
            assert result == []
            mock_thread.assert_called_once()
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[1] == "error"
            assert "Failed to collect markdown files" in call_args[2]

    @pytest.mark.asyncio
    async def test_save_markdown_lint_index_handles_cache_write_failure(
        self, tmp_path: Path
    ):
        """Test that save_markdown_lint_index handles cache write failures gracefully."""
        from cortex.core.exceptions import FileLockTimeoutError
        from cortex.tools.markdown_lint_cache import (
            MarkdownLintIndex,
            save_markdown_lint_index,
        )

        index = MarkdownLintIndex()
        with (
            patch(
                "cortex.tools.markdown_lint_cache.write_cache_json",
                new_callable=AsyncMock,
                side_effect=FileLockTimeoutError("markdown-lint-index.json", 30),
            ) as mock_write,
            patch(
                "cortex.tools.markdown_lint_cache.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
        ):
            # Act - should not raise
            await save_markdown_lint_index(tmp_path, index)

            # Assert
            mock_write.assert_called_once()
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[1] == "warning"
            assert "Failed to save markdown lint cache" in call_args[2]

    @pytest.mark.asyncio
    async def test_run_markdownlint_with_cache_handles_cache_load_failure(
        self, tmp_path: Path
    ):
        """Test that _run_markdownlint_with_cache handles cache load failures."""
        from cortex.core.exceptions import FileLockTimeoutError
        from cortex.tools.markdown_operations import (
            _run_markdownlint_with_cache,  # type: ignore[reportPrivateUsage]
        )

        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test\n\nContent")

        with (
            patch(
                "cortex.tools.markdown_lint_cache.load_markdown_lint_index",
                new_callable=AsyncMock,
                side_effect=FileLockTimeoutError("markdown-lint-index.json", 30),
            ),
            patch(
                "cortex.tools.markdown_lint_cache.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.markdown_operations._run_markdownlint_for_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "cortex.tools.markdown_operations._filter_files_for_linting",
                new_callable=AsyncMock,
                return_value=([], [], {}),
            ),
        ):
            # Act - should not crash, should return valid response
            result_str = await _run_markdownlint_with_cache(
                tmp_path,
                [test_file],
                ["markdownlint-cli2"],
                None,
                False,
                ctx=None,
            )

            # Assert
            result = json.loads(result_str)
            assert result["success"] is True
            # Should have logged warning about cache load failure
            assert any(
                "warning" in str(c[0][1])
                and "Failed to load markdown lint cache" in str(c[0][2])
                for c in mock_log.call_args_list
            )

    @pytest.mark.asyncio
    async def test_run_markdownlint_with_cache_handles_cache_update_failure(
        self, tmp_path: Path
    ):
        """Test that _run_markdownlint_with_cache handles cache update failures."""
        from cortex.core.exceptions import FileLockTimeoutError
        from cortex.tools.markdown_operations import (
            FileResult,  # type: ignore[reportPrivateUsage]
            _run_markdownlint_with_cache,  # type: ignore[reportPrivateUsage]
        )

        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test\n\nContent")

        results = [
            FileResult(
                file="test.md",
                fixed=True,
                errors=[],
                error_message=None,
            )
        ]

        with (
            patch(
                "cortex.tools.markdown_operations.load_markdown_lint_index_safe",
                new_callable=AsyncMock,
                return_value=type("obj", (object,), {"files": {}})(),
            ),
            patch(
                "cortex.tools.markdown_operations._filter_files_for_linting",
                new_callable=AsyncMock,
                return_value=([test_file], [], {"test.md": "hash123"}),
            ),
            patch(
                "cortex.tools.markdown_operations._run_markdownlint_for_files",
                new_callable=AsyncMock,
                return_value=results,
            ),
            patch(
                "cortex.tools.markdown_operations._update_markdown_lint_cache_from_results",
                new_callable=AsyncMock,
                side_effect=FileLockTimeoutError("markdown-lint-index.json", 30),
            ),
            patch(
                "cortex.tools.markdown_operations.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
        ):
            # Act - should not crash, should return valid response
            result_str = await _run_markdownlint_with_cache(
                tmp_path,
                [test_file],
                ["markdownlint-cli2"],
                None,
                False,
                ctx=None,
            )

            # Assert
            result = json.loads(result_str)
            assert result["success"] is True
            assert result["files_processed"] == 1
            # Should have logged warning about cache update failure
            assert any(
                "warning" in str(c[0][1])
                and "Failed to update markdown lint cache" in str(c[0][2])
                for c in mock_log.call_args_list
            )

    def test_parse_markdownlint_output(self):
        """Test _parse_markdownlint_output helper."""
        from cortex.tools.markdown_operations import (
            _parse_markdownlint_output,  # type: ignore[reportPrivateUsage]
        )

        stdout = "Fixed: file.md\nFixed: file2.md"
        errors = _parse_markdownlint_output(stdout)

        assert len(errors) == 2
        assert "file.md" in errors[0]
        assert "file2.md" in errors[1]

    def test_is_cached_clean_entry(self) -> None:
        """Test _is_cached_clean_entry helper for cache reuse logic."""
        from cortex.tools.markdown_operations import (  # type: ignore[reportPrivateUsage]
            _is_cached_clean_entry,
        )

        assert _is_cached_clean_entry("sha256:abc", "sha256:abc", dry_run=False) is True
        assert (
            _is_cached_clean_entry("sha256:abc", "sha256:xyz", dry_run=False) is False
        )
        assert _is_cached_clean_entry("sha256:abc", "sha256:abc", dry_run=True) is False
        assert _is_cached_clean_entry(None, "sha256:abc", dry_run=False) is False

    @pytest.mark.asyncio
    async def test_compute_file_hashes_parallel(self, tmp_path: Path) -> None:
        """_compute_file_hashes returns rel_path -> hash for multiple files."""
        from cortex.tools.markdown_operations import (  # type: ignore[reportPrivateUsage]
            _compute_file_hashes,
        )

        _ = (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
        _ = (tmp_path / "b.md").write_text("# B\n", encoding="utf-8")
        files = [tmp_path / "a.md", tmp_path / "b.md"]

        hashes = await _compute_file_hashes(files, tmp_path)

        assert len(hashes) == 2
        assert "a.md" in hashes and hashes["a.md"] is not None
        assert "b.md" in hashes and hashes["b.md"] is not None
        assert hashes["a.md"] != hashes["b.md"]


class TestGetAllMarkdownFiles:
    """Tests for _get_all_markdown_files helper."""

    @pytest.mark.asyncio
    async def test_get_all_markdown_files_excludes_archived_plans(
        self, tmp_path: Path
    ) -> None:
        """Ensure archived plans are excluded from all-files scan.

        This matches CI behavior and prevents timeouts when many archived
        plan files exist.
        """
        # Arrange
        project_root = tmp_path
        docs_dir = project_root / "docs"
        plans_archive_dir = get_cortex_path(
            project_root, CortexResourceType.PLANS_ARCHIVE
        )
        docs_dir.mkdir(parents=True)
        plans_archive_dir.mkdir(parents=True)

        kept_file = docs_dir / "kept.md"
        archived_file = plans_archive_dir / "archived.md"
        _ = kept_file.write_text("# Kept\n", encoding="utf-8")
        _ = archived_file.write_text("# Archived\n", encoding="utf-8")

        # Act
        files = await _get_all_markdown_files(project_root)

        # Assert
        file_strs = {str(p) for p in files}
        assert str(kept_file) in file_strs
        assert str(archived_file) not in file_strs

    def test_calculate_statistics(self):
        """Test _calculate_statistics helper."""
        from cortex.tools.markdown_operations import (  # type: ignore[reportPrivateUsage]
            FileResult,
            _calculate_statistics,
        )

        results: list[FileResult] = [
            FileResult(file="file1.md", fixed=True, errors=[], error_message=None),
            FileResult(file="file2.md", fixed=False, errors=[], error_message=None),
            FileResult(file="file3.md", fixed=False, errors=[], error_message="Error"),
        ]

        files_fixed, files_with_errors, files_unchanged = _calculate_statistics(results)

        assert files_fixed == 1
        assert files_with_errors == 1
        assert files_unchanged == 1


class TestMarkdownlintBatchHelpers:
    """Tests for batching helpers used by markdown lint tool."""

    @pytest.mark.asyncio
    async def test_run_markdownlint_for_files_empty_returns_initial(
        self, tmp_path: Path
    ):
        """_run_markdownlint_for_files returns initial results when no files to lint."""
        from cortex.tools.markdown_operations import (  # type: ignore[reportPrivateUsage]
            FileResult,
            _run_markdownlint_for_files,
        )

        initial = [FileResult(file="a.md", fixed=False, errors=[], error_message=None)]
        results = await _run_markdownlint_for_files(
            files_to_lint=[],
            initial_results=initial,
            root_path=tmp_path,
            markdownlint_cmd=["markdownlint-cli2"],
            config_path=None,
            dry_run=False,
        )

        assert results == initial

    @pytest.mark.asyncio
    async def test_run_markdownlint_with_cache_uses_helpers(self, tmp_path: Path):
        """_run_markdownlint_with_cache wires cache, filtering, and execution."""
        from cortex.tools.markdown_lint_cache import MarkdownLintIndex
        from cortex.tools.markdown_operations import (  # pyright: ignore[reportPrivateUsage]
            _run_markdownlint_with_cache,
        )

        # Empty index: docs/file.md not cached, so it gets linted
        index = MarkdownLintIndex(files={})

        with (
            patch(
                "cortex.tools.markdown_operations.load_markdown_lint_index_safe",
                new_callable=AsyncMock,
                return_value=index,
            ) as mock_load,
            patch(
                "cortex.tools.markdown_operations._filter_files_for_linting",
                new_callable=AsyncMock,
                return_value=(
                    [tmp_path / "docs" / "file.md"],
                    [],
                    {"docs/file.md": "sha256:new"},
                ),
            ) as mock_filter,
            patch(
                "cortex.tools.markdown_operations._run_markdownlint_for_files",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_run_files,
            patch(
                "cortex.tools.markdown_operations._update_markdown_lint_cache_from_results",
                new_callable=AsyncMock,
            ) as mock_update,
        ):
            result_json = await _run_markdownlint_with_cache(
                root_path=tmp_path,
                files=[tmp_path / "docs" / "file.md"],
                markdownlint_cmd=["markdownlint-cli2"],
                config_path=None,
                dry_run=False,
            )

        parsed = json.loads(result_json)
        assert parsed["success"] is True
        mock_load.assert_called_once()
        mock_filter.assert_called_once()
        mock_run_files.assert_called_once()
        mock_update.assert_called_once()


class TestFixMarkdownLintProgressReporting:
    """Tests for progress reporting in fix_markdown_lint helpers."""

    @pytest.mark.asyncio
    async def test_run_markdownlint_for_files_reports_initial_progress_when_ctx(
        self, tmp_path: Path
    ) -> None:
        """When ctx is provided, _run_markdownlint_for_files reports 0/total once."""
        from cortex.tools.markdown_operations import (  # type: ignore[reportPrivateUsage]
            FileResult,
            _run_markdownlint_for_files,
        )

        files_to_lint = [tmp_path / "a.md", tmp_path / "b.md"]
        initial_results: list[FileResult] = []

        mock_results = [
            FileResult(file="a.md", fixed=True, errors=[], error_message=None),
            FileResult(file="b.md", fixed=False, errors=[], error_message=None),
        ]

        mock_ctx = AsyncMock()

        with (
            patch(
                "cortex.tools.markdown_operations._process_markdown_files_sequential",
                new_callable=AsyncMock,
                return_value=mock_results,
            ) as mock_seq,
            patch(
                "cortex.tools.markdown_operations.report_progress_safe",
                new_callable=AsyncMock,
            ) as mock_progress,
        ):
            results = await _run_markdownlint_for_files(
                files_to_lint=files_to_lint,
                initial_results=initial_results,
                root_path=tmp_path,
                markdownlint_cmd=["markdownlint-cli2"],
                config_path=None,
                dry_run=False,
                ctx=mock_ctx,
                index=None,
                file_hashes=None,
            )

        assert results == mock_results
        _ = mock_seq.assert_awaited_once()
        _ = mock_progress.assert_awaited_once_with(
            mock_ctx, 0.0, float(len(files_to_lint))
        )

    @pytest.mark.asyncio
    async def test_run_markdownlint_for_files_no_progress_when_ctx_none(
        self, tmp_path: Path
    ) -> None:
        """When ctx is None, _run_markdownlint_for_files does not report progress."""
        from cortex.tools.markdown_operations import (  # type: ignore[reportPrivateUsage]
            FileResult,
            _run_markdownlint_for_files,
        )

        files_to_lint = [tmp_path / "a.md"]
        initial_results: list[FileResult] = []

        mock_results = [
            FileResult(file="a.md", fixed=True, errors=[], error_message=None),
        ]

        with (
            patch(
                "cortex.tools.markdown_operations._process_markdown_files_sequential",
                new_callable=AsyncMock,
                return_value=mock_results,
            ),
            patch(
                "cortex.tools.markdown_operations.report_progress_safe",
                new_callable=AsyncMock,
            ) as mock_progress,
        ):
            results = await _run_markdownlint_for_files(
                files_to_lint=files_to_lint,
                initial_results=initial_results,
                root_path=tmp_path,
                markdownlint_cmd=["markdownlint-cli2"],
                config_path=None,
                dry_run=False,
                ctx=None,
                index=None,
                file_hashes=None,
            )

        assert results == mock_results
        mock_progress.assert_not_called()

    @pytest.mark.asyncio
    async def test_after_one_file_reports_progress_with_ctx_and_total(
        self, tmp_path: Path
    ) -> None:
        """_after_one_file reports processed/total when ctx and progress_total set."""
        from cortex.tools.markdown_operations import (  # type: ignore[reportPrivateUsage]
            FileResult,
            _after_one_file,
        )

        results: list[FileResult] = []
        current_n = [0]
        mock_ctx = AsyncMock()
        file_result = FileResult(
            file="a.md",
            fixed=True,
            errors=[],
            error_message=None,
        )

        with patch(
            "cortex.tools.markdown_operations.report_progress_safe",
            new_callable=AsyncMock,
        ) as mock_progress:
            await _after_one_file(
                file_result,
                results,
                current_n,
                index=None,
                file_hashes=None,
                root_path=tmp_path,
                progress_ctx=mock_ctx,
                progress_total=3,
            )

        assert len(results) == 1
        assert current_n[0] == 1
        _ = mock_progress.assert_awaited_once_with(mock_ctx, 1.0, 3.0)

    @pytest.mark.asyncio
    async def test_after_one_file_skips_progress_when_ctx_none(
        self, tmp_path: Path
    ) -> None:
        """_after_one_file is a no-op for progress when ctx is None."""
        from cortex.tools.markdown_operations import (  # type: ignore[reportPrivateUsage]
            FileResult,
            _after_one_file,
        )

        results: list[FileResult] = []
        current_n = [0]
        file_result = FileResult(
            file="a.md",
            fixed=True,
            errors=[],
            error_message=None,
        )

        with patch(
            "cortex.tools.markdown_operations.report_progress_safe",
            new_callable=AsyncMock,
        ) as mock_progress:
            await _after_one_file(
                file_result,
                results,
                current_n,
                index=None,
                file_hashes=None,
                root_path=tmp_path,
                progress_ctx=None,
                progress_total=3,
            )

        assert len(results) == 1
        assert current_n[0] == 1
        mock_progress.assert_not_called()
