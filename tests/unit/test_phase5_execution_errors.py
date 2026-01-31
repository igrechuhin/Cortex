"""Unit tests for phase5_execution_errors module."""

import json

from cortex.tools.phase5_execution_errors import (
    create_execution_error_response,
    create_invalid_action_error,
    create_missing_param_error,
)


class TestCreateMissingParamError:
    """Tests for create_missing_param_error."""

    def test_returns_valid_json_with_missing_param_message(self) -> None:
        result = create_missing_param_error("suggestion_id", "approve")
        data = json.loads(result)
        assert data["status"] == "error"
        assert "suggestion_id" in data.get("action_required", "")
        assert "approve" in data.get("action_required", "")


class TestCreateInvalidActionError:
    """Tests for create_invalid_action_error."""

    def test_returns_valid_json_with_invalid_action_message(self) -> None:
        result = create_invalid_action_error("unknown")
        data = json.loads(result)
        assert data["status"] == "error"
        assert "unknown" in data.get("action_required", "")


class TestCreateExecutionErrorResponse:
    """Tests for create_execution_error_response."""

    def test_validation_error_branch_sets_validation_action_required(self) -> None:
        error = ValueError("validation failed: invalid schema")
        result = create_execution_error_response(error)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "validate_first" in data.get("action_required", "")

    def test_validation_error_type_name_hits_validation_branch(self) -> None:
        """Error type name containing ValidationError hits validation branch."""

        class ValidationError(ValueError):
            pass

        error = ValidationError("invalid")
        result = create_execution_error_response(error)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "validate_first" in data.get("action_required", "")

    def test_permission_error_branch_sets_permission_action_required(self) -> None:
        error = PermissionError("permission denied")
        result = create_execution_error_response(error)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "permission" in data.get("action_required", "").lower()

    def test_file_not_found_error_branch_sets_not_found_action_required(self) -> None:
        error = FileNotFoundError("file not found")
        result = create_execution_error_response(error)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "get_memory_bank_stats" in data.get("action_required", "")

    def test_generic_error_branch_sets_generic_action_required(self) -> None:
        error = RuntimeError("unexpected failure")
        result = create_execution_error_response(error)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "dry_run" in data.get("action_required", "")
