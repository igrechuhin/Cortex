"""Tests for query_memory_bank_operations module."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from cortex.core.context_logging import MCPContext
from cortex.tools import query_memory_bank_operations
from cortex.tools.query_memory_bank_operations import (
    QueryMemoryBankParams,
    query_memory_bank,
)


@pytest.mark.asyncio
async def test_query_memory_bank_version_history_without_file_name() -> None:
    """query_memory_bank returns error when file_name is None for version_history."""
    result_str = await query_memory_bank(
        query_type="version_history",
        file_name=None,
        ctx=None,
    )
    result = json.loads(result_str)
    assert result["status"] == "error"
    assert "file_name is required" in result["error"]


@pytest.mark.asyncio
async def test_query_memory_bank_parse_links_without_file_name() -> None:
    """query_memory_bank returns error when file_name is None for parse_links."""
    result_str = await query_memory_bank(
        query_type="parse_links",
        file_name=None,
        ctx=None,
    )
    result = json.loads(result_str)
    assert result["status"] == "error"
    assert "file_name is required" in result["error"]


@pytest.mark.asyncio
async def test_query_memory_bank_resolve_transclusions_without_file_name() -> None:
    """query_memory_bank returns error when file_name is None for resolve_transclusions."""
    result_str = await query_memory_bank(
        query_type="resolve_transclusions",
        file_name=None,
        ctx=None,
    )
    result = json.loads(result_str)
    assert result["status"] == "error"
    assert "file_name is required" in result["error"]


@pytest.mark.asyncio
async def test_query_memory_bank_dependency_graph() -> None:
    """query_memory_bank calls dependency_graph handler."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        return '{"status": "success", "graph": {}}'

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS[  # type: ignore[reportPrivateUsage]
        "dependency_graph"
    ]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["dependency_graph"] = (  # type: ignore[reportPrivateUsage]
        mock_handler
    )
    try:
        result_str = await query_memory_bank(
            query_type="dependency_graph",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "success"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["dependency_graph"] = (  # type: ignore[reportPrivateUsage]
            original_handler
        )


@pytest.mark.asyncio
async def test_query_memory_bank_link_graph() -> None:
    """query_memory_bank calls link_graph handler."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        return '{"status": "success", "graph": {}}'

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS["link_graph"]  # type: ignore[reportPrivateUsage]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["link_graph"] = mock_handler  # type: ignore[reportPrivateUsage]
    try:
        result_str = await query_memory_bank(
            query_type="link_graph",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "success"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["link_graph"] = (  # type: ignore[reportPrivateUsage]
            original_handler
        )


@pytest.mark.asyncio
async def test_query_memory_bank_validate_links() -> None:
    """query_memory_bank calls validate_links handler."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        return '{"status": "success", "valid": true}'

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS[  # type: ignore[reportPrivateUsage]
        "validate_links"
    ]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["validate_links"] = mock_handler  # type: ignore[reportPrivateUsage]
    try:
        result_str = await query_memory_bank(
            query_type="validate_links",
            file_name="test.md",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "success"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["validate_links"] = (  # type: ignore[reportPrivateUsage]
            original_handler
        )


@pytest.mark.asyncio
async def test_query_memory_bank_unknown_query_type() -> None:
    """query_memory_bank returns error for unknown query_type."""
    result_str = await query_memory_bank(
        query_type="unknown_type",
        ctx=None,
    )
    result = json.loads(result_str)
    assert result["status"] == "error"
    assert "Unknown query_type" in result["error"]


@pytest.mark.asyncio
async def test_query_memory_bank_handler_exception() -> None:
    """query_memory_bank catches and returns handler exceptions as JSON."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        raise ValueError("Test error")

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"]  # type: ignore[reportPrivateUsage]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"] = mock_handler  # type: ignore[reportPrivateUsage]
    try:
        result_str = await query_memory_bank(
            query_type="stats",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert result["error"] == "Test error"
        assert result["error_type"] == "ValueError"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"] = original_handler  # type: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_query_memory_bank_logs_to_context() -> None:
    """query_memory_bank logs to context when provided."""
    mock_ctx: MCPContext = AsyncMock()

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        return '{"status": "success"}'

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"]  # type: ignore[reportPrivateUsage]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"] = mock_handler  # type: ignore[reportPrivateUsage]

    with patch("cortex.tools.query_memory_bank_operations.log_client") as mock_log:
        await query_memory_bank(
            query_type="stats",
            ctx=mock_ctx,
        )
        mock_log.assert_called_once()
        call_args = mock_log.call_args[0]
        assert call_args[0] == mock_ctx
        assert call_args[1] == "info"
        assert "query_memory_bank" in call_args[2]

    query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"] = original_handler  # type: ignore[reportPrivateUsage]
