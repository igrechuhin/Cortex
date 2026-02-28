"""Response formatters for the validate tool.

Extracted from validation_operations to keep the main module within line limits.
"""

import json
from typing import cast

from cortex.core.models import ResponseFormat
from cortex.tools.validation_helpers import ValidationCheckType


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
    check_type_str = check_type.value
    concise_payload = {
        "status": status,
        "check_type": check_type_str,
        "valid": bool(valid),
        "error_count": 0,
        "warning_count": 0,
    }
    return json.dumps(concise_payload, indent=2)
