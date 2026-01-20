"""
Unit tests for connection closure handling in mcp_stability.py.

Tests the enhanced connection closure detection, recovery, and retry logic.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import anyio
import pytest

from cortex.core.mcp_stability import (
    check_connection_health,
    with_mcp_stability,
)
from cortex.core.models import HealthMetrics


def _make_health_metrics(
    healthy: bool = True,
    concurrent_operations: int = 0,
    max_concurrent: int = 10,
    semaphore_available: int = 10,
    utilization_percent: float = 0.0,
    closure_count: int = 0,
    recovery_count: int = 0,
) -> HealthMetrics:
    """Create a HealthMetrics model for testing."""
    return HealthMetrics(
        healthy=healthy,
        concurrent_operations=concurrent_operations,
        max_concurrent=max_concurrent,
        semaphore_available=semaphore_available,
        utilization_percent=utilization_percent,
        closure_count=closure_count,
        recovery_count=recovery_count,
    )


class TestConnectionClosureHandling:
    """Tests for connection closure detection and recovery."""

    @pytest.mark.asyncio
    async def test_connection_health_check_before_execution(self) -> None:
        """Test that connection health is checked before tool execution."""

        # Arrange
        async def test_func() -> str:
            return "success"

        with (
            patch(
                "cortex.core.mcp_stability.check_connection_health",
                new_callable=AsyncMock,
                return_value=_make_health_metrics(healthy=False),
            ),
            pytest.raises(ConnectionError, match="Connection not healthy"),
        ):
            _ = await with_mcp_stability(test_func)

    @pytest.mark.asyncio
    async def test_connection_closure_detection(self) -> None:
        """Test that connection closure errors are detected."""

        # Arrange
        async def test_func() -> str:
            raise RuntimeError("MCP error -32000: Connection closed")

        with (
            patch(
                "cortex.core.mcp_stability.check_connection_health",
                new_callable=AsyncMock,
                return_value=_make_health_metrics(healthy=True),
            ),
            pytest.raises(ConnectionError, match="MCP connection failed"),
        ):
            _ = await with_mcp_stability(test_func)

    @pytest.mark.asyncio
    async def test_connection_recovery_on_retry(self) -> None:
        """Test that connection recovery works on retry."""
        # Arrange
        attempt_count = 0

        async def test_func() -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise RuntimeError("MCP error -32000: Connection closed")
            return "success"

        with patch(
            "cortex.core.mcp_stability.check_connection_health",
            new_callable=AsyncMock,
            side_effect=[
                _make_health_metrics(healthy=True),  # Initial check
                _make_health_metrics(healthy=True),  # Recovery check
            ],
        ):
            # Act
            result = await with_mcp_stability(test_func, timeout=10.0)

            # Assert
            assert result == "success"
            assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_broken_resource_error_connection_closure(self) -> None:
        """Test that BrokenResourceError is handled as connection closure."""

        # Arrange
        async def test_func() -> str:
            raise anyio.BrokenResourceError("Resource broken")

        with (
            patch(
                "cortex.core.mcp_stability.check_connection_health",
                new_callable=AsyncMock,
                return_value=_make_health_metrics(healthy=True),
            ),
            pytest.raises(ConnectionError, match="MCP connection failed"),
        ):
            _ = await with_mcp_stability(test_func)

    @pytest.mark.asyncio
    async def test_connection_closure_with_recovery(self) -> None:
        """Test connection closure with successful recovery."""
        # Arrange
        attempt_count = 0

        async def test_func() -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ConnectionError("Connection closed")
            return "success"

        with patch(
            "cortex.core.mcp_stability.check_connection_health",
            new_callable=AsyncMock,
            side_effect=[
                _make_health_metrics(healthy=True),  # Initial check
                _make_health_metrics(healthy=True),  # Recovery check
            ],
        ):
            # Act
            result = await with_mcp_stability(test_func, timeout=10.0)

            # Assert
            assert result == "success"
            assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_connection_closure_no_recovery(self) -> None:
        """Test connection closure when recovery is not possible."""

        # Arrange
        async def test_func() -> str:
            raise ConnectionError("Connection closed")

        with (
            patch(
                "cortex.core.mcp_stability.check_connection_health",
                new_callable=AsyncMock,
                side_effect=[
                    _make_health_metrics(healthy=True),  # Initial check
                    _make_health_metrics(healthy=False),  # Recovery check fails
                ],
            ),
            pytest.raises(ConnectionError, match="MCP connection failed"),
        ):
            _ = await with_mcp_stability(test_func, timeout=10.0)

    @pytest.mark.asyncio
    async def test_connection_health_check_includes_closure_metrics(self) -> None:
        """Test that connection health includes closure and recovery metrics."""
        # Act
        health = await check_connection_health()

        # Assert - use Pydantic model attribute access
        assert hasattr(health, "healthy")
        assert hasattr(health, "closure_count")
        assert hasattr(health, "recovery_count")
        assert isinstance(health.closure_count, int)
        assert isinstance(health.recovery_count, int)

    @pytest.mark.asyncio
    async def test_timeout_error_not_retried(self) -> None:
        """Test that timeout errors are not retried."""

        # Arrange
        async def test_func() -> str:
            raise TimeoutError("Operation timed out")

        with (
            patch(
                "cortex.core.mcp_stability.check_connection_health",
                new_callable=AsyncMock,
                return_value=_make_health_metrics(healthy=True),
            ),
            pytest.raises(asyncio.TimeoutError),
        ):
            _ = await with_mcp_stability(test_func, timeout=1.0)

    @pytest.mark.asyncio
    async def test_non_connection_error_not_retried(self) -> None:
        """Test that non-connection errors are not retried."""

        # Arrange
        async def test_func() -> str:
            raise ValueError("Invalid value")

        with (
            patch(
                "cortex.core.mcp_stability.check_connection_health",
                new_callable=AsyncMock,
                return_value=_make_health_metrics(healthy=True),
            ),
            pytest.raises(ValueError, match="Invalid value"),
        ):
            _ = await with_mcp_stability(test_func)

    @pytest.mark.asyncio
    async def test_connection_closure_keyword_detection(self) -> None:
        """Test that connection closure keywords are detected."""
        # Arrange
        from cortex.core.mcp_stability import (
            _is_connection_error,  # type: ignore[reportPrivateUsage]
        )

        # Test various connection closure error messages
        error_messages = [
            "MCP error -32000: Connection closed",
            "Connection closed",
            "connection reset",
            "broken pipe",
        ]

        for msg in error_messages:
            error = RuntimeError(msg)
            # Act
            result = _is_connection_error(error)
            # Assert
            assert result is True, f"Should detect connection error: {msg}"
