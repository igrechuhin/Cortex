import json

from cortex.core.models import ResponseFormat
from cortex.tools.validation_operations import (
    ValidateCheckTypeName,
    format_validate_response,
)


def test_format_validate_response_schema_single_concise() -> None:
    raw = json.dumps(
        {
            "status": "success",
            "check_type": "schema",
            "file_name": "projectBrief.md",
            "validation": {
                "valid": False,
                "errors": [{"message": "err"}],
                "warnings": [{"message": "warn"}],
            },
        }
    )

    out = format_validate_response(
        raw,
        check_type=ValidateCheckTypeName.SCHEMA,
        response_format=ResponseFormat.CONCISE,
    )
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["check_type"] == "schema"
    # With concise mode we at least preserve the fact that validation failed.
    assert data["valid"] is False


def test_format_validate_response_detailed_passthrough() -> None:
    """When response_format='detailed', payload should be unchanged."""
    original = json.dumps({"status": "success", "check_type": "schema"})
    out = format_validate_response(
        original,
        check_type=ValidateCheckTypeName.SCHEMA,
        response_format=ResponseFormat.DETAILED,
    )
    assert out == original


def test_format_validate_response_error_status_passthrough() -> None:
    """Error responses should be preserved even in concise mode."""
    original = json.dumps(
        {
            "status": "error",
            "check_type": "schema",
            "error": "Something went wrong",
            "error_type": "RuntimeError",
        }
    )

    out = format_validate_response(
        original,
        check_type=ValidateCheckTypeName.SCHEMA,
        response_format=ResponseFormat.CONCISE,
    )

    assert out == original


def test_format_validate_response_non_schema_uses_top_level_valid_flag() -> None:
    """For non-schema checks, concise payload should echo the top-level valid flag."""
    raw = json.dumps(
        {
            "status": "success",
            "check_type": "duplications",
            "valid": False,
            "duplicates_found": 3,
        }
    )

    out = format_validate_response(
        raw,
        check_type=ValidateCheckTypeName.DUPLICATIONS,
        response_format=ResponseFormat.CONCISE,
    )
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["check_type"] == "duplications"
    assert data["valid"] is False


def test_format_validate_response_invalid_json_returns_raw() -> None:
    """Invalid JSON should be returned unchanged in concise mode."""
    original = "this-is-not-json"

    out = format_validate_response(
        original,
        check_type=ValidateCheckTypeName.SCHEMA,
        response_format=ResponseFormat.CONCISE,
    )

    assert out == original


def test_format_validate_response_schema_prefers_inner_valid_over_top_level() -> None:
    """For schema checks, inner validation.valid should override top-level valid."""
    raw = json.dumps(
        {
            "status": "success",
            "check_type": "schema",
            "valid": True,
            "validation": {
                "valid": False,
                "errors": [{"message": "err"}],
            },
        }
    )

    out = format_validate_response(
        raw,
        check_type=ValidateCheckTypeName.SCHEMA,
        response_format=ResponseFormat.CONCISE,
    )
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["check_type"] == "schema"
    # Even though the top-level said True, the nested schema result is authoritative.
    assert data["valid"] is False


def test_format_validate_response_schema_uses_top_level_when_no_inner_valid() -> None:
    """For schema checks, fall back to the top-level valid flag when inner valid is missing."""
    raw = json.dumps(
        {
            "status": "success",
            "check_type": "schema",
            "valid": False,
            "validation": {
                "errors": [{"message": "err"}],
            },
        }
    )

    out = format_validate_response(
        raw,
        check_type=ValidateCheckTypeName.SCHEMA,
        response_format=ResponseFormat.CONCISE,
    )
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["check_type"] == "schema"
    assert data["valid"] is False
