"""Tests for usage_analytics MCP tools and Phase 43 resources."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.usage_analytics import (
    build_usage_report_text,
    calls_key,
    get_optimization_recommendations,
    get_optimization_recommendations_resource,
    get_tool_usage_report,
    get_tool_usage_report_resource,
    get_tool_usage_stats,
    get_tool_usage_stats_resource,
    get_unused_tools,
    get_unused_tools_resource,
    get_usage_events,
    get_usage_observation,
    get_usage_observation_resource,
    get_usage_timeline,
    parse_date_range,
    search_usage,
)


@pytest.mark.asyncio
class TestUsageAnalyticsResources:
    """Tests for Phase 43 usage analytics resources (cortex://usage/...)."""

    async def test_get_tool_usage_stats_resource_returns_json(self) -> None:
        """get_tool_usage_stats_resource returns JSON (Phase 43)."""
        payload = json.dumps(
            {
                "status": "success",
                "project_root": "/tmp",
                "tools": [],
                "total_events": 0,
            },
            indent=2,
        )
        with patch(
            "cortex.tools.usage_analytics.get_tool_usage_stats",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result_str = await get_tool_usage_stats_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert "tools" in result
        assert "total_events" in result

    async def test_get_unused_tools_resource_returns_json(self) -> None:
        """get_unused_tools_resource returns JSON (Phase 43)."""
        payload = json.dumps(
            {
                "status": "success",
                "project_root": "/tmp",
                "days": 90,
                "min_usage_count": 0,
                "unused_tools": [],
            },
            indent=2,
        )
        with patch(
            "cortex.tools.usage_analytics.get_unused_tools",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result_str = await get_unused_tools_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["days"] == 90
        assert "unused_tools" in result

    async def test_get_tool_usage_report_resource_returns_json(
        self,
    ) -> None:
        """get_tool_usage_report_resource returns JSON (Phase 43)."""
        payload = json.dumps(
            {
                "status": "success",
                "project_root": "/tmp",
                "report": "# MCP Tool Usage Report\n\nPeriod: ...",
            },
            indent=2,
        )
        with patch(
            "cortex.tools.usage_analytics.get_tool_usage_report",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result_str = await get_tool_usage_report_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert "report" in result

    async def test_get_optimization_recommendations_resource_returns_json(
        self,
    ) -> None:
        """get_optimization_recommendations_resource returns JSON (Phase 43)."""
        payload = json.dumps(
            {
                "status": "success",
                "project_root": "/tmp",
                "min_usage_threshold": 5,
                "days": 90,
                "low_usage_tools": [],
                "message": "Tools with usage at or below threshold...",
            },
            indent=2,
        )
        with patch(
            "cortex.tools.usage_analytics.get_optimization_recommendations",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result_str = await get_optimization_recommendations_resource()
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["min_usage_threshold"] == 5
        assert "low_usage_tools" in result

    async def test_get_usage_observation_resource_returns_json(self) -> None:
        """get_usage_observation_resource returns JSON (Phase 43)."""
        payload = json.dumps(
            {
                "status": "success",
                "project_root": "/tmp",
                "event": {"id": "abc", "tool_name": "x"},
            },
            indent=2,
        )
        with patch(
            "cortex.tools.usage_analytics.get_usage_observation",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            result_str = await get_usage_observation_resource("abc")
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["event"]["id"] == "abc"


class TestParseDateRange:
    """Unit tests for _parse_date_range helper."""

    def test_default_days_when_both_none(self) -> None:
        """When start_date and end_date are None, uses default_days from now."""
        start, end = parse_date_range(None, None, default_days=30)
        assert end.tzinfo is not None
        assert (end - start).days == 30

    def test_valid_end_date_parsed(self) -> None:
        """Valid end_date string is parsed (ISO with Z)."""
        _, end = parse_date_range(None, "2025-01-15T00:00:00Z", default_days=365)
        assert end.year == 2025
        assert end.month == 1
        assert end.day == 15

    def test_valid_start_date_parsed(self) -> None:
        """Valid start_date string is parsed."""
        start, _ = parse_date_range("2024-06-01", None, default_days=365)
        assert start.year == 2024
        assert start.month == 6
        assert start.day == 1

    def test_invalid_date_falls_back_to_default(self) -> None:
        """Invalid date string leaves start/end as default."""
        start, end = parse_date_range("not-a-date", None, default_days=7)
        assert (end - start).days == 7

    def test_empty_string_start_date_ignored(self) -> None:
        """Empty string for start_date fails parse and keeps default range."""
        start, end = parse_date_range("", None, default_days=14)
        assert (end - start).days == 14

    def test_default_days_zero(self) -> None:
        """default_days=0 gives same start and end (same day)."""
        start, end = parse_date_range(None, None, default_days=0)
        assert (end - start).days == 0
        assert start.date() == end.date()


class TestCallsKeyAndBuildReport:
    """Unit tests for _calls_key and _build_usage_report_text."""

    def test_calls_key_descending(self) -> None:
        """_calls_key returns negative total_calls for descending sort."""
        assert calls_key({"total_calls": 10}) == -10
        assert calls_key({"total_calls": 0}) == 0

    def test_build_usage_report_text(self) -> None:
        """_build_usage_report_text produces markdown with tools and total."""
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 31, tzinfo=UTC)
        tools: list[dict[str, object]] = [
            {"tool_name": "a", "total_calls": 5, "avg_duration_ms": 10.5},
            {"tool_name": "b", "total_calls": 3, "avg_duration_ms": 20.0},
        ]
        text = build_usage_report_text(tools, start, end, total=8)
        assert "2025-01-01" in text
        assert "2025-01-31" in text
        assert "Total events: 8" in text
        assert "**a**" in text and "5 calls" in text
        assert "**b**" in text and "3 calls" in text

    def test_calls_key_missing_total_calls_returns_zero(self) -> None:
        """_calls_key with missing total_calls uses 0."""
        assert calls_key({}) == 0
        assert calls_key({"tool_name": "x"}) == 0

    def test_calls_key_float_total_calls(self) -> None:
        """_calls_key with float total_calls works."""
        assert calls_key({"total_calls": 10.7}) == -10

    def test_build_report_empty_tools_list(self) -> None:
        """_build_usage_report_text with empty tools list still has period and total."""
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 31, tzinfo=UTC)
        text = build_usage_report_text([], start, end, total=0)
        assert "2025-01-01" in text
        assert "Total events: 0" in text
        assert "By tool" in text

    def test_build_report_tool_missing_optional_fields(self) -> None:
        """_build_usage_report_text handles tool with missing total_calls/avg_duration_ms."""
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 31, tzinfo=UTC)
        tools: list[dict[str, object]] = [{"tool_name": "partial"}]
        text = build_usage_report_text(tools, start, end, total=1)
        assert "**partial**" in text
        assert "0 calls" in text
        assert "0.0 ms" in text


@pytest.mark.asyncio
class TestUsageAnalyticsToolsUnavailable:
    """When usage tracker is unavailable, tools return JSON unavailable."""

    async def test_get_tool_usage_stats_unavailable(self) -> None:
        """get_tool_usage_stats returns unavailable when tracker is None."""
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result_str = await get_tool_usage_stats(ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "unavailable"
        assert "message" in result

    async def test_get_unused_tools_unavailable(self) -> None:
        """get_unused_tools returns unavailable when tracker is None."""
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result_str = await get_unused_tools(ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "unavailable"

    async def test_get_tool_usage_report_unavailable(self) -> None:
        """get_tool_usage_report returns unavailable when tracker is None."""
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result_str = await get_tool_usage_report(ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "unavailable"

    async def test_get_optimization_recommendations_unavailable(self) -> None:
        """get_optimization_recommendations returns unavailable when tracker is None."""
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result_str = await get_optimization_recommendations(ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "unavailable"

    async def test_get_usage_observation_unavailable(self) -> None:
        """get_usage_observation returns unavailable when tracker is None."""
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result_str = await get_usage_observation(id="abc", ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "unavailable"

    async def test_get_usage_timeline_unavailable(self) -> None:
        """get_usage_timeline returns unavailable when tracker is None."""
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result_str = await get_usage_timeline(around_id="abc", ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "unavailable"

    async def test_search_usage_unavailable(self) -> None:
        """search_usage returns unavailable when tracker is None."""
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result_str = await search_usage(ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "unavailable"

    async def test_get_usage_events_unavailable(self) -> None:
        """get_usage_events returns unavailable when tracker is None."""
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result_str = await get_usage_events(ids=["e1"], ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "unavailable"


@pytest.mark.asyncio
class TestUsageAnalyticsToolsSuccess:
    """When usage tracker is available, tools return success JSON."""

    async def test_get_tool_usage_stats_success(self) -> None:
        """get_tool_usage_stats returns success and tools when tracker returns data."""
        mock_tracker = AsyncMock()
        mock_tracker.get_usage_stats = AsyncMock(
            return_value={
                "tools": [{"tool_name": "x", "total_calls": 1}],
                "total_events": 1,
            }
        )
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_tool_usage_stats(ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["project_root"] == "/tmp"
        assert "tools" in result
        assert result["total_events"] == 1

    async def test_get_unused_tools_success(self) -> None:
        """get_unused_tools returns success and unused_tools list."""
        mock_tracker = AsyncMock()
        mock_tracker.get_unused_tools = AsyncMock(return_value=[{"tool_name": "y"}])
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_unused_tools(days=90, min_usage_count=0, ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["days"] == 90
        assert result["unused_tools"] == [{"tool_name": "y"}]

    async def test_get_tool_usage_report_success(self) -> None:
        """get_tool_usage_report returns success with report and optional recommendations."""
        mock_tracker = AsyncMock()
        mock_tracker.get_usage_stats = AsyncMock(
            return_value={"tools": [], "total_events": 0}
        )
        mock_tracker.get_unused_tools = AsyncMock(return_value=[])
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_tool_usage_report(
                format="markdown", include_recommendations=True, ctx=None
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert "report" in result
        assert "recommendations" in result

    async def test_get_optimization_recommendations_success(self) -> None:
        """get_optimization_recommendations returns success with low_usage_tools."""
        mock_tracker = AsyncMock()
        mock_tracker.get_unused_tools = AsyncMock(
            return_value=[{"tool_name": "z", "total_calls": 2}]
        )
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_optimization_recommendations(
                min_usage_threshold=5, days=90, ctx=None
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["min_usage_threshold"] == 5
        assert result["days"] == 90
        assert len(result["low_usage_tools"]) == 1
        assert "message" in result

    async def test_get_usage_observation_success(self) -> None:
        """get_usage_observation returns success with event payload."""

        class FakeEvent:
            def __init__(self, data: dict[str, object]) -> None:
                self._data = data

            def model_dump(self) -> dict[str, object]:
                return self._data

        mock_tracker = AsyncMock()
        fake_event = FakeEvent(
            {"id": "abc", "tool_name": "x", "result_summary": "short summary"}
        )
        mock_tracker.get_event_by_id = AsyncMock(return_value=fake_event)
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_usage_observation(id="abc", ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["project_root"] == "/tmp"
        assert result["event"]["id"] == "abc"
        assert result["event"]["tool_name"] == "x"
        assert result["event"]["result_summary"] == "short summary"

    async def test_search_usage_success(self) -> None:
        """search_usage returns success with compact results."""

        class FakeEvent:
            def __init__(self, data: dict[str, object]) -> None:
                self.id = str(data.get("id", "e1"))
                self.tool_name = str(data.get("tool_name", "tool_x"))
                self.timestamp = str(data.get("timestamp", "2026-02-10T12:00:00+00:00"))
                dur_raw = data.get("duration_ms", 1.0)
                self.duration_ms = (
                    float(dur_raw) if isinstance(dur_raw, (int, float)) else 1.0
                )
                self.success = bool(data.get("success", True))
                self.error_type = data.get("error_type")
                self.handler_kind = str(data.get("handler_kind", "tool"))

        mock_tracker = AsyncMock()
        mock_tracker.search_usage = AsyncMock(
            return_value=[
                FakeEvent(
                    {
                        "id": "e1",
                        "tool_name": "manage_file",
                        "timestamp": "2026-02-10T12:00:00+00:00",
                        "duration_ms": 10.0,
                        "success": True,
                        "error_type": None,
                        "handler_kind": "tool",
                    }
                )
            ]
        )
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await search_usage(
                start_date=None,
                end_date=None,
                tool_name=None,
                success=None,
                limit=10,
                ctx=None,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["project_root"] == "/tmp"
        assert result["total"] == 1
        assert len(result["results"]) == 1
        entry = result["results"][0]
        assert entry["id"] == "e1"
        assert entry["tool_name"] == "manage_file"
        assert entry["success"] is True

    async def test_get_usage_observation_not_found(self) -> None:
        """get_usage_observation returns error when id is missing."""
        mock_tracker = AsyncMock()
        mock_tracker.get_event_by_id = AsyncMock(return_value=None)
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_usage_observation(id="missing", ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "error"
        assert result["error_type"] == "UsageEventNotFound"

    async def test_get_usage_events_success_with_missing_ids(self) -> None:
        """get_usage_events returns events and missing_ids for unknown IDs."""

        class FakeEvent:
            def __init__(self, data: dict[str, object]) -> None:
                self._data = data
                self.id = str(data.get("id", "e1"))

            def model_dump(self) -> dict[str, object]:
                return self._data

        mock_tracker = AsyncMock()
        fake = FakeEvent(
            {"id": "e1", "tool_name": "manage_file", "result_summary": "summary text"}
        )
        mock_tracker.get_events_by_ids = AsyncMock(return_value=[fake])
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_usage_events(ids=["e1", "missing"], ctx=None)
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["project_root"] == "/tmp"
        assert len(result["events"]) == 1
        assert result["events"][0]["id"] == "e1"
        assert result["events"][0]["result_summary"] == "summary text"
        assert "missing" in result["missing_ids"]

    async def test_get_usage_timeline_success(self) -> None:
        """get_usage_timeline returns success with compact timeline entries."""

        class FakeEvent:
            def __init__(self, data: dict[str, object]) -> None:
                self.id = str(data.get("id", "e1"))
                self.tool_name = str(data.get("tool_name", "tool_x"))
                self.timestamp = str(data.get("timestamp", "2026-02-10T12:00:00+00:00"))
                dur_raw = data.get("duration_ms", 1.0)
                self.duration_ms = (
                    float(dur_raw) if isinstance(dur_raw, (int, float)) else 1.0
                )
                self.success = bool(data.get("success", True))
                self.error_type = data.get("error_type")
                self.handler_kind = str(data.get("handler_kind", "tool"))

        mock_tracker = AsyncMock()
        mock_tracker.get_usage_timeline = AsyncMock(
            return_value=[
                FakeEvent(
                    {
                        "id": "e1",
                        "tool_name": "manage_file",
                        "timestamp": "2026-02-10T12:00:00+00:00",
                        "duration_ms": 10.0,
                        "success": True,
                        "error_type": None,
                        "handler_kind": "tool",
                    }
                )
            ]
        )
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_usage_timeline(
                around_id="e1",
                limit=10,
                ctx=None,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["project_root"] == "/tmp"
        assert result["around_id"] == "e1"
        assert result["total"] == 1
        assert len(result["results"]) == 1
        entry = result["results"][0]
        assert entry["id"] == "e1"
        assert entry["tool_name"] == "manage_file"
        assert entry["success"] is True

    async def test_get_usage_timeline_clamps_limit_bounds(self) -> None:
        """get_usage_timeline clamps limit to [1, 500] before calling tracker."""
        mock_tracker = AsyncMock()
        mock_tracker.get_usage_timeline = AsyncMock(return_value=[])
        with (
            patch(
                "cortex.tools.usage_analytics.resolve_project_root_async",
                new_callable=AsyncMock,
                return_value=Path("/tmp"),
            ),
            patch(
                "cortex.tools.usage_analytics._get_tracker",
                new_callable=AsyncMock,
                return_value=mock_tracker,
            ),
        ):
            result_str = await get_usage_timeline(
                around_id="e1",
                limit=0,
                ctx=None,
            )
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["total"] == 0
        mock_tracker.get_usage_timeline.assert_awaited_once_with(
            around_id="e1",
            limit=1,
        )
