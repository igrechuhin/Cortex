"""
Markdown Operations Tools

This module contains MCP tools for markdown file operations.

Total: 2 tools
- fix_markdown_lint: Fix markdownlint errors in markdown files (modified or all files)
- fix_roadmap_corruption: Fix text corruption in roadmap.md (missing spaces, malformed dates, etc.)
"""

import asyncio
import json
import re
from pathlib import Path
from typing import TypedDict

from cortex.core.constants import MCP_TOOL_TIMEOUT_SECONDS
from cortex.core.mcp_stability import mcp_tool_wrapper
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
        async with asyncio.timeout(timeout):
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd) if cwd else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": process.returncode,
            }
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


async def _get_all_markdown_files(project_root: Path) -> list[Path]:
    """Get all markdown files in the project.

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
    ]
    for pattern in ("**/*.md", "**/*.mdc"):
        for file_path in project_root.rglob(pattern):
            # Skip common directories that shouldn't be linted
            file_str = str(file_path)
            if any(part in file_str for part in exclude_parts):
                continue
            if file_path.is_file() and file_path not in files:
                files.append(file_path)
    return sorted(set(files))


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


async def _find_markdownlint_command() -> list[str] | None:
    """Find available markdownlint-cli2 command.

    Checks for markdownlint-cli2 in PATH first, then tries npx as fallback.

    Returns:
        Command list to use (e.g., ["markdownlint-cli2"] or ["npx", "markdownlint-cli2"]),
        or None if not available
    """
    # Try direct command first
    result = await _run_command(["markdownlint-cli2", "--version"])
    if result.get("success", False):
        return ["markdownlint-cli2"]

    # Try npx as fallback (doesn't require global installation)
    result = await _run_command(["npx", "--yes", "markdownlint-cli2", "--version"])
    if result.get("success", False):
        return ["npx", "--yes", "markdownlint-cli2"]

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
    file_path: Path,
    project_root: Path,
    markdownlint_cmd: list[str],
    dry_run: bool = False,
) -> FileResult:
    """Run markdownlint --fix on a file.

    Args:
        file_path: Path to the markdown file
        project_root: Root directory of the project
        markdownlint_cmd: Command to use (e.g., ["markdownlint-cli2"] or ["npx", "--yes", "markdownlint-cli2"])
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


async def _validate_markdown_prerequisites(
    root_path: Path,
) -> tuple[str | None, list[str] | None]:
    """Validate git repository and markdownlint availability.

    Returns:
        Tuple of (error_response_string_or_none, markdownlint_command_or_none)
        If error_response is not None, markdownlint_command will be None.
    """
    git_check = await _run_command(["git", "rev-parse", "--git-dir"], cwd=root_path)
    if not git_check["success"]:
        return _create_error_response("Not in a git repository"), None

    markdownlint_cmd = await _find_markdownlint_command()
    if markdownlint_cmd is None:
        return (
            _create_error_response(
                "markdownlint-cli2 not found. "
                + "Install it with: npm install -g markdownlint-cli2 "
                + "or ensure npx is available (npx will auto-install it)"
            ),
            None,
        )

    return None, markdownlint_cmd


async def _process_markdown_files(
    files: list[Path],
    root_path: Path,
    markdownlint_cmd: list[str],
    dry_run: bool,
    max_concurrent: int = 5,
    batch_size: int = 50,
) -> list[FileResult]:
    """Process list of markdown files with batching and concurrency."""
    results: list[FileResult] = []
    semaphore = asyncio.Semaphore(max_concurrent)

    for i in range(0, len(files), batch_size):
        batch = files[i : i + batch_size]
        batch_results = await _process_batch(
            batch, root_path, markdownlint_cmd, dry_run, semaphore
        )
        results.extend(batch_results)

    return results


async def _process_batch(
    batch: list[Path],
    root_path: Path,
    markdownlint_cmd: list[str],
    dry_run: bool,
    semaphore: asyncio.Semaphore,
) -> list[FileResult]:
    """Process a batch of files concurrently."""

    async def process_single(file_path: Path) -> FileResult | None:
        if not file_path.exists():
            return None
        async with semaphore:
            return await _run_markdownlint_fix(
                file_path, root_path, markdownlint_cmd, dry_run
            )

    raw_results = await asyncio.gather(
        *[process_single(f) for f in batch], return_exceptions=True
    )
    return _filter_batch_results(raw_results)


def _filter_batch_results(
    raw_results: list[FileResult | None | BaseException],
) -> list[FileResult]:
    """Filter batch results and convert exceptions to error results."""
    results: list[FileResult] = []
    for result in raw_results:
        if result is None:
            continue
        if isinstance(result, BaseException):
            error_result: FileResult = {
                "file": "unknown",
                "fixed": False,
                "errors": [str(result)],
                "error_message": str(result),
            }
            results.append(error_result)
        else:
            results.append(result)
    return results


def _calculate_statistics(results: list[FileResult]) -> tuple[int, int, int]:
    """Calculate statistics from file results."""
    files_fixed = sum(1 for r in results if r["fixed"])
    files_with_errors = sum(1 for r in results if r["error_message"] is not None)
    files_unchanged = len(results) - files_fixed - files_with_errors
    return files_fixed, files_with_errors, files_unchanged


def _build_fix_response(results: list[FileResult]) -> str:
    """Build JSON response from file results."""
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


@mcp.tool()
@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_SECONDS)
async def fix_markdown_lint(
    project_root: str | None = None,
    include_untracked_markdown: bool = False,
    dry_run: bool = False,
    check_all_files: bool = False,
) -> str:
    """Fix markdownlint errors in markdown files.

    Automatically scans markdown files in the working copy,
    detects markdownlint errors, and fixes them automatically.

    Args:
        project_root: Path to project root directory. If None, uses current directory.
        include_untracked_markdown: Include untracked markdown files (default: False)
        dry_run: Check for errors without fixing them (default: False)
        check_all_files: Check all markdown files in project, not just modified ones (default: False)
            When True, scans all .md and .mdc files in the project instead of only git-modified files.

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

        Example 2: Check all markdown files for errors
        >>> await fix_markdown_lint(check_all_files=True)
        {
          "success": true,
          "files_processed": 45,
          "files_fixed": 12,
          "files_unchanged": 33,
          "files_with_errors": 0,
          "results": [...],
          "error_message": null
        }

        Example 3: Check for errors without fixing (dry-run)
        >>> await fix_markdown_lint(dry_run=True, check_all_files=True)
        {
          "success": true,
          "files_processed": 45,
          "files_fixed": 0,
          "files_unchanged": 33,
          "files_with_errors": 12,
          "results": [...],
          "error_message": null
        }

    Note:
        - Automatically detects markdownlint-cli2: checks PATH first, then tries npx as fallback
        - If not found, install with: npm install -g markdownlint-cli2
        - npx fallback works without global installation (auto-installs on first use)
        - When check_all_files=False: Only processes files tracked by git (staged, unstaged, optionally untracked)
        - When check_all_files=True: Processes all .md and .mdc files in the project (excludes .git, node_modules, venv, etc.)
        - Only processes .md and .mdc files
        - Returns error if not in a git repository (when check_all_files=False)
        - Returns error if markdownlint-cli2 is not available via PATH or npx
    """
    try:
        root_path = Path(get_project_root(project_root))

        # Validate prerequisites and get markdownlint command
        validation_error, markdownlint_cmd = await _validate_markdown_prerequisites(
            root_path
        )
        if validation_error:
            return validation_error
        assert markdownlint_cmd is not None  # Type narrowing

        # Get and process files
        if check_all_files:
            files = await _get_all_markdown_files(root_path)
        else:
            files = await _get_modified_markdown_files(
                root_path, include_untracked_markdown
            )
        if not files:
            return _create_empty_success_response()

        # Use batching and concurrency for large file sets
        # Process in batches of 50 with max 5 concurrent to avoid timeout
        results = await _process_markdown_files(
            files, root_path, markdownlint_cmd, dry_run, max_concurrent=5, batch_size=50
        )
        return _build_fix_response(results)

    except Exception as e:
        return _create_error_response(str(e))


class CorruptionMatch(TypedDict):
    """A detected corruption match."""

    line_num: int
    original: str
    fixed: str
    pattern: str


class FixRoadmapCorruptionResult(TypedDict):
    """Result of roadmap corruption fixing operation."""

    success: bool
    file_name: str
    corruption_count: int
    fixes_applied: list[CorruptionMatch]
    error_message: str | None


def _detect_pattern1(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect pattern 1: missing space/newline after completion date followed by capital."""
    pattern = re.compile(r"(Target completion:)(\d{4}-\d{2}-\d{2})([A-Za-z])")
    for i, line in enumerate(lines, 1):
        for m in pattern.finditer(line):
            if m.group(3).isupper():
                matches.append(
                    CorruptionMatch(
                        line_num=i,
                        original=m.group(0),
                        fixed=f"{m.group(1)} {m.group(2)}\n- [Phase",
                        pattern="missing_space_newline_after_completion_date",
                    )
                )


def _detect_pattern6_and_7(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect patterns 6 and 7: missing newline before phase links."""
    p6 = re.compile(r"(Target completion:)(\d{4}-\d{2}-\d{2})( - \[Phase)")
    for i, line in enumerate(lines, 1):
        for m in p6.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)} {m.group(2)}\n{m.group(3)}",
                    pattern="missing_newline_before_phase_link",
                )
            )
    p7 = re.compile(r"(Target completion:)(\d{4}-\d{2}-\d{2})(Phase)")
    for i, line in enumerate(lines, 1):
        for m in p7.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)} {m.group(2)}\n- [{m.group(3)}",
                    pattern="missing_space_newline_before_phase",
                )
            )


def _detect_completion_date_primary(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect primary completion date patterns (1, 6, 7)."""
    _detect_pattern1(lines, matches)
    _detect_pattern6_and_7(lines, matches)


def _detect_completion_date_secondary(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect secondary completion date patterns (10, 11)."""
    p10 = re.compile(r"(Target completion: \d{4}-\d{2}-\d{2}) (\[Conditional)")
    for i, line in enumerate(lines, 1):
        for m in p10.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)}\n- {m.group(2)}",
                    pattern="missing_newline_before_conditional",
                )
            )
    p11 = re.compile(r"(Target completion:)(\d{4}-\d{2}-\d{2})([^ -])")
    for i, line in enumerate(lines, 1):
        for m in p11.finditer(line):
            if not any(
                e["line_num"] == i and m.group(0) in e["original"] for e in matches
            ):
                matches.append(
                    CorruptionMatch(
                        line_num=i,
                        original=m.group(0),
                        fixed=f"{m.group(1)} {m.group(2)}{m.group(3)}",
                        pattern="missing_space_after_completion_colon",
                    )
                )


def _detect_completion_date_patterns(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect all 'Target completion:' date corruption patterns."""
    _detect_completion_date_primary(lines, matches)
    _detect_completion_date_secondary(lines, matches)


def _detect_phase_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect corruption patterns related to Phase references."""
    # Pattern 2: "Phase X% rate" -> "Phase X: Validate"
    pattern2 = re.compile(r"Phase (\d+)% rate")
    for i, line in enumerate(lines, 1):
        for match in pattern2.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed=f"Phase {match.group(1)}: Validate",
                    pattern="corrupted_phase_number",
                )
            )
    # Pattern 4: Missing newline before "-Phase"
    pattern4 = re.compile(r"([^\n])-Phase (\d+)")
    for i, line in enumerate(lines, 1):
        for match in pattern4.finditer(line):
            before = match.group(1)
            phase_num = match.group(2)
            fixed = (
                f"{before}\n- [Phase {phase_num}"
                if before.strip().endswith(")")
                else f"{before} - [Phase {phase_num}"
            )
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed=fixed,
                    pattern="missing_newline_before_phase",
                )
            )


def _detect_score_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect corruption patterns related to score formats."""
    # Pattern 5: "X.710 to Y.Z+" -> "X.7/10 to Y.Z+/10"
    pattern5 = re.compile(r"(\d+)\.(\d)(\d+) to (\d+)\.(\d+)\+")
    for i, line in enumerate(lines, 1):
        for match in pattern5.finditer(line):
            if match.group(3) == "10":
                matches.append(
                    CorruptionMatch(
                        line_num=i,
                        original=match.group(0),
                        fixed=f"{match.group(1)}.{match.group(2)}/10 to {match.group(4)}.{match.group(5)}+/10",
                        pattern="corrupted_score_format",
                    )
                )
    # Pattern 12: "8.710" -> "8.7/10" standalone
    pattern12 = re.compile(r"(\d+)\.(\d)(10)(\s|$)")
    for i, line in enumerate(lines, 1):
        for match in pattern12.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed=f"{match.group(1)}.{match.group(2)}/10{match.group(4)}",
                    pattern="corrupted_standalone_score",
                )
            )


def _detect_pattern3_implemented(
    lines: list[str], matches: list[CorruptionMatch]
) -> None:
    """Detect pattern 3: corrupted 'Implemented' text."""
    pattern = re.compile(r"\bented\b")
    for i, line in enumerate(lines, 1):
        for match in pattern.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=match.group(0),
                    fixed="Implemented",
                    pattern="corrupted_implemented",
                )
            )


def _detect_pattern8_and_9(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect patterns 8 and 9: date-fix and archive path issues."""
    p8 = re.compile(r"(\d{4}-\d{2}-\d{2})(Fix)")
    for i, line in enumerate(lines, 1):
        for m in p8.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)}) - {m.group(2)}",
                    pattern="missing_paren_space_before_fix",
                )
            )
    p9 = re.compile(r"(archive/Phase \d+)(phase-\d+)")
    for i, line in enumerate(lines, 1):
        for m in p9.finditer(line):
            matches.append(
                CorruptionMatch(
                    line_num=i,
                    original=m.group(0),
                    fixed=f"{m.group(1)}/{m.group(2)}",
                    pattern="missing_slash_in_archive_path",
                )
            )


def _detect_misc_patterns(lines: list[str], matches: list[CorruptionMatch]) -> None:
    """Detect miscellaneous corruption patterns."""
    _detect_pattern3_implemented(lines, matches)
    _detect_pattern8_and_9(lines, matches)


def _detect_roadmap_corruption(content: str) -> list[CorruptionMatch]:
    """Detect all corruption patterns in roadmap content."""
    matches: list[CorruptionMatch] = []
    lines = content.split("\n")
    _detect_completion_date_patterns(lines, matches)
    _detect_phase_patterns(lines, matches)
    _detect_score_patterns(lines, matches)
    _detect_misc_patterns(lines, matches)
    return matches


def _apply_roadmap_fixes(content: str, matches: list[CorruptionMatch]) -> str:
    """Apply fixes to roadmap content.

    Args:
        content: Original content
        matches: List of corruption matches to fix

    Returns:
        Fixed content
    """
    if not matches:
        return content

    # Sort matches by line number (descending) to avoid offset issues
    matches_sorted = sorted(matches, key=lambda m: m["line_num"], reverse=True)

    lines = content.split("\n")
    for match in matches_sorted:
        line_idx = match["line_num"] - 1
        if line_idx < len(lines):
            line = lines[line_idx]
            # Replace the corrupted pattern
            if "\n" in match["fixed"]:
                # Handle newline insertion - split the fix
                parts = match["fixed"].split("\n", 1)
                lines[line_idx] = line.replace(match["original"], parts[0])
                if len(parts) > 1 and line_idx + 1 < len(lines):
                    # Insert new line or prepend to next line
                    if parts[1].startswith("- "):
                        lines.insert(line_idx + 1, parts[1])
                    else:
                        lines[line_idx + 1] = parts[1] + lines[line_idx + 1]
            else:
                lines[line_idx] = line.replace(match["original"], match["fixed"])

    return "\n".join(lines)


def _create_roadmap_error_response(error_msg: str) -> str:
    """Create error response for roadmap corruption."""
    return json.dumps(
        {
            "success": False,
            "file_name": "roadmap.md",
            "corruption_count": 0,
            "fixes_applied": [],
            "error_message": error_msg,
        },
        indent=2,
    )


def _create_roadmap_success_response(matches: list[CorruptionMatch]) -> str:
    """Create success response for roadmap corruption."""
    result: FixRoadmapCorruptionResult = {
        "success": True,
        "file_name": "roadmap.md",
        "corruption_count": len(matches),
        "fixes_applied": matches,
        "error_message": None,
    }
    return json.dumps(result, indent=2)


@mcp.tool()
async def fix_roadmap_corruption(
    project_root: str | None = None, dry_run: bool = False
) -> str:
    """Fix text corruption in roadmap.md file.

    Detects and fixes corruption patterns: missing spaces/newlines, corrupted
    text like 'ented'->'Implemented', malformed dates, corrupted scores.
    """
    try:
        root_path = Path(get_project_root(project_root))
        roadmap_path = root_path / ".cortex" / "memory-bank" / "roadmap.md"
        if not roadmap_path.exists():
            return _create_roadmap_error_response(
                f"roadmap.md not found at {roadmap_path}"
            )
        content = roadmap_path.read_text(encoding="utf-8")
        matches = _detect_roadmap_corruption(content)
        if not dry_run and matches:
            fixed_content = _apply_roadmap_fixes(content, matches)
            _ = roadmap_path.write_text(fixed_content, encoding="utf-8")
        return _create_roadmap_success_response(matches)
    except Exception as e:
        return _create_roadmap_error_response(str(e))
