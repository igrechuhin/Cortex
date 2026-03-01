"""Helper functions for pre-commit tools.

Extracted to keep pre_commit_tools.py under 400 lines.
Public API re-exports from helper modules for backward compatibility.
"""

import json
import math
from collections.abc import Sequence
from typing import cast

from cortex.core.models import JsonValue, ModelDict
from cortex.tools.execution.pre_commit_helpers_models import (
    DEFAULT_CHECKS,
    PreCommitCheck,
)


def create_error_result(error: str, error_type: str = "ValueError") -> str:
    """Create error response JSON."""
    return json.dumps(
        {"status": "error", "error": error, "error_type": error_type},
        indent=2,
    )


def create_error_result_dict(error: str, error_type: str = "ValueError") -> ModelDict:
    """Create error response as dict for MCP (avoids double JSON encoding)."""
    from cortex.tools.error_formatters import format_tool_error

    exception: Exception
    if error_type == "ValueError":
        exception = ValueError(error)
    elif error_type == "FileNotFoundError":
        exception = FileNotFoundError(error)
    elif error_type == "Exception":
        exception = Exception(error)
    else:
        exception = ValueError(error)

    json_response = format_tool_error(
        exception,
        suggestion=(
            "Review the error details and ensure all parameters are valid. "
            "Check the tool documentation for correct usage."
        ),
        example={
            "checks": ["format", "type_check"],
            "test_timeout": 300,
            "coverage_threshold": 0.9,
            "strict_mode": False,
        },
    )
    result = json.loads(json_response)
    if error_type != "ValueError" and error_type != type(exception).__name__:
        result["error_type"] = error_type
    return result


def unsupported_language_result(
    language: str, supported_languages: tuple[str, ...]
) -> str:
    """Return error JSON for unsupported language."""
    supported = ", ".join(supported_languages)
    msg = (
        f"Language '{language}' is not yet supported. "
        + f"Supported languages: {supported}"
    )
    return create_error_result(msg)


def unsupported_language_result_dict(
    language: str, supported_languages: tuple[str, ...]
) -> ModelDict:
    """Return error dict for unsupported language (for MCP tool return)."""
    supported = ", ".join(supported_languages)
    msg = (
        f"Language '{language}' is not yet supported. "
        + f"Supported languages: {supported}"
    )
    return create_error_result_dict(msg)


def determine_checks_to_perform(checks: Sequence[str] | None) -> list[PreCommitCheck]:
    """Determine which checks to perform. Invalid names are skipped."""
    if not checks:
        return list(DEFAULT_CHECKS)
    result: list[PreCommitCheck] = []
    for name in checks:
        try:
            result.append(PreCommitCheck(name))
        except ValueError:
            continue
    if not result:
        return list(DEFAULT_CHECKS)
    if PreCommitCheck.QUALITY in result and PreCommitCheck.TYPE_CHECK not in result:
        quality_idx = result.index(PreCommitCheck.QUALITY)
        result.insert(quality_idx + 1, PreCommitCheck.TYPE_CHECK)
    return result


def _replace_nan_inf(value: JsonValue) -> JsonValue:
    """Recursively replace float nan/inf with None for JSON compatibility."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _replace_nan_inf(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_nan_inf(item) for item in value]
    return value


def _json_friendly_default(obj: object) -> str | None:
    """Convert non-JSON-serializable values for MCP response."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return str(obj)


def ensure_json_serializable_for_mcp(data: ModelDict) -> ModelDict:
    """Ensure dict round-trips through JSON for MCP (avoids serialization errors)."""
    sanitized = _replace_nan_inf(data)
    serialized = json.dumps(
        sanitized, separators=(",", ":"), default=_json_friendly_default
    )
    return cast(ModelDict, json.loads(serialized))
