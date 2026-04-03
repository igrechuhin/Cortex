"""Fix-quality implementation for pre-commit tools.

Extracted from pre_commit_tools to keep it under 400 lines.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.context_logging import MCPContext, log_client, report_progress_safe
from cortex.core.models import JsonValue, ModelDict, OperationStatus
from cortex.tools.evaluation.reflection import collect_git_diff_text
from cortex.tools.execution.autofix_ai_suggestions import (
    collect_autofix_ai_comment_suggestions,
)
from cortex.tools.execution.pre_commit_detached import (  # noqa: E402
    fix_args_hash,
    fix_result_path,
    start_fix_job_impl,
)
from cortex.tools.execution.pre_commit_helpers_remaining import (
    collect_remaining_issues,
    extract_check_results,
    extract_dict_from_object,
    extract_int_from_object,
    extract_list_from_object,
    truncate_large_logs_in_data,
)
from cortex.tools.execution.pre_commit_process import poll_for_result
from cortex.tools.execution.session_paths import session_dir

logger = logging.getLogger(__name__)


def _default_ai_suggestions() -> list[dict[str, str]]:
    return []


class FixQualityResult(BaseModel):
    """Result of autofix operation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: OperationStatus = Field(description="Operation status")
    errors_fixed: int = Field(ge=0, description="Number of errors fixed")
    warnings_fixed: int = Field(ge=0, description="Number of warnings fixed")
    formatting_issues_fixed: int = Field(
        ge=0, description="Number of formatting issues fixed"
    )
    markdown_issues_fixed: int = Field(
        ge=0, description="Number of markdown issues fixed"
    )
    type_errors_fixed: int = Field(ge=0, description="Number of type errors fixed")
    files_modified: list[str] = Field(
        default_factory=list, description="List of modified files"
    )
    remaining_issues: list[str] = Field(
        default_factory=list, description="List of remaining issues"
    )
    suggestions: list[dict[str, str]] = Field(
        default_factory=_default_ai_suggestions,
        description="Non-auto-applied hints (e.g. # AI: placement).",
    )
    error_message: str | None = Field(default=None, description="Error message if any")


def create_quality_error_response(error_message: str) -> str:
    """Create error response for quality fixes."""
    from cortex.tools.execution.error_formatters import format_tool_error

    return format_tool_error(
        Exception(error_message),
        suggestion=(
            "Review the error details. Ensure the project root is valid and "
            "quality tools (ruff, black, etc.) are available. Check file permissions."
        ),
        example={
            "include_untracked_markdown": True,
        },
        context={"error_message": error_message},
    )


def extract_fix_statistics(
    fix_errors_result: dict[str, JsonValue],
) -> tuple[int, int, int, int, list[str]]:
    """Extract statistics from fix_errors result."""
    results_obj = fix_errors_result.get("results", {})
    results = extract_dict_from_object(results_obj, {})
    fix_errors_check, format_check, type_check_result = extract_check_results(results)

    errors = extract_list_from_object(fix_errors_check.get("errors", []), [])
    warnings = extract_list_from_object(fix_errors_check.get("warnings", []), [])
    errors_fixed = len(errors)
    warnings_fixed = len(warnings)
    formatting_issues_fixed = extract_int_from_object(
        format_check.get("files_formatted", 0), 0
    )
    type_errors = extract_list_from_object(type_check_result.get("errors", []), [])
    type_errors_fixed = len(type_errors)
    files_modified_list = extract_list_from_object(
        fix_errors_result.get("files_modified", []), []
    )
    files_modified = list(set(files_modified_list))

    return (
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        type_errors_fixed,
        files_modified,
    )


def process_markdown_results(
    markdown_result: ModelDict, files_modified: list[str]
) -> int:
    """Process markdown fix results and update files_modified list."""
    markdown_issues_fixed = 0
    success_obj = markdown_result.get("success")
    if success_obj:
        files_fixed_obj = markdown_result.get("files_fixed", 0)
        markdown_issues_fixed = (
            int(files_fixed_obj) if isinstance(files_fixed_obj, (int, str)) else 0
        )
        results_obj = markdown_result.get("results", [])
        if isinstance(results_obj, list):
            for item in cast(list[JsonValue], results_obj):
                if isinstance(item, dict):
                    file_result = cast(ModelDict, item)
                    fixed_obj = file_result.get("fixed")
                    if fixed_obj:
                        file_path_obj = file_result.get("file", "")
                        file_path = str(file_path_obj) if file_path_obj else ""
                        if file_path and file_path not in files_modified:
                            files_modified.append(file_path)
    return markdown_issues_fixed


def build_quality_response_json(
    errors_fixed: int,
    warnings_fixed: int,
    formatting_issues_fixed: int,
    markdown_issues_fixed: int,
    type_errors_fixed: int,
    files_modified: list[str],
    remaining_issues: list[str],
    suggestions: list[dict[str, str]] | None = None,
) -> str:
    """Build quality fix response as JSON string."""
    response = FixQualityResult(
        status=OperationStatus.SUCCESS,
        errors_fixed=errors_fixed,
        warnings_fixed=warnings_fixed,
        formatting_issues_fixed=formatting_issues_fixed,
        markdown_issues_fixed=markdown_issues_fixed,
        type_errors_fixed=type_errors_fixed,
        files_modified=files_modified,
        remaining_issues=remaining_issues,
        suggestions=list(suggestions or []),
        error_message=None,
    )
    data = response.model_dump(mode="json")
    compact = truncate_large_logs_in_data(data)
    return json.dumps(compact, separators=(",", ":"))


def build_markdown_fix_output(
    fix_errors_result: ModelDict,
    markdown_issues_fixed: int,
    files_modified: list[str],
    *,
    files_modified_override: list[str] | None = None,
) -> str:
    """Build final quality response JSON from fix result and markdown stats."""
    remaining_issues = collect_remaining_issues(fix_errors_result)
    (
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        type_errors_fixed,
        _,
    ) = extract_fix_statistics(fix_errors_result)
    effective_files_modified = (
        files_modified_override
        if files_modified_override is not None
        else files_modified
    )
    return build_quality_response_json(
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        markdown_issues_fixed,
        type_errors_fixed,
        effective_files_modified,
        remaining_issues,
    )


def _extract_envelope_results(
    envelope: ModelDict,
) -> tuple[ModelDict, list[str], int]:
    """Extract fix results, files modified, and markdown issues from envelope."""
    inner_raw = envelope.get("result")
    fix_errors_result: ModelDict = (
        cast(ModelDict, inner_raw)
        if isinstance(inner_raw, dict)
        else cast(ModelDict, {})
    )
    (_, _, _, _, files_modified) = extract_fix_statistics(fix_errors_result)
    markdown_issues_fixed = 0
    md_raw = envelope.get("markdown_result")
    if isinstance(md_raw, dict):
        markdown_issues_fixed = process_markdown_results(
            cast(ModelDict, md_raw), files_modified
        )
    return fix_errors_result, files_modified, markdown_issues_fixed


def _parse_fix_envelope(
    envelope: ModelDict, files_modified_override: list[str] | None = None
) -> str:
    """Parse a completed fix worker envelope into FixQualityResult JSON."""
    status = str(envelope.get("status", ""))
    if status in ("error", "timeout"):
        error = str(envelope.get("error", "Fix worker failed"))
        return create_quality_error_response(error)
    fix_errors_result, files_modified, markdown_issues_fixed = (
        _extract_envelope_results(envelope)
    )
    return build_markdown_fix_output(
        fix_errors_result,
        markdown_issues_fixed,
        files_modified,
        files_modified_override=files_modified_override,
    )


def parse_fix_envelope(
    envelope: ModelDict, files_modified_override: list[str] | None = None
) -> str:
    """Public wrapper for fix envelope parsing used by tests and callers."""
    return _parse_fix_envelope(
        envelope, files_modified_override=files_modified_override
    )


def _get_tracked_git_changes(root: Path) -> set[str] | None:
    """Return tracked modified file paths from git status, or None if unavailable."""
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None

    changed_files: set[str] = set()
    for line in completed.stdout.splitlines():
        # Porcelain format: XY<space>path; skip malformed rows defensively.
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if path:
            changed_files.add(path)
    return changed_files


async def autofix_impl(
    root: Path,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> str:
    """Spawn detached fix worker, poll with heartbeats, parse result.

    Mirrors run_quality_gate's detached-subprocess + polling pattern so the
    asyncio event loop is never blocked: the MCP stdio transport stays alive
    and Cursor does not drop the connection during long-running fix operations.
    """
    tracked_before = _get_tracked_git_changes(root)
    await report_progress_safe(ctx, 5.0, 100.0)
    _ = start_fix_job_impl(root, include_untracked_markdown)
    args_hash = fix_args_hash(include_untracked_markdown)
    rp = fix_result_path(session_dir(root), args_hash)
    envelope = await poll_for_result(rp, ctx=ctx, timeout=960.0)
    tracked_after = _get_tracked_git_changes(root)
    files_modified_override: list[str] | None = None
    if tracked_before is not None and tracked_after is not None:
        files_modified_override = sorted(tracked_after - tracked_before)
    out = _parse_fix_envelope(
        cast(ModelDict, envelope), files_modified_override=files_modified_override
    )
    try:
        parsed: object = json.loads(out)
    except json.JSONDecodeError:
        await log_client(ctx, "info", "autofix: completed", logger_name=__name__)
        return out
    if not isinstance(parsed, dict):
        await log_client(ctx, "info", "autofix: completed", logger_name=__name__)
        return out
    data = cast(ModelDict, parsed)
    if data.get("status") == OperationStatus.SUCCESS.value:
        diff_text = collect_git_diff_text(root)
        sugs = collect_autofix_ai_comment_suggestions(diff_text)
        if sugs:
            data["suggestions"] = cast(JsonValue, sugs)
        out = json.dumps(data, separators=(",", ":"))
    await log_client(ctx, "info", "autofix: completed", logger_name=__name__)
    return out
