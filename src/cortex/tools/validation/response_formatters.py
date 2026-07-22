"""Response formatters for the validate tool.

Extracted from validation_operations to keep the main module within line limits.
"""

import json
from collections.abc import Callable
from typing import cast

from cortex.core.models import ResponseFormat
from cortex.tools.validation.helpers import ValidationCheckType


def parse_validate_json(raw: str) -> dict[str, object] | None:
    """Parse raw JSON string into a dict or return None on failure."""
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    return cast(dict[str, object], loaded)


def compute_validate_valid_flag(
    data: dict[str, object],
    check_type: ValidationCheckType,
) -> bool:
    """Best-effort validity flag for concise validate responses."""
    valid_val: bool = bool(data.get("valid", True))

    if check_type == ValidationCheckType.SCHEMA:
        validation_obj = data.get("validation")
        if isinstance(validation_obj, dict):
            validation_dict = cast(dict[str, object], validation_obj)
            inner_valid = validation_dict.get("valid")
            if isinstance(inner_valid, bool):
                valid_val = inner_valid
    return valid_val


def _list_len(data: dict[str, object], key: str) -> int:
    """Return len(data[key]) when it is a list, else 0."""
    value = data.get(key)
    if isinstance(value, list):
        return len(cast(list[object], value))
    return 0


def _counts_from_validation_block(data: dict[str, object]) -> tuple[int, int]:
    """Error/warning counts from a nested `validation: {errors, warnings}` block."""
    validation_obj = data.get("validation")
    if not isinstance(validation_obj, dict):
        return 0, 0
    validation_dict = cast(dict[str, object], validation_obj)
    return _list_len(validation_dict, "errors"), _list_len(validation_dict, "warnings")


def _counts_from_duplications(data: dict[str, object]) -> tuple[int, int]:
    """Error count from `duplicates_found`; duplications has no warning concept."""
    duplicates_found = data.get("duplicates_found")
    return (duplicates_found if isinstance(duplicates_found, int) else 0), 0


def _counts_from_quality(data: dict[str, object]) -> tuple[int, int]:
    """Single-file quality nests `score.validation`; all-files exposes `issues`."""
    score_obj = data.get("score")
    if isinstance(score_obj, dict):
        return _counts_from_validation_block(cast(dict[str, object], score_obj))
    return _list_len(data, "issues"), 0


def _counts_from_infrastructure(data: dict[str, object]) -> tuple[int, int]:
    """Error count from `issues_found`; infrastructure has no warning concept."""
    return _list_len(data, "issues_found"), 0


def _int_or_zero(value: object) -> int:
    """Return value when it is an int, else 0."""
    return value if isinstance(value, int) else 0


def _counts_from_timestamps(data: dict[str, object]) -> tuple[int, int]:
    """Error count from invalid-format/invalid-with-time counters (single or all-files)."""
    invalid_format = data.get("invalid_format_count", data.get("total_invalid_format"))
    invalid_with_time = data.get(
        "invalid_with_time_count", data.get("total_invalid_with_time")
    )
    return _int_or_zero(invalid_format) + _int_or_zero(invalid_with_time), 0


def _counts_from_roadmap_sync(data: dict[str, object]) -> tuple[int, int]:
    """Error count aggregates the same fields `validate_roadmap_sync` uses for `valid`."""
    error_fields = (
        "missing_roadmap_entries",
        "invalid_references",
        "unlinked_plans",
        "completed_entries_in_roadmap",
    )
    error_count = sum(_list_len(data, field) for field in error_fields)
    return error_count, _list_len(data, "warnings")


_COUNT_COMPUTERS: dict[
    ValidationCheckType, Callable[[dict[str, object]], tuple[int, int]]
] = {
    ValidationCheckType.SCHEMA: _counts_from_validation_block,
    ValidationCheckType.DUPLICATIONS: _counts_from_duplications,
    ValidationCheckType.QUALITY: _counts_from_quality,
    ValidationCheckType.INFRASTRUCTURE: _counts_from_infrastructure,
    ValidationCheckType.TIMESTAMPS: _counts_from_timestamps,
    ValidationCheckType.ROADMAP_SYNC: _counts_from_roadmap_sync,
}


def compute_validate_counts(
    data: dict[str, object],
    check_type: ValidationCheckType,
) -> tuple[int, int]:
    """Compute real (error_count, warning_count) for a concise validate response.

    Each check type has a distinct raw payload shape (see the handlers under
    `cortex.tools.validation`), so counts are derived per check type rather
    than from a single generic field. Falls back to (0, 0) — not a lie, since
    those check types genuinely have no list-shaped error/warning fields to
    count when `valid` is true, and this mirrors the true absence of detail.
    """
    computer = _COUNT_COMPUTERS.get(check_type)
    if computer is None:
        return 0, 0
    return computer(data)


def format_validate_response(
    raw: str,
    check_type: ValidationCheckType,
    response_format: ResponseFormat,
) -> str:
    """Format validate response based on response_format."""
    if response_format != ResponseFormat.CONCISE:
        return raw

    data = parse_validate_json(raw)
    if data is None:
        return raw

    status_raw = data.get("status")
    status_val: str = status_raw if isinstance(status_raw, str) else "success"
    status = status_val
    if status != "success":
        # Preserve full error payloads even in concise mode.
        return raw

    valid = compute_validate_valid_flag(data, check_type)
    error_count, warning_count = compute_validate_counts(data, check_type)
    check_type_str = check_type.value
    concise_payload = {
        "status": status,
        "check_type": check_type_str,
        "valid": bool(valid),
        "error_count": error_count,
        "warning_count": warning_count,
    }
    return json.dumps(concise_payload, indent=2)
