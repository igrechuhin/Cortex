"""
Unit tests for core utility modules.

Tests for:
- responses.py
- manager_registry.py
- mcp_tool_validator.py
- mcp_failure_handler.py
"""

# pyright: reportPrivateUsage=false

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.manager_registry import ManagerRegistry
from cortex.core.responses import error_response, success_response
from tests.helpers.managers import make_test_managers


class TestResponses:
    """Tests for responses module."""

    def test_success_response_basic(self) -> None:
        """Test basic success response."""
        # Act
        result = success_response({"count": 5})

        # Assert
        data = json.loads(result)
        assert data["status"] == "success"
        assert data["count"] == 5

    def test_success_response_complex_data(self) -> None:
        """Test success response with complex data."""
        # Arrange
        data: dict[str, object] = {
            "files": ["a.md", "b.md"],
            "stats": {"total": 100, "used": 50},
        }

        # Act
        result = success_response(data)

        # Assert
        parsed = json.loads(result)
        assert parsed["status"] == "success"
        assert parsed["files"] == ["a.md", "b.md"]
        assert parsed["stats"]["total"] == 100

    def test_error_response_basic(self) -> None:
        """Test basic error response."""
        # Act
        result = error_response(ValueError("Test error"))

        # Assert
        data = json.loads(result)
        assert data["status"] == "error"
        assert data["error"] == "Test error"
        assert data["error_type"] == "ValueError"

    def test_error_response_with_action(self) -> None:
        """Test error response with action required."""
        # Act
        result = error_response(
            RuntimeError("Config invalid"),
            action_required="Check configuration file",
        )

        # Assert
        data = json.loads(result)
        assert data["action_required"] == "Check configuration file"

    def test_error_response_with_context(self) -> None:
        """Test error response with context."""
        # Act
        result = error_response(
            FileNotFoundError("File missing"),
            context={"path": "/test/file.md"},
        )

        # Assert
        data = json.loads(result)
        assert data["context"]["path"] == "/test/file.md"

    def test_error_response_full(self) -> None:
        """Test error response with all options."""
        # Act
        result = error_response(
            ValueError("Invalid value"),
            action_required="Use positive number",
            context={"value": -5, "field": "budget"},
        )

        # Assert
        data = json.loads(result)
        assert data["status"] == "error"
        assert data["error_type"] == "ValueError"
        assert data["action_required"] == "Use positive number"
        assert data["context"]["value"] == -5


class TestManagerRegistry:
    """Tests for manager_registry module."""

    def test_init(self) -> None:
        """Test registry initialization."""
        # Act
        registry = ManagerRegistry()

        # Assert
        assert registry._managers == {}

    @pytest.mark.asyncio
    async def test_get_managers(self, tmp_path: Path) -> None:
        """Test getting managers for a project."""
        # Arrange
        registry = ManagerRegistry()
        mock_managers = make_test_managers(fs=MagicMock())

        with patch(
            "cortex.managers.initialization.initialize_managers",
            new_callable=AsyncMock,
            return_value=mock_managers,
        ):
            # Act
            result = await registry.get_managers(tmp_path)

            # Assert
            assert "fs" in result
            assert registry.has_managers(tmp_path)

    @pytest.mark.asyncio
    async def test_get_managers_cached(self, tmp_path: Path) -> None:
        """Test that managers are cached."""
        # Arrange
        registry = ManagerRegistry()
        mock_managers = make_test_managers(fs=MagicMock())

        with patch(
            "cortex.managers.initialization.initialize_managers",
            new_callable=AsyncMock,
            return_value=mock_managers,
        ) as mock_init:
            # Act - get twice
            _ = await registry.get_managers(tmp_path)
            _ = await registry.get_managers(tmp_path)

            # Assert - only called once
            assert mock_init.call_count == 1

    def test_clear_cache_all(self, tmp_path: Path) -> None:
        """Test clearing all cached managers."""
        # Arrange
        registry = ManagerRegistry()
        registry._managers[str(tmp_path)] = make_test_managers(fs=MagicMock())
        registry._managers["/other/path"] = make_test_managers(fs=MagicMock())

        # Act
        registry.clear_cache()

        # Assert
        assert registry._managers == {}

    def test_clear_cache_specific(self, tmp_path: Path) -> None:
        """Test clearing specific project cache."""
        # Arrange
        registry = ManagerRegistry()
        registry._managers[str(tmp_path)] = make_test_managers(fs=MagicMock())
        registry._managers["/other/path"] = make_test_managers(fs=MagicMock())

        # Act
        registry.clear_cache(tmp_path)

        # Assert
        assert not registry.has_managers(tmp_path)
        assert "/other/path" in registry._managers

    def test_has_managers_false(self, tmp_path: Path) -> None:
        """Test has_managers returns False when not cached."""
        # Arrange
        registry = ManagerRegistry()

        # Act & Assert
        assert not registry.has_managers(tmp_path)


class TestMCPToolValidator:
    """Tests for mcp_tool_validator module."""

    def test_validate_mcp_tool_response_success(self, tmp_path: Path) -> None:
        """Test validating successful MCP tool response."""
        from cortex.core.mcp_tool_validator import validate_mcp_tool_response

        # Arrange
        response = {"status": "success", "data": "test"}
        # Create .cortex directory for project detection
        (tmp_path / ".cortex").mkdir()

        # Act - no exception means success
        validate_mcp_tool_response(response, "test_tool", "test_step", str(tmp_path))

        # Assert - no exception raised

    def test_validate_mcp_tool_response_error_status_valid(
        self, tmp_path: Path
    ) -> None:
        """Test that error status is valid (tool worked, found errors)."""
        from cortex.core.mcp_tool_validator import validate_mcp_tool_response

        # Arrange
        response = {"status": "error", "error": "Type errors found"}
        (tmp_path / ".cortex").mkdir()

        # Act - error status is valid, not a tool failure
        # The function should not raise because status=error means the tool worked
        validate_mcp_tool_response(response, "test_tool", "test_step", str(tmp_path))

    def test_check_mcp_tool_failure_json_error(self, tmp_path: Path) -> None:
        """Test checking if JSON decode error is MCP tool failure."""
        import json

        from cortex.core.mcp_tool_validator import check_mcp_tool_failure

        # Arrange
        (tmp_path / ".cortex").mkdir()
        error = json.JSONDecodeError("Expecting value", "test", 0)

        # Act
        is_failure = check_mcp_tool_failure(
            error, "test_tool", "test_step", str(tmp_path)
        )

        # Assert - JSON decode error is always a tool failure
        assert is_failure is True

    def test_check_mcp_tool_failure_connection_reset(self, tmp_path: Path) -> None:
        """Test checking if connection reset is MCP tool failure."""
        from cortex.core.mcp_tool_validator import check_mcp_tool_failure

        # Arrange
        (tmp_path / ".cortex").mkdir()
        error = ConnectionError("Connection reset by peer")

        # Act
        is_failure = check_mcp_tool_failure(
            error, "test_tool", "test_step", str(tmp_path)
        )

        # Assert - Connection reset is a tool failure
        assert is_failure is True


class TestMCPFailureHandler:
    """Tests for mcp_failure_handler module."""

    def test_detect_failure_json_decode_error(self, tmp_path: Path) -> None:
        """Test detecting JSON decode error as failure."""
        import json

        from cortex.core.mcp_failure_handler import MCPToolFailureHandler

        # Arrange
        (tmp_path / ".cortex").mkdir()
        handler = MCPToolFailureHandler(tmp_path)
        error = json.JSONDecodeError("Expecting value", "test", 0)

        # Act
        is_failure = handler.detect_failure(error, "test_tool", "test_step")

        # Assert
        assert is_failure is True

    def test_detect_failure_connection_reset(self, tmp_path: Path) -> None:
        """Test detecting connection reset as failure."""
        from cortex.core.mcp_failure_handler import MCPToolFailureHandler

        # Arrange
        (tmp_path / ".cortex").mkdir()
        handler = MCPToolFailureHandler(tmp_path)
        error = ConnectionError("Connection reset by peer")

        # Act
        is_failure = handler.detect_failure(error, "test_tool", "test_step")

        # Assert
        assert is_failure is True

    def test_detect_failure_normal_value_error(self, tmp_path: Path) -> None:
        """Test that normal ValueError is not detected as failure."""
        from cortex.core.mcp_failure_handler import MCPToolFailureHandler

        # Arrange
        (tmp_path / ".cortex").mkdir()
        handler = MCPToolFailureHandler(tmp_path)
        # A normal value error without JSON/parsing keywords
        error = ValueError("Budget must be positive")

        # Act
        is_failure = handler.detect_failure(error, "test_tool", "test_step")

        # Assert
        assert is_failure is False

    def test_mcp_tool_failure_exception(self) -> None:
        """Test MCPToolFailure exception."""
        from cortex.core.mcp_failure_handler import MCPToolFailure

        # Act
        exc = MCPToolFailure(
            tool_name="test_tool",
            error=RuntimeError("Test error"),
            step_name="test_step",
        )

        # Assert
        assert exc.tool_name == "test_tool"
        assert exc.step_name == "test_step"
        assert "test_tool" in str(exc)

    def test_protocol_violation_exception(self) -> None:
        """Test ProtocolViolation exception."""
        from cortex.core.mcp_failure_handler import ProtocolViolation

        # Act
        exc = ProtocolViolation("Test violation")

        # Assert
        assert "Protocol violation" in str(exc)
        assert "Test violation" in str(exc)


class TestMCPStability:
    """Tests for mcp_stability module."""

    @pytest.mark.asyncio
    async def test_with_mcp_stability_success(self) -> None:
        """Test successful function execution with MCP stability."""
        from cortex.core.mcp_stability import with_mcp_stability

        # Arrange
        async def success_func() -> str:
            return "success"

        # Act
        result = await with_mcp_stability(success_func)

        # Assert
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_mcp_stability_timeout(self) -> None:
        """Test timeout handling with MCP stability."""
        # Arrange
        import asyncio

        from cortex.core.mcp_stability import with_mcp_stability

        async def slow_func() -> str:
            await asyncio.sleep(10)
            return "never reached"

        # Act & Assert
        with pytest.raises(TimeoutError):
            _ = await with_mcp_stability(slow_func, timeout=0.1)
