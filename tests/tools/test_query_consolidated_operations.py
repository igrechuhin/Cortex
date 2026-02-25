"""Tests for Phase 50 consolidated tools: query_memory_bank and query_usage."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.models import ResponseFormat
from cortex.managers.usage_models import ToolUsageEvent
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
async def test_query_usage_unused_response_structure() -> None:
    """query_usage(query_type=unused) returns JSON with required structure (Plan Step 7)."""
    payload = json.dumps(
        {
            "status": "success",
            "project_root": "/tmp/proj",
            "days": 30,
            "min_usage_count": 5,
            "unused_tools": ["tool_a", "tool_b"],
        },
        indent=2,
    )
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
    assert "unused_tools" in data
    assert isinstance(data["unused_tools"], list)
    assert data["unused_tools"] == ["tool_a", "tool_b"]
    assert "days" in data
    assert "min_usage_count" in data


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
async def test_query_usage_recommendations_response_structure() -> None:
    """query_usage(query_type=recommendations) returns JSON with required structure (Plan Step 7)."""
    payload = json.dumps(
        {
            "status": "success",
            "project_root": "/tmp/proj",
            "min_usage_threshold": 5,
            "days": 30,
            "low_usage_tools": ["deprecated_tool"],
            "message": "Tools with usage at or below threshold may be candidates for deprecation or consolidation.",
        },
        indent=2,
    )
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
    assert "low_usage_tools" in data
    assert isinstance(data["low_usage_tools"], list)
    assert data["low_usage_tools"] == ["deprecated_tool"]
    assert "min_usage_threshold" in data
    assert "days" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_query_usage_anomalies_unavailable() -> None:
    """query_usage with query_type=anomalies returns unavailable when tracker is None."""
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        with patch(
            "cortex.tools.query_usage_operations.log_client",
            new_callable=AsyncMock,
        ):
            result = await query_usage(
                query_type="anomalies",
                hours=24,
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "unavailable"
    assert data["session_window_hours"] == 24
    assert "message" in data


@pytest.mark.asyncio
async def test_query_usage_anomalies_success() -> None:
    """query_usage with query_type=anomalies returns tools_used and anomalies when tracker has events."""
    mock_events = [
        ToolUsageEvent(
            tool_name="manage_file",
            timestamp="2026-02-21T12:00:00Z",
            duration_ms=5.0,
            success=True,
            retry_count=0,
        ),
    ]
    mock_tracker = MagicMock()
    mock_tracker.search_usage = AsyncMock(return_value=mock_events)
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=mock_tracker,
        ),
    ):
        with patch(
            "cortex.tools.query_usage_operations.log_client",
            new_callable=AsyncMock,
        ):
            result = await query_usage(
                query_type="anomalies",
                hours=24,
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["session_window_hours"] == 24
    assert data["total_events"] == 1
    assert len(data["tools_used"]) == 1
    assert data["tools_used"][0]["tool_name"] == "manage_file"
    assert "high_retry_tools" in data
    assert "high_error_tools" in data


@pytest.mark.asyncio
async def test_query_usage_production_monitoring_unavailable() -> None:
    """query_usage with query_type=production_monitoring returns unavailable when tracker is None."""
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        with patch(
            "cortex.tools.query_usage_operations.log_client",
            new_callable=AsyncMock,
        ):
            result = await query_usage(
                query_type="production_monitoring",
                production_baseline_days=7,
                production_window_hours=24,
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "unavailable"
    assert data["baseline_days"] == 7
    assert data["current_window_hours"] == 24
    assert "message" in data


@pytest.mark.asyncio
async def test_query_usage_production_monitoring_success() -> None:
    """query_usage with query_type=production_monitoring returns success payload when tracker has events."""
    mock_tracker = MagicMock()
    mock_tracker.search_usage = AsyncMock(
        return_value=[
            ToolUsageEvent(
                tool_name="manage_file",
                timestamp="2026-02-21T12:00:00Z",
                duration_ms=5.0,
                success=True,
            ),
        ]
    )
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=mock_tracker,
        ),
    ):
        with patch(
            "cortex.tools.query_usage_operations.log_client",
            new_callable=AsyncMock,
        ):
            result = await query_usage(
                query_type="production_monitoring",
                production_baseline_days=7,
                production_window_hours=24,
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["baseline_days"] == 7
    assert data["current_window_hours"] == 24
    assert "metrics_current_global" in data
    assert "metrics_baseline_global" in data
    assert "drift_alerts" in data
    assert "weekly_summary_text" in data


@pytest.mark.asyncio
async def test_query_usage_token_efficiency_unavailable() -> None:
    """query_usage with query_type=token_efficiency returns unavailable when tracker is None."""
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        with patch(
            "cortex.tools.query_usage_operations.log_client",
            new_callable=AsyncMock,
        ):
            result = await query_usage(
                query_type="token_efficiency",
                days=30,
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "unavailable"
    assert data["days"] == 30
    assert "message" in data


@pytest.mark.asyncio
async def test_query_usage_token_efficiency_success() -> None:
    """query_usage with query_type=token_efficiency returns success with top tools when data exists."""
    mock_tracker = MagicMock()
    mock_tracker.search_usage = AsyncMock(
        return_value=[
            ToolUsageEvent(
                tool_name="load_context",
                timestamp="2026-02-21T12:00:00Z",
                duration_ms=100.0,
                success=True,
                response_tokens=3000,
            ),
        ]
    )
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=mock_tracker,
        ),
    ):
        with patch(
            "cortex.tools.query_usage_operations.log_client",
            new_callable=AsyncMock,
        ):
            result = await query_usage(
                query_type="token_efficiency",
                days=30,
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["days"] == 30
    assert data["event_count_with_tokens"] == 1
    assert "top_by_total" in data
    assert "top_by_avg" in data
    assert len(data["top_by_total"]) == 1
    assert data["top_by_total"][0]["tool_name"] == "load_context"
    assert data["top_by_total"][0]["total_response_tokens"] == 3000
    assert "optimization_recommendations" in data
    assert any("load_context" in r for r in data["optimization_recommendations"])


@pytest.mark.asyncio
async def test_query_usage_tool_classification_unavailable() -> None:
    """query_usage with query_type=tool_classification returns unavailable when tracker is None."""
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        with patch(
            "cortex.tools.query_usage_operations.log_client",
            new_callable=AsyncMock,
        ):
            result = await query_usage(
                query_type="tool_classification",
                days=30,
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "unavailable"
    assert "message" in data


@pytest.mark.asyncio
async def test_query_usage_tool_classification_success() -> None:
    """query_usage with query_type=tool_classification returns tools by usage with category."""
    mock_tracker = MagicMock()
    mock_tracker.get_usage_stats = AsyncMock(
        return_value={
            "tools": [
                {"tool_name": "manage_file", "total_calls": 100},
                {"tool_name": "load_context", "total_calls": 50},
            ],
            "total_events": 150,
        }
    )
    with (
        patch(
            "cortex.core.project_root_resolver.resolve_project_root_async",
            new_callable=AsyncMock,
            return_value=Path("/tmp"),
        ),
        patch(
            "cortex.tools.usage_analytics._get_tracker",
            new_callable=AsyncMock,
            return_value=mock_tracker,
        ),
    ):
        with patch(
            "cortex.tools.query_usage_operations.log_client",
            new_callable=AsyncMock,
        ):
            result = await query_usage(
                query_type="tool_classification",
                days=30,
                ctx=None,
            )
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["project_root"] == "/tmp"
    assert data["days"] == 30
    assert data["total_tools"] == 2
    assert data["total_events"] == 150
    assert "by_category" in data
    assert "tools" in data
    tools = data["tools"]
    assert len(tools) == 2
    assert tools[0]["tool_name"] == "manage_file"
    assert tools[0]["total_calls"] == 100
    assert "category" in tools[0]
    assert "rationale" in tools[0]


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
    assert call_kwargs["response_format"] == ResponseFormat.CONCISE


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
    assert call_kwargs["response_format"] == ResponseFormat.DETAILED


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
    assert call_kwargs["response_format"] == ResponseFormat.CONCISE
