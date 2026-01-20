"""Unit tests for MCP tool timeout behavior.

Tests verify that:
- Timeout wrappers enforce timeouts correctly
- Tools complete successfully within timeout limits
- Timeout errors are clear and actionable
- Different timeout categories work correctly
"""

import asyncio

import pytest

from cortex.core.constants import (
    MCP_TOOL_TIMEOUT_COMPLEX,
    MCP_TOOL_TIMEOUT_EXTERNAL,
    MCP_TOOL_TIMEOUT_FAST,
    MCP_TOOL_TIMEOUT_MEDIUM,
    MCP_TOOL_TIMEOUT_VERY_COMPLEX,
)
from cortex.core.mcp_stability import mcp_tool_wrapper, with_mcp_stability


async def fast_operation() -> str:
    """Fast operation that completes quickly."""
    await asyncio.sleep(0.1)
    return "success"


async def slow_operation(delay: float) -> str:
    """Slow operation that takes specified delay."""
    await asyncio.sleep(delay)
    return "success"


class TestTimeoutEnforcement:
    """Test that timeout wrappers enforce timeouts correctly."""

    @pytest.mark.asyncio
    async def test_fast_operation_completes_within_timeout(self) -> None:
        """Test that fast operations complete successfully within timeout."""
        result = await with_mcp_stability(fast_operation, timeout=MCP_TOOL_TIMEOUT_FAST)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_slow_operation_times_out(self) -> None:
        """Test that slow operations timeout correctly."""
        timeout = 0.5
        with pytest.raises(TimeoutError, match="exceeded timeout"):
            _ = await with_mcp_stability(
                slow_operation, timeout=timeout, delay=timeout + 0.5
            )

    @pytest.mark.asyncio
    async def test_operation_completes_just_before_timeout(self) -> None:
        """Test that operations completing just before timeout succeed."""
        timeout = 1.0
        result = await with_mcp_stability(
            slow_operation, timeout=timeout, delay=timeout - 0.1
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_error_message_is_clear(self) -> None:
        """Test that timeout error messages are clear and actionable."""
        timeout = 0.5
        with pytest.raises(TimeoutError) as exc_info:
            _ = await with_mcp_stability(
                slow_operation, timeout=timeout, delay=timeout + 0.5
            )
        assert "exceeded timeout" in str(exc_info.value)
        assert str(timeout) in str(exc_info.value)


class TestTimeoutDecorator:
    """Test that @mcp_tool_wrapper decorator works correctly."""

    @pytest.mark.asyncio
    async def test_decorator_applies_timeout(self) -> None:
        """Test that decorator applies timeout protection."""

        @mcp_tool_wrapper(timeout=0.5)
        async def decorated_function() -> str:
            await asyncio.sleep(0.1)
            return "success"

        result = await decorated_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_enforces_timeout(self) -> None:
        """Test that decorator enforces timeout."""

        @mcp_tool_wrapper(timeout=0.5)
        async def decorated_function() -> str:
            await asyncio.sleep(1.0)
            return "success"

        with pytest.raises(TimeoutError):
            _ = await decorated_function()

    @pytest.mark.asyncio
    async def test_decorator_preserves_signature(self) -> None:
        """Test that decorator preserves function signature for FastMCP."""
        import inspect

        @mcp_tool_wrapper(timeout=1.0)
        async def decorated_function(
            arg1: str, arg2: int = 42, *, kwarg: bool = True
        ) -> str:
            return f"{arg1}-{arg2}-{kwarg}"

        sig = inspect.signature(decorated_function)
        params = list(sig.parameters.keys())
        assert "arg1" in params
        assert "arg2" in params
        assert "kwarg" in params
        assert sig.return_annotation is str


class TestTimeoutCategories:
    """Test that different timeout categories work correctly."""

    @pytest.mark.asyncio
    async def test_fast_timeout_category(self) -> None:
        """Test fast timeout category (60s)."""
        result = await with_mcp_stability(fast_operation, timeout=MCP_TOOL_TIMEOUT_FAST)
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_FAST == 60

    @pytest.mark.asyncio
    async def test_medium_timeout_category(self) -> None:
        """Test medium timeout category (120s)."""
        result = await with_mcp_stability(
            fast_operation, timeout=MCP_TOOL_TIMEOUT_MEDIUM
        )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_MEDIUM == 120

    @pytest.mark.asyncio
    async def test_complex_timeout_category(self) -> None:
        """Test complex timeout category (300s)."""
        result = await with_mcp_stability(
            fast_operation, timeout=MCP_TOOL_TIMEOUT_COMPLEX
        )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_COMPLEX == 300

    @pytest.mark.asyncio
    async def test_very_complex_timeout_category(self) -> None:
        """Test very complex timeout category (600s)."""
        result = await with_mcp_stability(
            fast_operation, timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX
        )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_VERY_COMPLEX == 600

    @pytest.mark.asyncio
    async def test_external_timeout_category(self) -> None:
        """Test external timeout category (120s)."""
        result = await with_mcp_stability(
            fast_operation, timeout=MCP_TOOL_TIMEOUT_EXTERNAL
        )
        assert result == "success"
        assert MCP_TOOL_TIMEOUT_EXTERNAL == 120


class TestTimeoutEdgeCases:
    """Test edge cases for timeout behavior."""

    @pytest.mark.asyncio
    async def test_very_fast_operation_does_not_timeout_prematurely(
        self,
    ) -> None:
        """Test that very fast operations don't timeout prematurely."""

        async def very_fast() -> str:
            return "instant"

        result = await with_mcp_stability(very_fast, timeout=MCP_TOOL_TIMEOUT_FAST)
        assert result == "instant"

    @pytest.mark.asyncio
    async def test_operation_exceeding_timeout_raises_error(self) -> None:
        """Test that operations exceeding timeout raise TimeoutError."""
        timeout = 0.1
        with pytest.raises(TimeoutError):
            _ = await with_mcp_stability(
                slow_operation, timeout=timeout, delay=timeout * 2
            )

    @pytest.mark.asyncio
    async def test_timeout_with_exception_handling(self) -> None:
        """Test that timeout errors are properly handled."""
        timeout = 0.1

        async def operation_that_raises() -> str:
            await asyncio.sleep(timeout * 2)
            raise ValueError("Should not reach here")

        with pytest.raises(TimeoutError):
            _ = await with_mcp_stability(operation_that_raises, timeout=timeout)
