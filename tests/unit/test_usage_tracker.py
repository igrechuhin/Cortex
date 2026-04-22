"""Unit tests for UsageTracker (Phase 29)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from cortex.core.cache_json_access import read_cache_json
from cortex.core.cache_utils import get_cache_dir
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.core.synapse_usage_config import get_usage_storage_root
from cortex.managers.usage_models import ToolUsageEvent
from cortex.managers.usage_tracker import (
    UsageTracker,
    generate_usage_event_id,
    get_tool_optimization_config,
)
from cortex.managers.usage_tracker_events import persist_event


def _make_project_root(tmp_path: Path, usage_writable: bool = False) -> Path:
    """Create a project root with .cortex/.cache for usage storage.

    When usage_writable is True, adds .cortex/synapse/config.json so
    usage events are persisted. Default False = static snapshot (no writes).
    """
    root = tmp_path / "project"
    get_cache_dir(root).mkdir(parents=True)
    if usage_writable:
        synapse_dir = get_cortex_path(root, CortexResourceType.SYNAPSE)
        synapse_dir.mkdir(parents=True)
        _ = (synapse_dir / "config.json").write_text(
            '{"usage_writable": true}', encoding="utf-8"
        )
    return root


def _find_event_by_tool(
    raw_events: list[object], tool_name: str
) -> dict[str, object] | None:
    for entry in raw_events:
        if not isinstance(entry, dict):
            continue
        row = cast(dict[str, object], entry)
        if row.get("tool_name") == tool_name:
            return row
    return None


class TestUsageTrackerInitialization:
    """Test UsageTracker initialization."""

    def test_initialization_accepts_root(self, tmp_path: Path) -> None:
        """Test tracker accepts project root."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        assert tracker is not None

    @pytest.mark.asyncio
    async def test_record_works_with_default_config(self, tmp_path: Path) -> None:
        """Test recording works when usage_writable true and config minimal."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("test_tool", 1.0, True)
        result = await tracker.get_usage_stats()
        total_ev = result.get("total_events", 0)
        assert isinstance(total_ev, (int, float)) and total_ev >= 1


class TestGetToolOptimizationConfig:
    """Tests for get_tool_optimization_config (Step 6 single source of truth)."""

    def test_returns_defaults_when_config_missing(self, tmp_path: Path) -> None:
        """When usage_tracking.json is missing, returns default days/count/threshold."""
        root = _make_project_root(tmp_path)
        config = get_tool_optimization_config(root)
        assert config["days"] == 30
        assert config["min_usage_count"] == 0
        assert config["min_usage_threshold"] == 5

    def test_returns_defaults_when_tool_optimization_section_missing(
        self, tmp_path: Path
    ) -> None:
        """When file exists but tool_optimization key is missing, returns defaults."""
        root = _make_project_root(tmp_path)
        config_dir = get_cortex_path(root, CortexResourceType.CONFIG)
        config_dir.mkdir(parents=True)
        _ = (config_dir / "usage_tracking.json").write_text(
            '{"enabled": true, "retention_days": 60}', encoding="utf-8"
        )
        config = get_tool_optimization_config(root)
        assert config["days"] == 30
        assert config["min_usage_count"] == 0
        assert config["min_usage_threshold"] == 5

    def test_returns_file_values_when_present(self, tmp_path: Path) -> None:
        """When tool_optimization is present, returns its values."""
        root = _make_project_root(tmp_path)
        config_dir = get_cortex_path(root, CortexResourceType.CONFIG)
        config_dir.mkdir(parents=True)
        _ = (config_dir / "usage_tracking.json").write_text(
            '{"tool_optimization": {"days": 60, "min_usage_count": 2, "min_usage_threshold": 10}}',
            encoding="utf-8",
        )
        config = get_tool_optimization_config(root)
        assert config["days"] == 60
        assert config["min_usage_count"] == 2
        assert config["min_usage_threshold"] == 10

    def test_merges_partial_tool_optimization_with_defaults(
        self, tmp_path: Path
    ) -> None:
        """When only some keys are present, the rest use defaults."""
        root = _make_project_root(tmp_path)
        config_dir = get_cortex_path(root, CortexResourceType.CONFIG)
        config_dir.mkdir(parents=True)
        _ = (config_dir / "usage_tracking.json").write_text(
            '{"tool_optimization": {"days": 30}}',
            encoding="utf-8",
        )
        config = get_tool_optimization_config(root)
        assert config["days"] == 30
        assert config["min_usage_count"] == 0
        assert config["min_usage_threshold"] == 5


class TestRecordToolUsage:
    """Test record_tool_usage."""

    @pytest.mark.asyncio
    async def test_record_does_not_persist_when_usage_writable_false(
        self, tmp_path: Path
    ) -> None:
        """When usage_writable is false (static snapshot), no events are persisted."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("test_tool", 1.0, True)
        result = await tracker.get_usage_stats()
        assert result.get("total_events", 0) == 0

    @pytest.mark.asyncio
    async def test_record_does_not_persist_when_synapse_exists_and_config_missing(
        self, tmp_path: Path
    ) -> None:
        """When .cortex/synapse exists but config.json missing, writes stay disabled."""
        root = tmp_path / "project"
        get_cache_dir(root).mkdir(parents=True)
        get_cortex_path(root, CortexResourceType.SYNAPSE).mkdir(parents=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("test_tool", 1.0, True)
        result = await tracker.get_usage_stats()
        assert result.get("total_events", 0) == 0
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert raw in (None, [])
        assert storage_root == root / ".cortex" / ".cache"

    @pytest.mark.asyncio
    async def test_persist_event_short_circuits_when_usage_not_writable(
        self, tmp_path: Path
    ) -> None:
        """Direct persist_event calls are no-ops without explicit usage_writable opt-in."""
        root = _make_project_root(tmp_path)
        event = ToolUsageEvent(
            tool_name="test_tool",
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=1.0,
            success=True,
        )
        await persist_event(root, event)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(
            root,
            f"usage/events/{today}.json",
            cache_root=storage_root,
        )
        assert raw in (None, [])

    @pytest.mark.asyncio
    async def test_record_creates_event_file(self, tmp_path: Path) -> None:
        """Test recording creates events visible via get_usage_stats."""
        root = _make_project_root(tmp_path, usage_writable=True)
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
    async def test_record_persists_event_id(self, tmp_path: Path) -> None:
        """Recorded events include a stable id field in persisted JSON."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage(
            tool_name="with_id",
            duration_ms=5.0,
            success=True,
        )
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and raw
        first = raw[0]
        first_d = cast(dict[str, object], first) if isinstance(first, dict) else {}
        id_val = first_d.get("id")
        assert isinstance(id_val, str)
        assert id_val

    @pytest.mark.asyncio
    async def test_record_appends_to_existing_file(self, tmp_path: Path) -> None:
        """Test recording multiple events aggregates correctly."""
        root = _make_project_root(tmp_path, usage_writable=True)
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

    @pytest.mark.asyncio
    async def test_record_with_response_tokens(self, tmp_path: Path) -> None:
        """Test recording with response_tokens (Phase 62 token-efficiency tracking)."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage(
            tool_name="load_context",
            duration_ms=10.0,
            success=True,
            response_tokens=2048,
        )
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and raw
        first = raw[0]
        first_d = cast(dict[str, object], first) if isinstance(first, dict) else {}
        assert first_d.get("response_tokens") == 2048

    @pytest.mark.asyncio
    async def test_record_phase57_retry_and_validation_fields(
        self, tmp_path: Path
    ) -> None:
        """Test Phase 57 retry_count is persisted."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage(
            tool_name="test_tool",
            duration_ms=1.0,
            success=True,
            retry_count=2,
            param_validation_failure=None,
        )
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and raw
        first = _find_event_by_tool(raw, "test_tool")
        assert first is not None
        assert first.get("retry_count") == 2
        assert first.get("param_validation_failure") is None

    @pytest.mark.asyncio
    async def test_record_phase57_validation_failure_field(
        self, tmp_path: Path
    ) -> None:
        """Test Phase 57 param_validation_failure is persisted for failed events."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage(
            tool_name="other_tool",
            duration_ms=1.0,
            success=False,
            error_type="ValidationError",
            param_validation_failure="task_description: required",
        )
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw2 = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw2, list) and raw2
        other_event = _find_event_by_tool(raw2, "other_tool")
        assert other_event is not None
        assert (
            other_event.get("param_validation_failure") == "task_description: required"
        )


class TestResultSummaryPersistence:
    """Tests for result_summary field persistence."""

    @pytest.mark.asyncio
    async def test_result_summary_persisted_when_enabled(self, tmp_path: Path) -> None:
        """result_summary is persisted when tool is enabled in config."""
        import json

        root = _make_project_root(tmp_path, usage_writable=True)
        config_dir = get_cortex_path(root, CortexResourceType.CONFIG)
        config_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = config_dir / "usage_tracking.json"
        _ = cfg_path.write_text(
            json.dumps(
                {
                    "result_summary_enabled_tools": ["summary_tool"],
                }
            ),
            encoding="utf-8",
        )
        tracker = UsageTracker(root)
        await tracker.record_tool_usage(
            tool_name="summary_tool",
            duration_ms=1.0,
            success=True,
            result_summary="Completed run",
        )
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and raw
        first = raw[0]
        first_d = cast(dict[str, object], first) if isinstance(first, dict) else {}
        assert first_d.get("result_summary") == "Completed run"

    @pytest.mark.asyncio
    async def test_result_summary_omitted_when_not_enabled(
        self,
        tmp_path: Path,
    ) -> None:
        """result_summary is not stored when tool is not enabled in config."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage(
            tool_name="other_tool",
            duration_ms=1.0,
            success=True,
            result_summary="Should not persist",
        )
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and raw
        first = raw[0]
        first_d = cast(dict[str, object], first) if isinstance(first, dict) else {}
        # When the tool is not enabled for summaries, the stored value is None.
        assert first_d.get("result_summary") is None


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
        root = _make_project_root(tmp_path, usage_writable=True)
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


class TestBackfillIdsForExistingEvents:
    """Test ID backfill for events stored without id field."""

    def test_backfill_assigns_stable_ids(self) -> None:
        """Existing events without id receive stable, deterministic IDs."""
        legacy_event: dict[str, object] = {
            "tool_name": "legacy_tool",
            "timestamp": "2026-02-01T12:00:00+00:00",
            "duration_ms": 1.0,
            "success": True,
            "error_type": None,
            "params_hash": None,
            "handler_kind": "tool",
        }
        first_id = generate_usage_event_id(legacy_event)
        assert isinstance(first_id, str)
        assert first_id

        second_id = generate_usage_event_id(legacy_event)
        assert second_id == first_id


class TestGetUnusedTools:
    """Test get_unused_tools."""

    @pytest.mark.asyncio
    async def test_get_unused_tools_empty_when_no_events(self, tmp_path: Path) -> None:
        """Test get_unused_tools returns empty list when no events."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        unused = await tracker.get_unused_tools(days=30, min_usage_count=0)
        assert unused == []

    @pytest.mark.asyncio
    async def test_get_unused_tools_filters_low_usage(self, tmp_path: Path) -> None:
        """Test get_unused_tools returns tools at or below threshold."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("manage_file", 1.0, True)
        await tracker.record_tool_usage("manage_file", 1.0, True)
        await tracker.record_tool_usage("load_context", 1.0, True)
        end = datetime.now(UTC)
        start = end - timedelta(days=30)
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
        unused = await tracker.get_unused_tools(days=30, min_usage_count=5)
        assert "manage_file" in unused
        assert "load_context" in unused
        unused_threshold_2 = await tracker.get_unused_tools(days=30, min_usage_count=2)
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
        root = _make_project_root(tmp_path, usage_writable=True)
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


class TestGetEventById:
    """Tests for UsageTracker.get_event_by_id."""

    @pytest.mark.asyncio
    async def test_get_event_by_id_returns_matching_event(
        self,
        tmp_path: Path,
    ) -> None:
        """get_event_by_id returns event when id exists."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("tool_a", 1.0, True)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and raw
        first = raw[0]
        first_d = cast(dict[str, object], first) if isinstance(first, dict) else {}
        event_id = str(first_d.get("id"))
        found = await tracker.get_event_by_id(event_id)
        assert found is not None
        assert found.id == event_id
        assert found.tool_name == "tool_a"

    @pytest.mark.asyncio
    async def test_get_event_by_id_returns_none_when_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """get_event_by_id returns None when id does not exist."""
        root = _make_project_root(tmp_path)
        tracker = UsageTracker(root)
        result = await tracker.get_event_by_id("non-existent-id")
        assert result is None


class TestGetEventsByIds:
    """Tests for UsageTracker.get_events_by_ids."""

    @pytest.mark.asyncio
    async def test_get_events_by_ids_returns_matching_events(
        self,
        tmp_path: Path,
    ) -> None:
        """get_events_by_ids returns all events matching provided IDs."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("tool_a", 1.0, True)
        await tracker.record_tool_usage("tool_b", 2.0, False, error_type="Err")
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and len(raw) >= 2
        first = cast(dict[str, object], raw[0])
        second = cast(dict[str, object], raw[1])
        id1 = str(first.get("id"))
        id2 = str(second.get("id"))
        events = await tracker.get_events_by_ids([id1, id2])
        ids = {e.id for e in events}
        assert id1 in ids
        assert id2 in ids

    @pytest.mark.asyncio
    async def test_get_events_by_ids_skips_missing_and_preserves_order(
        self,
        tmp_path: Path,
    ) -> None:
        """get_events_by_ids skips missing IDs and preserves requested order."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("tool_a", 1.0, True)
        await tracker.record_tool_usage("tool_b", 2.0, True)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and len(raw) >= 2
        first = cast(dict[str, object], raw[0])
        second = cast(dict[str, object], raw[1])
        id1 = str(first.get("id"))
        id2 = str(second.get("id"))
        order = [id2, "missing-id", id1]
        events = await tracker.get_events_by_ids(order)
        assert [e.id for e in events] == [id2, id1]


class TestSearchUsage:
    """Tests for UsageTracker.search_usage."""

    @pytest.mark.asyncio
    async def test_search_usage_limits_and_sorts_results(
        self,
        tmp_path: Path,
    ) -> None:
        """search_usage returns limited, time-sorted events."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("tool_a", 5.0, True)
        await tracker.record_tool_usage("tool_a", 10.0, False)
        await tracker.record_tool_usage("tool_b", 3.0, True)
        results = await tracker.search_usage(
            start_date=None,
            end_date=None,
            tool_name=None,
            success=None,
            limit=2,
        )
        assert len(results) == 2
        timestamps = [ev.timestamp for ev in results]
        assert timestamps[0] >= timestamps[1]

    @pytest.mark.asyncio
    async def test_search_usage_filters_by_tool_and_success(
        self,
        tmp_path: Path,
    ) -> None:
        """search_usage filters events by tool_name and success flag."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("tool_a", 5.0, True)
        await tracker.record_tool_usage("tool_a", 10.0, False)
        await tracker.record_tool_usage("tool_b", 3.0, True)
        results = await tracker.search_usage(
            start_date=None,
            end_date=None,
            tool_name="tool_a",
            success=True,
            limit=10,
        )
        assert len(results) == 1
        ev = results[0]
        assert ev.tool_name == "tool_a"
        assert ev.success is True


class TestGetUsageTimelineBasic:
    """Tests for UsageTracker.get_usage_timeline."""

    @pytest.mark.asyncio
    async def test_get_usage_timeline_returns_events_around_id(
        self,
        tmp_path: Path,
    ) -> None:
        """get_usage_timeline returns sorted events including the center ID."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        # Record multiple events so we have context around a middle ID.
        await tracker.record_tool_usage("tool_a", 5.0, True)
        await tracker.record_tool_usage("tool_b", 10.0, False)
        await tracker.record_tool_usage("tool_c", 3.0, True)

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and len(raw) >= 3

        # Use the second event as the center of the timeline.
        middle = cast(dict[str, object], raw[1])
        center_id = str(middle.get("id"))

        events = await tracker.get_usage_timeline(around_id=center_id, limit=3)
        assert events
        assert len(events) <= 3
        assert any(ev.id == center_id for ev in events)

        timestamps = [ev.timestamp for ev in events]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_get_usage_timeline_returns_empty_for_missing_id(
        self,
        tmp_path: Path,
    ) -> None:
        """get_usage_timeline returns empty list when ID is not found."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("tool_a", 1.0, True)

        events = await tracker.get_usage_timeline(around_id="missing-id", limit=5)
        assert events == []

    @pytest.mark.asyncio
    async def test_get_usage_timeline_returns_empty_for_non_positive_limit(
        self,
        tmp_path: Path,
    ) -> None:
        """get_usage_timeline returns empty list when limit is non-positive."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("tool_a", 1.0, True)

        events_zero = await tracker.get_usage_timeline(around_id="any", limit=0)
        events_negative = await tracker.get_usage_timeline(around_id="any", limit=-1)
        assert events_zero == []
        assert events_negative == []

    @pytest.mark.asyncio
    async def test_search_usage_filters_by_query_keyword(
        self,
        tmp_path: Path,
    ) -> None:
        """search_usage filters events by keyword across basic text fields."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("alpha_tool", 5.0, True)
        await tracker.record_tool_usage(
            "beta_tool",
            10.0,
            False,
            error_type="CustomError",
        )
        await tracker.record_tool_usage("gamma_tool", 3.0, True)
        results = await tracker.search_usage(
            start_date=None,
            end_date=None,
            tool_name=None,
            success=None,
            limit=10,
            query="CustomError",
        )
        assert len(results) == 1
        event = results[0]
        assert event.tool_name == "beta_tool"
        assert event.error_type == "CustomError"


class TestGetUsageTimelineWindow:
    """Additional tests for UsageTracker.get_usage_timeline window behavior."""

    @pytest.mark.asyncio
    async def test_get_usage_timeline_returns_chronological_window(
        self,
        tmp_path: Path,
    ) -> None:
        """get_usage_timeline returns a chronological window around the id."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        # Record several events so we have context around a center event.
        for i in range(5):
            await tracker.record_tool_usage(f"tool_{i}", float(i + 1), True)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and len(raw) >= 5
        events = [
            cast(dict[str, object], item) for item in raw if isinstance(item, dict)
        ]
        center = events[2]
        center_id = str(center.get("id"))
        results = await tracker.get_usage_timeline(around_id=center_id, limit=3)
        assert 1 <= len(results) <= 3
        # Includes the center event.
        assert any(ev.id == center_id for ev in results)
        # Results are sorted chronologically by timestamp.
        timestamps = [ev.timestamp for ev in results]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_get_usage_timeline_missing_or_non_positive_limit(
        self,
        tmp_path: Path,
    ) -> None:
        """get_usage_timeline returns empty list for missing id or non-positive limit."""
        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        # No events yet: missing id yields empty list.
        result_no_events = await tracker.get_usage_timeline(
            around_id="missing",
            limit=5,
        )
        assert result_no_events == []
        # With events recorded, unknown id still yields empty list.
        await tracker.record_tool_usage("tool_x", 1.0, True)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        relative_key = f"usage/events/{today}.json"
        storage_root = get_usage_storage_root(root)
        raw = await read_cache_json(root, relative_key, cache_root=storage_root)
        assert isinstance(raw, list) and raw
        first = cast(dict[str, object], raw[0])
        existing_id = str(first.get("id"))
        missing_result = await tracker.get_usage_timeline(
            around_id="unknown-id",
            limit=5,
        )
        assert missing_result == []
        # Non-positive limit returns empty list even for existing id.
        zero_limit_result = await tracker.get_usage_timeline(
            around_id=existing_id,
            limit=0,
        )
        assert zero_limit_result == []


# ---------------------------------------------------------------------------
# Telemetry suppression during commit pipeline (Fix 1)
# ---------------------------------------------------------------------------


class TestTelemetrySuppressedDuringPipeline:
    @pytest.mark.asyncio
    async def test_record_skipped_when_pipeline_active(self, tmp_path: Path) -> None:
        """record_tool_usage is a no-op when commit pipeline dir exists."""
        from cortex.core.synapse_usage_config import get_usage_storage_root
        from cortex.tools.session.pipeline_handoff_io import (
            pipeline_dir,
            state_path,
        )

        root = _make_project_root(tmp_path, usage_writable=True)
        # Simulate an active pipeline by creating pipeline.json
        pdir = pipeline_dir(root, "commit")
        pdir.mkdir(parents=True, exist_ok=True)
        _ = state_path(pdir).write_text('{"started_at": "2026-01-01T00:00:00"}')

        tracker = UsageTracker(root)
        await tracker.record_tool_usage("my_tool", 50.0, True)

        storage_root = get_usage_storage_root(root)
        from datetime import UTC, datetime

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        events_file = storage_root / "usage" / "events" / f"{today}.json"
        assert not events_file.exists()

    @pytest.mark.asyncio
    async def test_record_proceeds_when_pipeline_inactive(self, tmp_path: Path) -> None:
        """record_tool_usage persists events when no pipeline dir exists."""
        from cortex.core.synapse_usage_config import get_usage_storage_root

        root = _make_project_root(tmp_path, usage_writable=True)
        tracker = UsageTracker(root)
        await tracker.record_tool_usage("my_tool", 50.0, True)

        storage_root = get_usage_storage_root(root)
        from datetime import UTC, datetime

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        events_file = storage_root / "usage" / "events" / f"{today}.json"
        assert events_file.exists()
