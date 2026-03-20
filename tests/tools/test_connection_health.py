"""
Unit tests for connection_health.py MCP tool.

Tests the health_check tool which monitors
MCP connection health and resource utilization.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.models import ConnectionHealth
from cortex.tools.session.connection_health import (
    check_mcp_connection_health_resource,
    health_check,
)


def _patch_usage_context():
    """Patch so ensure_usage_context skips slow resolve_project_root + get_managers."""
    return patch(
        "cortex.core.mcp_stability_usage.get_current_managers",
        return_value={},
    )


@pytest.mark.timeout(10)
class TestHealthCheck:
    """Tests for health_check tool."""

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test successful connection health check."""
        # Arrange
        expected_health = ConnectionHealth(
            healthy=True,
            concurrent_operations=2,
            max_concurrent=5,
            semaphore_available=3,
            utilization_percent=40.0,
        )

        with (
            _patch_usage_context(),
            patch(
                "cortex.tools.connection_health.check_connection_health",
                new_callable=AsyncMock,
                return_value=expected_health,
            ),
        ):
            # Act
            result_str = await health_check()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "success"
            assert "health" in result
            health_data = result["health"]
            assert health_data["healthy"] is True
            assert health_data["concurrent_operations"] == 2
            assert health_data["max_concurrent"] == 5
            assert health_data["semaphore_available"] == 3
            assert health_data["utilization_percent"] == 40.0

    @pytest.mark.asyncio
    async def test_health_check_error(self) -> None:
        """Test connection health check with error."""
        # Arrange
        error_message = "Connection failed"
        test_exception = RuntimeError(error_message)

        with (
            _patch_usage_context(),
            patch(
                "cortex.tools.connection_health.check_connection_health",
                new_callable=AsyncMock,
                side_effect=test_exception,
            ),
        ):
            # Act
            result_str = await health_check()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert "error" in result
            assert result["error"] == error_message
            assert result["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_health_check_value_error(self) -> None:
        """Test connection health check with ValueError."""
        # Arrange
        error_message = "Invalid value"
        test_exception = ValueError(error_message)

        with (
            _patch_usage_context(),
            patch(
                "cortex.tools.connection_health.check_connection_health",
                new_callable=AsyncMock,
                side_effect=test_exception,
            ),
        ):
            # Act
            result_str = await health_check()
            result = json.loads(result_str)

            # Assert
            assert result["status"] == "error"
            assert result["error"] == error_message
            assert result["error_type"] == "ValueError"


@pytest.mark.asyncio
@pytest.mark.timeout(10)
class TestCheckMCPConnectionHealthResource:
    """Tests for check_mcp_connection_health_resource (Phase 43 cortex://health/connection)."""

    async def test_health_check_resource_returns_json(
        self,
    ) -> None:
        """check_mcp_connection_health_resource returns JSON (Phase 43)."""
        expected_health = ConnectionHealth(
            healthy=True,
            concurrent_operations=1,
            max_concurrent=5,
            semaphore_available=4,
            utilization_percent=20.0,
        )
        with (
            _patch_usage_context(),
            patch(
                "cortex.tools.connection_health.health_check",
                new_callable=AsyncMock,
                return_value=json.dumps(
                    {"status": "success", "health": expected_health.model_dump()},
                    indent=2,
                ),
            ),
        ):
            result_str = await check_mcp_connection_health_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["health"]["healthy"] is True
