"""Post-lint cache persistence and per-file progress callbacks for markdown lint."""

from __future__ import annotations

from pathlib import Path

from cortex.core.context_logging import MCPContext, log_client, report_progress_safe
from cortex.core.exceptions import FileLockTimeoutError
from cortex.tools.files.markdown_lint_cache import (
    MarkdownLintIndex,
    save_markdown_lint_index,
)
from cortex.tools.files.markdown_lint_helpers import FileResult


async def _update_index_after_file(
    result: FileResult,
    index: MarkdownLintIndex,
    file_hashes: dict[str, str],
    root_path: Path,
) -> None:
    """Update markdown-lint cache after one file; persist so work is not lost (clean only)."""
    rel_path = result.file
    content_hash = file_hashes.get(rel_path)
    if content_hash is None:
        return
    if result.error_message is None:
        index.files[rel_path] = content_hash
    else:
        _ = index.files.pop(rel_path, None)
    await save_markdown_lint_index(root_path, index)


async def after_one_file(
    result: FileResult | None,
    results: list[FileResult],
    current_n: list[int],
    index: MarkdownLintIndex | None,
    file_hashes: dict[str, str] | None,
    root_path: Path,
    progress_ctx: MCPContext | None,
    progress_total: int | None,
) -> None:
    """Append result, update cache, and report progress after one file."""
    if result is not None:
        results.append(result)
        if index is not None and file_hashes is not None:
            await _update_index_after_file(result, index, file_hashes, root_path)
    current_n[0] = len(results)
    if progress_ctx and progress_total and result is not None:
        await report_progress_safe(
            progress_ctx, float(len(results)), float(progress_total)
        )


async def update_markdown_lint_cache_from_results(
    index: MarkdownLintIndex,
    project_root: Path,
    results: list[FileResult],
    file_hashes: dict[str, str],
) -> None:
    """Update markdown lint cache: add clean entries, remove dirty."""
    for result in results:
        file_path = result.file
        content_hash = file_hashes.get(file_path)
        if content_hash is None:
            continue
        if result.error_message is None:
            index.files[file_path] = content_hash
        else:
            _ = index.files.pop(file_path, None)
    await save_markdown_lint_index(project_root, index)


async def update_markdown_lint_cache_safe(
    index: MarkdownLintIndex,
    root_path: Path,
    results: list[FileResult],
    file_hashes: dict[str, str],
    ctx: MCPContext | None = None,
) -> None:
    """Update markdown lint cache with error handling."""
    try:
        await update_markdown_lint_cache_from_results(
            index, root_path, results, file_hashes
        )
    except (OSError, ValueError, KeyError, FileLockTimeoutError) as e:
        await log_client(
            ctx,
            "warning",
            f"Failed to update markdown lint cache: {e}",
            logger_name=__name__,
        )
