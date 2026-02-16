"""Tests for Phase 50 consolidated tools: query_memory_bank and query_usage."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.query_memory_bank_operations import query_memory_bank
from cortex.tools.query_usage_operations import query_usage

# -----------------------------------------------------------------------------
# query_memory_bank
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_memory_bank_stats_dispatches() -> None:
    """query_memory_bank with query_type=stats calls get_memory_bank_stats."""
    with patch(
        "cortex.tools.query_memory_bank_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.phase1_foundation_stats.get_memory_bank_stats",
            new_callable=AsyncMock,
            return_value=json.dumps(
                {"status": "success", "total_files": 7, "total_tokens": 1000},
                indent=2,
            ),
        ):
            result = await query_memory_bank(
                query_type="stats",
                response_format="concise",
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["total_files"] == 7


@pytest.mark.asyncio
async def test_query_memory_bank_version_history_requires_file_name() -> None:
    """query_memory_bank with query_type=version_history and no file_name returns error."""
    with patch(
        "cortex.tools.query_memory_bank_operations.log_client",
        new_callable=AsyncMock,
    ):
        result = await query_memory_bank(
            query_type="version_history",
            file_name=None,
            ctx=None,
        )
    data = json.loads(result)
    assert data["status"] == "error"
    assert "file_name is required" in data["error"]


@pytest.mark.asyncio
async def test_query_memory_bank_unknown_type_returns_error() -> None:
    """query_memory_bank with unknown query_type returns error JSON."""
    with patch(
        "cortex.tools.query_memory_bank_operations.log_client",
        new_callable=AsyncMock,
    ):
        result = await query_memory_bank(query_type="invalid_type", ctx=None)
    data = json.loads(result)
    assert data["status"] == "error"
    assert "Unknown query_type" in data["error"]


# -----------------------------------------------------------------------------
# query_usage
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_usage_stats_dispatches() -> None:
    """query_usage with query_type=stats calls get_tool_usage_stats."""
    payload = json.dumps(
        {"status": "success", "project_root": "/tmp", "top_5_tools": []},
        indent=2,
    )
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_tool_usage_stats",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result = await query_usage(query_type="stats", ctx=None)
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_usage_observation_requires_observation_id() -> None:
    """query_usage with query_type=observation and no observation_id returns error."""
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        result = await query_usage(
            query_type="observation",
            observation_id=None,
            ctx=None,
        )
    data = json.loads(result)
    assert data["status"] == "error"
    assert "observation_id is required" in data["error"]


@pytest.mark.asyncio
async def test_query_usage_unknown_type_returns_error() -> None:
    """query_usage with unknown query_type returns error JSON."""
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        result = await query_usage(query_type="invalid_type", ctx=None)
    data = json.loads(result)
    assert data["status"] == "error"
    assert "Unknown query_type" in data["error"]


@pytest.mark.asyncio
async def test_query_usage_timeline_requires_around_id() -> None:
    """query_usage with query_type=timeline and no around_id returns error."""
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        result = await query_usage(
            query_type="timeline",
            around_id=None,
            ctx=None,
        )
    data = json.loads(result)
    assert data["status"] == "error"
    assert "around_id is required" in data["error"]


@pytest.mark.asyncio
async def test_query_usage_timeline_with_around_id_dispatches() -> None:
    """query_usage with query_type=timeline and around_id calls get_usage_timeline."""
    payload = json.dumps({"status": "success", "events": []}, indent=2)
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_usage_timeline",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result = await query_usage(
                query_type="timeline",
                around_id="evt-1",
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_usage_observation_with_id_dispatches() -> None:
    """query_usage with query_type=observation and observation_id calls get_usage_observation."""
    payload = json.dumps({"status": "success", "id": "obs-1"}, indent=2)
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_usage_observation",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result = await query_usage(
                query_type="observation",
                observation_id="obs-1",
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_usage_events_with_ids_dispatches() -> None:
    """query_usage with query_type=events and ids calls get_usage_events."""
    payload = json.dumps(
        {"status": "success", "events": []},
        indent=2,
    )
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_usage_events",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result = await query_usage(
                query_type="events",
                ids=["evt-1"],
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_usage_unused_dispatches() -> None:
    """query_usage with query_type=unused calls get_unused_tools."""
    payload = json.dumps({"status": "success", "unused": []}, indent=2)
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_unused_tools",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result = await query_usage(query_type="unused", ctx=None)
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_usage_search_dispatches() -> None:
    """query_usage with query_type=search calls search_usage."""
    payload = json.dumps({"status": "success", "matches": []}, indent=2)
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.search_usage",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result = await query_usage(
                query_type="search",
                query="test",
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_usage_report_dispatches() -> None:
    """query_usage with query_type=report calls get_tool_usage_report."""
    payload = json.dumps({"status": "success", "report": ""}, indent=2)
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_tool_usage_report",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result = await query_usage(query_type="report", ctx=None)
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_usage_recommendations_dispatches() -> None:
    """query_usage with query_type=recommendations calls get_optimization_recommendations."""
    payload = json.dumps({"status": "success", "recommendations": []}, indent=2)
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_optimization_recommendations",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result = await query_usage(
                query_type="recommendations",
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_usage_handler_exception_returns_error_json() -> None:
    """query_usage when handler raises returns error JSON."""
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_tool_usage_stats",
            new_callable=AsyncMock,
            side_effect=RuntimeError("backend unavailable"),
        ):
            result = await query_usage(query_type="stats", ctx=None)
    data = json.loads(result)
    assert data["status"] == "error"
    assert "backend unavailable" in data["error"]


@pytest.mark.asyncio
async def test_query_usage_stats_with_response_format_concise() -> None:
    """query_usage passes response_format=concise to stats handler."""
    payload = json.dumps(
        {"status": "success", "project_root": "/tmp", "top_5_tools": []},
        indent=2,
    )
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_tool_usage_stats",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_stats:
            result = await query_usage(
                query_type="stats",
                response_format="concise",
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"
    # Verify response_format was passed to handler
    call_kwargs = mock_stats.call_args[1]
    assert call_kwargs["response_format"] == "concise"


@pytest.mark.asyncio
async def test_query_usage_stats_with_response_format_detailed() -> None:
    """query_usage passes response_format=detailed to stats handler."""
    payload = json.dumps(
        {"status": "success", "project_root": "/tmp", "all_tools": []},
        indent=2,
    )
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.get_tool_usage_stats",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_stats:
            result = await query_usage(
                query_type="stats",
                response_format="detailed",
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"
    # Verify response_format was passed to handler
    call_kwargs = mock_stats.call_args[1]
    assert call_kwargs["response_format"] == "detailed"


@pytest.mark.asyncio
async def test_query_usage_search_with_response_format_concise() -> None:
    """query_usage passes response_format=concise to search handler."""
    payload = json.dumps({"status": "success", "matches": []}, indent=2)
    with patch(
        "cortex.tools.query_usage_operations.log_client",
        new_callable=AsyncMock,
    ):
        with patch(
            "cortex.tools.usage_analytics.search_usage",
            new_callable=AsyncMock,
            return_value=payload,
        ) as mock_search:
            result = await query_usage(
                query_type="search",
                query="test",
                response_format="concise",
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"
    # Verify response_format was passed to handler
    call_kwargs = mock_search.call_args[1]
    assert call_kwargs["response_format"] == "concise"
