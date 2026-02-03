"""
Markdown Operations Tools

This module contains MCP tools for markdown file operations.

Total: 2 tools
- fix_markdown_lint: Fix markdownlint errors in markdown files (modified or all files)
- fix_roadmap_corruption: Fix text corruption in roadmap.md
  (missing spaces, malformed dates, etc.)
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

import aiofiles
from pydantic import BaseModel, ConfigDict, Field

from cortex.core.cache_json_access import read_cache_json, write_cache_json
from cortex.core.constants import (
    GIT_OPERATION_TIMEOUT_SECONDS,
    MARKDOWN_LINT_MAX_FILES_WHEN_CHECK_ALL,
    MCP_TOOL_TIMEOUT_VERY_COMPLEX,
)
from cortex.core.context_logging import MCPContext, log_client, report_progress_safe
from cortex.core.mcp_annotations import safe_write_annotations
from cortex.core.mcp_stability import ensure_usage_context, mcp_tool_wrapper
from cortex.core.models import GitCommandResult
from cortex.core.project_root_resolver import resolve_project_root_async
from cortex.server import mcp
from cortex.tools.roadmap_corruption import CorruptionMatch


class FileResult(BaseModel):
    """Result for a single file processing."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File path")
    fixed: bool = Field(description="Whether file was fixed")
    errors: list[str] = Field(default_factory=list, description="List of errors")
    error_message: str | None = Field(default=None, description="Error message if any")


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


class MarkdownLintFileCache(BaseModel):
    """Cache entry for a single markdown file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    path: str = Field(description="Relative file path from project root")
    content_hash: str = Field(description="File content hash (sha256:...)")
    last_checked: str | None = Field(
        default=None, description="UTC timestamp when file was last linted"
    )
    status: str = Field(
        default="clean",
        description="Lint status: 'clean' (no errors) or 'dirty' (errors present)",
    )


class MarkdownLintIndex(BaseModel):
    """On-disk index for markdown lint cache."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    version: str = Field(default="1.0", description="Schema version")
    files: dict[str, MarkdownLintFileCache] = Field(
        default_factory=dict, description="Map of relative path to cache entry"
    )


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


def _result_success(result: GitCommandResult) -> bool:
    return result.success


def _result_stdout(result: GitCommandResult) -> str:
    return result.stdout


def _result_stderr(result: GitCommandResult) -> str:
    return result.stderr


def _result_returncode(result: GitCommandResult) -> int | None:
    return result.returncode


def _result_error(result: GitCommandResult) -> str | None:
    return result.error


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


def _collect_markdown_files_sync(project_root: Path) -> list[Path]:
    """Synchronous file discovery for markdown files (run off event loop).

    Args:
        project_root: Root directory of the project

    Returns:
        List of all markdown file paths
    """
    files: list[Path] = []
    exclude_parts = [
        "/.git/",
        "/node_modules/",
        "/.venv/",
        "/venv/",
        "/__pycache__/",
        "/.pytest_cache/",
        "/htmlcov/",
        "/.coverage",
        "/.cortex/history/",  # Version history files
        "/.cortex/snapshots/",  # Snapshot files
        "/.cortex/plans/archive/",  # Archived plans (matches CI)
        ".cortex/plans/archive/",  # Also match relative paths
        "/.memory-bank-history/",  # Memory bank version history
        ".memory-bank-history/",  # Also match relative paths
        "/benchmark_results/",  # Benchmark output files
        "benchmark_results/",  # Also match relative paths
    ]
    for pattern in ("**/*.md", "**/*.mdc"):
        for file_path in project_root.rglob(pattern):
            file_str = str(file_path)
            if any(part in file_str for part in exclude_parts):
                continue
            if file_path.is_file() and file_path not in files:
                files.append(file_path)
    return sorted(set(files))


async def _get_all_markdown_files(project_root: Path) -> list[Path]:
    """Get all markdown files in the project (non-blocking).

    Runs synchronous rglob in a thread so the event loop stays responsive
    and the MCP tool timeout can cancel the operation if needed.
    """
    return await asyncio.to_thread(_collect_markdown_files_sync, project_root)


_MARKDOWN_LINT_CACHE_KEY = "markdown-lint-index.json"


async def _load_markdown_lint_index(project_root: Path) -> MarkdownLintIndex:
    """Load markdown lint index from .cortex/.cache/markdown-lint-index.json (concurrent-safe).

    Uses cache_json_access.read_cache_json. Updated automatically by fix_markdown_lint.
    """
    raw = await read_cache_json(project_root, _MARKDOWN_LINT_CACHE_KEY)
    if raw is None or not isinstance(raw, dict):
        return MarkdownLintIndex()
    try:
        return MarkdownLintIndex.model_validate(raw)
    except Exception:
        return MarkdownLintIndex()


async def _save_markdown_lint_index(
    project_root: Path, index: MarkdownLintIndex
) -> None:
    """Persist markdown lint index to .cortex/.cache/markdown-lint-index.json (concurrent-safe).

    Uses cache_json_access.write_cache_json. fix_markdown_lint updates this automatically.
    """
    await write_cache_json(
        project_root, _MARKDOWN_LINT_CACHE_KEY, index.model_dump(), indent=2
    )


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


async def _find_markdownlint_command() -> list[str] | None:
    """Find available markdownlint-cli2 command.

    Checks for markdownlint-cli2 in PATH first, then tries npx as fallback.

    Returns:
        Command list to use (e.g., ["markdownlint-cli2"] or
        ["npx", "markdownlint-cli2"]),
        or None if not available
    """
    # Try direct command first
    result = await _run_command(["markdownlint-cli2", "--version"])
    if _result_success(result):
        return ["markdownlint-cli2"]

    # Try npx as fallback (doesn't require global installation)
    result = await _run_command(["npx", "--yes", "markdownlint-cli2", "--version"])
    if _result_success(result):
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


def _parse_markdownlint_errors(stderr: str) -> list[str]:
    """Parse markdownlint errors from stderr."""
    errors: list[str] = []
    for line in stderr.strip().split("\n"):
        if line.strip() and not line.startswith("markdownlint-cli2"):
            errors.append(line.strip())
    return errors


def _parse_markdownlint_output(stdout: str) -> list[str]:
    """Parse markdownlint output from stdout."""
    errors: list[str] = []
    for line in stdout.strip().split("\n"):
        if line.strip():
            errors.append(line.strip())
    return errors


def _build_error_result(
    relative_path: str,
    errors: list[str],
    return_code: int | None,
    error_msg: str | None,
) -> FileResult:
    """Build error result for markdownlint fix."""
    if return_code == 0 and errors:
        return FileResult(
            file=relative_path,
            fixed=True,
            errors=errors,
            error_message=None,
        )

    error_message = error_msg if isinstance(error_msg, str) else "Unknown error"
    if not error_message and errors:
        error_message = "; ".join(errors[:3])

    return FileResult(
        file=relative_path,
        fixed=False,
        errors=errors,
        error_message=error_message,
    )


async def _run_markdownlint_fix(
    file_path: Path,
    project_root: Path,
    markdownlint_cmd: list[str],
    dry_run: bool = False,
) -> FileResult:
    """Run markdownlint --fix on a file.

    Args:
        file_path: Path to the markdown file
        project_root: Root directory of the project
        markdownlint_cmd: Command to use (e.g., ["markdownlint-cli2"] or
        ["npx", "--yes", "markdownlint-cli2"])
        config_path: Optional path to config file (e.g., .markdownlint-cli2.yaml)
        dry_run: If True, only check without fixing (default: False)

    Returns:
        FileResult with processing status
    """
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


def _create_error_response(error_message: str) -> str:
    """Create error response JSON."""
    return json.dumps(
        {
            "success": False,
            "files_processed": 0,
            "files_fixed": 0,
            "files_unchanged": 0,
            "files_with_errors": 0,
            "results": [],
            "error_message": error_message,
        },
        indent=2,
    )


def _create_empty_success_response() -> str:
    """Create empty success response JSON."""
    return json.dumps(
        {
            "success": True,
            "files_processed": 0,
            "files_fixed": 0,
            "files_unchanged": 0,
            "files_with_errors": 0,
            "results": [],
            "error_message": None,
        },
        indent=2,
    )


async def _validate_markdown_prerequisites(
    root_path: Path,
) -> tuple[str | None, list[str] | None, Path | None]:
    """Validate git repository and markdownlint availability.

    Returns:
        Tuple of (error_response_string_or_none, markdownlint_command_or_none,
        config_path_or_none). If error_response is not None, markdownlint_command
        and config_path will be None.
    """
    git_check = await _run_command(["git", "rev-parse", "--git-dir"], cwd=root_path)
    if not _result_success(git_check):
        return _create_error_response("Not in a git repository"), None, None

    markdownlint_cmd = await _find_markdownlint_command()
    if markdownlint_cmd is None:
        return (
            _create_error_response(
                "markdownlint-cli2 not found. "
                + "Install it with: npm install -g markdownlint-cli2 "
                + "or ensure npx is available (npx will auto-install it)"
            ),
            None,
            None,
        )
    config_path = _find_markdownlint_config(root_path)
    return None, markdownlint_cmd, config_path


def _not_in_git_repo_hint(project_root_was_none: bool) -> str:
    """Return hint when git check fails; callers can append to error message."""
    if not project_root_was_none:
        return ""
    return (
        " When running under an MCP client (e.g. Cursor), the server's working "
        "directory may not be your workspace. Pass project_root explicitly set "
        "to your workspace root path (the folder opened in the IDE)."
    )


async def _get_markdown_files_to_process(
    root_path: Path, check_all_files: bool, include_untracked_markdown: bool
) -> list[Path]:
    """Get list of markdown files to process."""
    if check_all_files:
        return await _get_all_markdown_files(root_path)
    return await _get_modified_markdown_files(root_path, include_untracked_markdown)


def _is_cached_clean_entry(
    cache_entry: MarkdownLintFileCache | None,
    content_hash: str,
    dry_run: bool,
) -> bool:
    """Return True if cache entry indicates a clean file we can skip."""
    return (
        cache_entry is not None
        and cache_entry.content_hash == content_hash
        and cache_entry.status == "clean"
        and not dry_run
    )


_HASH_CONCURRENCY = 32


async def _compute_file_hashes(
    files: list[Path], project_root: Path, max_concurrent: int = _HASH_CONCURRENCY
) -> dict[str, str | None]:
    """Compute content hashes for files in parallel.

    Returns:
        Mapping of relative path -> content hash (or None if unreadable).
    """
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
        cache_entry = index.files.get(rel_path)
        if _is_cached_clean_entry(cache_entry, content_hash, dry_run):
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


async def _process_one_markdown_file(
    file_path: Path,
    root_path: Path,
    markdownlint_cmd: list[str],
    dry_run: bool,
) -> FileResult | None:
    """Run markdownlint on one file; return FileResult or None if file missing."""
    if not file_path.exists():
        return None
    try:
        return await _run_markdownlint_fix(
            file_path, root_path, markdownlint_cmd, dry_run
        )
    except Exception as e:
        return FileResult(
            file=str(file_path.relative_to(root_path)),
            fixed=False,
            errors=[str(e)],
            error_message=str(e),
        )


async def _process_markdown_files_sequential(
    files: list[Path],
    root_path: Path,
    markdownlint_cmd: list[str],
    dry_run: bool,
    *,
    progress_ctx: MCPContext | None = None,
    progress_total: int | None = None,
) -> list[FileResult]:
    """Process markdown files sequentially (single-threaded).

    This approach is simpler and more reliable than concurrent processing:
    - Avoids spawning multiple npx processes (each has ~1s startup overhead)
    - Works better with the cache (cache lookups filter most files)
    - Reduces MCP connection load during long operations

    When progress_ctx and progress_total are set, reports progress every 3 files
    to keep the MCP connection alive and avoid client idle timeout (Connection closed).
    """
    results: list[FileResult] = []
    report_every = 3
    for file_path in files:
        result = await _process_one_markdown_file(
            file_path, root_path, markdownlint_cmd, dry_run
        )
        if result is not None:
            results.append(result)
        if progress_ctx is not None and progress_total is not None and result:
            n = len(results)
            if n == 1 or n % report_every == 0 or n == progress_total:
                await report_progress_safe(
                    progress_ctx, float(n), float(progress_total)
                )
    return results


def _calculate_statistics(results: list[FileResult]) -> tuple[int, int, int]:
    """Calculate statistics from file results."""
    files_fixed = sum(1 for r in results if r.fixed)
    files_with_errors = sum(1 for r in results if r.error_message is not None)
    files_unchanged = len(results) - files_fixed - files_with_errors
    return files_fixed, files_with_errors, files_unchanged


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
    """Update markdown lint cache with latest hashes and statuses."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for result in results:
        file_path = result.file
        content_hash = file_hashes.get(file_path)
        if content_hash is None:
            continue
        status = "clean" if result.error_message is None else "dirty"
        index.files[file_path] = MarkdownLintFileCache(
            path=file_path,
            content_hash=content_hash,
            last_checked=now,
            status=status,
        )
    await _save_markdown_lint_index(project_root, index)


async def _run_markdownlint_for_files(
    files_to_lint: list[Path],
    initial_results: list[FileResult],
    root_path: Path,
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    *,
    ctx: MCPContext | None = None,
) -> list[FileResult]:
    """Run markdownlint for the given files and combine with initial results."""
    if not files_to_lint:
        return initial_results

    if ctx is not None:
        await report_progress_safe(ctx, 0.0, float(len(files_to_lint)))

    cmd_with_config = markdownlint_cmd.copy()
    if config_path is not None:
        config_relative = config_path.relative_to(root_path)
        cmd_with_config.extend(["--config", str(config_relative)])

    lint_results = await _process_markdown_files_sequential(
        files_to_lint,
        root_path,
        cmd_with_config,
        dry_run,
        progress_ctx=ctx,
        progress_total=len(files_to_lint),
    )
    return [*initial_results, *lint_results]


def _apply_validation_error_hint(
    validation_error: str, project_root: str | None
) -> str:
    """Apply not-in-git hint to validation error JSON when applicable; return final JSON."""
    if project_root is None and "Not in a git repository" in validation_error:
        hint = _not_in_git_repo_hint(True)
        if hint:
            data = json.loads(validation_error)
            if data.get("error_message"):
                data["error_message"] = data["error_message"].rstrip() + hint
                return json.dumps(data, indent=2)
    return validation_error


async def _fix_markdown_lint_impl(
    project_root: str | None,
    include_untracked_markdown: bool,
    dry_run: bool,
    check_all_files: bool,
    ctx: MCPContext | None = None,
) -> str:
    """Core implementation for fix_markdown_lint MCP tool."""
    root_path = await resolve_project_root_async(project_root, ctx)
    validation_error, markdownlint_cmd, config_path = (
        await _validate_markdown_prerequisites(root_path)
    )
    if validation_error:
        return _apply_validation_error_hint(validation_error, project_root)
    assert markdownlint_cmd is not None
    files = await _get_markdown_files_to_process(
        root_path, check_all_files, include_untracked_markdown
    )
    if not files:
        return _create_empty_success_response()
    if check_all_files and len(files) > MARKDOWN_LINT_MAX_FILES_WHEN_CHECK_ALL:
        files = files[:MARKDOWN_LINT_MAX_FILES_WHEN_CHECK_ALL]
    return await _run_markdownlint_with_cache(
        root_path, files, markdownlint_cmd, config_path, dry_run, ctx
    )


async def _run_markdownlint_with_cache(
    root_path: Path,
    files: list[Path],
    markdownlint_cmd: list[str],
    config_path: Path | None,
    dry_run: bool,
    ctx: MCPContext | None = None,
) -> str:
    """Run markdownlint with cache handling and build response JSON."""
    index = await _load_markdown_lint_index(root_path)
    files_to_lint, initial_results, file_hashes = await _filter_files_for_linting(
        root_path,
        files,
        index,
        dry_run,
    )
    results = await _run_markdownlint_for_files(
        files_to_lint,
        initial_results,
        root_path,
        markdownlint_cmd,
        config_path,
        dry_run,
        ctx=ctx,
    )
    await _update_markdown_lint_cache_from_results(
        index,
        root_path,
        results,
        file_hashes,
    )
    return _build_fix_response(results)


async def _fix_markdown_lint_run_or_error(
    ctx: MCPContext | None,
    project_root: str | None,
    include_untracked_markdown: bool,
    dry_run: bool,
    check_all_files: bool,
) -> tuple[str, bool]:
    """Run fix_markdown_lint impl; return (result_json, success)."""
    try:
        result = await _fix_markdown_lint_impl(
            project_root,
            include_untracked_markdown,
            dry_run,
            check_all_files,
            ctx,
        )
        return (result, True)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await log_client(
            ctx, "error", f"fix_markdown_lint: failed: {e}", logger_name=__name__
        )
        return (_create_error_response(str(e)), False)
    except BaseException as e:  # pragma: no cover - defensive guardrail
        await log_client(
            ctx,
            "error",
            f"fix_markdown_lint: fatal: {e!r}",
            logger_name=__name__,
        )
        return (_create_error_response(f"Fatal markdown lint error: {e!r}"), False)


@mcp.tool(annotations=safe_write_annotations("Fix Markdown Lint"))
@ensure_usage_context
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)
async def fix_markdown_lint(
    project_root: str | None = None,
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
    with aggregate counts and per-file `FileResult` entries.

    When project_root is not provided, the server resolves it via MCP roots
    (roots/list) when the client supports them, so the agent does not need to
    pass it. If resolution fails, the error message suggests passing
    project_root explicitly.
    """
    await log_client(ctx, "info", "fix_markdown_lint: starting", logger_name=__name__)
    result, ok = await _fix_markdown_lint_run_or_error(
        ctx,
        project_root,
        include_untracked_markdown,
        dry_run,
        check_all_files,
    )
    if ok:
        await log_client(
            ctx, "info", "fix_markdown_lint: completed", logger_name=__name__
        )
    return result


def _detect_roadmap_corruption(  # pyright: ignore[unused-function]
    content: str,
) -> list[CorruptionMatch]:
    """Proxy to roadmap corruption detection helper for test compatibility.

    This helper is imported in tests via private name usage.
    """
    module = import_module("cortex.tools.roadmap_corruption")
    detector = getattr(module, "_detect_roadmap_corruption")  # noqa: B009
    return detector(content)


_ROADMAP_CORRUPTION_HELPER = _detect_roadmap_corruption
