"""Unit tests for MCP tool failure detection and protocol enforcement.

Tests verify that:
- Failure detection correctly identifies tool failures
- Investigation plans are created automatically
- Roadmap is updated with blockers
- Protocol violations are prevented
- Response validation works correctly
"""

import json
from pathlib import Path

import pytest

from cortex.core.mcp_failure_handler import (
    MCPToolFailure,
    MCPToolFailureHandler,
)
from cortex.core.mcp_tool_validator import (
    check_mcp_tool_failure,
    handle_mcp_tool_failure,
    validate_mcp_tool_response,
)
from cortex.core.models import JsonValue
from tests.helpers.types import RawJSONDict


class TestFailureDetection:
    """Test that failure detection correctly identifies tool failures."""

    def test_detect_json_parsing_error(self, tmp_path: Path) -> None:
        """Test that JSON parsing errors are detected."""
        handler = MCPToolFailureHandler(tmp_path)
        error = json.JSONDecodeError("Expecting value", "", 0)
        assert handler.detect_failure(error, "test_tool", "test_step") is True

    def test_detect_json_value_error(self, tmp_path: Path) -> None:
        """Test that JSON-related ValueError is detected."""
        handler = MCPToolFailureHandler(tmp_path)
        error = ValueError("Invalid JSON encoding")
        assert handler.detect_failure(error, "test_tool", "test_step") is True

    def test_detect_connection_error(self, tmp_path: Path) -> None:
        """Test that connection errors are detected."""
        handler = MCPToolFailureHandler(tmp_path)
        error = ConnectionError("Connection closed")
        assert handler.detect_failure(error, "test_tool", "test_step") is True

    def test_detect_unexpected_behavior(self, tmp_path: Path) -> None:
        """Test that unexpected behavior errors are detected."""
        handler = MCPToolFailureHandler(tmp_path)
        error = TypeError("Unexpected type")
        assert handler.detect_failure(error, "test_tool", "test_step") is True

    def test_detect_fastmcp_error(self, tmp_path: Path) -> None:
        """Test that FastMCP errors are detected."""
        handler = MCPToolFailureHandler(tmp_path)
        error = RuntimeError("MCP error -32000: Connection closed")
        assert handler.detect_failure(error, "test_tool", "test_step") is True

    def test_ignore_expected_errors(self, tmp_path: Path) -> None:
        """Test that expected errors (validation failures) are not detected."""
        handler = MCPToolFailureHandler(tmp_path)
        # Validation failure - not a tool failure
        error = ValueError("Validation failed: file not found")
        assert handler.detect_failure(error, "test_tool", "test_step") is False


class TestInvestigationPlanCreation:
    """Test that investigation plans are created automatically."""

    def test_create_investigation_plan(self, tmp_path: Path) -> None:
        """Test that investigation plan is created with correct content."""
        handler = MCPToolFailureHandler(tmp_path)
        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = handler.create_investigation_plan("test_tool", error, "test_step")

        assert plan_path.exists()
        assert plan_path.name.startswith("phase-investigate-test_tool-failure-")
        assert plan_path.suffix == ".md"

        content = plan_path.read_text(encoding="utf-8")
        assert "test_tool" in content
        assert "test_step" in content
        assert "JSONDecodeError" in content
        assert "ASAP (Blocker)" in content

    def test_investigation_plan_structure(self, tmp_path: Path) -> None:
        """Test that investigation plan has correct structure."""
        handler = MCPToolFailureHandler(tmp_path)
        error = ConnectionError("Connection closed")
        plan_path = handler.create_investigation_plan("test_tool", error, "test_step")

        content = plan_path.read_text(encoding="utf-8")
        assert "## Goal" in content
        assert "## Context" in content
        assert "## Requirements" in content
        assert "## Implementation Steps" in content
        assert "## Success Criteria" in content
        assert "## Notes" in content


class TestRoadmapIntegration:
    """Test that roadmap is updated with blockers."""

    def test_add_to_roadmap(self, tmp_path: Path) -> None:
        """Test that investigation plan is added to roadmap."""
        # Create memory bank directory and roadmap
        memory_bank = tmp_path / ".cortex" / "memory-bank"
        memory_bank.mkdir(parents=True)
        roadmap = memory_bank / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Blockers (ASAP Priority)\n\n", encoding="utf-8"
        )

        handler = MCPToolFailureHandler(tmp_path)
        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = handler.create_investigation_plan("test_tool", error, "test_step")
        handler.add_to_roadmap(plan_path, "test_tool", error)

        content = roadmap.read_text(encoding="utf-8")
        assert "test_tool" in content
        assert "ASAP (PLANNING)" in content
        assert "Investigate and fix MCP tool failure" in content

    def test_add_to_roadmap_creates_section(self, tmp_path: Path) -> None:
        """Test that roadmap section is created if it doesn't exist."""
        # Create memory bank directory and roadmap without blockers section
        memory_bank = tmp_path / ".cortex" / "memory-bank"
        memory_bank.mkdir(parents=True)
        roadmap = memory_bank / "roadmap.md"
        _ = roadmap.write_text("# Roadmap\n\nSome content\n", encoding="utf-8")

        handler = MCPToolFailureHandler(tmp_path)
        error = json.JSONDecodeError("Expecting value", "", 0)
        plan_path = handler.create_investigation_plan("test_tool", error, "test_step")
        handler.add_to_roadmap(plan_path, "test_tool", error)

        content = roadmap.read_text(encoding="utf-8")
        assert "## Blockers (ASAP Priority)" in content


class TestProtocolEnforcement:
    """Test that protocol violations are prevented."""

    def test_handle_failure_raises_exception(self, tmp_path: Path) -> None:
        """Test that handle_failure always raises MCPToolFailure."""
        handler = MCPToolFailureHandler(tmp_path)
        error = json.JSONDecodeError("Expecting value", "", 0)

        with pytest.raises(MCPToolFailure) as exc_info:
            handler.handle_failure("test_tool", error, "test_step")

        assert exc_info.value.tool_name == "test_tool"
        assert exc_info.value.step_name == "test_step"
        assert exc_info.value.error == error

    def test_handle_failure_creates_plan(self, tmp_path: Path) -> None:
        """Test that handle_failure creates investigation plan."""
        # Create memory bank directory and roadmap
        memory_bank = tmp_path / ".cortex" / "memory-bank"
        memory_bank.mkdir(parents=True)
        roadmap = memory_bank / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Blockers (ASAP Priority)\n\n", encoding="utf-8"
        )

        handler = MCPToolFailureHandler(tmp_path)
        error = json.JSONDecodeError("Expecting value", "", 0)

        with pytest.raises(MCPToolFailure):
            handler.handle_failure("test_tool", error, "test_step")

        # Check that plan was created
        plans_dir = tmp_path / ".cortex" / "plans"
        plan_files = list(plans_dir.glob("phase-investigate-test_tool-failure-*.md"))
        assert len(plan_files) == 1

        # Check that roadmap was updated
        content = roadmap.read_text(encoding="utf-8")
        assert "test_tool" in content


class TestResponseValidation:
    """Test that response validation works correctly."""

    def test_validate_none_response(self, tmp_path: Path) -> None:
        """Test that None response is detected as failure."""
        with pytest.raises(MCPToolFailure):
            validate_mcp_tool_response(None, "test_tool", "test_step", str(tmp_path))

    def test_validate_error_status_is_valid_response(self, tmp_path: Path) -> None:
        """Test that error status in response is NOT a tool failure.

        A response with status="error" means the tool worked correctly and found
        errors in the code (e.g., type errors, lint errors). This is different from
        a tool failure (JSON parsing, connection error, etc.).
        """
        response: JsonValue = {
            "status": "error",
            "error": "Type checking found 5 errors",
            "total_errors": 5,
        }
        # Should NOT raise - error status is a valid response
        validate_mcp_tool_response(response, "test_tool", "test_step", str(tmp_path))

    def test_validate_json_string_response(self, tmp_path: Path) -> None:
        """Test that JSON string response is detected as failure."""
        response = json.dumps({"status": "success"})
        with pytest.raises(MCPToolFailure):
            validate_mcp_tool_response(
                response, "test_tool", "test_step", str(tmp_path)
            )

    def test_validate_valid_response(self, tmp_path: Path) -> None:
        """Test that valid response passes validation."""
        response: JsonValue = {"status": "success", "data": "test"}
        # Should not raise
        validate_mcp_tool_response(response, "test_tool", "test_step", str(tmp_path))

    def test_validate_response_without_status(self, tmp_path: Path) -> None:
        """Test that response without status field logs warning but doesn't fail."""
        response: JsonValue = {"data": "test"}  # Missing status field
        # Should not raise (just logs warning)
        validate_mcp_tool_response(response, "test_tool", "test_step", str(tmp_path))


class TestValidatorHelpers:
    """Test validator helper functions."""

    def test_check_mcp_tool_failure(self, tmp_path: Path) -> None:
        """Test that check_mcp_tool_failure correctly identifies failures."""
        error = json.JSONDecodeError("Expecting value", "", 0)
        assert (
            check_mcp_tool_failure(error, "test_tool", "test_step", str(tmp_path))
            is True
        )

        error = ValueError("Validation failed")
        assert (
            check_mcp_tool_failure(error, "test_tool", "test_step", str(tmp_path))
            is False
        )

    def test_handle_mcp_tool_failure_raises(self, tmp_path: Path) -> None:
        """Test that handle_mcp_tool_failure always raises."""
        # Create memory bank directory and roadmap
        memory_bank = tmp_path / ".cortex" / "memory-bank"
        memory_bank.mkdir(parents=True)
        roadmap = memory_bank / "roadmap.md"
        _ = roadmap.write_text(
            "# Roadmap\n\n## Blockers (ASAP Priority)\n\n", encoding="utf-8"
        )

        error = json.JSONDecodeError("Expecting value", "", 0)
        with pytest.raises(MCPToolFailure):
            handle_mcp_tool_failure(error, "test_tool", "test_step", str(tmp_path))


class TestMCPToolWrapperIntegration:
    """Integration tests for mcp_tool_wrapper in production scenarios."""

    def test_wrapper_basic_execution(self, tmp_path: Path) -> None:
        """Test that mcp_tool_wrapper executes tools correctly."""
        import asyncio

        from cortex.core.mcp_stability import mcp_tool_wrapper

        @mcp_tool_wrapper(timeout=1.0)
        async def valid_tool() -> dict[str, object]:
            """Tool that returns valid response."""
            return {"status": "success", "data": "test"}

        # Act
        result: RawJSONDict = asyncio.run(valid_tool())  # type: ignore[arg-type]

        # Assert
        assert result == {"status": "success", "data": "test"}

    def test_wrapper_propagates_value_errors(self, tmp_path: Path) -> None:
        """Test that wrapper propagates ValueError exceptions."""
        import asyncio

        from cortex.core.mcp_stability import mcp_tool_wrapper

        @mcp_tool_wrapper(timeout=1.0)
        async def tool_with_validation_error() -> dict[str, object]:
            """Tool that raises expected validation error."""
            raise ValueError("Validation failed: file not found")

        # Act & Assert - ValueError should propagate through
        with pytest.raises(ValueError, match="Validation failed"):
            _ = asyncio.run(tool_with_validation_error())  # type: ignore[arg-type]
