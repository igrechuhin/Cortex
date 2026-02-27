"""Unit tests for tool error formatters."""

import json

from cortex.core.models import JsonDict, JsonValue, ResponseStatus
from cortex.tools.tool_error_formatters import (
    ToolErrorResponse,
    format_configuration_error,
    format_external_tool_error,
    format_file_not_found_error,
    format_invalid_parameter_error,
    format_missing_parameter_error,
    format_tool_error,
    format_validation_error,
)


class TestToolErrorResponse:
    """Test ToolErrorResponse model."""

    def test_basic_error_response(self) -> None:
        """Test basic error response creation."""
        response = ToolErrorResponse(
            status=ResponseStatus.ERROR,
            error="Test error",
            error_type="ValueError",
        )
        assert response.status == "error"
        assert response.error == "Test error"
        assert response.error_type == "ValueError"
        assert response.suggestion is None
        assert response.example is None
        assert response.available_options is None

    def test_full_error_response(self) -> None:
        """Test error response with all fields."""
        response = ToolErrorResponse(
            status=ResponseStatus.ERROR,
            error="Test error",
            error_type="ValueError",
            suggestion="Do something else",
            example={"param": "value"},
            available_options=["option1", "option2"],
            context=JsonDict.from_dict({"key": "value"}),
        )
        assert response.suggestion == "Do something else"
        assert response.example == {"param": "value"}
        assert response.available_options == ["option1", "option2"]

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        response = ToolErrorResponse(
            status=ResponseStatus.ERROR,
            error="Test error",
            error_type="ValueError",
            suggestion="Test suggestion",
        )
        json_str = response.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["status"] == "error"
        assert parsed["error"] == "Test error"
        assert parsed["suggestion"] == "Test suggestion"
        assert "example" not in parsed  # None fields excluded

    def test_exclude_none_fields(self) -> None:
        """Test that None fields are excluded from JSON."""
        response = ToolErrorResponse(
            status=ResponseStatus.ERROR,
            error="Test error",
            error_type="ValueError",
        )
        json_str = response.to_json()
        parsed = json.loads(json_str)
        assert "suggestion" not in parsed
        assert "example" not in parsed
        assert "available_options" not in parsed
        assert "context" not in parsed


class TestFormatToolError:
    """Test format_tool_error function."""

    def test_basic_error_formatting(self) -> None:
        """Test basic error formatting."""
        error = ValueError("Invalid value")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert parsed["error"] == "Invalid value"
        assert parsed["error_type"] == "ValueError"

    def test_with_suggestion(self) -> None:
        """Test error formatting with suggestion."""
        error = ValueError("Invalid value")
        result = format_tool_error(error, suggestion="Use a valid value")
        parsed = json.loads(result)
        assert parsed["suggestion"] == "Use a valid value"

    def test_with_example(self) -> None:
        """Test error formatting with example."""
        error = ValueError("Invalid value")
        example: dict[str, JsonValue] = {"param": "valid_value"}
        result = format_tool_error(error, example=example)
        parsed = json.loads(result)
        assert parsed["example"] == example

    def test_with_available_options(self) -> None:
        """Test error formatting with available options."""
        error = ValueError("Invalid value")
        options = ["option1", "option2", "option3"]
        result = format_tool_error(error, available_options=options)
        parsed = json.loads(result)
        assert parsed["available_options"] == options

    def test_with_context(self) -> None:
        """Test error formatting with context."""
        error = ValueError("Invalid value")
        context: dict[str, JsonValue] = {"file_name": "test.md", "line": 42}
        result = format_tool_error(error, context=context)
        parsed = json.loads(result)
        assert "context" in parsed
        assert parsed["context"]["file_name"] == "test.md"

    def test_auto_generate_suggestion_file_not_found(self) -> None:
        """Test auto-generation of suggestion for FileNotFoundError."""
        error = FileNotFoundError("File test.md not found")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert "file" in parsed["suggestion"].lower()
        assert "available" in parsed["suggestion"].lower()

    def test_auto_generate_suggestion_invalid(self) -> None:
        """Test auto-generation of suggestion for invalid value."""
        error = ValueError("Invalid parameter: 'bad'")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert (
            "parameter" in parsed["suggestion"].lower()
            or "format" in parsed["suggestion"].lower()
        )

    def test_auto_generate_suggestion_missing_required(self) -> None:
        """Test auto-generation of suggestion for missing required."""
        error = ValueError("Missing required parameter: 'file_name'")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert "required" in parsed["suggestion"].lower()

    def test_action_required_legacy_field(self) -> None:
        """Test that action_required is preserved for backward compatibility."""
        error = ValueError("Test error")
        result = format_tool_error(error, action_required="Legacy action")
        parsed = json.loads(result)
        assert parsed["action_required"] == "Legacy action"

    def test_auto_suggestion_permission_error(self) -> None:
        """Test auto-suggestion for permission/access errors."""
        error = PermissionError("Permission denied: no access to .cortex")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert (
            "permission" in parsed["suggestion"].lower()
            or "access" in parsed["suggestion"].lower()
        )

    def test_auto_suggestion_timeout_error(self) -> None:
        """Test auto-suggestion for timeout/lock errors."""
        error = TimeoutError("Operation timed out waiting for lock")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert (
            "timeout" in parsed["suggestion"].lower()
            or "lock" in parsed["suggestion"].lower()
        )

    def test_auto_suggestion_validation_error(self) -> None:
        """Test auto-suggestion for validation errors (message has 'validation' but not 'invalid')."""
        error = ValueError("Schema validation requirements not met")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert "validation" in parsed["suggestion"].lower()

    def test_auto_suggestion_connection_closed(self) -> None:
        """Test auto-suggestion for MCP connection/closure errors."""
        error = RuntimeError("MCP error -32000: Connection closed")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert "reconnect" in parsed["suggestion"].lower()
        assert "troubleshooting" in parsed["suggestion"].lower()

    def test_auto_suggestion_tool_not_found(self) -> None:
        """Test auto-suggestion for tool not found (often after connection drop)."""
        error = ValueError("Tool not found: manage_file")
        result = format_tool_error(error)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert "mcp" in parsed["suggestion"].lower()
        assert "reconnect" in parsed["suggestion"].lower()


class TestFormatFileNotFoundError:
    """Test format_file_not_found_error function."""

    def test_basic_file_not_found(self) -> None:
        """Test basic file not found error."""
        available = ["activeContext.md", "progress.md", "roadmap.md"]
        result = format_file_not_found_error("missing.md", available)
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "missing.md" in parsed["error"]
        assert parsed["available_options"] == available
        assert parsed["example"] is not None
        assert "file_name" in parsed["example"]

    def test_with_fuzzy_match(self) -> None:
        """Test file not found with fuzzy matching."""
        available = ["activeContext.md", "progress.md", "roadmap.md"]
        result = format_file_not_found_error("activecontext.md", available)  # Typo
        parsed = json.loads(result)
        assert (
            "Did you mean" in parsed["suggestion"]
            or "activeContext" in parsed["suggestion"]
        )

    def test_empty_available_files(self) -> None:
        """Test file not found with no available files."""
        result = format_file_not_found_error("missing.md", [])
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert parsed["available_options"] == []


class TestFormatInvalidParameterError:
    """Test format_invalid_parameter_error function."""

    def test_basic_invalid_parameter(self) -> None:
        """Test basic invalid parameter error."""
        valid = ["schema", "duplications", "quality"]
        result = format_invalid_parameter_error(
            "check_type", "invalid", valid, "validate"
        )
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "invalid" in parsed["error"]
        assert parsed["available_options"] == valid
        assert parsed["example"] is not None
        assert parsed["example"]["check_type"] in valid

    def test_with_fuzzy_match(self) -> None:
        """Test invalid parameter with fuzzy matching."""
        valid = ["schema", "duplications", "quality"]
        result = format_invalid_parameter_error(
            "check_type", "scheme", valid, "validate"
        )  # Typo
        parsed = json.loads(result)
        assert (
            "Did you mean" in parsed["suggestion"] or "schema" in parsed["suggestion"]
        )


class TestFormatMissingParameterError:
    """Test format_missing_parameter_error function."""

    def test_basic_missing_parameter(self) -> None:
        """Test basic missing parameter error."""
        missing = ["file_name", "operation"]
        result = format_missing_parameter_error(missing, "manage_file")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert "file_name" in parsed["error"]
        assert "operation" in parsed["error"]
        assert parsed["example"] is not None
        assert "file_name" in parsed["example"]
        assert "operation" in parsed["example"]

    def test_with_custom_example(self) -> None:
        """Test missing parameter with custom example."""
        missing = ["file_name"]
        example: dict[str, JsonValue] = {
            "file_name": "activeContext.md",
            "operation": "read",
        }
        result = format_missing_parameter_error(missing, "manage_file", example=example)
        parsed = json.loads(result)
        assert parsed["example"] == example


class TestFormatValidationError:
    """Test format_validation_error function."""

    def test_basic_validation_error(self) -> None:
        """Test basic validation error."""
        error = ValueError("Validation failed")
        result = format_validation_error(error)
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert parsed["suggestion"] is not None

    def test_with_violations(self) -> None:
        """Test validation error with violations."""
        error = ValueError("Validation failed")
        violations = [
            {"field": "title", "message": "Title is required"},
            {"field": "content", "message": "Content cannot be empty"},
        ]
        result = format_validation_error(error, violations=violations)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert "2" in parsed["suggestion"]  # Should mention count
        assert "context" in parsed
        assert "violations" in parsed["context"]

    def test_with_fix_suggestions(self) -> None:
        """Test validation error with fix suggestions."""
        error = ValueError("Validation failed")
        fixes = ["Add required section", "Fix formatting"]
        result = format_validation_error(error, fix_suggestions=fixes)
        parsed = json.loads(result)
        assert parsed["suggestion"] is not None
        assert "Add required section" in parsed["suggestion"]


class TestFormatConfigurationError:
    """Test format_configuration_error function."""

    def test_basic_configuration_error(self) -> None:
        """Test basic configuration error."""
        error = ValueError("Invalid configuration")
        result = format_configuration_error(error)
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert parsed["suggestion"] is not None

    def test_with_component(self) -> None:
        """Test configuration error with component."""
        error = ValueError("Invalid configuration")
        result = format_configuration_error(error, component="validation")
        parsed = json.loads(result)
        assert "validation" in parsed["suggestion"].lower()
        assert parsed["context"]["component"] == "validation"

    def test_with_current_config(self) -> None:
        """Test configuration error with current config."""
        error = ValueError("Invalid configuration")
        config: dict[str, JsonValue] = {"enabled": True, "threshold": 0.8}
        result = format_configuration_error(error, current_config=config)
        parsed = json.loads(result)
        assert parsed["context"]["current_config"] == config

    def test_with_expected_format(self) -> None:
        """Test configuration error with expected format."""
        error = ValueError("Invalid configuration")
        result = format_configuration_error(
            error, expected_format="JSON object with 'enabled' boolean field"
        )
        parsed = json.loads(result)
        assert "Expected format" in parsed["suggestion"]


class TestFormatExternalToolError:
    """Test format_external_tool_error function."""

    def test_basic_external_tool_error(self) -> None:
        """Test basic external tool error."""
        error = FileNotFoundError("Command 'ruff' not found")
        result = format_external_tool_error(error, "ruff")
        parsed = json.loads(result)
        assert parsed["status"] == "error"
        assert parsed["context"]["external_tool"] == "ruff"
        assert parsed["suggestion"] is not None
        assert "ruff" in parsed["suggestion"]

    def test_with_troubleshooting_steps(self) -> None:
        """Test external tool error with troubleshooting steps."""
        error = FileNotFoundError("Command 'ruff' not found")
        steps = ["Install ruff: pip install ruff", "Verify PATH includes Python bin"]
        result = format_external_tool_error(error, "ruff", troubleshooting_steps=steps)
        parsed = json.loads(result)
        assert "Install ruff" in parsed["suggestion"]


class TestFuzzyMatching:
    """Test fuzzy matching functionality via public API."""

    def test_fuzzy_match_exact(self) -> None:
        """Test fuzzy matching with exact match via format_file_not_found_error."""
        available = ["activeContext.md", "progress.md", "roadmap.md"]
        result = format_file_not_found_error("activeContext.md", available)
        parsed = json.loads(result)
        assert "activeContext.md" in parsed["available_options"]

    def test_fuzzy_match_typo(self) -> None:
        """Test fuzzy matching with typo via format_file_not_found_error."""
        available = ["activeContext.md", "progress.md", "roadmap.md"]
        result = format_file_not_found_error("activecontext.md", available)  # Typo
        parsed = json.loads(result)
        # Should suggest the correct file
        assert (
            "Did you mean" in parsed["suggestion"]
            or "activeContext" in parsed["suggestion"]
        )

    def test_fuzzy_match_invalid_parameter(self) -> None:
        """Test fuzzy matching via format_invalid_parameter_error."""
        valid = ["schema", "duplications", "quality"]
        result = format_invalid_parameter_error(
            "check_type", "scheme", valid, "validate"
        )
        parsed = json.loads(result)
        # Should suggest the correct value
        assert (
            "Did you mean" in parsed["suggestion"] or "schema" in parsed["suggestion"]
        )

    def test_fuzzy_match_no_match(self) -> None:
        """Test fuzzy matching with no good match."""
        available = ["activeContext.md", "progress.md", "roadmap.md"]
        result = format_file_not_found_error("completely_different.md", available)
        parsed = json.loads(result)
        # Should still list available files
        assert parsed["available_options"] == available
