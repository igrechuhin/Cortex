"""
Unit tests for connection_health.py MCP tool.

Tests the check_mcp_connection_health tool which monitors
MCP connection health and resource utilization.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.connection_health import check_mcp_connection_health


class TestCheckMCPConnectionHealth:
    """Tests for check_mcp_connection_health tool."""

    @pytest.mark.asyncio
    async def test_check_connection_health_success(self) -> None:
        """Test successful connection health check."""
        # Arrange
        expected_health = {
            "healthy": True,
            "concurrent_operations": 2,
            "max_concurrent": 5,
            "semaphore_available": 3,
            "utilization_percent": 40.0,
        }

        with patch(
            "cortex.tools.connection_health.check_connection_health",
            new_callable=AsyncMock,
            return_value=expected_health,
        ):
            # Act
            result_str = await check_mcp_connection_health()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "health" in result
            assert result["health"] == expected_health
            assert result["health"]["healthy"] is True
            assert result["health"]["concurrent_operations"] == 2
            assert result["health"]["max_concurrent"] == 5
            assert result["health"]["semaphore_available"] == 3
            assert result["health"]["utilization_percent"] == 40.0

    @pytest.mark.asyncio
    async def test_check_connection_health_error(self) -> None:
        """Test connection health check with error."""
        # Arrange
        error_message = "Connection failed"
        test_exception = RuntimeError(error_message)

        with patch(
            "cortex.tools.connection_health.check_connection_health",
            new_callable=AsyncMock,
            side_effect=test_exception,
        ):
            # Act
            result_str = await check_mcp_connection_health()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "error" in result
            assert result["error"] == error_message
            assert result["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_check_connection_health_value_error(self) -> None:
        """Test connection health check with ValueError."""
        # Arrange
        error_message = "Invalid value"
        test_exception = ValueError(error_message)

        with patch(
            "cortex.tools.connection_health.check_connection_health",
            new_callable=AsyncMock,
            side_effect=test_exception,
        ):
            # Act
            result_str = await check_mcp_connection_health()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert result["error"] == error_message
            assert result["error_type"] == "ValueError"
