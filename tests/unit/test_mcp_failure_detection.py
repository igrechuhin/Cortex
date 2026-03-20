"""Unit tests for MCP tool failure detection (mcp_failure_detection module).

Tests lock in classification behavior for check_json_error, check_connection_error,
and detect_failure with canned exceptions and optional ctx.
"""

from __future__ import annotations

import json

import pytest

from cortex.core.mcp_failure_detection import (
    check_connection_error,
    check_json_error,
    detect_failure,
)


class TestCheckJsonError:
    """Tests for JSON error classification."""

    @pytest.mark.asyncio
    async def test_json_decode_error_returns_true(self) -> None:
        error = json.JSONDecodeError("Expecting value", "", 0)
        result = await check_json_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_json_value_error_returns_true(self) -> None:
        error = ValueError("Invalid JSON encoding")
        result = await check_json_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_non_json_value_error_returns_false(self) -> None:
        error = ValueError("Validation failed: file not found")
        result = await check_json_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_other_exception_returns_false(self) -> None:
        error = TypeError("something else")
        result = await check_json_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is False


class TestCheckConnectionError:
    """Tests for connection error classification."""

    @pytest.mark.asyncio
    async def test_connection_error_with_keyword_returns_true(self) -> None:
        error = ConnectionError("Connection closed")
        result = await check_connection_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_broken_pipe_returns_true(self) -> None:
        error = BrokenPipeError("broken pipe")
        result = await check_connection_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_os_error_connection_reset_returns_true(self) -> None:
        error = OSError("connection reset by peer")
        result = await check_connection_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_connection_error_without_keyword_returns_false(self) -> None:
        # ConnectionError with message that has no keyword from list returns False
        error = ConnectionError("Something unrelated")
        result = await check_connection_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_value_error_returns_false(self) -> None:
        error = ValueError("not a connection error")
        result = await check_connection_error(
            error, str(error).lower(), "tool", "step", ctx=None
        )
        assert result is False


class TestDetectFailure:
    """Tests for detect_failure (full classification pipeline)."""

    @pytest.mark.asyncio
    async def test_detect_json_decode_error(self) -> None:
        error = json.JSONDecodeError("Expecting value", "", 0)
        assert await detect_failure(error, "t", "s", ctx=None) is True

    @pytest.mark.asyncio
    async def test_detect_connection_error(self) -> None:
        error = ConnectionError("Connection closed")
        assert await detect_failure(error, "t", "s", ctx=None) is True

    @pytest.mark.asyncio
    async def test_detect_type_error_unexpected(self) -> None:
        error = TypeError("Unexpected type received")
        assert await detect_failure(error, "t", "s", ctx=None) is True

    @pytest.mark.asyncio
    async def test_detect_fastmcp_in_message(self) -> None:
        error = RuntimeError("fastmcp internal error")
        assert await detect_failure(error, "t", "s", ctx=None) is True

    @pytest.mark.asyncio
    async def test_detect_mcp_error_in_message(self) -> None:
        error = RuntimeError("MCP error -32000")
        assert await detect_failure(error, "t", "s", ctx=None) is True

    @pytest.mark.asyncio
    async def test_ignore_validation_value_error(self) -> None:
        error = ValueError("Validation failed: file not found")
        assert await detect_failure(error, "t", "s", ctx=None) is False

    @pytest.mark.asyncio
    async def test_ignore_generic_runtime_error(self) -> None:
        error = RuntimeError("Some other failure")
        assert await detect_failure(error, "t", "s", ctx=None) is False
