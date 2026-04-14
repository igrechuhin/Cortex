"""Unit tests for FastMCP server middleware wiring."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import anyio
import mcp.types as mt
import pytest
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.tools.base import ToolResult

from cortex.server_middleware import (
    TOKEN_TO_BYTE_MULTIPLIER,
    DisconnectMiddleware,
    create_server_middleware,
    is_debug_logging_enabled,
)


@pytest.mark.asyncio
async def test_disconnect_middleware_absorbs_closed_resource_error() -> None:
    middleware = DisconnectMiddleware()
    context = cast(MiddlewareContext[object], SimpleNamespace(method="tools/call"))

    async def call_next(context: object) -> object:
        _ = context
        raise anyio.ClosedResourceError()

    result = await middleware.on_message(context=context, call_next=call_next)
    assert result is None


@pytest.mark.asyncio
async def test_disconnect_middleware_passes_through_success_result() -> None:
    middleware = DisconnectMiddleware()
    context = cast(MiddlewareContext[object], SimpleNamespace(method="tools/call"))
    expected = ToolResult(content="ok")

    async def call_next(context: object) -> object:
        _ = context
        return expected

    result = await middleware.on_message(context=context, call_next=call_next)
    assert result is expected


def test_is_debug_logging_enabled_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_DEBUG", "1")
    assert is_debug_logging_enabled() is True
    monkeypatch.delenv("CORTEX_DEBUG", raising=False)
    monkeypatch.setenv("CORTEX_MCP_LOG_LEVEL", "debug")
    assert is_debug_logging_enabled() is True
    monkeypatch.setenv("CORTEX_MCP_LOG_LEVEL", "info")
    assert is_debug_logging_enabled() is False


def test_create_server_middleware_uses_configured_response_limit(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / ".cortex" / "config"
    _ = config_dir.mkdir(parents=True, exist_ok=True)
    _ = (config_dir / "optimization.json").write_text(
        '{"enabled": true, "max_response_tokens": 1234}',
        encoding="utf-8",
    )

    middleware_stack = create_server_middleware(tmp_path)
    response_limiter = next(
        m for m in middleware_stack if isinstance(m, ResponseLimitingMiddleware)
    )
    assert response_limiter.max_size == 1234 * TOKEN_TO_BYTE_MULTIPLIER


@pytest.mark.asyncio
async def test_response_limiting_middleware_truncates_oversized_tool_result(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / ".cortex" / "config"
    _ = config_dir.mkdir(parents=True, exist_ok=True)
    _ = (config_dir / "optimization.json").write_text(
        '{"enabled": true, "max_response_tokens": 5}',
        encoding="utf-8",
    )

    middleware_stack = create_server_middleware(tmp_path)
    response_limiter = next(
        m for m in middleware_stack if isinstance(m, ResponseLimitingMiddleware)
    )

    context = cast(
        MiddlewareContext[mt.CallToolRequestParams],
        SimpleNamespace(message=SimpleNamespace(name="demo")),
    )

    async def call_next(context: object) -> ToolResult:
        _ = context
        return ToolResult(content="x" * 200)

    result = await response_limiter.on_call_tool(context, call_next)
    first = result.content[0]
    assert isinstance(first, mt.TextContent)
    assert len(first.text) < 200
    assert "Response truncated due to size limit" in first.text


def test_create_server_middleware_includes_logging_only_in_debug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CORTEX_DEBUG", raising=False)
    monkeypatch.delenv("CORTEX_MCP_LOG_LEVEL", raising=False)

    middleware_without_debug = create_server_middleware(tmp_path)
    assert not any(
        isinstance(item, LoggingMiddleware) for item in middleware_without_debug
    )

    monkeypatch.setenv("CORTEX_MCP_LOG_LEVEL", "debug")
    middleware_with_debug = create_server_middleware(tmp_path)
    assert any(isinstance(item, LoggingMiddleware) for item in middleware_with_debug)
