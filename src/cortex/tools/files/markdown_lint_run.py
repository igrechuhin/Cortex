"""Run markdownlint in batches with heartbeat and progress reporting."""

# pyright: reportPrivateUsage=false

import asyncio
import re
from pathlib import Path

from cortex.core.constants import (
    MARKDOWN_LINT_BATCH_SIZE,
    MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS,
)
from cortex.core.context_logging import MCPContext, report_progress_safe
from cortex.tools.files.markdown_lint_cache import MarkdownLintIndex
from cortex.tools.files.markdown_lint_core import after_one_file, run_command
from cortex.tools.files.markdown_lint_helpers import (
    FileResult,
    _build_error_result,
    _build_markdownlint_batch_results,
    _chunk_paths,
    _parse_markdownlint_errors,
    _parse_markdownlint_lines_by_file,
    _parse_markdownlint_output,
    _result_error,
    _result_returncode,
    _result_stderr,
    _result_stdout,
    _result_success,
)

__all__ = [
    "_process_markdown_files_sequential",
    "run_markdownlint_batch",
    "run_markdownlint_fix",
    "run_markdownlint_for_files",
]


async def _run_markdownlint_fix(  # pyright: ignore[reportUnusedFunction]
    file_path: Path,
    project_root: Path,
    markdownlint_cmd: list[str],
    dry_run: bool = False,
) -> FileResult:
    """Run markdownlint --fix on a file; returns FileResult."""
    relative_path = file_path.relative_to(project_root)
    cmd = markdownlint_cmd.copy()

    if not dry_run:
        cmd.append("--fix")
    cmd.append(str(relative_path))

    result = await run_command(cmd, cwd=project_root, timeout=60)

    if not _result_success(result):
        error_msg = _result_error(result)
        return_code = _result_returncode(result)
        errors = _parse_markdownlint_errors(_result_stderr(result))
        return _build_error_result(str(relative_path), errors, return_code, error_msg)

    errors = _parse_markdownlint_output(_result_stdout(result))
    fixed = bool(errors) and not dry_run

    return FileResult(
        file=str(relative_path),
        fixed=fixed,
        errors=errors,
        error_message=None,
    )


async def _run_per_file_fallback(
    file_paths: list[Path],
    project_root: Path,
    markdownlint_cmd: list[str],
    dry_run: bool,
) -> list[FileResult]:
    """Re-run each file individually to get rule codes when batch fails."""
    fallback_results: list[FileResult] = []
    for file_path in file_paths:
        file_result = await _run_markdownlint_fix(
            file_path, project_root, markdownlint_cmd, dry_run
        )
        fallback_results.append(file_result)
    return fallback_results


def _has_parsed_rule_codes(
    rel_strs: list[str],
    by_file: dict[str, list[str]],
    stderr: str,
) -> bool:
    """Check if stderr parsing yielded any rule codes (MD followed by 3 digits pattern)."""
    if any(by_file.get(rel, []) for rel in rel_strs):
        return True
    return bool(re.search(r"MD\d{3}", stderr))


def _build_batch_command(
    rel_strs: list[str],
    markdownlint_cmd: list[str],
    config_path: Path | None,
    project_root: Path,
    dry_run: bool,
) -> list[str]:
    """Build command for batch markdownlint run."""
    cmd = markdownlint_cmd.copy()
    if not dry_run:
        cmd.append("--fix")
    if config_path is not None:
        cmd.extend(["--config", str(config_path.relative_to(project_root))])
    cmd.extend(rel_strs)
    return cmd


async def _run_markdownlint_batch(
    file_paths: list[Path],
    project_root: Path,
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
) -> list[FileResult]:
    """Run markdownlint --fix on multiple files in one invocation."""
    if not file_paths:
        return []
    rel_strs = [str(p.relative_to(project_root)) for p in file_paths]
    cmd = _build_batch_command(
        rel_strs, markdownlint_cmd, config_path, project_root, dry_run
    )
    result = await run_command(cmd, cwd=project_root, timeout=120)
    success = _result_success(result)
    out = _result_stdout(result) if success else _result_stderr(result)
    by_file = _parse_markdownlint_lines_by_file(out)
    raw_lines = _parse_markdownlint_output(out) if success else []

    if not success and not _has_parsed_rule_codes(
        rel_strs, by_file, _result_stderr(result)
    ):
        return await _run_per_file_fallback(
            file_paths, project_root, markdownlint_cmd, dry_run
        )

    return _build_markdownlint_batch_results(
        rel_strs, result, by_file, raw_lines, dry_run
    )


# Public aliases for code that needs to call these (e.g. tests)
run_markdownlint_batch = _run_markdownlint_batch
run_markdownlint_fix = _run_markdownlint_fix


async def _markdown_lint_heartbeat_loop(
    progress_ctx: MCPContext,
    current_n: list[int],
    total: int,
) -> None:
    """Send progress (current_n, total) every N seconds to keep MCP connection alive."""
    while True:
        await asyncio.sleep(MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS)
        n = current_n[0]
        await report_progress_safe(progress_ctx, float(n), float(total))


def _start_markdown_lint_heartbeat(
    progress_ctx: MCPContext | None,
    current_n: list[int],
    total: int,
) -> asyncio.Task[None] | None:
    """Start heartbeat task if progress reporting is enabled."""
    if progress_ctx is None or total <= 0:
        return None
    return asyncio.create_task(
        _markdown_lint_heartbeat_loop(progress_ctx, current_n, total)
    )


async def _cancel_heartbeat_task(task: asyncio.Task[None] | None) -> None:
    """Cancel and await the heartbeat task if present."""
    if task is None:
        return
    _ = task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _run_batched_markdown_loop(
    files: list[Path],
    root_path: Path,
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    results: list[FileResult],
    current_n: list[int],
    index: MarkdownLintIndex | None,
    file_hashes: dict[str, str] | None,
    progress_ctx: MCPContext | None,
    progress_total: int | None,
) -> None:
    """Run markdown lint in batches; appends to results and updates current_n."""
    chunks = _chunk_paths(files, MARKDOWN_LINT_BATCH_SIZE)
    for chunk in chunks:
        batch_results = await _run_markdownlint_batch(
            chunk, root_path, markdownlint_cmd, config_path, dry_run
        )
        for result in batch_results:
            await after_one_file(
                result,
                results,
                current_n,
                index,
                file_hashes,
                root_path,
                progress_ctx,
                progress_total,
            )


async def _run_markdownlint_for_batches(
    files: list[Path],
    root_path: Path,
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    index: MarkdownLintIndex | None,
    file_hashes: dict[str, str] | None,
    progress_ctx: MCPContext | None,
    progress_total: int,
) -> list[FileResult]:
    """Run markdownlint batches and return the collected results."""
    results: list[FileResult] = []
    current_n: list[int] = [0]
    await _run_batched_markdown_loop(
        files,
        root_path,
        markdownlint_cmd,
        config_path,
        dry_run,
        results,
        current_n,
        index,
        file_hashes,
        progress_ctx,
        progress_total,
    )
    return results


async def _process_markdown_files_sequential(
    files: list[Path],
    root_path: Path,
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    *,
    progress_ctx: MCPContext | None = None,
    progress_total: int | None = None,
    index: MarkdownLintIndex | None = None,
    file_hashes: dict[str, str] | None = None,
) -> list[FileResult]:
    """Process markdown files in batches. Heartbeat avoids MCP client idle timeout."""
    existing_files = [f for f in files if f.is_file()]
    if not existing_files:
        return []
    total = progress_total if progress_total is not None else len(existing_files)
    return await _run_markdownlint_with_heartbeat(
        existing_files,
        root_path,
        markdownlint_cmd,
        config_path,
        dry_run,
        progress_ctx=progress_ctx,
        progress_total=total,
        index=index,
        file_hashes=file_hashes,
    )


async def _run_markdownlint_with_heartbeat(
    files: list[Path],
    root_path: Path,
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    *,
    progress_ctx: MCPContext | None,
    progress_total: int,
    index: MarkdownLintIndex | None,
    file_hashes: dict[str, str] | None,
) -> list[FileResult]:
    """Run markdownlint batches while sending heartbeat progress."""
    current_n: list[int] = [0]
    heartbeat_task = _start_markdown_lint_heartbeat(
        progress_ctx, current_n, progress_total
    )
    try:
        return await _run_markdownlint_for_batches(
            files,
            root_path,
            markdownlint_cmd,
            config_path,
            dry_run,
            index,
            file_hashes,
            progress_ctx,
            progress_total,
        )
    finally:
        await _cancel_heartbeat_task(heartbeat_task)


async def run_markdownlint_for_files(
    files_to_lint: list[Path],
    initial_results: list[FileResult],
    root_path: Path,
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    *,
    ctx: MCPContext | None = None,
    index: MarkdownLintIndex | None = None,
    file_hashes: dict[str, str] | None = None,
) -> list[FileResult]:
    """Run markdownlint for the given files and combine with initial results."""
    if not files_to_lint:
        return initial_results

    if ctx is not None:
        await report_progress_safe(ctx, 0.0, float(len(files_to_lint)))

    lint_results = await _process_markdown_files_sequential(
        files_to_lint,
        root_path,
        markdownlint_cmd,
        config_path,
        dry_run,
        progress_ctx=ctx,
        progress_total=len(files_to_lint),
        index=index,
        file_hashes=file_hashes,
    )
    return [*initial_results, *lint_results]
