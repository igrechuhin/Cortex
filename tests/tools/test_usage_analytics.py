"""Tests for usage_analytics MCP tools and Phase 43 resources."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from cortex.tools.usage_analytics import (
    get_optimization_recommendations_resource,
    get_tool_usage_report_resource,
    get_tool_usage_stats_resource,
    get_unused_tools_resource,
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
