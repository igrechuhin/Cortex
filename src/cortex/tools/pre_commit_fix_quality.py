"""Fix-quality implementation for pre-commit tools.

Extracted from pre_commit_tools to keep it under 400 lines.
"""

import json
import logging
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.context_logging import MCPContext, log_client, report_progress_safe
from cortex.core.models import JsonValue, ModelDict, OperationStatus
from cortex.tools.pre_commit_helpers_models import PreCommitCheck
from cortex.tools.pre_commit_helpers_remaining import (
    collect_remaining_issues,
    extract_check_results,
    extract_dict_from_object,
    extract_int_from_object,
    extract_list_from_object,
    truncate_large_logs_in_data,
)

logger = logging.getLogger(__name__)


def _ensure_result_dict(value: ModelDict | str) -> ModelDict:
    """Ensure value is a dict; parse JSON string if needed (e.g. cancellation response).

    MCP stability can return CANCELLED_RESPONSE_JSON as a string. Prevents
    AttributeError: 'str' object has no attribute 'get'.
    """
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return (
            cast(ModelDict, parsed) if isinstance(parsed, dict) else cast(ModelDict, {})
        )
    except (json.JSONDecodeError, TypeError):
        return cast(ModelDict, {"status": "error", "error": str(value)})


class FixQualityResult(BaseModel):
    """Result of fix_quality_issues operation."""

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
    error_message: str | None = Field(default=None, description="Error message if any")


def create_quality_error_response(error_message: str) -> str:
    """Create error response for quality fixes."""
    from cortex.tools.tool_error_formatters import format_tool_error

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
        error_message=None,
    )
    data = response.model_dump(mode="json")
    compact = truncate_large_logs_in_data(data)
    return json.dumps(compact, separators=(",", ":"))


def build_markdown_fix_output(
    fix_errors_result: ModelDict,
    markdown_issues_fixed: int,
    files_modified: list[str],
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
    return build_quality_response_json(
        errors_fixed,
        warnings_fixed,
        formatting_issues_fixed,
        markdown_issues_fixed,
        type_errors_fixed,
        files_modified,
        remaining_issues,
    )


async def _run_quality_checks() -> ModelDict | str:
    """Run quality checks and return result or error response."""
    from cortex.tools.pre_commit_tools import execute_pre_commit_checks

    raw_result = await execute_pre_commit_checks(
        checks=[
            PreCommitCheck.FIX_ERRORS.value,
            PreCommitCheck.FORMAT.value,
            PreCommitCheck.TYPE_CHECK.value,
        ],
        test_timeout=300,
        coverage_threshold=0.90,
        strict_mode=False,
    )
    fix_errors_result = _ensure_result_dict(raw_result)
    if fix_errors_result.get("status") == "error" and (
        "error" in fix_errors_result or "error_type" in fix_errors_result
    ):
        error_obj = fix_errors_result.get("error")
        return create_quality_error_response(
            str(error_obj) if error_obj is not None else "Unknown error"
        )
    return fix_errors_result


async def _fix_markdown_and_update_files(
    include_untracked: bool,
    files_modified_list: list[str],
) -> int:
    """Fix markdown lint errors and update files_modified list."""
    from cortex.tools.files.markdown_operations import fix_markdown_lint

    markdown_result_json = await fix_markdown_lint(
        include_untracked_markdown=include_untracked,
        dry_run=False,
    )
    markdown_result_raw: JsonValue = json.loads(markdown_result_json)
    if not isinstance(markdown_result_raw, dict):
        return 0
    markdown_result = cast(ModelDict, markdown_result_raw)
    return process_markdown_results(markdown_result, files_modified_list)


async def fix_quality_issues_impl(
    root: Path,
    include_untracked_markdown: bool,
    ctx: MCPContext | None,
) -> str:
    """Run quality fixes and return JSON result."""
    await report_progress_safe(ctx, 10.0, 100.0)
    fix_errors_result = await _run_quality_checks()
    if isinstance(fix_errors_result, str):
        await log_client(
            ctx,
            "warning",
            "fix_quality_issues: quality checks returned error",
            logger_name=__name__,
        )
        return fix_errors_result

    (_, _, _, _, files_modified) = extract_fix_statistics(fix_errors_result)
    await report_progress_safe(ctx, 50.0, 100.0)
    markdown_issues_fixed = await _fix_markdown_and_update_files(
        include_untracked_markdown, files_modified
    )
    out = build_markdown_fix_output(
        fix_errors_result, markdown_issues_fixed, files_modified
    )
    await report_progress_safe(ctx, 100.0, 100.0)
    await log_client(ctx, "info", "fix_quality_issues: completed", logger_name=__name__)
    return out
