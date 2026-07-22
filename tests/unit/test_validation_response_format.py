import json

from cortex.core.models import ResponseFormat
from cortex.tools.validation.helpers import ValidationCheckType
from cortex.tools.validation.response_formatters import (
    compute_validate_counts,
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
        check_type=ValidationCheckType.SCHEMA,
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
        check_type=ValidationCheckType.SCHEMA,
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
        check_type=ValidationCheckType.SCHEMA,
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
        check_type=ValidationCheckType.DUPLICATIONS,
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
        check_type=ValidationCheckType.SCHEMA,
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
        check_type=ValidationCheckType.SCHEMA,
        response_format=ResponseFormat.CONCISE,
    )
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["check_type"] == "schema"
    # Even though the top-level said True, the nested schema result is authoritative.
    assert data["valid"] is False


def test_format_validate_response_schema_concise_reports_real_counts() -> None:
    """CONCISE schema responses must report actual error/warning counts, not 0."""
    raw = json.dumps(
        {
            "status": "success",
            "check_type": "schema",
            "validation": {
                "valid": False,
                "errors": [{"message": "err1"}, {"message": "err2"}],
                "warnings": [{"message": "warn"}],
            },
        }
    )

    out = format_validate_response(
        raw,
        check_type=ValidationCheckType.SCHEMA,
        response_format=ResponseFormat.CONCISE,
    )
    data = json.loads(out)

    assert data["error_count"] == 2
    assert data["warning_count"] == 1


def test_format_validate_response_roadmap_sync_concise_reports_real_counts() -> None:
    """CONCISE roadmap_sync responses must aggregate the same fields as `valid`."""
    raw = json.dumps(
        {
            "status": "success",
            "check_type": "roadmap_sync",
            "valid": False,
            "missing_roadmap_entries": [{"todo": "a"}],
            "invalid_references": [{"file_path": "x.py"}, {"file_path": "y.py"}],
            "unlinked_plans": ["plan.md"],
            "completed_entries_in_roadmap": [],
            "warnings": ["stale entry"],
        }
    )

    out = format_validate_response(
        raw,
        check_type=ValidationCheckType.ROADMAP_SYNC,
        response_format=ResponseFormat.CONCISE,
    )
    data = json.loads(out)

    assert data["valid"] is False
    assert data["error_count"] == 4
    assert data["warning_count"] == 1


def test_compute_validate_counts_duplications_uses_duplicates_found() -> None:
    """Duplications has no warning concept; error_count comes from duplicates_found."""
    data: dict[str, object] = {
        "duplicates_found": 3,
        "exact_duplicates": [],
        "similar_content": [],
    }

    error_count, warning_count = compute_validate_counts(
        data, ValidationCheckType.DUPLICATIONS
    )

    assert error_count == 3
    assert warning_count == 0


def test_compute_validate_counts_infrastructure_uses_issues_found() -> None:
    """Infrastructure error_count comes from the issues_found list length."""
    data: dict[str, object] = {"issues_found": [{"type": "a"}, {"type": "b"}]}

    error_count, warning_count = compute_validate_counts(
        data, ValidationCheckType.INFRASTRUCTURE
    )

    assert error_count == 2
    assert warning_count == 0


def test_compute_validate_counts_timestamps_sums_invalid_counters() -> None:
    """Timestamps error_count sums invalid-format and invalid-with-time counters."""
    data: dict[str, object] = {"invalid_format_count": 2, "invalid_with_time_count": 1}

    error_count, warning_count = compute_validate_counts(
        data, ValidationCheckType.TIMESTAMPS
    )

    assert error_count == 3
    assert warning_count == 0


def test_compute_validate_counts_timestamps_all_files_variant() -> None:
    """All-files timestamps responses use total_invalid_* counters instead."""
    data: dict[str, object] = {"total_invalid_format": 4, "total_invalid_with_time": 0}

    error_count, warning_count = compute_validate_counts(
        data, ValidationCheckType.TIMESTAMPS
    )

    assert error_count == 4
    assert warning_count == 0


def test_compute_validate_counts_quality_single_file_uses_nested_validation() -> None:
    """Single-file quality nests errors/warnings under score.validation."""
    data: dict[str, object] = {
        "score": {
            "validation": {
                "errors": [{"message": "e"}],
                "warnings": [{"message": "w1"}, {"message": "w2"}],
            }
        }
    }

    error_count, warning_count = compute_validate_counts(
        data, ValidationCheckType.QUALITY
    )

    assert error_count == 1
    assert warning_count == 2


def test_compute_validate_counts_quality_all_files_uses_issues() -> None:
    """All-files quality has no nested validation block; uses the issues list."""
    data: dict[str, object] = {"issues": ["low completeness", "stale freshness"]}

    error_count, warning_count = compute_validate_counts(
        data, ValidationCheckType.QUALITY
    )

    assert error_count == 2
    assert warning_count == 0


def test_compute_validate_counts_valid_response_reports_zero() -> None:
    """A genuinely valid roadmap_sync response reports zero counts (truthfully)."""
    data: dict[str, object] = {
        "valid": True,
        "missing_roadmap_entries": [],
        "invalid_references": [],
        "unlinked_plans": [],
        "completed_entries_in_roadmap": [],
        "warnings": [],
    }

    error_count, warning_count = compute_validate_counts(
        data, ValidationCheckType.ROADMAP_SYNC
    )

    assert error_count == 0
    assert warning_count == 0


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
        check_type=ValidationCheckType.SCHEMA,
        response_format=ResponseFormat.CONCISE,
    )
    data = json.loads(out)

    assert data["status"] == "success"
    assert data["check_type"] == "schema"
    assert data["valid"] is False
