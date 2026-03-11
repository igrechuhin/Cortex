"""Helpers for markdown lint: parsing, result building, and GitCommandResult accessors.

All helpers are used by markdown_operations; reportUnusedFunction is disabled for this module.
"""

# pyright: reportUnusedFunction=false

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.models import GitCommandResult

__all__ = [
    "FileResult",
    "apply_validation_error_hint",
    "_build_error_result",
    "_build_markdownlint_batch_results",
    "_build_markdownlint_error_result",
    "_build_markdownlint_success_result",
    "calculate_statistics",
    "_chunk_paths",
    "_not_in_git_repo_hint",
    "parse_markdownlint_errors",
    "_parse_markdownlint_lines_by_file",
    "parse_markdownlint_output",
    "_result_error",
    "_result_returncode",
    "_result_stderr",
    "_result_stdout",
    "_result_success",
]


class FileResult(BaseModel):
    """Result for a single file processing."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File path")
    fixed: bool = Field(description="Whether file was fixed")
    errors: list[str] = Field(default_factory=list, description="List of errors")
    error_message: str | None = Field(default=None, description="Error message if any")


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


def _parse_markdownlint_errors(stderr: str) -> list[str]:
    """Parse markdownlint errors from stderr.

    Extracts rule codes (e.g. MD036) and error messages from stderr output.
    Handles various formats including 'file:line:rule' and standalone rule codes.
    """
    errors: list[str] = []
    for line in stderr.strip().split("\n"):
        s = line.strip()
        if not s:
            continue

        # Skip generic version banner lines from markdownlint/rumdl CLIs, which
        # are not actionable lint errors and should not be counted.
        if s.lower().startswith("markdownlint-cli2 version") or s.lower().startswith(
            "rumdl "
        ):
            continue

        # Extract rule codes (MD followed by 3 digits)
        rule_codes = re.findall(r"MD\d{3}", s)
        if rule_codes:
            # Include the full line if it contains rule codes
            errors.append(s)
        elif s:
            # Include non-empty lines even without explicit rule codes
            # (may contain error messages that are still useful)
            errors.append(s)

    return errors


parse_markdownlint_errors = _parse_markdownlint_errors


def _parse_markdownlint_output(stdout: str) -> list[str]:
    """Parse markdownlint output from stdout."""
    errors: list[str] = []
    for line in stdout.strip().split("\n"):
        if line.strip():
            errors.append(line.strip())
    return errors


parse_markdownlint_output = _parse_markdownlint_output


def _try_parse_file_with_spaces(s: str, by_file: dict[str, list[str]]) -> bool:
    """Try parsing 'file: line: rule' format (with spaces). Returns True if matched."""
    idx = s.find(": ")
    if idx > 0:
        file_part = s[:idx].strip()
        if file_part and (".md" in file_part or ".mdc" in file_part):
            by_file.setdefault(file_part, []).append(s)
            return True
    return False


def _try_parse_file_no_spaces(s: str, by_file: dict[str, list[str]]) -> bool:
    """Try parsing 'file:line:rule' format (no spaces). Returns True if matched."""
    for ext in [".md", ".mdc"]:
        if ext in s:
            ext_pos = s.find(ext)
            if ext_pos > 0:
                potential_file = s[: ext_pos + len(ext)]
                rest = s[ext_pos + len(ext) :].strip()
                if rest.startswith(":") and len(rest) > 1:
                    by_file.setdefault(potential_file, []).append(s)
                    return True
    return False


def _try_parse_file_from_rule_code(s: str, by_file: dict[str, list[str]]) -> bool:
    """Try extracting file path from line containing rule code. Returns True if matched."""
    rule_match = re.search(r"MD\d{3}", s)
    if rule_match:
        rule_pos = rule_match.start()
        before_rule = s[:rule_pos].strip()
        for ext in [".md", ".mdc"]:
            if ext in before_rule:
                ext_pos = before_rule.rfind(ext)
                if ext_pos >= 0:
                    file_part = before_rule[: ext_pos + len(ext)]
                    if file_part:
                        by_file.setdefault(file_part, []).append(s)
                        return True
    return False


def _parse_markdownlint_lines_by_file(output: str) -> dict[str, list[str]]:
    """Parse markdownlint output into per-file line groups.

    Lines follow 'file: line: rule' format. Returns mapping of
    relative file path to list of lines for that file.

    Also handles variations like 'file:line:rule' (no spaces) and
    extracts rule codes (e.g. MD036) even when format differs slightly.
    """
    by_file: dict[str, list[str]] = {}
    for line in output.strip().split("\n"):
        s = line.strip()
        if not s or s.startswith("markdownlint"):
            continue

        # Try different parsing strategies in order
        if _try_parse_file_with_spaces(s, by_file):
            continue
        if _try_parse_file_no_spaces(s, by_file):
            continue
        _ = _try_parse_file_from_rule_code(s, by_file)

    return by_file


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


def _build_markdownlint_success_result(
    rel: str,
    lines: list[str],
    raw_lines: list[str],
    output_suggests_fix: bool,
    single_file: bool,
    dry_run: bool,
) -> FileResult:
    """Build FileResult for a successful markdownlint run on one file."""
    fixed = (bool(lines) or (output_suggests_fix and single_file)) and not dry_run
    return FileResult(
        file=rel,
        fixed=fixed,
        errors=lines or raw_lines,
        error_message=None,
    )


def _build_markdownlint_error_result(
    rel: str,
    lines: list[str],
    result: GitCommandResult,
) -> FileResult:
    """Return FileResult for a failed markdownlint run on one file."""
    error_msg = _result_error(result) or "; ".join(lines[:3]) if lines else ""
    return _build_error_result(
        rel,
        lines,
        _result_returncode(result),
        error_msg or "Markdown lint failed",
    )


def _one_file_markdownlint_result(
    rel: str,
    success: bool,
    result: GitCommandResult,
    by_file: dict[str, list[str]],
    raw_lines: list[str],
    output_suggests_fix: bool,
    single_file: bool,
    dry_run: bool,
) -> FileResult:
    """Return FileResult for one file in a markdownlint batch."""
    if success:
        return _build_markdownlint_success_result(
            rel,
            by_file.get(rel, []),
            raw_lines,
            output_suggests_fix,
            single_file,
            dry_run,
        )
    if rel in by_file:
        return _build_markdownlint_error_result(rel, by_file.get(rel, []), result)
    return _build_markdownlint_success_result(rel, [], [], False, single_file, dry_run)


def _build_markdownlint_batch_results(
    rel_strs: list[str],
    result: GitCommandResult,
    by_file: dict[str, list[str]],
    raw_lines: list[str],
    dry_run: bool,
) -> list[FileResult]:
    """Build per-file results from markdownlint batch output.

    When the batch run fails (success=False), only files that appear in
    by_file (parsed from stderr) have errors; other files are treated as
    clean so we do not report 500 failures for one batch failure.
    """
    success = _result_success(result)
    output_suggests_fix = success and bool(raw_lines)
    single_file = len(rel_strs) == 1
    return [
        _one_file_markdownlint_result(
            rel,
            success,
            result,
            by_file,
            raw_lines,
            output_suggests_fix,
            single_file,
            dry_run,
        )
        for rel in rel_strs
    ]


def calculate_statistics(results: list[FileResult]) -> tuple[int, int, int]:
    """Return (files_fixed, files_with_errors, files_unchanged)."""
    files_fixed = sum(1 for r in results if r.fixed)
    files_with_errors = sum(1 for r in results if r.error_message is not None)
    files_unchanged = len(results) - files_fixed - files_with_errors
    return (files_fixed, files_with_errors, files_unchanged)


def _chunk_paths(files: list[Path], size: int) -> list[list[Path]]:
    """Split file list into chunks of at most size."""
    return [files[i : i + size] for i in range(0, len(files), size)]


def _not_in_git_repo_hint(project_root_was_none: bool) -> str:
    """Return hint when git check fails."""
    if not project_root_was_none:
        return ""
    return " When running under MCP, use workspace root or client roots (roots/list)."


def apply_validation_error_hint(validation_error: str) -> str:
    """Apply not-in-git hint to validation error JSON when applicable; return final JSON."""
    if "Not in a git repository" in validation_error:
        hint = _not_in_git_repo_hint(True)
        if hint:
            data = json.loads(validation_error)
            if data.get("error_message"):
                data["error_message"] = data["error_message"].rstrip() + hint
                return json.dumps(data, indent=2)
    return validation_error
