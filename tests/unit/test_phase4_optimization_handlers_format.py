"""Unit tests for optimization_handlers_format module."""

import json
from typing import cast

from cortex.core.models import ResponseFormat
from cortex.tools.optimization_handlers_format import (
    add_zero_file_warning_if_needed,
    build_concise_payload,
    count_files_from_result,
    format_and_add_warnings_if_needed,
    format_detailed_load_context_response,
    format_load_context_error,
    format_load_context_response,
)


class TestCountFilesFromResult:
    """Tests for count_files_from_result."""

    def test_count_from_files_list(self) -> None:
        """Count files from 'files' list."""
        result = cast(
            dict[str, object],
            {"files": ["a.md", "b.md"], "status": "success"},
        )
        assert count_files_from_result(result) == 2

    def test_count_from_total_files(self) -> None:
        """Count files from total_files when files is not a list."""
        result = cast(
            dict[str, object],
            {"files": "invalid", "total_files": 5, "status": "success"},
        )
        assert count_files_from_result(result) == 5

    def test_count_from_selected_files_list(self) -> None:
        """Count files from selected_files list."""
        result = cast(
            dict[str, object],
            {"selected_files": ["x.md", "y.md", "z.md"], "status": "success"},
        )
        assert count_files_from_result(result) == 3

    def test_count_zero_when_no_files_key(self) -> None:
        """Return 0 when no files-related keys present."""
        result = cast(dict[str, object], {"status": "success"})
        assert count_files_from_result(result) == 0

    def test_count_zero_when_files_not_list(self) -> None:
        """Return 0 when files is not a list and no total_files."""
        result = cast(dict[str, object], {"files": "string", "status": "success"})
        assert count_files_from_result(result) == 0


class TestAddZeroFileWarningIfNeeded:
    """Tests for add_zero_file_warning_if_needed."""

    def test_adds_warning_when_zero_files_success(self) -> None:
        """Add zero-files warning when success with 0 files."""
        result_str = json.dumps(
            {"status": "success", "files": [], "total_tokens": 0},
            indent=2,
        )
        out = add_zero_file_warning_if_needed(
            result_str, task_description="Implement X", token_budget=10000
        )
        data = json.loads(out)
        assert "warnings" in data
        assert len(data["warnings"]) == 1
        assert data["warnings"][0]["type"] == "zero_files_selected"
        assert data["warnings"][0]["task_description"] == "Implement X"

    def test_returns_original_on_non_success(self) -> None:
        """Return original when status is not success."""
        result_str = json.dumps({"status": "error", "error": "Failed"})
        out = add_zero_file_warning_if_needed(result_str, "task", 5000)
        assert out == result_str

    def test_returns_original_on_invalid_json(self) -> None:
        """Return original when JSON is invalid."""
        out = add_zero_file_warning_if_needed("not valid json", "task", 5000)
        assert out == "not valid json"


class TestFormatLoadContextError:
    """Tests for format_load_context_error."""

    def test_formats_error_with_suggestion_and_example(self) -> None:
        """format_load_context_error returns JSON with error, suggestion, and example."""
        result = format_load_context_error(ValueError("Test error"))
        data = json.loads(result)
        assert data.get("status") == "error"
        assert "error" in data or "message" in data
        assert "suggestion" in data
        assert "example" in data
        example = data["example"]
        assert "task_description" in example
        assert "token_budget" in example

    def test_preserves_original_error_message(self) -> None:
        """format_load_context_error includes original error text."""
        msg = "Specific validation failure"
        result = format_load_context_error(ValueError(msg))
        assert msg in result


class TestFormatDetailedLoadContextResponse:
    """Tests for format_detailed_load_context_response."""

    def test_injects_role_when_available(self) -> None:
        """Inject role into response when provided."""
        out = json.dumps({"status": "success", "files": []}, indent=2)
        result = format_detailed_load_context_response(out, role="feature")
        data = json.loads(result)
        assert data["role"] == "feature"

    def test_returns_unchanged_when_role_none(self) -> None:
        """Return unchanged when role is None."""
        out = json.dumps({"status": "success"}, indent=2)
        result = format_detailed_load_context_response(out, role=None)
        assert result == out

    def test_returns_original_on_json_error(self) -> None:
        """Return original on JSON decode error."""
        result = format_detailed_load_context_response("invalid", role="feature")
        assert result == "invalid"

    def test_returns_original_when_data_is_not_dict(self) -> None:
        """Return original when JSON parses to non-dict (e.g. array)."""
        out = json.dumps([1, 2, 3])
        result = format_detailed_load_context_response(out, role="feature")
        assert result == out


class TestBuildConcisePayload:
    """Tests for build_concise_payload."""

    def test_builds_with_selected_files_dict(self) -> None:
        """Build payload when selected_files is a dict (file->content)."""
        data = cast(
            dict[str, object],
            {
                "status": "success",
                "task_description": "Test",
                "strategy": "priority",
                "selected_files": {"b.md": "...", "a.md": "..."},
                "total_tokens": 100,
                "utilization": 0.5,
            },
        )
        result = build_concise_payload(data, role="testing")
        parsed = json.loads(result)
        assert parsed["file_names"] == ["a.md", "b.md"]
        assert parsed["role"] == "testing"

    def test_builds_without_role(self) -> None:
        """Build payload without role when role is None."""
        data = cast(
            dict[str, object],
            {
                "status": "success",
                "task_description": "T",
                "strategy": "s",
                "selected_files": {},
                "total_tokens": 0,
                "utilization": 0.0,
            },
        )
        result = build_concise_payload(data, role=None)
        parsed = json.loads(result)
        assert "role" not in parsed

    def test_builds_with_selected_files_as_list(self) -> None:
        """Build payload when selected_files is a list (fallback to empty file_names)."""
        data = cast(
            dict[str, object],
            {
                "status": "success",
                "selected_files": ["a.md", "b.md"],
                "total_tokens": 50,
            },
        )
        result = build_concise_payload(data, role=None)
        parsed = json.loads(result)
        assert parsed["file_names"] == []
        assert parsed["total_tokens"] == 50


class TestFormatLoadContextResponse:
    """Tests for format_load_context_response."""

    def test_concise_format_builds_payload(self) -> None:
        """Concise format uses build_concise_payload."""
        out = json.dumps(
            {
                "status": "success",
                "selected_files": {"f.md": "x"},
                "total_tokens": 10,
                "utilization": 0.2,
            },
            indent=2,
        )
        result = format_load_context_response(
            out, response_format=ResponseFormat.CONCISE, role=None
        )
        parsed = json.loads(result)
        assert "file_names" in parsed
        assert parsed["file_names"] == ["f.md"]

    def test_detailed_format_passthrough(self) -> None:
        """Detailed format passes through format_detailed_load_context_response."""
        out = json.dumps({"status": "success"}, indent=2)
        result = format_load_context_response(
            out, response_format=ResponseFormat.DETAILED, role="x"
        )
        parsed = json.loads(result)
        assert parsed["role"] == "x"

    def test_concise_format_returns_original_when_non_dict_json(self) -> None:
        """Concise format returns original when JSON parses to non-dict (e.g. array)."""
        out = json.dumps([1, 2, 3])
        result = format_load_context_response(
            out, response_format=ResponseFormat.CONCISE, role=None
        )
        assert result == out


class TestFormatAndAddWarningsIfNeeded:
    """Tests for format_and_add_warnings_if_needed."""

    def test_adds_warning_for_non_trivial_zero_files(self) -> None:
        """Add zero-file warning when non-trivial task has 0 files."""
        out = json.dumps(
            {"status": "success", "files": [], "total_tokens": 0},
            indent=2,
        )
        result = format_and_add_warnings_if_needed(
            out,
            response_format=ResponseFormat.DETAILED,
            role="feature",
            task_description="Implement new feature",
            token_budget=15000,
        )
        data = json.loads(result)
        assert "warnings" in data
        assert any(w.get("type") == "zero_files_selected" for w in data["warnings"])
