"""Usage tracking manager for MCP tool analytics (Phase 29)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import aiofiles

from cortex.core.cache_utils import CacheType, get_cache_dir
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
    }


def _load_config(project_root: Path) -> dict[str, bool | int | float | list[str]]:
    """Load usage tracking config from .cortex/config/usage_tracking.json."""
    import json

    config_path = project_root / ".cortex" / "config" / "usage_tracking.json"
    if not config_path.is_file():
        return _default_config()
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        config = _default_config()
        if isinstance(data, dict):
            for key in ("enabled", "anonymize_params", "aggregation_enabled"):
                if key in data and isinstance(data[key], bool):
                    config[key] = data[key]
            if "retention_days" in data and isinstance(data["retention_days"], int):
                config["retention_days"] = data["retention_days"]
            if "opt_out_tools" in data and isinstance(data["opt_out_tools"], list):
                _raw_opt = cast(list[object], data["opt_out_tools"])
                config["opt_out_tools"] = [s for s in _raw_opt if isinstance(s, str)]
            if "min_duration_ms" in data and isinstance(
                data["min_duration_ms"], (int, float)
            ):
                config["min_duration_ms"] = float(data["min_duration_ms"])
        return config
    except (OSError, json.JSONDecodeError):
        return _default_config()


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

    async def record_tool_usage(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error_type: str | None = None,
        params_hash: str | None = None,
    ) -> None:
        """Record a single tool usage event.

        Args:
            tool_name: Name of the MCP tool invoked.
            duration_ms: Execution duration in milliseconds.
            success: Whether the tool completed without error.
            error_type: Exception type name if failed.
            params_hash: Optional hash of anonymized parameters.
        """
        if not self._is_enabled() or self._is_opt_out(tool_name):
            return
        min_val = self._config.get("min_duration_ms", 0.0)
        min_duration = float(min_val) if isinstance(min_val, (int, float)) else 0.0
        if duration_ms < min_duration:
            return
        event = ToolUsageEvent(
            tool_name=tool_name,
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
            params_hash=(
                params_hash if self._config.get("anonymize_params", True) else None
            ),
        )
        await _persist_event(self._events_dir, event)

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
            self._events_dir, start_date, end_date, tool_name
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


def _to_row_dict(obj: object) -> dict[str, object]:
    """Convert tool stat to dict for get_unused_tools iteration."""
    if isinstance(obj, dict):
        return cast(dict[str, object], obj)
    method = getattr(obj, "model_dump", None)
    if callable(method):
        out: object = method()
        return cast(dict[str, object], out) if isinstance(out, dict) else {}
    return {}


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


async def _persist_event(events_dir: Path, event: ToolUsageEvent) -> None:
    """Append a single event to the daily JSON file."""
    events_dir.mkdir(parents=True, exist_ok=True)
    date_str = event.timestamp[:10]
    path = events_dir / f"{date_str}.json"
    existing: list[dict[str, object]] = []
    if path.exists():
        async with aiofiles.open(path, encoding="utf-8") as f:
            content = await f.read()
            if content.strip():
                import json

                existing = list(json.loads(content))
    existing.append(event.model_dump())
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        import json

        _ = await f.write(json.dumps(existing, indent=2))


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
        try:
            out.append(ToolUsageEvent.model_validate(item_d))
        except Exception:
            continue
    return out


async def _load_events_in_range(
    events_dir: Path,
    start_date: datetime | None,
    end_date: datetime | None,
    tool_name: str | None,
) -> list[ToolUsageEvent]:
    """Load events from daily JSON files in the given range."""
    import json

    if not events_dir.is_dir():
        return []
    start_str = (start_date or datetime.now(UTC) - timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )
    end_str = (end_date or datetime.now(UTC)).strftime("%Y-%m-%d")
    events: list[ToolUsageEvent] = []
    for path in events_dir.glob("*.json"):
        if (
            not path.name.endswith(".json")
            or path.stem < start_str
            or path.stem > end_str
        ):
            continue
        try:
            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()
                events.extend(_parse_events_from_content(content, tool_name))
        except (OSError, json.JSONDecodeError):
            continue
    return events
