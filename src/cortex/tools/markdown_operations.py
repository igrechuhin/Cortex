"""
Markdown Operations Tools

This module contains MCP tools for markdown file operations.

Total: 1 tool
- fix_markdown_lint: Fix markdownlint errors in modified markdown files
"""

import asyncio
import json
from pathlib import Path
from typing import TypedDict

from cortex.managers.initialization import get_project_root
from cortex.server import mcp


class FileResult(TypedDict):
    """Result for a single file processing."""

    file: str
    fixed: bool
    errors: list[str]
    error_message: str | None


class FixMarkdownLintResult(TypedDict):
    """Result of markdown lint fixing operation."""

    success: bool
    files_processed: int
    files_fixed: int
    files_unchanged: int
    files_with_errors: int
    results: list[FileResult]
    error_message: str | None


def _create_error_result(error: str) -> dict[str, object]:
    """Create error result dict."""
    return {
        "success": False,
        "error": error,
        "stdout": "",
        "stderr": "",
        "returncode": -1,
    }


async def _run_command(
    cmd: list[str], cwd: Path | None = None, timeout: int = 30
) -> dict[str, object]:
    """Run a command asynchronously with timeout.

    Args:
        cmd: Command and arguments as list
        cwd: Working directory (default: None)
        timeout: Timeout in seconds (default: 30)

    Returns:
        Dict with success status, stdout, stderr, returncode
    """
    try:
        process = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=timeout,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return {
            "success": process.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "returncode": process.returncode,
        }
    except asyncio.TimeoutError:
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
    if diff_result["success"]:
        _parse_git_output(str(diff_result.get("stdout", "")), project_root, files)

    # Get staged files
    cached_result = await _run_command(
        ["git", "diff", "--cached", "--name-only"], cwd=project_root
    )
    if cached_result["success"]:
        _parse_git_output(str(cached_result.get("stdout", "")), project_root, files)

    # Optionally include untracked files
    if include_untracked:
        status_result = await _run_command(
            ["git", "status", "--porcelain"], cwd=project_root
        )
        if status_result["success"]:
            _parse_untracked_files(
                str(status_result.get("stdout", "")), project_root, files
            )

    return sorted(set(files))


async def _check_markdownlint_available() -> bool:
    """Check if markdownlint-cli2 is available in PATH.

    Returns:
        True if markdownlint-cli2 is available, False otherwise
    """
    result = await _run_command(["markdownlint-cli2", "--version"])
    success = result.get("success", False)
    return bool(success)


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
    relative_path: str, errors: list[str], return_code: int, error_msg: str | None
) -> FileResult:
    """Build error result for markdownlint fix."""
    if return_code == 0 and errors:
        return {
            "file": relative_path,
            "fixed": True,
            "errors": errors,
            "error_message": None,
        }

    error_message = error_msg if isinstance(error_msg, str) else "Unknown error"
    if not error_message and errors:
        error_message = "; ".join(errors[:3])

    return {
        "file": relative_path,
        "fixed": False,
        "errors": errors,
        "error_message": error_message,
    }


async def _run_markdownlint_fix(
    file_path: Path, project_root: Path, dry_run: bool = False
) -> FileResult:
    """Run markdownlint --fix on a file.

    Args:
        file_path: Path to the markdown file
        project_root: Root directory of the project
        dry_run: If True, only check without fixing (default: False)

    Returns:
        FileResult with processing status
    """
    relative_path = file_path.relative_to(project_root)
    cmd = ["markdownlint-cli2"]
    if not dry_run:
        cmd.append("--fix")
    cmd.append(str(relative_path))

    result = await _run_command(cmd, cwd=project_root, timeout=60)

    if not result["success"]:
        error_msg_obj = result.get("error")
        error_msg = str(error_msg_obj) if error_msg_obj is not None else None
        stderr = str(result.get("stderr", ""))
        returncode_obj = result.get("returncode", -1)
        return_code = (
            int(returncode_obj) if isinstance(returncode_obj, (int, str)) else -1
        )
        errors = _parse_markdownlint_errors(stderr)
        return _build_error_result(str(relative_path), errors, return_code, error_msg)

    # Success - check if file was actually modified
    stdout = str(result.get("stdout", ""))
    errors = _parse_markdownlint_output(stdout)
    fixed = bool(errors) and not dry_run

    return {
        "file": str(relative_path),
        "fixed": fixed,
        "errors": errors,
        "error_message": None,
    }


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


async def _validate_markdown_prerequisites(root_path: Path) -> str | None:
    """Validate git repository and markdownlint availability."""
    git_check = await _run_command(["git", "rev-parse", "--git-dir"], cwd=root_path)
    if not git_check["success"]:
        return _create_error_response("Not in a git repository")

    if not await _check_markdownlint_available():
        return _create_error_response(
            "markdownlint-cli2 not found. "
            + "Install it with: npm install -g markdownlint-cli2"
        )

    return None


async def _process_markdown_files(
    files: list[Path], root_path: Path, dry_run: bool
) -> list[FileResult]:
    """Process list of markdown files."""
    results: list[FileResult] = []
    for file_path in files:
        if not file_path.exists():
            continue
        result = await _run_markdownlint_fix(file_path, root_path, dry_run)
        results.append(result)
    return results


def _calculate_statistics(results: list[FileResult]) -> tuple[int, int, int]:
    """Calculate statistics from file results."""
    files_fixed = sum(1 for r in results if r["fixed"])
    files_with_errors = sum(1 for r in results if r["error_message"] is not None)
    files_unchanged = len(results) - files_fixed - files_with_errors
    return files_fixed, files_with_errors, files_unchanged


@mcp.tool()
async def fix_markdown_lint(
    project_root: str | None = None,
    include_untracked: bool = False,
    dry_run: bool = False,
) -> str:
    """Fix markdownlint errors in modified markdown files.

    Automatically scans modified markdown files in the working copy,
    detects markdownlint errors, and fixes them automatically.

    Args:
        project_root: Path to project root directory. If None, uses current directory.
        include_untracked: Include untracked markdown files (default: False)
        dry_run: Check for errors without fixing them (default: False)

    Returns:
        JSON string with fix results containing:
        - success: Whether operation succeeded
        - files_processed: Number of files processed
        - files_fixed: Number of files with fixes applied
        - files_unchanged: Number of files unchanged
        - files_with_errors: Number of files with unfixable errors
        - results: List of FileResult objects with per-file details
        - error_message: Error message if operation failed

    Examples:
        Example 1: Fix markdownlint errors in modified files
        >>> await fix_markdown_lint()
        {
          "success": true,
          "files_processed": 3,
          "files_fixed": 2,
          "files_unchanged": 1,
          "files_with_errors": 0,
          "results": [
            {
              "file": "README.md",
              "fixed": true,
              "errors": ["Fixed trailing spaces"],
              "error_message": null
            }
          ],
          "error_message": null
        }

        Example 2: Check for errors without fixing (dry-run)
        >>> await fix_markdown_lint(dry_run=True)
        {
          "success": true,
          "files_processed": 3,
          "files_fixed": 0,
          "files_unchanged": 1,
          "files_with_errors": 2,
          "results": [...],
          "error_message": null
        }

    Note:
        - Requires markdownlint-cli2 to be installed: npm install -g markdownlint-cli2
        - Only processes files tracked by git (staged, unstaged, optionally untracked)
        - Only processes .md and .mdc files
        - Returns error if not in a git repository
        - Returns error if markdownlint-cli2 is not available
    """
    try:
        root_path = Path(get_project_root(project_root))

        # Validate prerequisites
        validation_error = await _validate_markdown_prerequisites(root_path)
        if validation_error:
            return validation_error

        # Get and process files
        files = await _get_modified_markdown_files(root_path, include_untracked)
        if not files:
            return _create_empty_success_response()

        results = await _process_markdown_files(files, root_path, dry_run)
        files_fixed, files_with_errors, files_unchanged = _calculate_statistics(results)
        script_result: FixMarkdownLintResult = {
            "success": files_with_errors == 0,
            "files_processed": len(results),
            "files_fixed": files_fixed,
            "files_unchanged": files_unchanged,
            "files_with_errors": files_with_errors,
            "results": results,
            "error_message": None,
        }

        return json.dumps(script_result, indent=2)

    except Exception as e:
        return _create_error_response(str(e))
