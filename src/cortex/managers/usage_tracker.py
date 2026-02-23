"""Usage tracking manager for MCP tool analytics (Phase 29)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from cortex.core.cache_json_access import read_cache_json, read_modify_write_cache_json
from cortex.core.cache_utils import CacheType, get_cache_dir
from cortex.core.models import HandlerKind
from cortex.core.path_resolver import CortexResourceType, get_cortex_path
from cortex.managers.usage_models import ToolUsageEvent, ToolUsageStats


def _default_config() -> dict[str, bool | int | float | list[str]]:
    """Return default usage tracking configuration."""
    return {
        "enabled": True,
        "anonymize_params": True,
        "retention_days": 90,
        "aggregation_enabled": True,
        "opt_out_tools": [],
        "min_duration_ms": 0.0,
        "result_summary_enabled_tools": [],
    }


def _apply_config_overrides(
    config: dict[str, bool | int | float | list[str]],
    data: dict[str, object],
) -> None:
    """Merge persisted usage_tracking.json values into the default config."""
    for key in ("enabled", "anonymize_params", "aggregation_enabled"):
        val = data.get(key)
        if isinstance(val, bool):
            config[key] = val
    retention = data.get("retention_days")
    if isinstance(retention, int):
        config["retention_days"] = retention
    opt_out_raw = data.get("opt_out_tools")
    if isinstance(opt_out_raw, list):
        raw_list = cast(list[object], opt_out_raw)
        config["opt_out_tools"] = [s for s in raw_list if isinstance(s, str)]
    min_dur = data.get("min_duration_ms")
    if isinstance(min_dur, (int, float)):
        config["min_duration_ms"] = float(min_dur)
    summary_raw = data.get("result_summary_enabled_tools")
    if isinstance(summary_raw, list):
        raw_list = cast(list[object], summary_raw)
        config["result_summary_enabled_tools"] = [
            s for s in raw_list if isinstance(s, str)
        ]


def _load_config(project_root: Path) -> dict[str, bool | int | float | list[str]]:
    """Load usage tracking config from .cortex/config/usage_tracking.json."""
    import json

    config_dir = get_cortex_path(project_root, CortexResourceType.CONFIG)
    config_path = config_dir / "usage_tracking.json"
    if not config_path.is_file():
        return _default_config()
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        config = _default_config()
        if isinstance(data, dict):
            _apply_config_overrides(config, cast(dict[str, object], data))
        return config
    except (OSError, json.JSONDecodeError):
        return _default_config()


def get_tool_optimization_config(
    project_root: Path,
) -> dict[str, int]:
    """Load tool optimization threshold from .cortex/config/usage_tracking.json.

    Returns dict with keys days, min_usage_count, min_usage_threshold.
    Used as single source of truth for "tools below usage threshold" so the
    list can be tuned without code changes. Missing keys use defaults.
    """
    import json

    defaults: dict[str, int] = {
        "days": 30,
        "min_usage_count": 0,
        "min_usage_threshold": 5,
    }
    config_dir = get_cortex_path(project_root, CortexResourceType.CONFIG)
    config_path = config_dir / "usage_tracking.json"
    if not config_path.is_file():
        return defaults.copy()
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return defaults.copy()
        data_dict = cast(dict[str, object], data)
        section = data_dict.get("tool_optimization")
        if not isinstance(section, dict):
            return defaults.copy()
        section_dict = cast(dict[str, object], section)
        out = defaults.copy()
        for key in ("days", "min_usage_count", "min_usage_threshold"):
            val = section_dict.get(key)
            if isinstance(val, int):
                out[key] = val
        return out
    except (OSError, json.JSONDecodeError):
        return defaults.copy()


class UsageTracker:
    """Tracks MCP tool usage for analytics and optimization recommendations."""

    def __init__(self, project_root: Path) -> None:
        """Initialize usage tracker.

        Args:
            project_root: Project root directory (for .cortex path resolution).
        """
        self._project_root = project_root
        self._usage_dir: Path = get_cache_dir(project_root, CacheType.USAGE)
        self._events_dir: Path = self._usage_dir / "events"
        self._config = _load_config(project_root)

    def _is_enabled(self) -> bool:
        return bool(self._config.get("enabled", True))

    def _is_opt_out(self, tool_name: str) -> bool:
        opt_out_raw = self._config.get("opt_out_tools")
        opt_out: list[str] = list(opt_out_raw) if isinstance(opt_out_raw, list) else []
        return tool_name in opt_out

    def _is_result_summary_enabled(self, tool_name: str) -> bool:
        """Return True if result summaries are enabled for the given tool."""
        raw = self._config.get("result_summary_enabled_tools")
        tools: list[str] = list(raw) if isinstance(raw, list) else []
        return tool_name in tools

    def _should_record_event(self, tool_name: str, duration_ms: float) -> bool:
        """Determine whether an event should be recorded based on config."""
        if not self._is_enabled() or self._is_opt_out(tool_name):
            return False
        min_val = self._config.get("min_duration_ms", 0.0)
        min_duration = float(min_val) if isinstance(min_val, (int, float)) else 0.0
        return duration_ms >= min_duration

    def _select_result_summary(
        self,
        tool_name: str,
        result_summary: str | None,
    ) -> str | None:
        """Return stored result summary value for this tool/event."""
        if not result_summary:
            return None
        return result_summary if self._is_result_summary_enabled(tool_name) else None

    def _build_usage_event(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error_type: str | None,
        params_hash: str | None,
        handler_kind: HandlerKind,
        result_summary: str | None,
        retry_count: int | None,
        param_validation_failure: str | None,
        result_used: bool | None,
    ) -> ToolUsageEvent:
        """Build a ToolUsageEvent from recording parameters (Phase 57)."""
        summary = self._select_result_summary(tool_name, result_summary)
        return ToolUsageEvent(
            tool_name=tool_name,
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
            params_hash=(
                params_hash if self._config.get("anonymize_params", True) else None
            ),
            handler_kind=handler_kind,
            result_summary=summary,
            retry_count=retry_count,
            param_validation_failure=param_validation_failure,
            result_used=result_used,
        )

    async def record_tool_usage(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error_type: str | None = None,
        params_hash: str | None = None,
        handler_kind: HandlerKind = HandlerKind.TOOL,
        result_summary: str | None = None,
        retry_count: int | None = None,
        param_validation_failure: str | None = None,
        result_used: bool | None = None,
    ) -> None:
        """Record a single tool or resource usage event."""
        if not self._should_record_event(tool_name, duration_ms):
            return
        event = self._build_usage_event(
            tool_name,
            duration_ms,
            success,
            error_type,
            params_hash,
            handler_kind,
            result_summary,
            retry_count,
            param_validation_failure,
            result_used,
        )
        await _persist_event(self._project_root, event)

    async def get_usage_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        tool_name: str | None = None,
    ) -> dict[str, object]:
        """Return aggregated usage statistics.

        Args:
            start_date: Start of date range (inclusive).
            end_date: End of date range (inclusive).
            tool_name: If set, filter to this tool only.

        Returns:
            Dict with keys: tools (list of ToolUsageStats), total_events.
        """
        events = await _load_events_in_range(
            self._project_root, start_date, end_date, tool_name
        )
        by_tool: dict[str, list[ToolUsageEvent]] = {}
        for ev in events:
            by_tool.setdefault(ev.tool_name, []).append(ev)
        stats_list: list[ToolUsageStats] = [
            _aggregate_events(name, evs) for name, evs in by_tool.items()
        ]
        return {
            "tools": [s.model_dump() for s in stats_list],
            "total_events": len(events),
        }

    async def get_unused_tools(
        self,
        days: int = 90,
        min_usage_count: int = 0,
    ) -> list[str]:
        """Return tool names with usage count at or below threshold.

        Args:
            days: Look back this many days.
            min_usage_count: Tools with total_calls <= this are "unused".

        Returns:
            List of tool names that are unused or rarely used.
        """
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        result = await self.get_usage_stats(start_date=start, end_date=end)
        tools_raw = result.get("tools", [])
        _raw_list = cast(list[object], tools_raw if isinstance(tools_raw, list) else [])
        tools_list: list[dict[str, object]] = [
            cast(dict[str, object], x) for x in _raw_list if isinstance(x, dict)
        ]
        unused: list[str] = []
        for t in tools_list:
            row = _to_row_dict(t)
            if "tool_name" not in row:
                continue
            total_val: object = row.get("total_calls")
            total_calls = int(total_val) if isinstance(total_val, (int, float)) else 0
            if total_calls <= min_usage_count:
                unused.append(str(row["tool_name"]))
        return sorted(unused)

    async def get_event_by_id(self, event_id: str) -> ToolUsageEvent | None:
        """Return a single usage event by its stable ID.

        Scans the default analytics window (last 365 days) for the given id.
        """
        events = await _load_events_in_range(
            self._project_root,
            None,
            None,
            None,
        )
        for event in events:
            if event.id == event_id:
                return event
        return None

    async def get_events_by_ids(
        self,
        event_ids: list[str],
    ) -> list[ToolUsageEvent]:
        """Return all usage events matching the given stable IDs.

        Args:
            event_ids: List of event IDs to resolve.

        Returns:
            List of ToolUsageEvent instances whose id is in event_ids. The
            result preserves the order of event_ids and omits IDs that are
            not found.
        """
        if not event_ids:
            return []
        events = await _load_events_in_range(
            self._project_root,
            None,
            None,
            None,
        )
        by_id: dict[str, ToolUsageEvent] = {e.id: e for e in events}
        # Preserve caller-specified order while skipping missing IDs.
        return [by_id[event_id] for event_id in event_ids if event_id in by_id]

    async def search_usage(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        tool_name: str | None,
        success: bool | None,
        limit: int,
        query: str | None = None,
    ) -> list[ToolUsageEvent]:
        """Search usage events and return a compact, time-sorted subset."""
        if limit <= 0:
            return []
        events = await _load_events_in_range(
            self._project_root,
            start_date,
            end_date,
            tool_name,
        )
        events = _filter_events_by_success(events, success)
        events = _filter_events_by_query(events, query)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def get_usage_timeline(
        self,
        around_id: str,
        limit: int,
    ) -> list[ToolUsageEvent]:
        """Return chronological context around a given usage event.

        Args:
            around_id: ID of the central usage event.
            limit: Maximum number of events to return (including the center).

        Returns:
            List of usage events in chronological order that includes the
            event with the given ID when found. Returns an empty list if
            the ID is not found or limit is non-positive.
        """
        if limit <= 0:
            return []
        events = await _load_events_in_range(
            self._project_root,
            None,
            None,
            None,
        )
        if not events:
            return []
        events.sort(key=lambda e: e.timestamp)
        center_index: int | None = None
        for idx, event in enumerate(events):
            if event.id == around_id:
                center_index = idx
                break
        if center_index is None:
            return []
        window = min(limit, len(events))
        start = max(0, center_index - window // 2)
        end = start + window
        if end > len(events):
            end = len(events)
            start = max(0, end - window)
        return events[start:end]


def _to_row_dict(obj: ToolUsageStats | dict[str, object]) -> dict[str, object]:
    """Convert tool stat to dict for get_unused_tools iteration."""
    if isinstance(obj, dict):
        return obj
    out = obj.model_dump()
    return cast(dict[str, object], out)


def _error_types_from_events(events: list[ToolUsageEvent]) -> dict[str, int]:
    """Build error_type -> count from events."""
    out: dict[str, int] = {}
    for e in events:
        if e.error_type:
            out[e.error_type] = out.get(e.error_type, 0) + 1
    return out


def _aggregate_events(tool_name: str, events: list[ToolUsageEvent]) -> ToolUsageStats:
    """Aggregate a list of events into ToolUsageStats."""
    empty_ts = datetime.now(UTC).isoformat()
    if not events:
        return ToolUsageStats(
            tool_name=tool_name,
            total_calls=0,
            successful_calls=0,
            failed_calls=0,
            avg_duration_ms=0.0,
            min_duration_ms=0.0,
            max_duration_ms=0.0,
            error_types={},
            first_used=empty_ts,
            last_used=empty_ts,
        )
    durations = [e.duration_ms for e in events]
    success_count = sum(1 for e in events if e.success)
    timestamps = [e.timestamp for e in events]
    return ToolUsageStats(
        tool_name=tool_name,
        total_calls=len(events),
        successful_calls=success_count,
        failed_calls=len(events) - success_count,
        avg_duration_ms=sum(durations) / len(durations),
        min_duration_ms=min(durations),
        max_duration_ms=max(durations),
        error_types=_error_types_from_events(events),
        first_used=min(timestamps),
        last_used=max(timestamps),
    )


def _filter_events_by_success(
    events: list[ToolUsageEvent],
    success: bool | None,
) -> list[ToolUsageEvent]:
    """Filter events by success flag when provided."""
    if success is None:
        return events
    return [e for e in events if e.success is success]


def _filter_events_by_query(
    events: list[ToolUsageEvent],
    query: str | None,
) -> list[ToolUsageEvent]:
    """Filter events by case-insensitive keyword across basic text fields."""
    if not query:
        return events
    needle = query.lower()
    filtered: list[ToolUsageEvent] = []
    for event in events:
        fields = [
            event.tool_name,
            event.error_type or "",
            event.result_summary or "",
        ]
        if any(needle in value.lower() for value in fields):
            filtered.append(event)
    return filtered


async def _persist_event(project_root: Path, event: ToolUsageEvent) -> None:
    """Append a single event to .cortex/.cache/usage/events/{date}.json (concurrent-safe).

    Uses read_modify_write_cache_json so all tool/resource requests are tracked
    reliably from multiple chat sessions.
    """
    date_str = event.timestamp[:10]
    relative_key = f"usage/events/{date_str}.json"

    def append_event(existing: list[object] | dict[str, object]) -> list[object]:
        lst = list(existing) if isinstance(existing, list) else []
        lst.append(event.model_dump())
        return lst

    await read_modify_write_cache_json(
        project_root,
        relative_key,
        append_event,
        default=[],
    )


def _parse_events_from_content(
    content: str, tool_name: str | None
) -> list[ToolUsageEvent]:
    """Parse JSON content into ToolUsageEvent list, optionally filter by tool_name."""
    import json

    raw: list[object] = list(json.loads(content)) if content.strip() else []
    out: list[ToolUsageEvent] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        item_d = cast(dict[str, object], item)
        if tool_name and item_d.get("tool_name") != tool_name:
            continue
        _ensure_event_id(item_d)
        try:
            out.append(ToolUsageEvent.model_validate(item_d))
        except Exception:
            continue
    return out


def generate_usage_event_id(data: dict[str, object]) -> str:
    """Generate a stable UUIDv5-based ID for a usage event."""
    base = "|".join(
        str(data.get(key, ""))
        for key in (
            "timestamp",
            "tool_name",
            "duration_ms",
            "success",
            "error_type",
            "params_hash",
            "handler_kind",
            "retry_count",
            "param_validation_failure",
            "result_used",
        )
    )
    return str(uuid5(NAMESPACE_URL, base))


def _ensure_event_id(item: dict[str, object]) -> None:
    """Ensure usage event dict has a stable ID for backfilled data.

    For persisted events written before the id field existed, derive a
    deterministic UUIDv5 from core fields so the same event gets the same
    ID on every read.
    """
    existing = item.get("id")
    if isinstance(existing, str) and existing:
        return
    item["id"] = generate_usage_event_id(item)


async def _load_events_in_range(
    project_root: Path,
    start_date: datetime | None,
    end_date: datetime | None,
    tool_name: str | None,
) -> list[ToolUsageEvent]:
    """Load events from daily JSON files in the given range (concurrent-safe)."""
    start_str = (start_date or datetime.now(UTC) - timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )
    end_str = (end_date or datetime.now(UTC)).strftime("%Y-%m-%d")
    events: list[ToolUsageEvent] = []
    start_d = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_str, "%Y-%m-%d").date()
    delta = timedelta(days=1)
    d = start_d
    while d <= end_d:
        date_str = d.strftime("%Y-%m-%d")
        relative_key = f"usage/events/{date_str}.json"
        raw = await read_cache_json(project_root, relative_key)
        if isinstance(raw, list):
            content = __import__("json").dumps(raw)
            events.extend(_parse_events_from_content(content, tool_name))
        d = d + delta
    return events
