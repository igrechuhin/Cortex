"""MCP tools for markdown file operations (fix_markdown_lint, fix_roadmap_corruption)."""

# pyright: reportPrivateUsage=false

import asyncio
import hashlib
import json
from pathlib import Path

import aiofiles
from pydantic import BaseModel, ConfigDict, Field

from cortex.core.constants import (
    GIT_OPERATION_TIMEOUT_SECONDS,
    MARKDOWN_LINT_BATCH_SIZE,
    MARKDOWN_LINT_PROGRESS_HEARTBEAT_SECONDS,
    MCP_TOOL_TIMEOUT_VERY_COMPLEX,
)
from cortex.core.context_logging import MCPContext, log_client, report_progress_safe
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import GitCommandResult
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.markdown_lint_cache import (
    MarkdownLintIndex,
    load_markdown_lint_index_safe,
    save_markdown_lint_index,
)
from cortex.tools.markdown_lint_helpers import (
    FileResult,
    _apply_validation_error_hint,
    _build_error_result,
    _build_markdownlint_batch_results,
    _calculate_statistics,
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
from cortex.tools.markdown_lint_responses import (
    create_empty_success_response,
    create_error_response,
)
from cortex.tools.roadmap_corruption import CorruptionMatch

__all__ = [
    "FileResult",
    "FixMarkdownLintResult",
    "_calculate_statistics",
    "fix_markdown_lint",
]


class FixMarkdownLintResult(BaseModel):
    """Result of markdown lint fixing operation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    success: bool = Field(description="Whether operation succeeded")
    files_processed: int = Field(ge=0, description="Number of files processed")
    files_fixed: int = Field(ge=0, description="Number of files fixed")
    files_unchanged: int = Field(ge=0, description="Number of files unchanged")
    files_with_errors: int = Field(ge=0, description="Number of files with errors")
    results: list[FileResult] = Field(
        default_factory=lambda: list[FileResult](), description="File results"
    )
    error_message: str | None = Field(default=None, description="Error message if any")


def _create_error_result(error: str) -> GitCommandResult:
    """Create error result."""
    return GitCommandResult(
        success=False,
        error=error,
        stdout="",
        stderr="",
        returncode=-1,
    )


async def _run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = GIT_OPERATION_TIMEOUT_SECONDS,
) -> GitCommandResult:
    """Run a command asynchronously with timeout.

    Args:
        cmd: Command and arguments as list
        cwd: Working directory (default: None)
        timeout: Timeout in seconds (default from constants)

    Returns:
        GitCommandResult with success status, stdout, stderr, returncode
    """
    try:
        async with asyncio.timeout(timeout):
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            return GitCommandResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                returncode=process.returncode,
            )
    except TimeoutError:
        return _create_error_result(f"Command timed out after {timeout}s")
    except Exception as e:
        return _create_error_result(str(e))


def _parse_git_output(stdout: str, project_root: Path, files: list[Path]) -> None:
    """Parse git command output and add markdown files to list."""
    for line in stdout.strip().split("\n"):
        if line.strip():
            file_path = project_root / line.strip()
            if file_path.suffix in (".md", ".mdc") and file_path not in files:
                files.append(file_path)


def _parse_untracked_files(stdout: str, project_root: Path, files: list[Path]) -> None:
    """Parse untracked files from git status output."""
    for line in stdout.strip().split("\n"):
        if line.startswith("??"):
            file_path = project_root / line[3:].strip()
            if file_path.suffix in (".md", ".mdc") and file_path not in files:
                files.append(file_path)


async def _calculate_file_hash(file_path: Path) -> str | None:
    """Calculate sha256 hash for a file."""
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(8192)
                if not chunk:
                    break
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"
    except Exception:
        return None


async def _get_modified_markdown_files(
    project_root: Path, include_untracked: bool = False
) -> list[Path]:
    """Get list of modified markdown files from git.

    Args:
        project_root: Root directory of the project
        include_untracked: Include untracked files (default: False)

    Returns:
        List of modified markdown file paths
    """
    files: list[Path] = []

    # Get staged and unstaged modified files
    diff_result = await _run_command(["git", "diff", "--name-only"], cwd=project_root)
    if _result_success(diff_result):
        _parse_git_output(_result_stdout(diff_result), project_root, files)

    # Get staged files
    cached_result = await _run_command(
        ["git", "diff", "--cached", "--name-only"], cwd=project_root
    )
    if _result_success(cached_result):
        _parse_git_output(_result_stdout(cached_result), project_root, files)

    # Optionally include untracked files
    if include_untracked:
        status_result = await _run_command(
            ["git", "status", "--porcelain"], cwd=project_root
        )
        if _result_success(status_result):
            _parse_untracked_files(_result_stdout(status_result), project_root, files)

    return sorted(set(files))


def _local_markdownlint_path(project_root: Path) -> Path | None:
    """Return path to local node_modules/.bin/markdownlint-cli2 if present."""
    local_bin = project_root / "node_modules" / ".bin" / "markdownlint-cli2"
    if local_bin.exists():
        return local_bin.resolve()
    # Windows
    win_cmd = project_root / "node_modules" / ".bin" / "markdownlint-cli2.cmd"
    if win_cmd.exists():
        return win_cmd.resolve()
    return None


async def _find_markdownlint_command(
    project_root: Path | None = None,
) -> list[str] | None:
    """Find available markdownlint-cli2 command.

    Checks (1) local node_modules/.bin if project_root given, (2) PATH,
    (3) npx as fallback.

    Returns:
        Command list to use (e.g., ["/path/to/markdownlint-cli2"] or
        ["npx", "--yes", "markdownlint-cli2"]), or None if not available
    """
    # Prefer local install (avoids npx network/SSL when running)
    if project_root is not None:
        local = _local_markdownlint_path(project_root)
        if local is not None:
            result = await _run_command([str(local), "--version"], cwd=project_root)
            if _result_success(result) or "markdownlint-cli2" in _result_stdout(result):
                return [str(local)]

    # Try direct command in PATH
    result = await _run_command(["markdownlint-cli2", "--version"])
    if _result_success(result) or "markdownlint-cli2" in _result_stdout(result):
        return ["markdownlint-cli2"]

    # Try npx as fallback (may hit network/SSL in some environments)
    result = await _run_command(
        ["npx", "--yes", "markdownlint-cli2", "--version"],
        cwd=project_root if project_root is not None else None,
    )
    if _result_success(result) or "markdownlint-cli2" in _result_stdout(result):
        return ["npx", "--yes", "markdownlint-cli2"]

    return None


def _find_markdownlint_config(project_root: Path) -> Path | None:
    """Find markdownlint config file in project root.

    Checks for .markdownlint-cli2.yaml first (supports ignore patterns),
    then falls back to .markdownlint.json.

    Args:
        project_root: Root directory of the project

    Returns:
        Path to config file if found, None otherwise
    """
    # Prefer .markdownlint-cli2.yaml (supports ignore patterns)
    yaml_config = project_root / ".markdownlint-cli2.yaml"
    if yaml_config.exists():
        return yaml_config

    # Fall back to .markdownlint.json
    json_config = project_root / ".markdownlint.json"
    if json_config.exists():
        return json_config

    return None


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

    result = await _run_command(cmd, cwd=project_root, timeout=60)

    if not _result_success(result):
        error_msg = _result_error(result)
        return_code = _result_returncode(result)
        errors = _parse_markdownlint_errors(_result_stderr(result))
        return _build_error_result(str(relative_path), errors, return_code, error_msg)

    # Success - check if file was actually modified
    errors = _parse_markdownlint_output(_result_stdout(result))
    fixed = bool(errors) and not dry_run

    return FileResult(
        file=str(relative_path),
        fixed=fixed,
        errors=errors,
        error_message=None,
    )


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
    cmd = markdownlint_cmd.copy()
    if not dry_run:
        cmd.append("--fix")
    if config_path is not None:
        cmd.extend(["--config", str(config_path.relative_to(project_root))])
    cmd.extend(rel_strs)
    result = await _run_command(cmd, cwd=project_root, timeout=120)
    out = _result_stdout(result) if _result_success(result) else _result_stderr(result)
    by_file = _parse_markdownlint_lines_by_file(out)
    raw_lines = _parse_markdownlint_output(out) if _result_success(result) else []
    return _build_markdownlint_batch_results(
        rel_strs,
        result,
        by_file,
        raw_lines,
        dry_run,
    )


async def _validate_markdown_prerequisites(
    root_path: Path,
) -> tuple[str | None, list[str] | None, Path | None]:
    """Validate git and markdownlint; return (error_or_none, cmd_or_none, config_or_none)."""
    git_check = await _run_command(["git", "rev-parse", "--git-dir"], cwd=root_path)
    if not _result_success(git_check):
        return create_error_response("Not in a git repository"), None, None

    markdownlint_cmd = await _find_markdownlint_command(root_path)
    if markdownlint_cmd is None:
        return (
            create_error_response(
                "markdownlint-cli2 not found. "
                + "From project root run: npm install (uses package.json), "
                + "or: npm install -g markdownlint-cli2, or ensure npx is available."
            ),
            None,
            None,
        )
    config_path = _find_markdownlint_config(root_path)
    return None, markdownlint_cmd, config_path


async def _get_markdown_files_to_process(
    root_path: Path, include_untracked_markdown: bool
) -> list[Path]:
    """Get git-modified (and optionally untracked) markdown files to process."""
    return await _get_modified_markdown_files(root_path, include_untracked_markdown)


def _is_cached_clean_entry(
    stored_hash: str | None,
    content_hash: str,
    dry_run: bool,
) -> bool:
    """Return True if stored hash equals current hash (clean, skip lint)."""
    return stored_hash is not None and stored_hash == content_hash and not dry_run


_HASH_CONCURRENCY = 32


async def _compute_file_hashes(
    files: list[Path], project_root: Path, max_concurrent: int = _HASH_CONCURRENCY
) -> dict[str, str | None]:
    """Compute content hashes for files in parallel; path -> hash or None."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def hash_one(file_path: Path) -> tuple[str, str | None]:
        rel = str(file_path.relative_to(project_root))
        async with semaphore:
            h = await _calculate_file_hash(file_path)
        return rel, h

    pairs = await asyncio.gather(
        *[hash_one(fp) for fp in files], return_exceptions=True
    )
    out: dict[str, str | None] = {}
    for p in pairs:
        if isinstance(p, BaseException):
            continue
        rel, h = p
        out[rel] = h
    return out


async def _filter_files_for_linting(
    project_root: Path,
    files: list[Path],
    index: MarkdownLintIndex,
    dry_run: bool,
) -> tuple[list[Path], list[FileResult], dict[str, str]]:
    """Filter files using lint cache and prepare initial results.

    Uses parallel hashing so cache lookups are fast even with many files;
    only files not in cache or with changed content are passed to markdownlint.
    """
    file_hashes = await _compute_file_hashes(files, project_root)

    files_to_lint: list[Path] = []
    initial_results: list[FileResult] = []
    hashes_for_cache: dict[str, str] = {}

    for file_path in files:
        rel_path = str(file_path.relative_to(project_root))
        content_hash = file_hashes.get(rel_path)
        if content_hash is None:
            files_to_lint.append(file_path)
            continue

        hashes_for_cache[rel_path] = content_hash
        stored_hash = index.files.get(rel_path)
        if _is_cached_clean_entry(stored_hash, content_hash, dry_run):
            initial_results.append(
                FileResult(
                    file=rel_path,
                    fixed=False,
                    errors=[],
                    error_message=None,
                )
            )
            continue

        files_to_lint.append(file_path)

    return files_to_lint, initial_results, hashes_for_cache


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


async def _after_one_file(
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
            await _after_one_file(
                result,
                results,
                current_n,
                index,
                file_hashes,
                root_path,
                progress_ctx,
                progress_total,
            )


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


def _build_fix_response(results: list[FileResult]) -> str:
    """Build JSON response from file results."""
    files_fixed, files_with_errors, files_unchanged = _calculate_statistics(results)
    script_result = FixMarkdownLintResult(
        success=files_with_errors == 0,
        files_processed=len(results),
        files_fixed=files_fixed,
        files_unchanged=files_unchanged,
        files_with_errors=files_with_errors,
        results=results,
        error_message=None,
    )
    return json.dumps(script_result.model_dump(), indent=2)


async def _update_markdown_lint_cache_from_results(
    index: MarkdownLintIndex,
    project_root: Path,
    results: list[FileResult],
    file_hashes: dict[str, str],
) -> None:
    """Update markdown lint cache: add clean entries, remove dirty. Cache errors handled by save_markdown_lint_index."""
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


async def _run_markdownlint_for_files(
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


async def _fix_markdown_lint_impl(
    root_path: Path,
    include_untracked_markdown: bool,
    dry_run: bool,
    ctx: MCPContext | None = None,
) -> str:
    """Core implementation for fix_markdown_lint MCP tool.

    Always scopes to git-modified (+ optionally untracked) markdown files.
    For full-repo lint, use ``markdownlint-cli2 --fix`` directly from the shell.
    """
    validation_error, markdownlint_cmd, config_path = (
        await _validate_markdown_prerequisites(root_path)
    )
    if validation_error:
        return _apply_validation_error_hint(validation_error)
    assert markdownlint_cmd is not None
    files = await _get_markdown_files_to_process(root_path, include_untracked_markdown)
    if not files:
        return create_empty_success_response()
    return await _run_markdownlint_with_cache(
        root_path, files, markdownlint_cmd, config_path, dry_run, ctx
    )


async def _update_markdown_lint_cache_safe(
    index: MarkdownLintIndex,
    root_path: Path,
    results: list[FileResult],
    file_hashes: dict[str, str],
    ctx: MCPContext | None = None,
) -> None:
    """Update markdown lint cache with error handling.

    Cache update failures are non-fatal - lint results are still valid.
    """
    try:
        await _update_markdown_lint_cache_from_results(
            index, root_path, results, file_hashes
        )
    except Exception as e:
        await log_client(
            ctx,
            "warning",
            f"Failed to update markdown lint cache: {e}",
            logger_name=__name__,
        )


async def _run_markdownlint_with_cache(
    root_path: Path,
    files: list[Path],
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    ctx: MCPContext | None = None,
) -> str:
    """Run markdownlint with cache handling and build response JSON.

    Cache operations are wrapped in try/except to prevent server crashes.
    Cache failures are non-fatal - lint results are still returned.
    """
    index = await load_markdown_lint_index_safe(root_path, ctx)
    files_to_lint, initial_results, file_hashes = await _filter_files_for_linting(
        root_path, files, index, dry_run
    )
    results = await _run_markdownlint_for_files(
        files_to_lint,
        initial_results,
        root_path,
        markdownlint_cmd,
        config_path,
        dry_run,
        ctx=ctx,
        index=index,
        file_hashes=file_hashes,
    )
    # Final cache update in case any results were missed by incremental updates.
    await _update_markdown_lint_cache_safe(
        index,
        root_path,
        results,
        file_hashes,
        ctx,
    )
    return _build_fix_response(results)


async def _fix_markdown_lint_run_or_error(
    ctx: MCPContext | None,
    root_path: Path,
    include_untracked_markdown: bool,
    dry_run: bool,
) -> tuple[str, bool]:
    """Run fix_markdown_lint impl; return (result_json, success)."""
    try:
        result = await _fix_markdown_lint_impl(
            root_path,
            include_untracked_markdown,
            dry_run,
            ctx,
        )
        return (result, True)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await log_client(
            ctx, "error", f"fix_markdown_lint: failed: {e}", logger_name=__name__
        )
        return (create_error_response(str(e)), False)
    except BaseException as e:  # pragma: no cover - defensive guardrail
        await log_client(
            ctx,
            "error",
            f"fix_markdown_lint: fatal: {e!r}",
            logger_name=__name__,
        )
        return (create_error_response(f"Fatal markdown lint error: {e!r}"), False)


@mcp.tool(annotations=safe_write_annotations("Fix Markdown Lint"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX, enable_progress=False)
async def fix_markdown_lint(
    include_untracked_markdown: bool = False,
    dry_run: bool = False,
    check_all_files: bool = False,
    ctx: MCPContext | None = None,
) -> str:
    """Fix markdownlint errors in markdown files.

    USE WHEN: User wants markdown fixes, user needs lint fixes, user
    requests markdown lint fix, user wants to fix markdown errors.

    EXAMPLES: 'fix markdown lint', 'fix markdown errors', 'auto-fix
    markdown', 'fix markdown formatting'.

    RETURNS: JSON with fixes applied, files modified, and lint results.

    Scans markdown files in the working copy, runs `markdownlint-cli2`,
    and optionally applies `--fix` to resolve reported issues.

    The return value is a JSON string encoded from `FixMarkdownLintResult`
    with aggregate counts and per-file `FileResult` entries. Project root
    is resolved by the server (MCP roots or cwd/script detection).

    **Scope**: Always scopes to git-modified and (optionally) untracked
    markdown files. The ``check_all_files`` parameter is accepted for
    backward compatibility but **ignored** — it has no effect. For
    full-repo lint, run ``node_modules/.bin/markdownlint-cli2 --fix``
    directly from the shell.
    """
    _ = check_all_files  # Accepted for backward compat, always scoped to git-modified
    await log_client(ctx, "info", "fix_markdown_lint: starting", logger_name=__name__)
    root_path = await resolve_project_root_async(None, ctx)
    result, ok = await _fix_markdown_lint_run_or_error(
        ctx,
        root_path,
        include_untracked_markdown,
        dry_run,
    )
    if ok:
        await log_client(
            ctx, "info", "fix_markdown_lint: completed", logger_name=__name__
        )
    return result


_ROADMAP_CORRUPTION_HELPER = CorruptionMatch
