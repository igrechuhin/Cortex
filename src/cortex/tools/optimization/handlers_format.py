"""
Phase 4: Optimization Handlers - Response Formatting Helpers

Format load_context responses, add zero-file warnings, and build concise payloads.
"""

import json
from typing import cast

from cortex.core.models import ResponseFormat

from .handlers_validation import is_non_trivial_task


def format_load_context_error(error: Exception) -> str:
    """Format error response for load_context failures."""
    from cortex.tools.execution.error_formatters import format_tool_error

    return format_tool_error(
        error,
        suggestion=(
            "Verify task_description is clear and token_budget is appropriate. "
            "Try reducing token_budget or using depth='metadata_only' for large contexts."
        ),
        example={
            "task_description": "Example task description",
            "token_budget": 10000,
            "strategy": "dependency_aware",
        },
    )


def count_files_from_result(result_data: dict[str, object]) -> int:
    """Count files from load_context result data.

    Args:
        result_data: Parsed JSON result data

    Returns:
        Number of files selected
    """
    files_count = 0
    if "files" in result_data:
        files_list = result_data.get("files")
        if isinstance(files_list, list):
            typed_files_list = cast(list[object], files_list)
            files_count = len(typed_files_list)
        elif "total_files" in result_data:
            total_files = result_data.get("total_files")
            if isinstance(total_files, int):
                files_count = total_files
    elif "selected_files" in result_data:
        selected_files = result_data.get("selected_files")
        if isinstance(selected_files, list):
            typed_selected_files = cast(list[object], selected_files)
            files_count = len(typed_selected_files)
    return files_count


def _warnings_with_zero_file_appended(
    result_data: dict[str, object],
    task_description: str,
    token_budget: int | None,
) -> list[dict[str, object]]:
    """Return existing warnings list with zero-files warning appended."""
    warnings_raw: object = result_data.get("warnings")
    warnings: list[dict[str, object]] = []
    if isinstance(warnings_raw, list):
        typed_warnings_raw = cast(list[object], warnings_raw)
        for item in typed_warnings_raw:
            if isinstance(item, dict):
                warnings.append(cast(dict[str, object], item))
    warnings.append(
        {
            "type": "zero_files_selected",
            "message": (
                "Non-trivial task resulted in zero selected files. "
                "This may indicate insufficient context or a configuration issue. "
                "Consider increasing token_budget or reviewing task_description."
            ),
            "task_description": task_description,
            "token_budget": token_budget,
        }
    )
    return warnings


def add_zero_file_warning_if_needed(
    result_str: str, task_description: str, token_budget: int | None
) -> str:
    """Add zero-file warning to result if non-trivial task has zero files.

    Args:
        result_str: JSON string result from load_context
        task_description: Task description
        token_budget: Token budget used

    Returns:
        Updated result string with warning if needed, original otherwise
    """
    try:
        result_data: dict[str, object] = json.loads(result_str)
        if result_data.get("status") != "success":
            return result_str
        if count_files_from_result(result_data) == 0:
            result_data["warnings"] = _warnings_with_zero_file_appended(
                result_data, task_description, token_budget
            )
            return json.dumps(result_data, indent=2)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return result_str


def format_detailed_load_context_response(out: str, role: str | None) -> str:
    """Return detailed response JSON, injecting role when available."""
    if role is None:
        return out
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return out
    if not isinstance(data, dict):
        return out
    typed = cast(dict[str, object], data)
    if "role" not in typed:
        typed["role"] = role
    return json.dumps(typed, indent=2)


def build_concise_payload(data: dict[str, object], role: str | None) -> str:
    """Build concise response payload from detailed JSON data."""
    selected_files_raw = data.get("selected_files")
    file_names: list[str] = []
    if isinstance(selected_files_raw, dict):
        selected_files_typed = cast(dict[str, object], selected_files_raw)
        file_names = sorted(selected_files_typed.keys())

    concise_payload: dict[str, object] = {
        "status": data.get("status", "success"),
        "task_description": data.get("task_description"),
        "strategy": data.get("strategy"),
        "file_names": file_names,
        "total_tokens": data.get("total_tokens"),
        "utilization": data.get("utilization"),
    }
    if role is not None:
        concise_payload["role"] = role
    return json.dumps(concise_payload, indent=2)


def format_load_context_response(
    out: str,
    response_format: ResponseFormat,
    role: str | None = None,
) -> str:
    """Format load_context response payload based on response_format."""
    if response_format != ResponseFormat.CONCISE:
        return format_detailed_load_context_response(out, role)

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return out
    if not isinstance(data, dict):
        return out
    typed = cast(dict[str, object], data)
    return build_concise_payload(typed, role)


def format_and_add_warnings_if_needed(
    out: str,
    response_format: ResponseFormat,
    role: str,
    task_description: str,
    token_budget: int | None,
) -> str:
    """Format response and add zero-file warnings if needed."""
    result_str = format_load_context_response(out, response_format, role)
    if is_non_trivial_task(task_description):
        result_str = add_zero_file_warning_if_needed(
            result_str, task_description, token_budget
        )
    return result_str
