"""
Additional markdown lint tests (split from test_fix_markdown_lint for file size limits).
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.files.markdown_operations import (
    FileResult,
    run_markdownlint_batch,
)
from tests.unit.fix_markdown_lint_test_support import (
    MarkdownlintBatchCounters,
    build_mock_batch_success_only,
    build_mock_no_rule_codes_batch,
    build_mock_parsed_rule_codes_batch,
    patch_cache_load_failure_mocks,
    patch_cache_update_failure_mocks,
    patch_run_markdownlint_with_cache_wiring,
    run_mdf_under_seq_progress_mocks,
)


class TestHelperFunctions:
    """Test helper functions in markdown_operations."""

    def test_parse_git_output(self, tmp_path: Path):
        """Test parse_git_output helper."""
        from cortex.tools.files.markdown_operations import parse_git_output

        files: list[Path] = []
        stdout = "file1.md\nfile2.md\nfile3.txt"
        parse_git_output(stdout, tmp_path, files)

        assert len(files) == 2
        assert any("file1.md" in str(f) for f in files)
        assert any("file2.md" in str(f) for f in files)

    def test_parse_untracked_files(self, tmp_path: Path):
        """Test parse_untracked_files helper."""
        from cortex.tools.files.markdown_operations import parse_untracked_files

        files: list[Path] = []
        stdout = "?? file1.md\n?? file2.mdc\n?? file3.txt"
        parse_untracked_files(stdout, tmp_path, files)

        assert len(files) == 2
        assert any("file1.md" in str(f) for f in files)
        assert any("file2.mdc" in str(f) for f in files)

    def test_parse_git_output_rejects_absolute_path(self, tmp_path: Path) -> None:
        """parse_git_output ignores lines that are absolute paths."""
        from cortex.tools.files.markdown_operations import parse_git_output

        files: list[Path] = []
        stdout = "/etc/passwd\n/tmp/evil.md\nnormal.md"
        parse_git_output(stdout, tmp_path, files)

        assert len(files) == 1
        assert any("normal.md" in str(f) for f in files)
        assert not any("/etc/passwd" in str(f) for f in files)

    def test_parse_git_output_rejects_traversal(self, tmp_path: Path) -> None:
        """parse_git_output ignores lines with .. path traversal segments."""
        from cortex.tools.files.markdown_operations import parse_git_output

        files: list[Path] = []
        stdout = "../outside.md\n../../secret.md\nnormal.md"
        parse_git_output(stdout, tmp_path, files)

        assert len(files) == 1
        assert any("normal.md" in str(f) for f in files)

    def test_parse_untracked_files_rejects_absolute_path(self, tmp_path: Path) -> None:
        """parse_untracked_files ignores untracked entries with absolute paths."""
        from cortex.tools.files.markdown_operations import parse_untracked_files

        files: list[Path] = []
        stdout = "?? /tmp/evil.md\n?? normal.md"
        parse_untracked_files(stdout, tmp_path, files)

        assert len(files) == 1
        assert any("normal.md" in str(f) for f in files)

    def test_parse_untracked_files_rejects_traversal(self, tmp_path: Path) -> None:
        """parse_untracked_files ignores untracked entries with .. segments."""
        from cortex.tools.files.markdown_operations import parse_untracked_files

        files: list[Path] = []
        stdout = "?? ../outside.md\n?? normal.mdc"
        parse_untracked_files(stdout, tmp_path, files)

        assert len(files) == 1
        assert any("normal.mdc" in str(f) for f in files)

    def test_parse_markdownlint_errors(self):
        """Test parse_markdownlint_errors helper."""
        from cortex.tools.files.markdown_operations import parse_markdownlint_errors

        stderr = "file.md: 1:1 MD022\nmarkdownlint-cli2 version\nfile.md: 2:1 MD032"
        errors = parse_markdownlint_errors(stderr)

        assert len(errors) == 2
        assert any("MD022" in e for e in errors)


class TestFixMarkdownLintErrorHandling:
    """Test error handling improvements for Phase 59 (connection closed fix)."""

    @pytest.mark.asyncio
    async def test_save_markdown_lint_index_handles_cache_write_failure(
        self, tmp_path: Path
    ):
        """Test that save_markdown_lint_index handles cache write failures gracefully."""
        from cortex.core.exceptions import FileLockTimeoutError
        from cortex.tools.files.markdown_lint_cache import (
            MarkdownLintIndex,
            save_markdown_lint_index,
        )

        index = MarkdownLintIndex()
        with (
            patch(
                "cortex.tools.files.markdown_lint_cache.write_cache_json",
                new_callable=AsyncMock,
                side_effect=FileLockTimeoutError("markdown-lint-index.json", 30),
            ) as mock_write,
            patch(
                "cortex.tools.files.markdown_lint_cache.log_client",
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
        """Test that run_markdownlint_with_cache handles cache load failures."""
        from cortex.tools.files.markdown_operations import run_markdownlint_with_cache

        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test\n\nContent")

        with patch_cache_load_failure_mocks() as mock_log:
            result_str = await run_markdownlint_with_cache(
                tmp_path,
                [test_file],
                ["rumdl"],
                None,
                False,
                ctx=None,
            )

        result = json.loads(result_str)
        assert result["success"] is True
        assert any(
            "warning" in str(c[0][1])
            and "Failed to load markdown lint cache" in str(c[0][2])
            for c in mock_log.call_args_list
        )

    @pytest.mark.asyncio
    async def test_run_markdownlint_with_cache_handles_cache_update_failure(
        self, tmp_path: Path
    ):
        """Test that run_markdownlint_with_cache handles cache update failures."""
        from cortex.tools.files.markdown_operations import run_markdownlint_with_cache

        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test\n\nContent")

        with patch_cache_update_failure_mocks(test_file) as mock_log:
            result_str = await run_markdownlint_with_cache(
                tmp_path,
                [test_file],
                ["rumdl"],
                None,
                False,
                ctx=None,
            )

        result = json.loads(result_str)
        assert result["success"] is True
        assert result["files_processed"] == 1
        assert any(
            len(c[0]) >= 3
            and "warning" in str(c[0][1])
            and "Failed to update markdown lint cache" in str(c[0][2])
            for c in mock_log.call_args_list
        )

    def test_parse_markdownlint_output(self):
        """Test parse_markdownlint_output helper."""
        from cortex.tools.files.markdown_operations import parse_markdownlint_output

        stdout = "Fixed: file.md\nFixed: file2.md"
        errors = parse_markdownlint_output(stdout)

        assert len(errors) == 2
        assert "file.md" in errors[0]
        assert "file2.md" in errors[1]

    def test_is_cached_clean_entry(self) -> None:
        """Test is_cached_clean_entry helper for cache reuse logic."""
        from cortex.tools.files.markdown_operations import is_cached_clean_entry

        assert is_cached_clean_entry("sha256:abc", "sha256:abc", dry_run=False) is True
        assert is_cached_clean_entry("sha256:abc", "sha256:xyz", dry_run=False) is False
        assert is_cached_clean_entry("sha256:abc", "sha256:abc", dry_run=True) is False
        assert is_cached_clean_entry(None, "sha256:abc", dry_run=False) is False

    @pytest.mark.asyncio
    async def test_compute_file_hashes_parallel(self, tmp_path: Path) -> None:
        """compute_file_hashes returns rel_path -> hash for multiple files."""
        from cortex.tools.files.markdown_operations import compute_file_hashes

        _ = (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
        _ = (tmp_path / "b.md").write_text("# B\n", encoding="utf-8")
        files = [tmp_path / "a.md", tmp_path / "b.md"]

        hashes = await compute_file_hashes(files, tmp_path)

        assert len(hashes) == 2
        assert "a.md" in hashes and hashes["a.md"] is not None
        assert "b.md" in hashes and hashes["b.md"] is not None
        assert hashes["a.md"] != hashes["b.md"]


class TestMarkdownLintHelpers:
    """Tests for markdown lint helper functions."""

    def test_calculate_statistics(self):
        """Test calculate_statistics helper."""
        from cortex.tools.files.markdown_operations import (
            FileResult,
            calculate_statistics,
        )

        results: list[FileResult] = [
            FileResult(file="file1.md", fixed=True, errors=[], error_message=None),
            FileResult(file="file2.md", fixed=False, errors=[], error_message=None),
            FileResult(file="file3.md", fixed=False, errors=[], error_message="Error"),
        ]

        files_fixed, files_with_errors, files_unchanged = calculate_statistics(results)

        assert files_fixed == 1
        assert files_with_errors == 1
        assert files_unchanged == 1


class TestMarkdownlintBatchHelpers:
    """Tests for batching helpers used by markdown lint tool."""

    @pytest.mark.asyncio
    async def test_run_markdownlint_for_files_empty_returns_initial(
        self, tmp_path: Path
    ):
        """run_markdownlint_for_files returns initial results when no files to lint."""
        from cortex.tools.files.markdown_operations import (
            FileResult,
            run_markdownlint_for_files,
        )

        initial = [FileResult(file="a.md", fixed=False, errors=[], error_message=None)]
        results = await run_markdownlint_for_files(
            files_to_lint=[],
            initial_results=initial,
            root_path=tmp_path,
            markdownlint_cmd=["rumdl", "check"],
            config_path=None,
            dry_run=False,
        )

        assert results == initial

    @pytest.mark.asyncio
    async def test_run_markdownlint_with_cache_uses_helpers(self, tmp_path: Path):
        """run_markdownlint_with_cache wires cache, filtering, and execution."""
        from cortex.tools.files.markdown_operations import run_markdownlint_with_cache

        with patch_run_markdownlint_with_cache_wiring(tmp_path) as (
            mock_load,
            mock_filter,
            mock_run_files,
            mock_update,
        ):
            result_json = await run_markdownlint_with_cache(
                root_path=tmp_path,
                files=[tmp_path / "docs" / "file.md"],
                markdownlint_cmd=["rumdl", "check"],
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
        """When ctx is provided, run_markdownlint_for_files reports 0/total once."""
        files_to_lint = [tmp_path / "a.md", tmp_path / "b.md"]
        mock_results = [
            FileResult(file="a.md", fixed=True, errors=[], error_message=None),
            FileResult(file="b.md", fixed=False, errors=[], error_message=None),
        ]
        mock_ctx = AsyncMock()
        results, mock_seq, mock_progress = await run_mdf_under_seq_progress_mocks(
            tmp_path,
            files_to_lint,
            mock_results,
            mock_ctx,
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
        """When ctx is None, run_markdownlint_for_files does not report progress."""
        files_to_lint = [tmp_path / "a.md"]
        mock_results = [
            FileResult(file="a.md", fixed=True, errors=[], error_message=None),
        ]

        results, _, mock_progress = await run_mdf_under_seq_progress_mocks(
            tmp_path,
            files_to_lint,
            mock_results,
            None,
        )

        assert results == mock_results
        mock_progress.assert_not_called()

    @pytest.mark.asyncio
    async def test_after_one_file_reports_progress_with_ctx_and_total(
        self, tmp_path: Path
    ) -> None:
        """after_one_file reports processed/total when ctx and progress_total set."""
        from cortex.tools.files.markdown_operations import FileResult, after_one_file

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
            "cortex.tools.files.markdown_lint_cache_updates.report_progress_safe",
            new_callable=AsyncMock,
        ) as mock_progress:
            await after_one_file(
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
        """after_one_file is a no-op for progress when ctx is None."""
        from cortex.tools.files.markdown_operations import FileResult, after_one_file

        results: list[FileResult] = []
        current_n = [0]
        file_result = FileResult(
            file="a.md",
            fixed=True,
            errors=[],
            error_message=None,
        )

        with patch(
            "cortex.tools.files.markdown_lint_cache_updates.report_progress_safe",
            new_callable=AsyncMock,
        ) as mock_progress:
            await after_one_file(
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


class TestBatchErrorReporting:
    """Test improved error reporting when batch fails without rule codes."""

    @pytest.mark.asyncio
    async def test_batch_failure_with_no_rule_codes_triggers_per_file_fallback(
        self, tmp_path: Path
    ):
        """Test that batch failure with no parsed rule codes triggers per-file fallback."""
        project_root = tmp_path
        file1 = tmp_path / "file1.md"
        file2 = tmp_path / "file2.md"
        _ = file1.write_text("# Test\n")
        _ = file2.write_text("# Test\n")

        markdownlint_cmd = ["rumdl", "check"]
        counters = MarkdownlintBatchCounters()
        mock_run = build_mock_no_rule_codes_batch(counters)

        with patch(
            "cortex.tools.files.markdown_lint_run.run_command",
            side_effect=mock_run,
        ):
            results = await run_markdownlint_batch(
                [file1, file2],
                project_root,
                markdownlint_cmd,
                None,
                dry_run=False,
            )

        assert counters.batch_calls == 1, "Batch should be called once"
        assert (
            counters.per_file_calls == 2
        ), "Per-file fallback should run for each file"
        assert len(results) == 2
        for result in results:
            assert result.error_message is not None
            assert len(result.errors) > 0, "Each file should have rule codes"
            assert any("MD036" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_batch_failure_with_parsed_rule_codes_no_fallback(
        self, tmp_path: Path
    ):
        """Test that batch failure with parsed rule codes does not trigger fallback."""
        project_root = tmp_path
        file1 = tmp_path / "file1.md"
        file2 = tmp_path / "file2.md"
        _ = file1.write_text("# Test\n")
        _ = file2.write_text("# Test\n")

        markdownlint_cmd = ["rumdl", "check"]
        counters = MarkdownlintBatchCounters()
        mock_run = build_mock_parsed_rule_codes_batch(counters)

        with patch(
            "cortex.tools.files.markdown_lint_run.run_command",
            side_effect=mock_run,
        ):
            results = await run_markdownlint_batch(
                [file1, file2],
                project_root,
                markdownlint_cmd,
                None,
                dry_run=False,
            )

        assert counters.batch_calls == 1, "Batch should be called once"
        assert counters.per_file_calls == 0, "Per-file fallback should not run"
        assert len(results) == 2
        file1_result = next(r for r in results if r.file == "file1.md")
        file2_result = next(r for r in results if r.file == "file2.md")
        assert any("MD036" in e for e in file1_result.errors)
        assert any("MD022" in e for e in file2_result.errors)

    @pytest.mark.asyncio
    async def test_batch_success_no_fallback(self, tmp_path: Path):
        """Test that successful batch run does not trigger fallback."""
        project_root = tmp_path
        file1 = tmp_path / "file1.md"
        file2 = tmp_path / "file2.md"
        _ = file1.write_text("# Test\n")
        _ = file2.write_text("# Test\n")

        markdownlint_cmd = ["rumdl", "check"]
        counters = MarkdownlintBatchCounters()
        mock_run = build_mock_batch_success_only(counters)

        with patch(
            "cortex.tools.files.markdown_lint_run.run_command",
            side_effect=mock_run,
        ):
            results = await run_markdownlint_batch(
                [file1, file2],
                project_root,
                markdownlint_cmd,
                None,
                dry_run=False,
            )

        assert counters.batch_calls == 1, "Batch should be called once"
        assert counters.per_file_calls == 0, "Per-file fallback should not run"
        assert len(results) == 2
        for result in results:
            assert result.error_message is None
