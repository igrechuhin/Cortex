"""
Pattern Analysis - Analyze temporal patterns, unused files, and access frequency.

This module handles analysis of file access patterns including temporal analysis,
unused file detection, and access frequency calculations.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import cast

from cortex.analysis.pattern_types import (
    AccessRecord,
    FileStatsEntry,
    TemporalPatternsResult,
    UnusedFileEntry,
)
from cortex.core.constants import ACCESS_LOG_MAX_ENTRIES


def calculate_cutoff_date(time_range_days: int) -> str:
    """Calculate cutoff date string for time range.

    Args:
        time_range_days: Number of days to look back

    Returns:
        ISO format cutoff date string
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_days)
    return cutoff_date.isoformat()


def count_accesses_in_range(
    accesses: list[AccessRecord], cutoff_str: str
) -> dict[str, dict[str, object]]:
    """Count file accesses within time range.

    Args:
        accesses: List of access records
        cutoff_str: ISO format cutoff date string

    Returns:
        Dictionary mapping file paths to access statistics
    """

    def default_stats() -> dict[str, object]:
        """Create default stats dict."""
        return {"count": 0, "last_access": None, "task_count": 0, "tasks": set()}

    access_counts: dict[str, dict[str, object]] = defaultdict(default_stats)

    for access in accesses:
        access_timestamp = access["timestamp"]
        if access_timestamp >= cutoff_str:
            file_path = access["file"]
            if file_path:
                update_access_stats(access_counts[file_path], access)

    return access_counts


def update_access_stats(stats: dict[str, object], access: AccessRecord) -> None:
    """Update access statistics for a single access record.

    Args:
        stats: Statistics dictionary to update
        access: Access record to process
    """
    count_raw_val: object = stats.get("count", 0)
    count = int(count_raw_val) if isinstance(count_raw_val, (int, float)) else 0
    stats["count"] = count + 1
    stats["last_access"] = access["timestamp"]

    task_id = access["task_id"]
    if task_id:
        tasks_raw_val: object = stats.get("tasks")
        if isinstance(tasks_raw_val, set):
            tasks: set[str] = cast(set[str], tasks_raw_val)
            tasks.add(task_id)
        else:
            stats["tasks"] = {task_id}


def _get_task_count(tasks_raw: object) -> int:
    """Extract task count from tasks collection."""
    if isinstance(tasks_raw, (set, list)):
        tasks_collection: set[str] | list[str] = cast(set[str] | list[str], tasks_raw)
        return len(tasks_collection)
    return 0


def format_access_results(
    access_counts: dict[str, dict[str, object]],
    min_access_count: int,
    time_range_days: int,
) -> dict[str, dict[str, object]]:
    """Filter and format access results.

    Args:
        access_counts: Dictionary of access counts by file path
        min_access_count: Minimum access count to include
        time_range_days: Number of days in time range

    Returns:
        Formatted result dictionary
    """
    result: dict[str, dict[str, object]] = {}
    for file_path, stats in access_counts.items():
        count_raw: object = stats.get("count", 0)
        count = int(count_raw) if isinstance(count_raw, (int, float)) else 0
        if count >= min_access_count:
            tasks_raw: object = stats.get("tasks", set[str]())
            task_count = _get_task_count(tasks_raw)
            result[file_path] = {
                "access_count": count,
                "last_access": stats.get("last_access"),
                "task_count": task_count,
                "avg_accesses_per_day": count / time_range_days,
            }
    return result


def get_access_frequency(
    accesses: list[AccessRecord],
    time_range_days: int = 30,
    min_access_count: int = 1,
) -> dict[str, dict[str, object]]:
    """Get file access frequency within a time range.

    Performance optimization: Only processes the most recent ACCESS_LOG_MAX_ENTRIES
    entries to prevent O(n) complexity scaling issues on very large access logs.

    Args:
        accesses: List of access records
        time_range_days: Number of days to analyze
        min_access_count: Minimum access count to include

    Returns:
        Dictionary mapping file paths to access statistics
    """
    cutoff_str = calculate_cutoff_date(time_range_days)

    # Optimization: Only process most recent entries
    recent_accesses = (
        accesses[-ACCESS_LOG_MAX_ENTRIES:]
        if len(accesses) > ACCESS_LOG_MAX_ENTRIES
        else accesses
    )

    access_counts = count_accesses_in_range(recent_accesses, cutoff_str)
    return format_access_results(access_counts, min_access_count, time_range_days)


def calculate_cutoff_date_str(time_range_days: int) -> str:
    """Calculate cutoff date string for unused file detection."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_days)
    return cutoff_date.isoformat()


def is_file_unused(stats: FileStatsEntry, cutoff_str: str) -> bool:
    """Check if a file is unused based on stats and cutoff date."""
    last_access_raw = stats.get("last_access")
    last_access_str = last_access_raw if isinstance(last_access_raw, str) else ""
    return not last_access_str or last_access_str < cutoff_str


def build_unused_file_entry(
    file_path: str, stats: FileStatsEntry, cutoff_str: str
) -> UnusedFileEntry:
    """Build unused file entry dictionary."""
    last_access_raw = stats.get("last_access")
    last_access_str = last_access_raw if isinstance(last_access_raw, str) else ""

    days_since_access: int | None = None
    if last_access_str:
        try:
            last_access_dt = datetime.fromisoformat(last_access_str)
            days_since_access = (datetime.now(timezone.utc) - last_access_dt).days
        except (ValueError, TypeError):
            days_since_access = None

    total_accesses_raw: object = stats.get("total_accesses", 0)
    total_accesses_int = (
        int(total_accesses_raw) if isinstance(total_accesses_raw, (int, float)) else 0
    )

    return {
        "file": file_path,
        "last_access": last_access_str if last_access_str else None,
        "days_since_access": days_since_access,
        "total_accesses": total_accesses_int,
        "status": ("never_accessed" if not last_access_str else "stale"),
    }


def sort_unused_files(unused: list[UnusedFileEntry]) -> list[UnusedFileEntry]:
    """Sort unused files by days since access (most stale first)."""

    def get_days_since_access(x: UnusedFileEntry) -> float:
        days_val = x["days_since_access"]
        if days_val is not None:
            return float(days_val)
        return float("inf")

    unused.sort(key=get_days_since_access, reverse=True)
    return unused


def get_unused_files(
    file_stats: dict[str, FileStatsEntry], time_range_days: int = 90
) -> list[UnusedFileEntry]:
    """
    Identify files that haven't been accessed recently.

    Args:
        file_stats: Dictionary of file statistics
        time_range_days: Number of days to consider for "unused"

    Returns:
        List of unused files with last access information
    """
    cutoff_str = calculate_cutoff_date_str(time_range_days)

    unused: list[UnusedFileEntry] = [
        build_unused_file_entry(file_path, stats, cutoff_str)
        for file_path, stats in file_stats.items()
        if is_file_unused(stats, cutoff_str)
    ]

    return sort_unused_files(unused)


def calculate_temporal_cutoff(time_range_days: int) -> str:
    """Calculate cutoff date string for temporal analysis."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_days)
    return cutoff_date.isoformat()


def collect_temporal_data(
    accesses: list[AccessRecord], cutoff_str: str
) -> dict[str, defaultdict[int | str, int]]:
    """Collect temporal distribution data."""
    hourly: defaultdict[int, int] = defaultdict(int)
    daily: defaultdict[str, int] = defaultdict(int)
    weekly: defaultdict[str, int] = defaultdict(int)

    for access in accesses:
        timestamp_raw: object = access.get("timestamp", "")
        timestamp_str = str(timestamp_raw) if timestamp_raw else ""
        if timestamp_str >= cutoff_str:
            try:
                dt = datetime.fromisoformat(timestamp_str)
                hourly[dt.hour] += 1
                daily[dt.strftime("%Y-%m-%d")] += 1
                weekly[dt.strftime("%A")] += 1
            except (ValueError, TypeError):
                pass

    return {
        "hourly": cast(defaultdict[int | str, int], hourly),
        "daily": cast(defaultdict[int | str, int], daily),
        "weekly": cast(defaultdict[int | str, int], weekly),
    }


def calculate_peak_times(
    temporal_data: dict[str, defaultdict[int | str, int]],
) -> dict[str, int | str | None]:
    """Calculate peak hour and day."""
    hourly = temporal_data["hourly"]
    weekly = temporal_data["weekly"]

    def get_count(x: tuple[object, int]) -> int:
        return x[1]

    peak_hour_raw = max(hourly.items(), key=get_count)[0] if hourly else None
    peak_hour: int | None = (
        int(peak_hour_raw) if isinstance(peak_hour_raw, (int, float)) else None
    )

    peak_day_raw = max(weekly.items(), key=get_count)[0] if weekly else None
    peak_day: str | None = str(peak_day_raw) if peak_day_raw else None

    return {"peak_hour": peak_hour, "peak_day": peak_day}


def build_temporal_dicts(
    temporal_data: dict[str, defaultdict[int | str, int]],
) -> tuple[dict[int, int], dict[str, int], dict[str, int]]:
    """Build temporal distribution dictionaries."""
    hourly = temporal_data["hourly"]
    daily = temporal_data["daily"]
    weekly = temporal_data["weekly"]
    hourly_dict: dict[int, int] = {
        k: v for k, v in hourly.items() if isinstance(k, int)
    }
    daily_dict: dict[str, int] = {k: v for k, v in daily.items() if isinstance(k, str)}
    weekly_dict: dict[str, int] = {
        k: v for k, v in weekly.items() if isinstance(k, str)
    }
    return hourly_dict, daily_dict, weekly_dict


def extract_peak_times(
    peak_times: dict[str, int | str | None],
) -> tuple[int | None, str | None]:
    """Extract peak hour and day from peak_times dict."""
    peak_hour_val = peak_times.get("peak_hour")
    peak_hour: int | None = (
        int(peak_hour_val) if isinstance(peak_hour_val, (int, float)) else None
    )
    peak_day_val = peak_times.get("peak_day")
    peak_day: str | None = str(peak_day_val) if peak_day_val else None
    return peak_hour, peak_day


def build_temporal_result(
    time_range_days: int,
    temporal_data: dict[str, defaultdict[int | str, int]],
    peak_times: dict[str, int | str | None],
) -> TemporalPatternsResult:
    """Build temporal patterns result."""
    hourly_dict, daily_dict, weekly_dict = build_temporal_dicts(temporal_data)
    peak_hour, peak_day = extract_peak_times(peak_times)
    total_accesses = sum(hourly_dict.values())
    avg_accesses = total_accesses / max(len(daily_dict), 1)

    return {
        "time_range_days": time_range_days,
        "total_accesses": total_accesses,
        "hourly_distribution": hourly_dict,
        "daily_distribution": daily_dict,
        "weekly_distribution": weekly_dict,
        "peak_hour": peak_hour,
        "peak_day": peak_day,
        "avg_accesses_per_day": avg_accesses,
    }


def get_temporal_patterns(
    accesses: list[AccessRecord], time_range_days: int = 30
) -> TemporalPatternsResult:
    """
    Analyze temporal access patterns (hourly, daily, weekly).

    Args:
        accesses: List of access records
        time_range_days: Number of days to analyze

    Returns:
        Dictionary with temporal pattern statistics
    """
    cutoff_str = calculate_temporal_cutoff(time_range_days)
    temporal_data = collect_temporal_data(accesses, cutoff_str)
    peak_times = calculate_peak_times(temporal_data)

    return build_temporal_result(time_range_days, temporal_data, peak_times)
