"""Git, command discovery, config, file hashes, and cache filtering for markdown lint."""

# pyright: reportPrivateUsage=false

import asyncio
import hashlib
from pathlib import Path

import aiofiles

from cortex.core.constants import GIT_OPERATION_TIMEOUT_SECONDS
from cortex.core.context_logging import MCPContext, log_client, report_progress_safe
from cortex.core.models import GitCommandResult
from cortex.tools.markdown_lint_cache import MarkdownLintIndex, save_markdown_lint_index
from cortex.tools.markdown_lint_helpers import (
    FileResult,
    _result_stdout,
    _result_success,
)
from cortex.tools.markdown_lint_responses import create_error_response

__all__ = [
    "after_one_file",
    "compute_file_hashes",
    "filter_files_for_linting",
    "find_markdownlint_command",
    "get_markdown_files_to_process",
    "get_modified_markdown_files",
    "is_cached_clean_entry",
    "parse_git_output",
    "parse_untracked_files",
    "run_command",
    "_update_markdown_lint_cache_from_results",
    "update_markdown_lint_cache_safe",
    "validate_markdown_prerequisites",
]


def _create_error_result(error: str) -> GitCommandResult:
    """Create error result."""
    return GitCommandResult(
        success=False,
        error=error,
        stdout="",
        stderr="",
        returncode=-1,
    )


async def run_command(
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


parse_git_output = _parse_git_output
parse_untracked_files = _parse_untracked_files


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


async def get_modified_markdown_files(
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

    diff_result = await run_command(["git", "diff", "--name-only"], cwd=project_root)
    if _result_success(diff_result):
        _parse_git_output(_result_stdout(diff_result), project_root, files)

    cached_result = await run_command(
        ["git", "diff", "--cached", "--name-only"], cwd=project_root
    )
    if _result_success(cached_result):
        _parse_git_output(_result_stdout(cached_result), project_root, files)

    if include_untracked:
        status_result = await run_command(
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
    win_cmd = project_root / "node_modules" / ".bin" / "markdownlint-cli2.cmd"
    if win_cmd.exists():
        return win_cmd.resolve()
    return None


async def find_markdownlint_command(
    project_root: Path | None = None,
) -> list[str] | None:
    """Find available markdownlint-cli2 command."""
    if project_root is not None:
        local = _local_markdownlint_path(project_root)
        if local is not None:
            result = await run_command([str(local), "--version"], cwd=project_root)
            if _result_success(result) or "markdownlint-cli2" in _result_stdout(result):
                return [str(local)]

    result = await run_command(["markdownlint-cli2", "--version"])
    if _result_success(result) or "markdownlint-cli2" in _result_stdout(result):
        return ["markdownlint-cli2"]

    result = await run_command(
        ["npx", "--yes", "markdownlint-cli2", "--version"],
        cwd=project_root if project_root is not None else None,
    )
    if _result_success(result) or "markdownlint-cli2" in _result_stdout(result):
        return ["npx", "--yes", "markdownlint-cli2"]

    return None


def _find_markdownlint_config(project_root: Path) -> Path | None:
    """Find markdownlint config file in project root."""
    yaml_config = project_root / ".markdownlint-cli2.yaml"
    if yaml_config.exists():
        return yaml_config
    json_config = project_root / ".markdownlint.json"
    if json_config.exists():
        return json_config
    return None


async def validate_markdown_prerequisites(
    root_path: Path,
) -> tuple[str | None, list[str] | None, Path | None]:
    """Validate git and markdownlint; return (error_or_none, cmd_or_none, config_or_none)."""
    git_check = await run_command(["git", "rev-parse", "--git-dir"], cwd=root_path)
    if not _result_success(git_check):
        return create_error_response("Not in a git repository"), None, None

    markdownlint_cmd = await find_markdownlint_command(root_path)
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


async def get_markdown_files_to_process(
    root_path: Path, include_untracked_markdown: bool
) -> list[Path]:
    """Get git-modified (and optionally untracked) markdown files to process."""
    return await get_modified_markdown_files(root_path, include_untracked_markdown)


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


async def filter_files_for_linting(
    project_root: Path,
    files: list[Path],
    index: MarkdownLintIndex,
    dry_run: bool,
) -> tuple[list[Path], list[FileResult], dict[str, str]]:
    """Filter files using lint cache and prepare initial results."""
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


# Public aliases for code that needs to call these (e.g. tests)
is_cached_clean_entry = _is_cached_clean_entry
compute_file_hashes = _compute_file_hashes
after_one_file = _after_one_file


async def _update_markdown_lint_cache_from_results(
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
