"""
Unit tests for cortex.tools.markdown_operations.py script.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cortex.core.models import GitCommandResult
from cortex.tools.files.markdown_operations import (
    find_markdownlint_command,
    get_all_markdown_files_for_lint,
    get_modified_markdown_files,
    run_command,
    run_markdownlint_fix,
)
from tests.unit.fix_markdown_lint_test_support import (
    patch_fix_markdown_lint_ctx_logging,
    patch_fix_markdown_lint_success,
    patch_lock_timeout_cache_update,
)


class TestRunCommand:
    """Test run_command function."""

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
            "cortex.tools.files.markdown_lint_core.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ):
            # Act
            result = await run_command(["test", "command"])

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
            "cortex.tools.files.markdown_lint_core.asyncio.create_subprocess_exec",
            side_effect=mock_create_subprocess,
        ):
            # Act
            result = await run_command(["test", "command"])

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
            "cortex.tools.files.markdown_lint_core.asyncio.create_subprocess_exec",
            side_effect=slow_subprocess,
        ):
            # Act
            result = await run_command(["test", "command"], timeout=5)

            # Assert
            assert result.success is False
            assert result.error is not None
            assert "timed out" in result.error
            assert result.returncode == -1

    @pytest.mark.asyncio
    async def test_run_command_oserror_returns_error_result(self):
        """Expected subprocess/setup failures map to GitCommandResult error."""
        with patch(
            "cortex.tools.files.markdown_lint_core.asyncio.create_subprocess_exec",
            side_effect=OSError("Test error"),
        ):
            result = await run_command(["test", "command"])

        assert result.success is False
        assert result.error is not None
        assert "Test error" in result.error
        assert result.returncode == -1

    @pytest.mark.asyncio
    async def test_run_command_unexpected_exception_returns_error_result(self):
        """Tool boundary: unexpected errors map to GitCommandResult (no bare raise)."""
        with patch(
            "cortex.tools.files.markdown_lint_core.asyncio.create_subprocess_exec",
            side_effect=RuntimeError("bug"),
        ):
            result = await run_command(["test", "command"])

        assert result.success is False
        assert result.error is not None
        assert "bug" in result.error
        assert result.returncode == -1


class TestMarkdownLintCoreNarrowExceptions:
    """Narrow exception handling for helpers other than ``run_command`` (which maps ``Exception``)."""

    @pytest.mark.asyncio
    async def test_calculate_file_hash_oserror_returns_none(
        self, tmp_path: Path
    ) -> None:
        """I/O failures yield None so callers can treat the file as needing work."""
        from cortex.tools.files import markdown_lint_core as mlc

        path = tmp_path / "x.md"
        _ = path.write_text("hi", encoding="utf-8")
        with patch(
            "cortex.tools.files.markdown_lint_core.aiofiles.open",
            side_effect=OSError("read failed"),
        ):
            assert await mlc.calculate_file_hash(path) is None

    @pytest.mark.asyncio
    async def test_calculate_file_hash_typeerror_propagates(
        self, tmp_path: Path
    ) -> None:
        """Unexpected errors from hashing are not masked as a silent None."""
        from cortex.tools.files import markdown_lint_core as mlc

        path = tmp_path / "x.md"
        _ = path.write_text("hi", encoding="utf-8")

        class _BadFile:
            async def __aenter__(self) -> "_BadFile":
                return self

            async def __aexit__(self, *args: object) -> None:
                return None

            async def read(self, _n: int) -> bytes:
                raise TypeError("unexpected")

        with (
            patch(
                "cortex.tools.files.markdown_lint_core.aiofiles.open",
                return_value=_BadFile(),
            ),
            pytest.raises(TypeError, match="unexpected"),
        ):
            _ = await mlc.calculate_file_hash(path)

    @pytest.mark.asyncio
    async def test_update_markdown_lint_cache_safe_lock_timeout_logs(
        self, tmp_path: Path
    ) -> None:
        """FileLockTimeoutError from cache update is logged, not re-raised."""
        from cortex.tools.files import markdown_lint_core as mlc

        with patch_lock_timeout_cache_update(tmp_path) as (
            index,
            root,
            results,
            hashes,
            mock_log,
        ):
            await mlc.update_markdown_lint_cache_safe(
                index, root, results, hashes, ctx=None
            )

        mock_log.assert_awaited_once()
        assert "Failed to update markdown lint cache" in str(
            mock_log.await_args_list[0]
        )

    @pytest.mark.asyncio
    async def test_update_markdown_lint_cache_safe_runtime_error_propagates(
        self, tmp_path: Path
    ) -> None:
        """Programming errors during cache update are not swallowed."""
        from cortex.tools.files import markdown_lint_cache_updates as mlcu
        from cortex.tools.files import markdown_lint_core as mlc
        from cortex.tools.files.markdown_lint_cache import MarkdownLintIndex
        from cortex.tools.files.markdown_lint_helpers import FileResult

        index = MarkdownLintIndex()
        results = [
            FileResult(
                file="a.md",
                fixed=False,
                errors=[],
                error_message=None,
            )
        ]
        hashes = {"a.md": "sha256:abc"}

        with (
            patch.object(
                mlcu,
                "update_markdown_lint_cache_from_results",
                new_callable=AsyncMock,
                side_effect=RuntimeError("bug"),
            ),
            pytest.raises(RuntimeError, match="bug"),
        ):
            await mlc.update_markdown_lint_cache_safe(
                index, tmp_path, results, hashes, ctx=None
            )


class TestGetAllMarkdownFilesForLint:
    """Test get_all_markdown_files_for_lint (CI parity)."""

    def test_includes_md_and_mdc_excludes_ci_dirs(self, tmp_path: Path) -> None:
        """All .md/.mdc are found; node_modules, .venv, .git, archive are excluded."""
        _ = (tmp_path / "a.md").write_text("")
        _ = (tmp_path / "b.mdc").write_text("")
        (tmp_path / "docs" / "c.md").parent.mkdir(parents=True, exist_ok=True)
        _ = (tmp_path / "docs" / "c.md").write_text("")
        (tmp_path / "node_modules" / "x.md").parent.mkdir(parents=True, exist_ok=True)
        _ = (tmp_path / "node_modules" / "x.md").write_text("")
        (tmp_path / ".venv" / "y.md").parent.mkdir(parents=True, exist_ok=True)
        _ = (tmp_path / ".venv" / "y.md").write_text("")
        (tmp_path / ".cortex" / "plans" / "archive" / "z.md").parent.mkdir(
            parents=True, exist_ok=True
        )
        _ = (tmp_path / ".cortex" / "plans" / "archive" / "z.md").write_text("")
        (tmp_path / ".cortex" / "history" / "snap.md").parent.mkdir(
            parents=True, exist_ok=True
        )
        _ = (tmp_path / ".cortex" / "history" / "snap.md").write_text("")
        (tmp_path / ".cortex" / ".cache" / "session" / "pre.md").parent.mkdir(
            parents=True, exist_ok=True
        )
        _ = (tmp_path / ".cortex" / ".cache" / "session" / "pre.md").write_text("")
        out = get_all_markdown_files_for_lint(tmp_path)
        paths = {str(p.relative_to(tmp_path)) for p in out}
        assert "a.md" in paths
        assert "b.mdc" in paths
        assert "docs/c.md" in paths
        assert "node_modules/x.md" not in paths
        assert ".venv/y.md" not in paths
        assert ".cortex/plans/archive/z.md" not in paths
        assert ".cortex/history/snap.md" not in paths
        assert ".cortex/.cache/session/pre.md" not in paths

    def test_respects_max_files(self, tmp_path: Path) -> None:
        """Returns at most max_files paths."""
        for i in range(10):
            _ = (tmp_path / f"f{i}.md").write_text("")
        out = get_all_markdown_files_for_lint(tmp_path, max_files=5)
        assert len(out) == 5


class TestGetModifiedMarkdownFiles:
    """Test get_modified_markdown_files function."""

    @pytest.mark.asyncio
    async def test_get_modified_files_from_diff(self, tmp_path: Path):
        """Test getting modified files from git diff."""
        # Arrange
        project_root = tmp_path
        diff_output = "file1.md\nfile2.mdc\nfile3.txt"

        with patch(
            "cortex.tools.files.markdown_lint_core.run_command",
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
            files = await get_modified_markdown_files(project_root)

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
            "cortex.tools.files.markdown_lint_core.run_command",
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
            files = await get_modified_markdown_files(project_root)

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
            "cortex.tools.files.markdown_lint_core.run_command",
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
            files = await get_modified_markdown_files(
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
            "cortex.tools.files.markdown_lint_core.run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = [
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
                GitCommandResult(success=True, stdout="", stderr="", returncode=0),
            ]

            # Act
            files = await get_modified_markdown_files(project_root)

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
            "cortex.tools.files.markdown_lint_core.run_command",
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
            files = await get_modified_markdown_files(project_root)

            # Assert
            assert len(files) == 1
            assert "file1.md" in str(files[0])


class TestCheckMarkdownlintAvailable:
    """Test find_markdownlint_command function."""

    @pytest.mark.asyncio
    async def test_markdownlint_available(self):
        """Test when markdownlint is available via PATH."""
        # Arrange
        with patch(
            "cortex.tools.files.markdown_lint_core.run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=True,
                stdout="rumdl version 1.0.0",
                stderr="",
                returncode=0,
            )

            # Act
            result = await find_markdownlint_command()

            # Assert
            assert result == ["rumdl", "check"]
            mock_run.assert_called_once_with(["rumdl", "--version"])

    @pytest.mark.asyncio
    async def test_markdownlint_available_via_npx(self):
        """Test when markdownlint is available via npx."""
        # Arrange
        with patch(
            "cortex.tools.files.markdown_lint_core.run_command",
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
                    stdout="rumdl version 1.0.0",
                    stderr="",
                    returncode=0,
                ),
            ]

            # Act
            result = await find_markdownlint_command()

            # Assert
            assert result == ["npx", "--yes", "rumdl", "check"]
            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_markdownlint_not_available(self):
        """Test when markdownlint is not available."""
        # Arrange
        with patch(
            "cortex.tools.files.markdown_lint_core.run_command",
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
            result = await find_markdownlint_command()

            # Assert
            assert result is None
            assert mock_run.call_count == 2  # Should try both discovery attempts

    @pytest.mark.asyncio
    async def test_markdownlint_prefers_local_node_modules(self, tmp_path: Path):
        """Test that local rumdl CLI is used when present."""
        (tmp_path / "node_modules" / ".bin").mkdir(parents=True)
        local_bin = tmp_path / "node_modules" / ".bin" / "rumdl"
        _ = local_bin.write_text("#!/bin/sh\nexit 0")

        with patch(
            "cortex.tools.files.markdown_lint_core.run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=True,
                stdout="rumdl",
                stderr="",
                returncode=0,
            )

            result = await find_markdownlint_command(tmp_path)

            assert result is not None
            assert len(result) == 2
            assert "rumdl" in result[0]
            assert str(tmp_path) in result[0]
            assert result[1] == "check"
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == str(local_bin.resolve())
            assert call_args[1] == "--version"


class TestRunMarkdownlintFix:
    """Test run_markdownlint_fix function."""

    @pytest.mark.asyncio
    async def test_run_markdownlint_fix_success(self, tmp_path: Path):
        """Test successful markdownlint fix."""
        # Arrange
        project_root = tmp_path
        file_path = tmp_path / "test.md"
        _ = file_path.write_text("# Test\n\nContent")

        with patch(
            "cortex.tools.files.markdown_lint_run.run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=True, stdout="Fixed: test.md", stderr="", returncode=0
            )

            # Act
            result = await run_markdownlint_fix(
                file_path, project_root, ["rumdl"], dry_run=False
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
            "cortex.tools.files.markdown_lint_run.run_command",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = GitCommandResult(
                success=True,
                stdout="test.md: 5:1 MD022/blanks-around-headings",
                stderr="",
                returncode=0,
            )

            # Act
            result = await run_markdownlint_fix(
                file_path, project_root, ["rumdl"], dry_run=True
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
            "cortex.tools.files.markdown_lint_run.run_command",
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
            result = await run_markdownlint_fix(
                file_path, project_root, ["rumdl"], dry_run=False
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
            "cortex.tools.files.markdown_lint_run.run_command",
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
            result = await run_markdownlint_fix(
                file_path, project_root, ["rumdl"], dry_run=False
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
            "cortex.tools.files.markdown_lint_run.run_command",
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
            result = await run_markdownlint_fix(
                file_path, project_root, ["rumdl"], dry_run=False
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
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test\n\nContent")

        with patch_fix_markdown_lint_success(tmp_path, test_file):
            result_str = await fix_markdown_lint()

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["files_processed"] == 1
        assert result["files_fixed"] == 1

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_not_git_repo(self, tmp_path: Path):
        """Test error when not in git repository."""
        # Arrange
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.files.markdown_lint.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.files.markdown_lint_core.run_command",
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
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.files.markdown_lint.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.files.markdown_lint_core.run_command",
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
        """Test error when markdownlint CLI is not available."""
        # Arrange
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.files.markdown_lint.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.files.markdown_lint_core.run_command",
                new_callable=AsyncMock,
            ) as mock_run,
            patch(
                "cortex.tools.files.markdown_lint_core.find_markdownlint_command",
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
            assert "rumdl" in result["error_message"]

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_no_files(self, tmp_path: Path):
        """Test when no modified files found."""
        # Arrange
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.files.markdown_lint.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.files.markdown_lint_core.run_command",
                new_callable=AsyncMock,
            ) as mock_run,
            patch(
                "cortex.tools.files.markdown_lint_core.find_markdownlint_command",
                new_callable=AsyncMock,
                return_value=["rumdl", "check"],
            ),
            patch(
                "cortex.tools.files.markdown_lint_core.get_modified_markdown_files",
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
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.files.markdown_lint.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.files.markdown_lint.validate_markdown_prerequisites",
                new_callable=AsyncMock,
                side_effect=ValueError("Test error"),
            ),
        ):
            result_str = await fix_markdown_lint()
            result = json.loads(result_str)
            assert result["success"] is False
            assert "Test error" in result["error_message"]

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_check_all_files_ignored(self, tmp_path: Path):
        """Test that check_all_files is accepted for backward compat but ignored."""
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        with (
            patch(
                "cortex.tools.files.markdown_lint.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.files.markdown_lint.validate_markdown_prerequisites",
                new_callable=AsyncMock,
                return_value=(None, ["rumdl"], None),
            ),
            patch(
                "cortex.tools.files.markdown_lint.get_markdown_files_to_process",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_get_files,
            patch(
                "cortex.tools.files.markdown_lint.run_markdownlint_with_cache",
            ),
        ):
            # Act — pass check_all_files=True but it should be ignored
            result_str = await fix_markdown_lint(check_all_files=True)
            result = json.loads(result_str)

            # Assert — tool succeeds and get_markdown_files_to_process
            # is called without check_all_files
            assert result["success"] is True
            mock_get_files.assert_called_once_with(tmp_path, False)


class TestFixMarkdownLintContextLogging:
    """Test fix_markdown_lint Context logging (FastMCP)."""

    @pytest.mark.asyncio
    async def test_fix_markdown_lint_calls_log_client_on_start_and_completion_when_ctx_passed(
        self, tmp_path: Path
    ) -> None:
        """When ctx is passed, fix_markdown_lint logs start and completion."""
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        mock_ctx = AsyncMock()
        with patch_fix_markdown_lint_ctx_logging(tmp_path) as mock_log:
            result_str = await fix_markdown_lint(ctx=mock_ctx)

        result = json.loads(result_str)
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
        from cortex.tools.files.markdown_operations import fix_markdown_lint

        mock_ctx = AsyncMock()
        with (
            patch(
                "cortex.tools.files.markdown_lint.log_client",
                new_callable=AsyncMock,
            ) as mock_log,
            patch(
                "cortex.tools.files.markdown_lint.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=tmp_path,
            ),
            patch(
                "cortex.tools.files.markdown_lint.validate_markdown_prerequisites",
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
