"""Tests for query_memory_bank_operations module."""

from __future__ import annotations

import json
from pathlib import Path
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


@pytest.mark.asyncio
async def test_query_memory_bank_version_history_with_file_name() -> None:
    """query_memory_bank calls version_history handler when file_name is provided."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        return '{"status": "success", "version_history": []}'

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS[  # type: ignore[reportPrivateUsage]
        "version_history"
    ]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["version_history"] = (  # type: ignore[reportPrivateUsage]
        mock_handler
    )
    try:
        result_str = await query_memory_bank(
            query_type="version_history",
            file_name="test.md",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "success"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["version_history"] = (  # type: ignore[reportPrivateUsage]
            original_handler
        )


@pytest.mark.asyncio
async def test_query_memory_bank_parse_links_with_file_name() -> None:
    """query_memory_bank calls parse_links handler when file_name is provided."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        return '{"status": "success", "links": []}'

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS[  # type: ignore[reportPrivateUsage]
        "parse_links"
    ]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["parse_links"] = (  # type: ignore[reportPrivateUsage]
        mock_handler
    )
    try:
        result_str = await query_memory_bank(
            query_type="parse_links",
            file_name="test.md",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "success"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["parse_links"] = (  # type: ignore[reportPrivateUsage]
            original_handler
        )


@pytest.mark.asyncio
async def test_query_memory_bank_resolve_transclusions_with_file_name() -> None:
    """query_memory_bank calls resolve_transclusions handler when file_name is provided."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        return '{"status": "success", "resolved": ""}'

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS[  # type: ignore[reportPrivateUsage]
        "resolve_transclusions"
    ]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["resolve_transclusions"] = (  # type: ignore[reportPrivateUsage]
        mock_handler
    )
    try:
        result_str = await query_memory_bank(
            query_type="resolve_transclusions",
            file_name="test.md",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "success"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["resolve_transclusions"] = (  # type: ignore[reportPrivateUsage]
            original_handler
        )


@pytest.mark.asyncio
async def test_query_memory_bank_stats_with_response_format_concise() -> None:
    """query_memory_bank passes response_format=concise to stats handler."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        assert params.response_format == "concise"
        return '{"status": "success", "total_files": 7, "total_tokens": 1000}'

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"]  # type: ignore[reportPrivateUsage]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"] = mock_handler  # type: ignore[reportPrivateUsage]
    try:
        result_str = await query_memory_bank(
            query_type="stats",
            response_format="concise",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "success"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"] = original_handler  # type: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_query_memory_bank_stats_with_response_format_detailed() -> None:
    """query_memory_bank passes response_format=detailed to stats handler."""

    async def mock_handler(
        params: QueryMemoryBankParams, ctx: MCPContext | None
    ) -> str:
        assert params.response_format == "detailed"
        return (
            '{"status": "success", "total_files": 7, "total_tokens": 1000, "files": []}'
        )

    original_handler = query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"]  # type: ignore[reportPrivateUsage]
    query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"] = mock_handler  # type: ignore[reportPrivateUsage]
    try:
        result_str = await query_memory_bank(
            query_type="stats",
            response_format="detailed",
            ctx=None,
        )
        result = json.loads(result_str)
        assert result["status"] == "success"
    finally:
        query_memory_bank_operations._MEMORY_BANK_HANDLERS["stats"] = original_handler  # type: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_query_memory_bank_stats_calls_real_handler(
    temp_project_root: Path, memory_bank_dir: Path
) -> None:
    """query_memory_bank calls real stats handler to cover import statements."""
    # Create a basic memory bank file to ensure stats handler can run
    test_file = memory_bank_dir / "projectBrief.md"
    _ = test_file.write_text("# Project Brief\n\nTest content.")

    # This test ensures the import statements inside handlers are covered
    with patch(
        "cortex.tools.query_memory_bank_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=temp_project_root,
        ):
            # Call without mocking the handler to execute imports
            result_str = await query_memory_bank(
                query_type="stats",
                response_format="concise",
                ctx=None,
            )
            result = json.loads(result_str)
            assert result["status"] == "success"
            assert "total_files" in result or "summary" in result
