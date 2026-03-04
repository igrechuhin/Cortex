"""Unit tests for shared MCP response_builder helpers."""

from cortex.tools.response_builder import error_response, success_response


class TestSuccessResponse:
    """Tests for success_response helper."""

    def test_builds_status_success_with_payload(self) -> None:
        """Success response uses status=success and includes payload fields."""
        result = success_response(value=1, message="ok")
        assert result["status"] == "success"
        assert result["value"] == 1
        assert result["message"] == "ok"


class TestErrorResponse:
    """Tests for error_response helper."""

    def test_builds_status_error_with_message(self) -> None:
        """Error response uses status=error and error field."""
        result = error_response("Something failed")
        assert result["status"] == "error"
        assert result["error"] == "Something failed"
        assert "error_code" not in result

    def test_includes_error_code_and_extra_fields(self) -> None:
        """Error response can include error_code and extra context."""
        result = error_response(
            "Bad input",
            error_code="invalid_input",
            field="name",
            error_type="ValueError",
        )
        assert result["status"] == "error"
        assert result["error"] == "Bad input"
        assert result["error_code"] == "invalid_input"
        assert result["field"] == "name"
        assert result["error_type"] == "ValueError"
