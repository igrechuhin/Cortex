"""Collect remaining issues after fix_errors.

Extracted from pre_commit_helpers to keep modules under 400 lines.
"""

from typing import cast

from cortex.core.models import JsonValue, ModelDict


def extract_dict_from_object(
    obj: JsonValue, default: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """Extract dict from object with type checking."""
    return cast(dict[str, JsonValue], obj) if isinstance(obj, dict) else default


def extract_list_from_object(obj: JsonValue, default: list[str]) -> list[str]:
    """Extract list from object with type checking.

    Returns list of strings, filtering out non-string items.
    """
    if isinstance(obj, list):
        obj_list = cast(list[JsonValue], obj)
        return [str(item) for item in obj_list if isinstance(item, (str, int, float))]
    return default


def extract_int_from_object(obj: JsonValue, default: int) -> int:
    """Extract int from object with type checking."""
    return int(obj) if isinstance(obj, (int, str)) else default


def extract_check_results(
    results: dict[str, JsonValue],
) -> tuple[ModelDict, ModelDict, ModelDict]:
    """Extract check result dicts from results."""
    fix_errors_check_raw = results.get("fix_errors")
    format_check_raw = results.get("format")
    type_check_result_raw = results.get("type_check")

    fix_errors_check: ModelDict
    if isinstance(fix_errors_check_raw, dict):
        fix_errors_check = cast(ModelDict, fix_errors_check_raw)
    else:
        fix_errors_check = cast(ModelDict, {})

    format_check: ModelDict
    if isinstance(format_check_raw, dict):
        format_check = cast(ModelDict, format_check_raw)
    else:
        format_check = cast(ModelDict, {})

    type_check_result: ModelDict
    if isinstance(type_check_result_raw, dict):
        type_check_result = cast(ModelDict, type_check_result_raw)
    else:
        type_check_result = cast(ModelDict, {})

    return fix_errors_check, format_check, type_check_result


def _check_fix_errors_remaining(fix_errors_check: ModelDict) -> str | None:
    """Check if fix_errors check has remaining issues."""
    fix_errors_list = extract_list_from_object(fix_errors_check.get("errors", []), [])
    fix_errors_success_obj = fix_errors_check.get("success")
    if isinstance(fix_errors_success_obj, bool):
        fix_errors_success = bool(fix_errors_success_obj)
    else:
        fix_errors_success = len(fix_errors_list) == 0

    if not fix_errors_success and fix_errors_list:
        return f"{len(fix_errors_list)} linting/formatting errors remain after auto-fix"
    return None


def _check_format_remaining(format_check: ModelDict) -> str | None:
    """Check if format check has remaining issues."""
    format_errors_list = extract_list_from_object(format_check.get("errors", []), [])
    format_success_obj = format_check.get("success")
    if isinstance(format_success_obj, bool):
        format_success = bool(format_success_obj)
    else:
        format_success = len(format_errors_list) == 0

    if not format_success and format_errors_list:
        return f"{len(format_errors_list)} formatting errors remain after auto-fix"
    return None


def _check_type_check_remaining(type_check_result: ModelDict) -> str | None:
    """Check if type_check has remaining issues."""
    type_errors_list = extract_list_from_object(type_check_result.get("errors", []), [])
    type_check_success_obj = type_check_result.get("success")
    if isinstance(type_check_success_obj, bool):
        type_check_success = bool(type_check_success_obj)
    else:
        type_check_success = len(type_errors_list) == 0

    if not type_check_success and type_errors_list:
        return f"{len(type_errors_list)} type errors remain after auto-fix"
    return None


def _check_type_warnings_remaining(type_check_result: ModelDict) -> str | None:
    """Check if type_check has remaining warnings (e.g. unknown variable types)."""
    type_warnings_list = extract_list_from_object(
        type_check_result.get("warnings", []), []
    )
    if type_warnings_list:
        return f"{len(type_warnings_list)} type-check warnings remain after auto-fix"
    return None


def _check_warnings_remaining(fix_errors_check: ModelDict) -> str | None:
    """Check if fix_errors check has remaining warnings."""
    fix_warnings_list = extract_list_from_object(
        fix_errors_check.get("warnings", []), []
    )
    if fix_warnings_list:
        return f"{len(fix_warnings_list)} warnings remain after auto-fix"
    return None


MAX_LOG_OUTPUT_LENGTH = 4000


def truncate_log_value(value: str, max_length: int = MAX_LOG_OUTPUT_LENGTH) -> str:
    """Truncate very large log strings to keep JSON responses compact."""
    if len(value) <= max_length:
        return value
    truncated_chars = len(value) - max_length
    suffix = f"\n...[truncated {truncated_chars} characters]..."
    return value[:max_length] + suffix


def truncate_large_logs_in_data(obj: JsonValue) -> JsonValue:
    """Recursively truncate large log fields in JSON-like data."""
    if isinstance(obj, dict):
        truncated: dict[str, JsonValue] = {}
        for key, value in obj.items():
            if isinstance(value, str) and key == "output":
                truncated[key] = truncate_log_value(value)
            else:
                truncated[key] = truncate_large_logs_in_data(value)
        return truncated
    if isinstance(obj, list):
        return [truncate_large_logs_in_data(item) for item in obj]
    return obj


def collect_remaining_issues(fix_errors_result: ModelDict) -> list[str]:
    """Collect remaining issues that couldn't be auto-fixed.

    Checks actual check results to determine if there are remaining errors,
    rather than using aggregate total_errors/total_warnings which may include
    errors that were already fixed or errors from checks that succeeded.
    """
    remaining_issues: list[str] = []

    results_obj = fix_errors_result.get("results", {})
    results = extract_dict_from_object(results_obj, {})

    fix_errors_check, format_check, type_check_result = extract_check_results(results)

    issue = _check_fix_errors_remaining(fix_errors_check)
    if issue:
        remaining_issues.append(issue)

    issue = _check_format_remaining(format_check)
    if issue:
        remaining_issues.append(issue)

    issue = _check_type_check_remaining(type_check_result)
    if issue:
        remaining_issues.append(issue)

    issue = _check_type_warnings_remaining(type_check_result)
    if issue:
        remaining_issues.append(issue)

    issue = _check_warnings_remaining(fix_errors_check)
    if issue:
        remaining_issues.append(issue)

    return remaining_issues
