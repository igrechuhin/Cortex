"""Shared mocks and patch helpers for markdown lint unit tests."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

from cortex.core.exceptions import FileLockTimeoutError
from cortex.core.models import GitCommandResult
from cortex.tools.files.markdown_lint_cache import MarkdownLintIndex
from cortex.tools.files.markdown_operations import (
    FileResult,
    run_markdownlint_for_files,
)


class MarkdownlintBatchCounters:
    """Mutable counters for batch vs per-file mock invocations."""

    def __init__(self) -> None:
        self.batch_calls = 0
        self.per_file_calls = 0


def build_mock_no_rule_codes_batch(counters: MarkdownlintBatchCounters):
    async def mock_run_command(
        cmd: list[str], cwd: Path | None = None, timeout: int = 120
    ) -> GitCommandResult:
        if cmd and "rumdl" in str(cmd[0]):
            file_args = [arg for arg in cmd if ".md" in str(arg)]
            if len(file_args) > 1:
                counters.batch_calls += 1
                return GitCommandResult(
                    success=False,
                    stdout="",
                    stderr="Some generic error message without rule codes",
                    returncode=1,
                    error="Markdown lint failed",
                )
            if len(file_args) == 1:
                counters.per_file_calls += 1
                file_name = file_args[0]
                return GitCommandResult(
                    success=False,
                    stdout="",
                    stderr=f"{file_name}: 1:1 MD036/no-emphasis-as-heading",
                    returncode=1,
                    error="Markdown lint failed",
                )
        return GitCommandResult(success=True, stdout="", stderr="", returncode=0)

    return mock_run_command


def build_mock_parsed_rule_codes_batch(counters: MarkdownlintBatchCounters):
    async def mock_run_command(
        cmd: list[str], cwd: Path | None = None, timeout: int = 120
    ) -> GitCommandResult:
        if "--fix" in cmd and len(cmd) > 3:
            counters.batch_calls += 1
            return GitCommandResult(
                success=False,
                stdout="",
                stderr=(
                    "file1.md: 1:1 MD036/no-emphasis-as-heading\n"
                    "file2.md: 1:1 MD022/blanks-around-headings"
                ),
                returncode=1,
                error="Markdown lint failed",
            )
        if "--fix" in cmd and len(cmd) == 3:
            counters.per_file_calls += 1
        return GitCommandResult(success=True, stdout="", stderr="", returncode=0)

    return mock_run_command


def build_mock_batch_success_only(counters: MarkdownlintBatchCounters):
    async def mock_run_command(
        cmd: list[str], cwd: Path | None = None, timeout: int = 120
    ) -> GitCommandResult:
        if "--fix" in cmd and len(cmd) > 3:
            counters.batch_calls += 1
            return GitCommandResult(
                success=True,
                stdout="Fixed",
                stderr="",
                returncode=0,
            )
        if "--fix" in cmd and len(cmd) == 3:
            counters.per_file_calls += 1
        return GitCommandResult(success=True, stdout="", stderr="", returncode=0)

    return mock_run_command


@contextmanager
def patch_lock_timeout_cache_update(tmp_path: Path):
    from cortex.tools.files import markdown_lint_cache_updates as mlcu
    from cortex.tools.files.markdown_lint_helpers import FileResult as HelperFileResult

    index = MarkdownLintIndex()
    results = [
        HelperFileResult(file="a.md", fixed=False, errors=[], error_message=None),
    ]
    hashes = {"a.md": "sha256:abc"}
    with (
        patch.object(
            mlcu,
            "update_markdown_lint_cache_from_results",
            new_callable=AsyncMock,
            side_effect=FileLockTimeoutError("markdown-lint-index.json", 30),
        ),
        patch.object(mlcu, "log_client", new_callable=AsyncMock) as mock_log,
    ):
        yield index, tmp_path, results, hashes, mock_log


@contextmanager
def patch_fix_markdown_lint_success(tmp_path: Path, test_file: Path):
    one_fixed = [FileResult(file="test.md", fixed=True, errors=[], error_message=None)]
    p_root = patch(
        "cortex.tools.files.markdown_lint.resolve_project_root_async",
        new_callable=AsyncMock,
        return_value=tmp_path,
    )
    p_cmd = patch(
        "cortex.tools.files.markdown_lint_core.run_command",
        new_callable=AsyncMock,
    )
    p_find = patch(
        "cortex.tools.files.markdown_lint_core.find_markdownlint_command",
        new_callable=AsyncMock,
        return_value=["rumdl", "check"],
    )
    p_files = patch(
        "cortex.tools.files.markdown_lint.get_markdown_files_to_process",
        new_callable=AsyncMock,
        return_value=[test_file],
    )
    p_run = patch(
        "cortex.tools.files.markdown_lint.run_markdownlint_for_files",
        new_callable=AsyncMock,
        return_value=one_fixed,
    )
    with p_root, p_cmd as mock_run_core, p_find, p_files, p_run:
        mock_run_core.return_value = GitCommandResult(
            success=True, stdout="", stderr="", returncode=0
        )
        yield


@contextmanager
def patch_fix_markdown_lint_ctx_logging(tmp_path: Path):
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
            "cortex.tools.files.markdown_lint_core.run_command",
            new_callable=AsyncMock,
        ) as mock_run,
        patch(
            "cortex.tools.files.markdown_lint_core.find_markdownlint_command",
            new_callable=AsyncMock,
            return_value=["rumdl", "check"],
        ),
        patch(
            "cortex.tools.files.markdown_lint_core.get_markdown_files_to_process",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        mock_run.return_value = GitCommandResult(
            success=True, stdout="", stderr="", returncode=0
        )
        yield mock_log


@contextmanager
def patch_cache_load_failure_mocks():
    with (
        patch(
            "cortex.tools.files.markdown_lint_cache.load_markdown_lint_index",
            new_callable=AsyncMock,
            side_effect=FileLockTimeoutError("markdown-lint-index.json", 30),
        ),
        patch(
            "cortex.tools.files.markdown_lint_cache.log_client",
            new_callable=AsyncMock,
        ) as mock_log,
        patch(
            "cortex.tools.files.markdown_lint.run_markdownlint_for_files",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "cortex.tools.files.markdown_lint.filter_files_for_linting",
            new_callable=AsyncMock,
            return_value=([], [], {}),
        ),
    ):
        yield mock_log


@contextmanager
def patch_cache_update_failure_mocks(test_file: Path):
    results = [FileResult(file="test.md", fixed=True, errors=[], error_message=None)]
    lock_exc = FileLockTimeoutError("markdown-lint-index.json", 30)
    p_load = patch(
        "cortex.tools.files.markdown_lint.load_markdown_lint_index_safe",
        new_callable=AsyncMock,
        return_value=MarkdownLintIndex(),
    )
    p_filter = patch(
        "cortex.tools.files.markdown_lint.filter_files_for_linting",
        new_callable=AsyncMock,
        return_value=([test_file], [], {"test.md": "hash123"}),
    )
    p_run = patch(
        "cortex.tools.files.markdown_lint.run_markdownlint_for_files",
        new_callable=AsyncMock,
        return_value=results,
    )
    p_upd = patch(
        "cortex.tools.files.markdown_lint_cache_updates.update_markdown_lint_cache_from_results",
        new_callable=AsyncMock,
        side_effect=lock_exc,
    )
    p_log = patch(
        "cortex.tools.files.markdown_lint_cache_updates.log_client",
        new_callable=AsyncMock,
    )
    with p_load, p_filter, p_run, p_upd, p_log as mock_log:
        yield mock_log


@contextmanager
def patch_run_markdownlint_with_cache_wiring(tmp_path: Path):
    index = MarkdownLintIndex(files={})
    with (
        patch(
            "cortex.tools.files.markdown_lint.load_markdown_lint_index_safe",
            new_callable=AsyncMock,
            return_value=index,
        ) as mock_load,
        patch(
            "cortex.tools.files.markdown_lint.filter_files_for_linting",
            new_callable=AsyncMock,
            return_value=(
                [tmp_path / "docs" / "file.md"],
                [],
                {"docs/file.md": "sha256:new"},
            ),
        ) as mock_filter,
        patch(
            "cortex.tools.files.markdown_lint.run_markdownlint_for_files",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_run_files,
        patch(
            "cortex.tools.files.markdown_lint_cache_updates.update_markdown_lint_cache_from_results",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        yield mock_load, mock_filter, mock_run_files, mock_update


@contextmanager
def patch_run_markdownlint_for_files_sequential_progress(
    mock_results: list[FileResult],
):
    with (
        patch(
            "cortex.tools.files.markdown_lint_run.process_markdown_files_sequential",
            new_callable=AsyncMock,
            return_value=mock_results,
        ) as mock_seq,
        patch(
            "cortex.tools.files.markdown_lint_run.report_progress_safe",
            new_callable=AsyncMock,
        ) as mock_progress,
    ):
        yield mock_seq, mock_progress


async def run_mdf_under_seq_progress_mocks(
    tmp_path: Path,
    files_to_lint: list[Path],
    mock_results: list[FileResult],
    mock_ctx: AsyncMock | None,
) -> tuple[list[FileResult], AsyncMock, AsyncMock]:
    with patch_run_markdownlint_for_files_sequential_progress(mock_results) as (
        mock_seq,
        mock_progress,
    ):
        out = await run_markdownlint_for_files(
            files_to_lint=files_to_lint,
            initial_results=[],
            root_path=tmp_path,
            markdownlint_cmd=["rumdl", "check"],
            config_path=None,
            dry_run=False,
            ctx=mock_ctx,
            index=None,
            file_hashes=None,
        )
    return out, mock_seq, mock_progress
