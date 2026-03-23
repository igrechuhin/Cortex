"""Usage tracking manager for MCP tool analytics (Phase 29)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from cortex.core.models import HandlerKind
from cortex.core.pipeline_state import is_commit_pipeline_active
from cortex.core.synapse_usage_config import is_usage_writable
from cortex.managers.usage_models import ToolUsageEvent, ToolUsageStats
from cortex.managers.usage_tracker_aggregation import (
    aggregate_events,
    filter_events_by_query,
    filter_events_by_success,
    to_row_dict,
)
from cortex.managers.usage_tracker_config import (
    get_tool_optimization_config,
    load_usage_tracker_config,
)
from cortex.managers.usage_tracker_events import (
    generate_usage_event_id,
    load_events_in_range,
    persist_event,
)

__all__ = ["UsageTracker", "get_tool_optimization_config", "generate_usage_event_id"]


class UsageTracker:
    """Tracks MCP tool usage for analytics and optimization recommendations."""

    def __init__(self, project_root: Path) -> None:
        """Initialize usage tracker.

        Args:
            project_root: Project root directory (for .cortex path resolution).
        """
        self._project_root = project_root
        self._config = load_usage_tracker_config(project_root)

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
        response_tokens: int | None,
    ) -> ToolUsageEvent:
        """Build a ToolUsageEvent from recording parameters (Phase 57/62)."""
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
            response_tokens=response_tokens,
        )

    async def _build_and_persist_usage_event(
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
        response_tokens: int | None,
    ) -> None:
        """Build a usage event and persist it to storage."""
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
            response_tokens,
        )
        await persist_event(self._project_root, event)

    def _should_skip_recording(self, tool_name: str, duration_ms: float) -> bool:
        """Return True if recording should be skipped."""
        if is_commit_pipeline_active(self._project_root):
            return True
        return not is_usage_writable(
            self._project_root
        ) or not self._should_record_event(tool_name, duration_ms)

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
        response_tokens: int | None = None,
    ) -> None:
        """Record a single tool or resource usage event."""
        if self._should_skip_recording(tool_name, duration_ms):
            return
        await self._build_and_persist_usage_event(
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
            response_tokens,
        )

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
        events = await load_events_in_range(
            self._project_root, start_date, end_date, tool_name
        )
        by_tool: dict[str, list[ToolUsageEvent]] = {}
        for ev in events:
            by_tool.setdefault(ev.tool_name, []).append(ev)
        stats_list: list[ToolUsageStats] = [
            aggregate_events(name, evs) for name, evs in by_tool.items()
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
            row = to_row_dict(t)
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
        events = await load_events_in_range(
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
        events = await load_events_in_range(
            self._project_root,
            None,
            None,
            None,
        )
        by_id: dict[str, ToolUsageEvent] = {e.id: e for e in events}
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
        events = await load_events_in_range(
            self._project_root,
            start_date,
            end_date,
            tool_name,
        )
        events = filter_events_by_success(events, success)
        events = filter_events_by_query(events, query)
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
        events = await load_events_in_range(
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
