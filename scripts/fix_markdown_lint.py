#!/usr/bin/env python3
"""
Markdown Lint Fix Tool.

Automatically scans modified markdown files in the working copy,
detects markdownlint errors, and fixes them automatically.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TypedDict


class FileResult(TypedDict):
    """Result for a single file processing."""

    file: str
    fixed: bool
    errors: list[str]
    error_message: str | None


class ScriptResult(TypedDict):
    """Overall script execution result."""

    success: bool
    files_processed: int
    files_fixed: int
    files_unchanged: int
    files_with_errors: int
    results: list[FileResult]
    error_message: str | None


async def run_command(
    cmd: list[str], cwd: Path | None = None, timeout: int = 30
) -> dict[str, object]:
    """
    Run a command asynchronously with timeout.

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
        return {
            "success": False,
            "error": f"Command timed out after {timeout}s",
            "stdout": "",
            "stderr": "",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
            "returncode": -1,
        }


async def get_modified_markdown_files(
    project_root: Path, include_untracked: bool = False
) -> list[Path]:
    """
    Get list of modified markdown files from git.

    Args:
        project_root: Root directory of the project
        include_untracked: Include untracked files (default: False)

    Returns:
        List of modified markdown file paths
    """
    files: list[Path] = []

    # Get staged and unstaged modified files
    diff_result = await run_command(["git", "diff", "--name-only"], cwd=project_root)
    if diff_result["success"]:
        stdout = diff_result.get("stdout", "")
        if isinstance(stdout, str):
            for line in stdout.strip().split("\n"):
                if line.strip():
                    file_path = project_root / line.strip()
                    if file_path.suffix in (".md", ".mdc"):
                        files.append(file_path)

    # Get staged files
    cached_result = await run_command(
        ["git", "diff", "--cached", "--name-only"], cwd=project_root
    )
    if cached_result["success"]:
        stdout = cached_result.get("stdout", "")
        if isinstance(stdout, str):
            for line in stdout.strip().split("\n"):
                if line.strip():
                    file_path = project_root / line.strip()
                    if file_path.suffix in (".md", ".mdc") and file_path not in files:
                        files.append(file_path)

    # Optionally include untracked files
    if include_untracked:
        status_result = await run_command(
            ["git", "status", "--porcelain"], cwd=project_root
        )
        if status_result["success"]:
            stdout = status_result.get("stdout", "")
            if isinstance(stdout, str):
                for line in stdout.strip().split("\n"):
                    if line.startswith("??"):
                        file_path = project_root / line[3:].strip()
                        if (
                            file_path.suffix in (".md", ".mdc")
                            and file_path not in files
                        ):
                            files.append(file_path)

    return sorted(set(files))


async def check_markdownlint_available() -> bool:
    """
    Check if markdownlint-cli2 is available in PATH.

    Returns:
        True if markdownlint-cli2 is available, False otherwise
    """
    result = await run_command(["markdownlint-cli2", "--version"])
    return result["success"]


async def run_markdownlint_fix(
    file_path: Path, project_root: Path, dry_run: bool = False
) -> FileResult:
    """
    Run markdownlint --fix on a file.

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

    result = await run_command(cmd, cwd=project_root, timeout=60)

    if not result["success"]:
        error_msg = result.get("error")
        stderr = result.get("stderr", "")
        return_code = result.get("returncode", -1)

        # Parse markdownlint errors from stderr
        errors: list[str] = []
        if isinstance(stderr, str):
            for line in stderr.strip().split("\n"):
                if line.strip() and not line.startswith("markdownlint-cli2"):
                    errors.append(line.strip())

        # If return code is 0 but there were errors, it means some were fixed
        if return_code == 0 and errors:
            return {
                "file": str(relative_path),
                "fixed": True,
                "errors": errors,
                "error_message": None,
            }

        # If return code is non-zero, there were unfixable errors
        error_message = error_msg if isinstance(error_msg, str) else "Unknown error"
        if not error_message and errors:
            error_message = "; ".join(errors[:3])

        return {
            "file": str(relative_path),
            "fixed": False,
            "errors": errors,
            "error_message": error_message,
        }

    # Success - check if file was actually modified
    stdout = result.get("stdout", "")
    errors: list[str] = []
    if isinstance(stdout, str):
        for line in stdout.strip().split("\n"):
            if line.strip():
                errors.append(line.strip())

    # If there's output, it means fixes were applied
    fixed = bool(errors) and not dry_run

    return {
        "file": str(relative_path),
        "fixed": fixed,
        "errors": errors,
        "error_message": None,
    }


async def main() -> int:
    """
    Main entry point for the script.

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    parser = argparse.ArgumentParser(
        description="Fix markdownlint errors in modified markdown files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check for errors without fixing them",
    )
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="Include untracked markdown files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args()

    project_root = args.project_root or Path.cwd()

    # Check if we're in a git repository
    git_check = await run_command(["git", "rev-parse", "--git-dir"], cwd=project_root)
    if not git_check["success"]:
        error_msg = "Not in a git repository"
        if args.json:
            result: ScriptResult = {
                "success": False,
                "files_processed": 0,
                "files_fixed": 0,
                "files_unchanged": 0,
                "files_with_errors": 0,
                "results": [],
                "error_message": error_msg,
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        return 1

    # Check if markdownlint-cli2 is available
    if not await check_markdownlint_available():
        error_msg = (
            "markdownlint-cli2 not found. "
            "Install it with: npm install -g markdownlint-cli2"
        )
        if args.json:
            result = {
                "success": False,
                "files_processed": 0,
                "files_fixed": 0,
                "files_unchanged": 0,
                "files_with_errors": 0,
                "results": [],
                "error_message": error_msg,
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        return 1

    # Get modified markdown files
    files = await get_modified_markdown_files(
        project_root, include_untracked=args.include_untracked
    )

    if not files:
        if args.json:
            result = {
                "success": True,
                "files_processed": 0,
                "files_fixed": 0,
                "files_unchanged": 0,
                "files_with_errors": 0,
                "results": [],
                "error_message": None,
            }
            print(json.dumps(result, indent=2))
        else:
            print("No modified markdown files found.")
        return 0

    # Process each file
    results: list[FileResult] = []
    for file_path in files:
        if not file_path.exists():
            continue
        result = await run_markdownlint_fix(
            file_path, project_root, dry_run=args.dry_run
        )
        results.append(result)

    # Calculate statistics
    files_fixed = sum(1 for r in results if r["fixed"])
    files_with_errors = sum(1 for r in results if r["error_message"] is not None)
    files_unchanged = len(results) - files_fixed - files_with_errors

    # Build final result
    script_result: ScriptResult = {
        "success": files_with_errors == 0,
        "files_processed": len(results),
        "files_fixed": files_fixed,
        "files_unchanged": files_unchanged,
        "files_with_errors": files_with_errors,
        "results": results,
        "error_message": None,
    }

    # Output results
    if args.json:
        print(json.dumps(script_result, indent=2))
    else:
        print(f"\nProcessed {len(results)} markdown file(s):")
        print(f"  Fixed: {files_fixed}")
        print(f"  Unchanged: {files_unchanged}")
        print(f"  Errors: {files_with_errors}")

        if files_fixed > 0:
            print("\nFixed files:")
            for r in results:
                if r["fixed"]:
                    print(f"  - {r['file']}")

        if files_with_errors > 0:
            print("\nFiles with errors:")
            for r in results:
                if r["error_message"]:
                    print(f"  - {r['file']}: {r['error_message']}")

    return 0 if script_result["success"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
