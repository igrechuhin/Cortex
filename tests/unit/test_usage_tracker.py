"""Unit tests for UsageTracker (Phase 29)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from cortex.managers.usage_tracker import UsageTracker


def _make_project_root(tmp_path: Path) -> Path:
    """Create a project root with .cortex/.cache for usage storage."""
    root = tmp_path / "project"
    (root / ".cortex" / ".cache").mkdir(parents=True)
    return root


class TestUsageTrackerInitialization:
    """Test UsageTracker initialization."""

    def test_initialization_accepts_root(self, tmp_path: Path) -> None:
        """Test tracker accepts project root."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        assert tracker is not None

    @pytest.mark.asyncio
    async def test_record_works_with_default_config(self, tmp_path: Path) -> None:
        """Test recording works when .cortex/config/usage_tracking.json missing."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("test_tool", 1.0, True)
        result = await tracker.get_usage_stats()
        total_ev = result.get("total_events", 0)
        assert isinstance(total_ev, (int, float)) and total_ev >= 1


class TestRecordToolUsage:
    """Test record_tool_usage."""

    @pytest.mark.asyncio
    async def test_record_creates_event_file(self, tmp_path: Path) -> None:
        """Test recording creates events visible via get_usage_stats."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage(
            tool_name="manage_file",
            duration_ms=10.0,
            success=True,
        )
        result: dict[str, object] = await tracker.get_usage_stats()
        total_ev = result.get("total_events", 0)
        assert isinstance(total_ev, (int, float)) and total_ev >= 1
        tools_raw = result.get("tools", [])
        _raw = cast(list[object], tools_raw) if isinstance(tools_raw, list) else []
        tools_list: list[dict[str, object]] = [
            cast(dict[str, object], t) for t in _raw if isinstance(t, dict)
        ]
        tools: dict[str, dict[str, object]] = {
            str(t["tool_name"]): t for t in tools_list
        }
        assert "manage_file" in tools
        assert tools["manage_file"]["avg_duration_ms"] == 10.0
        assert tools["manage_file"]["successful_calls"] == 1

    @pytest.mark.asyncio
    async def test_record_appends_to_existing_file(self, tmp_path: Path) -> None:
        """Test recording multiple events aggregates correctly."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage(
            tool_name="manage_file",
            duration_ms=5.0,
            success=True,
        )
        await tracker.record_tool_usage(
            tool_name="load_context",
            duration_ms=20.0,
            success=False,
            error_type="ValueError",
        )
        result = await tracker.get_usage_stats()
        total_ev = result.get("total_events", 0)
        assert isinstance(total_ev, (int, float)) and total_ev >= 2
        tools_raw = result.get("tools", [])
        _raw = cast(list[object], tools_raw) if isinstance(tools_raw, list) else []
        tools_list = [cast(dict[str, object], t) for t in _raw if isinstance(t, dict)]
        tools = {str(t["tool_name"]): t for t in tools_list}
        assert "load_context" in tools
        err_types: object = tools["load_context"].get("error_types")
        err_dict: dict[str, object] = (
            cast(dict[str, object], err_types) if isinstance(err_types, dict) else {}
        )
        assert err_dict.get("ValueError") == 1


class TestGetUsageStats:
    """Test get_usage_stats."""

    @pytest.mark.asyncio
    async def test_get_usage_stats_empty_when_no_events(self, tmp_path: Path) -> None:
        """Test get_usage_stats returns empty tools when no events."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        result = await tracker.get_usage_stats()
        assert result.get("total_events", 0) == 0
        assert result.get("tools", []) == []

    @pytest.mark.asyncio
    async def test_get_usage_stats_aggregates_events(self, tmp_path: Path) -> None:
        """Test get_usage_stats aggregates recorded events."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("manage_file", 10.0, True)
        await tracker.record_tool_usage("manage_file", 20.0, True)
        await tracker.record_tool_usage("load_context", 5.0, False, error_type="Err")
        result = await tracker.get_usage_stats()
        assert result.get("total_events") == 3
        tools_raw = result.get("tools", [])
        _raw = cast(list[object], tools_raw) if isinstance(tools_raw, list) else []
        tools_list: list[dict[str, object]] = [
            cast(dict[str, object], t) for t in _raw if isinstance(t, dict)
        ]
        tools_dict: dict[str, dict[str, object]] = {
            str(t["tool_name"]): t for t in tools_list
        }
        assert "manage_file" in tools_dict
        assert tools_dict["manage_file"]["total_calls"] == 2
        assert tools_dict["manage_file"]["successful_calls"] == 2
        assert tools_dict["manage_file"]["avg_duration_ms"] == 15.0
        assert "load_context" in tools_dict
        assert tools_dict["load_context"]["failed_calls"] == 1
        err_ty: object = tools_dict["load_context"].get("error_types")
        err_d: dict[str, object] = (
            cast(dict[str, object], err_ty) if isinstance(err_ty, dict) else {}
        )
        assert err_d.get("Err") == 1


class TestGetUnusedTools:
    """Test get_unused_tools."""

    @pytest.mark.asyncio
    async def test_get_unused_tools_empty_when_no_events(self, tmp_path: Path) -> None:
        """Test get_unused_tools returns empty list when no events."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        unused = await tracker.get_unused_tools(days=90, min_usage_count=0)
        assert unused == []

    @pytest.mark.asyncio
    async def test_get_unused_tools_filters_low_usage(self, tmp_path: Path) -> None:
        """Test get_unused_tools returns tools at or below threshold."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("manage_file", 1.0, True)
        await tracker.record_tool_usage("manage_file", 1.0, True)
        await tracker.record_tool_usage("load_context", 1.0, True)
        end = datetime.now(UTC)
        start = end - timedelta(days=90)
        stats = await tracker.get_usage_stats(start_date=start, end_date=end)
        st_ev = stats.get("total_events", 0)
        assert isinstance(st_ev, (int, float)) and st_ev >= 3
        tools_list_raw: object = stats.get("tools") or []
        _raw = (
            cast(list[object], tools_list_raw)
            if isinstance(tools_list_raw, list)
            else []
        )
        tools_list: list[dict[str, object]] = [
            cast(dict[str, object], t) for t in _raw if isinstance(t, dict)
        ]
        assert len(tools_list) >= 2
        unused = await tracker.get_unused_tools(days=90, min_usage_count=5)
        assert "manage_file" in unused
        assert "load_context" in unused
        unused_threshold_2 = await tracker.get_unused_tools(days=90, min_usage_count=2)
        assert "manage_file" in unused_threshold_2
        assert "load_context" in unused_threshold_2


class TestAggregateEventsViaStats:
    """Test aggregation via get_usage_stats (public API)."""

    @pytest.mark.asyncio
    async def test_empty_events_yields_empty_tools(self, tmp_path: Path) -> None:
        """Test get_usage_stats with no events returns empty tools."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        result = await tracker.get_usage_stats()
        assert result.get("total_events", 0) == 0
        assert result.get("tools", []) == []

    @pytest.mark.asyncio
    async def test_single_event_stats(self, tmp_path: Path) -> None:
        """Test single event produces correct aggregated stats."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("single_tool", 10.0, True)
        result = await tracker.get_usage_stats()
        assert result.get("total_events") == 1
        tl_raw = result.get("tools", [])
        _raw = cast(list[object], tl_raw) if isinstance(tl_raw, list) else []
        tools_list: list[dict[str, object]] = [
            cast(dict[str, object], t) for t in _raw if isinstance(t, dict)
        ]
        assert len(tools_list) == 1
        assert tools_list[0]["tool_name"] == "single_tool"
        assert tools_list[0]["total_calls"] == 1
        assert tools_list[0]["avg_duration_ms"] == 10.0
