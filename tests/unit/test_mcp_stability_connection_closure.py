"""
Unit tests for connection closure handling in mcp_stability.py.

Tests the connection closure detection, retry logic, and error handling.
"""

import asyncio

import pytest

from cortex.core.mcp_stability import (
    check_connection_health,
    with_mcp_stability,
)


class TestConnectionClosureHandling:
    """Tests for connection closure detection and recovery."""

    @pytest.mark.asyncio
    async def test_successful_execution(self) -> None:
        """Test that successful execution returns result."""
        # Arrange
        async def test_func() -> str:
            return "success"

        # Act
        result = await with_mcp_stability(test_func, timeout=10.0)

        # Assert
        assert result == "success"

    @pytest.mark.asyncio
    async def test_connection_error_causes_retry(self) -> None:
        """Test that connection errors trigger retry logic."""
        # Arrange
        attempt_count = 0

        async def test_func() -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("Connection closed")
            return "success"

        # Act
        result = await with_mcp_stability(test_func, timeout=10.0)

        # Assert
        assert result == "success"
        assert attempt_count == 3  # Two failures, then success

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

        # Act
        result = await with_mcp_stability(test_func, timeout=10.0)

        # Assert
        assert result == "success"
        assert attempt_count == 2

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

        # Act
        result = await with_mcp_stability(test_func, timeout=10.0)

        # Assert
        assert result == "success"
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_connection_health_check_returns_health_dict(self) -> None:
        """Test that connection health returns expected health metrics dict."""
        # Act
        health = await check_connection_health()

        # Assert - check_connection_health returns dict with health metrics
        assert "healthy" in health
        assert "concurrent_operations" in health
        assert "max_concurrent" in health
        assert "semaphore_available" in health
        assert "utilization_percent" in health
        assert isinstance(health["healthy"], bool)
        assert isinstance(health["concurrent_operations"], int)
        assert isinstance(health["max_concurrent"], int)

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self) -> None:
        """Test that timeout errors from the stability layer are raised."""
        # Arrange
        async def test_func() -> str:
            await asyncio.sleep(10)  # Deliberately exceed timeout
            return "success"

        # Act & Assert - timeout protection raises TimeoutError
        with pytest.raises(TimeoutError, match="exceeded timeout"):
            _ = await with_mcp_stability(test_func, timeout=0.1)

    @pytest.mark.asyncio
    async def test_value_error_not_retried(self) -> None:
        """Test that ValueErrors are not retried."""
        # Arrange
        attempt_count = 0

        async def test_func() -> str:
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Invalid value")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid value"):
            _ = await with_mcp_stability(test_func)

        # Should not retry for ValueError
        assert attempt_count == 1

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

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self) -> None:
        """Test that max retries are exhausted on persistent connection errors."""
        # Arrange
        attempt_count = 0

        async def test_func() -> str:
            nonlocal attempt_count
            attempt_count += 1
            raise ConnectionError("Connection closed")

        # Act & Assert
        with pytest.raises(RuntimeError, match="MCP connection failed.*after 3 attempts"):
            _ = await with_mcp_stability(test_func, timeout=10.0)

        # Should have attempted 3 times (default retry count)
        assert attempt_count == 3
