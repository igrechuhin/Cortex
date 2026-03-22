"""Usage analytics data collection: date ranges, ID lists, tracker resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from cortex.managers.initialization import get_managers
from cortex.managers.lazy_manager import LazyManager
from cortex.managers.usage_tracker import UsageTracker


def usage_date_range_from_strings(
    start_date: str | None, end_date: str | None, default_days: int = 365
) -> tuple[datetime, datetime]:
    """Parse start/end date strings; default to default_days ago to now.

    Invalid ISO strings are silently ignored and the default range bound is
    kept (start defaults to ``default_days`` ago, end defaults to now).
    """
    end = datetime.now(UTC)
    start = end - timedelta(days=default_days)
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    return start, end


def parse_date_range(
    start_date: str | None, end_date: str | None, default_days: int = 365
) -> tuple[datetime, datetime]:
    """Public entrypoint for date range parsing (tests and callers)."""
    return usage_date_range_from_strings(start_date, end_date, default_days)


def normalize_usage_observation_ids(ids: list[str]) -> list[str]:
    """Drop empty strings; preserve order (non-empty whitespace kept)."""
    return [i for i in ids if i]


async def resolve_usage_tracker(project_root: Path) -> UsageTracker | None:
    """Resolve UsageTracker for project root."""
    managers = await get_managers(project_root)
    raw: object = getattr(managers, "usage_tracker", None)
    if raw is None:
        return None
    if isinstance(raw, LazyManager):
        resolved: object = cast(object, await raw.get())
        return resolved if isinstance(resolved, UsageTracker) else None
    return raw if isinstance(raw, UsageTracker) else None
