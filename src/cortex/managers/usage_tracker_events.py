"""Usage event persistence and loading (Phase 81 split from usage_tracker)."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from cortex.core.cache_json_access import read_cache_json, read_modify_write_cache_json
from cortex.core.synapse_usage_config import get_usage_storage_root
from cortex.managers.usage_models import ToolUsageEvent

logger = logging.getLogger(__name__)


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


def ensure_event_id(item: dict[str, object]) -> None:
    """Ensure usage event dict has a stable ID for backfilled data.

    For persisted events written before the id field existed, derive a
    deterministic UUIDv5 from core fields so the same event gets the same
    ID on every read.
    """
    existing = item.get("id")
    if isinstance(existing, str) and existing:
        return
    item["id"] = generate_usage_event_id(item)


def parse_events_from_content(
    content: str, tool_name: str | None
) -> list[ToolUsageEvent]:
    """Parse JSON content into ToolUsageEvent list, optionally filter by tool_name."""
    raw: list[object] = list(json.loads(content)) if content.strip() else []
    out: list[ToolUsageEvent] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        item_d = cast(dict[str, object], item)
        if tool_name and item_d.get("tool_name") != tool_name:
            continue
        ensure_event_id(item_d)
        try:
            out.append(ToolUsageEvent.model_validate(item_d))
        except Exception as e:
            logger.debug("_parse_usage_events: skip invalid event: %s", e)
            continue
    return out


async def persist_event(project_root: Path, event: ToolUsageEvent) -> None:
    """Append a single event to usage/events/{date}.json (concurrent-safe).

    When usage_writable is true, writes to Synapse .cache (project_root/.cortex/
    synapse/.cache/usage/events/). Uses read_modify_write_cache_json for
    reliable multi-session tracking.
    """
    date_str = event.timestamp[:10]
    relative_key = f"usage/events/{date_str}.json"
    cache_root = get_usage_storage_root(project_root)

    def append_event(existing: list[object] | dict[str, object]) -> list[object]:
        lst = list(existing) if isinstance(existing, list) else []
        lst.append(event.model_dump())
        return lst

    await read_modify_write_cache_json(
        project_root,
        relative_key,
        append_event,
        default=[],
        cache_root=cache_root,
    )


async def load_events_in_range(
    project_root: Path,
    start_date: datetime | None,
    end_date: datetime | None,
    tool_name: str | None,
) -> list[ToolUsageEvent]:
    """Load events from daily JSON files in the given range (concurrent-safe).

    Uses get_usage_storage_root so reads match write location (Synapse or project).
    """
    start_str = (start_date or datetime.now(UTC) - timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )
    end_str = (end_date or datetime.now(UTC)).strftime("%Y-%m-%d")
    events: list[ToolUsageEvent] = []
    storage_root = get_usage_storage_root(project_root)
    start_d = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_str, "%Y-%m-%d").date()
    delta = timedelta(days=1)
    d = start_d
    while d <= end_d:
        date_str = d.strftime("%Y-%m-%d")
        relative_key = f"usage/events/{date_str}.json"
        raw = await read_cache_json(project_root, relative_key, cache_root=storage_root)
        if isinstance(raw, list):
            content = json.dumps(raw)
            events.extend(parse_events_from_content(content, tool_name))
        d = d + delta
    return events
