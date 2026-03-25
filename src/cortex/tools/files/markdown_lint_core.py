"""Git, command discovery, config, file hashes, and cache filtering for markdown lint.

This module was originally implemented for a Node-based markdown linter and now
uses ``rumdl`` as the underlying Markdown linter/formatter. Public function
names are kept stable (e.g. ``find_markdownlint_command``) for backward
compatibility so callers do not need to change imports when tooling is upgraded.
"""

# pyright: reportPrivateUsage=false

import asyncio
import hashlib
import subprocess
from pathlib import Path

import aiofiles

from cortex.core.constants import GIT_OPERATION_TIMEOUT_SECONDS
from cortex.core.models import GitCommandResult
from cortex.tools.files.markdown_lint_cache import MarkdownLintIndex
from cortex.tools.files.markdown_lint_cache_updates import (
    _update_markdown_lint_cache_from_results,
    after_one_file,
    update_markdown_lint_cache_safe,
)
from cortex.tools.files.markdown_lint_helpers import (
    FileResult,
    _result_stdout,
    _result_success,
)
from cortex.tools.files.markdown_lint_responses import create_error_response

# Excludes matching CI quality workflow (quality.yml markdown step)
_ALL_MARKDOWN_EXCLUDE_DIRS = (
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".git",
)
_ALL_MARKDOWN_EXCLUDE_PREFIXES = (
    ".cortex/plans/archive",
    ".cortex/history/",
    ".cortex/.cache/",
)
_CI_PARITY_MAX_MARKDOWN_FILES = 500

__all__ = [
    "after_one_file",
    "compute_file_hashes",
    "filter_files_for_linting",
    # Backward-compatible name: now discovers rumdl instead of the legacy Node-based linter
    "find_markdownlint_command",
    "get_all_markdown_files_for_lint",
    "get_markdown_files_to_process",
    "get_modified_markdown_files",
    "is_cached_clean_entry",
    "parse_git_output",
    "parse_untracked_files",
    "run_command",
    "_update_markdown_lint_cache_from_results",
    "update_markdown_lint_cache_safe",
    "validate_markdown_prerequisites",
    "calculate_file_hash",
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
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        return _create_error_result(str(e))


def _parse_git_output(stdout: str, project_root: Path, files: list[Path]) -> None:
    """Parse git command output and add markdown files to list."""
    for line in stdout.strip().split("\n"):
        rel = line.strip()
        if not rel:
            continue
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            continue
        file_path = project_root / rel_path
        if file_path.suffix in (".md", ".mdc") and file_path not in files:
            files.append(file_path)


def _parse_untracked_files(stdout: str, project_root: Path, files: list[Path]) -> None:
    """Parse untracked files from git status output."""
    for line in stdout.strip().split("\n"):
        if not line.startswith("??"):
            continue
        rel = line[3:].strip()
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            continue
        file_path = project_root / rel_path
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
    except (OSError, UnicodeDecodeError):
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


async def find_markdownlint_command(
    project_root: Path | None = None,
) -> list[str] | None:
    """Find available rumdl command (backward-compatible name).

    Returns a base command including the ``check`` subcommand so callers
    can append ``--fix`` and file paths directly.

    Discovery order:

    1. Local ``node_modules/.bin/rumdl`` when ``project_root`` is provided.
    2. ``rumdl`` on PATH (installed into the Python environment).
    3. ``npx --yes rumdl`` as a final fallback.
    """
    # 1) Prefer a project-local CLI when project_root is known.
    if project_root is not None:
        local_bin = project_root / "node_modules" / ".bin" / "rumdl"
        if local_bin.exists():
            result = await run_command([str(local_bin.resolve()), "--version"])
            if _result_success(result) or "rumdl" in _result_stdout(result):
                return [str(local_bin.resolve()), "check"]

    # 2) Try rumdl on PATH.
    result = await run_command(["rumdl", "--version"])
    if _result_success(result) or "rumdl" in _result_stdout(result):
        return ["rumdl", "check"]

    # 3) Fallback to npx-based invocation.
    result = await run_command(["npx", "--yes", "rumdl", "--version"])
    if _result_success(result) or "rumdl" in _result_stdout(result):
        return ["npx", "--yes", "rumdl", "check"]

    return None


def _find_markdownlint_config(project_root: Path) -> Path | None:
    """Find Markdown lint config file in project root.

    ``rumdl init`` creates ``.rumdl.toml`` (hidden file) by default — that is
    the canonical name.  ``rumdl.toml`` (no leading dot) is a legacy alias that
    some older documentation referenced; we check it as a fallback so existing
    projects are not broken.
    """
    for name in (".rumdl.toml", "rumdl.toml"):
        config = project_root / name
        if config.exists():
            return config
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
        message = (
            "rumdl not found. Install it into the Python environment for example via "
            "'uv sync --extra dev' (adds rumdl CLI), or ensure a compatible rumdl "
            "binary is on PATH."
        )
        return (create_error_response(message), None, None)
    config_path = _find_markdownlint_config(root_path)
    return None, markdownlint_cmd, config_path


def get_all_markdown_files_for_lint(
    project_root: Path,
    max_files: int = _CI_PARITY_MAX_MARKDOWN_FILES,
) -> list[Path]:
    """Get all markdown files for lint (CI parity with quality.yml markdown step).

    Excludes: node_modules, .venv, venv, __pycache__, .git, and paths under
    ``.cortex/plans/archive``, ``.cortex/history/``, and ``.cortex/.cache/``
    (mirrors detached worker markdown collection and CI/Makefile rumdl scope).
    Returns up to max_files paths, sorted.
    """
    out: list[Path] = []
    try:
        for path in project_root.rglob("*"):
            if len(out) >= max_files:
                break
            if not path.is_file():
                continue
            if path.suffix not in (".md", ".mdc"):
                continue
            try:
                rel = path.relative_to(project_root)
            except ValueError:
                continue
            parts = rel.parts
            if any(d in parts for d in _ALL_MARKDOWN_EXCLUDE_DIRS):
                continue
            rel_posix = str(rel).replace("\\", "/")
            if any(rel_posix.startswith(p) for p in _ALL_MARKDOWN_EXCLUDE_PREFIXES):
                continue
            out.append(path)
    except OSError:
        pass
    return sorted(out)[:max_files]


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


# Public aliases for code that needs to call these (e.g. tests)
is_cached_clean_entry = _is_cached_clean_entry
compute_file_hashes = _compute_file_hashes
calculate_file_hash = _calculate_file_hash
