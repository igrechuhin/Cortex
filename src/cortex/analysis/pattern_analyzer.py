"""
Pattern Analyzer - Analyze usage patterns and access frequency.

This module tracks file access patterns, identifies frequently co-accessed files,
detects unused content, and analyzes task-based access patterns.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import TypedDict, cast

from cortex.core.async_file_utils import open_async_text_file
from cortex.core.constants import ACCESS_LOG_MAX_ENTRIES
from cortex.core.exceptions import MemoryBankError


class AccessRecord(TypedDict):
    """Single file access event record."""

    timestamp: str
    file: str
    task_id: str | None
    task_description: str | None
    context_files: list[str]


class FileStatsEntry(TypedDict, total=False):
    """Aggregated statistics for a single file."""

    total_accesses: int
    first_access: str
    last_access: str
    tasks: list[str]


class TaskPatternEntry(TypedDict, total=False):
    """Task-based access pattern entry."""

    description: str | None
    files: list[str]
    timestamp: str


class UnusedFileEntry(TypedDict):
    """Unused file entry with access information."""

    file: str
    last_access: str | None
    days_since_access: int | None
    total_accesses: int
    status: str


class TaskPatternResult(TypedDict):
    """Task pattern result entry."""

    task_id: str
    description: str
    file_count: int
    files: list[str]
    timestamp: str


class TemporalPatternsResult(TypedDict):
    """Temporal patterns result."""

    time_range_days: int
    total_accesses: int
    hourly_distribution: dict[int, int]
    daily_distribution: dict[str, int]
    weekly_distribution: dict[str, int]
    peak_hour: int | None
    peak_day: str | None
    avg_accesses_per_day: float


class AccessLog(TypedDict):
    """Structured access log stored on disk."""

    version: str
    accesses: list[AccessRecord]
    file_stats: dict[str, FileStatsEntry]
    co_access_patterns: dict[str, int]
    task_patterns: dict[str, TaskPatternEntry]


class PatternAnalyzer:
    """
    Analyzes Memory Bank usage patterns to identify optimization opportunities.

    Features:
    - Track file access frequency and patterns
    - Identify frequently co-accessed files
    - Detect unused or stale content
    - Analyze task-based access patterns
    - Track temporal access patterns (daily/weekly trends)
    """

    def __init__(self, project_root: Path):
        """
        Initialize pattern analyzer.

        Args:
            project_root: Root directory of the project
        """
        self.project_root: Path = Path(project_root)
        self.access_log_path: Path = self.project_root / ".memory-bank-access-log.json"
        self.access_data: AccessLog = self._load_access_log()

    def _load_access_log(self) -> AccessLog:
        """
        Load access log from disk.

        Note:
            This method uses synchronous I/O during initialization for simplicity.
            For performance-critical paths, consider using async alternatives.
        """
        if not self.access_log_path.exists():
            return create_default_access_log()

        try:
            with open(self.access_log_path, encoding="utf-8") as f:
                data_raw: object = json.load(f)
                return normalize_access_log(data_raw)
        except (OSError, json.JSONDecodeError):
            # If corrupted, start fresh but keep backup
            if self.access_log_path.exists():
                backup_path = self.access_log_path.with_suffix(".json.backup")
                _ = self.access_log_path.rename(backup_path)

            return create_default_access_log()

    async def _save_access_log(self):
        """Save access log to disk."""
        try:
            async with open_async_text_file(
                self.access_log_path, "w", "utf-8"
            ) as file_handle:
                _ = await file_handle.write(json.dumps(self.access_data, indent=2))
        except OSError as e:
            raise MemoryBankError(f"Failed to save access log: {e}") from e

    def _update_file_stats(self, file_path: str, timestamp: str, task_id: str | None):
        """Update file statistics for an access event."""
        file_stats = self.access_data["file_stats"]
        if file_path not in file_stats:
            file_stats[file_path] = {
                "total_accesses": 0,
                "first_access": timestamp,
                "last_access": timestamp,
                "tasks": [],
            }

        stats = file_stats[file_path]
        total_accesses_raw: object = stats.get("total_accesses", 0)
        total_accesses = (
            int(total_accesses_raw)
            if isinstance(total_accesses_raw, (int, float))
            else 0
        )
        stats["total_accesses"] = total_accesses + 1
        stats["last_access"] = timestamp

        if task_id:
            tasks_raw: object = stats.get("tasks", [])
            tasks_list: list[object] = (
                cast(list[object], tasks_raw) if isinstance(tasks_raw, list) else []
            )
            tasks: list[str] = [str(t) for t in tasks_list if t is not None]
            if task_id not in tasks:
                tasks.append(task_id)
                stats["tasks"] = tasks

    def _update_co_access_patterns(self, file_path: str, context_files: list[str]):
        """Update co-access patterns for files accessed together."""
        for other_file in context_files:
            if other_file != file_path:
                key = tuple(sorted([file_path, other_file]))
                key_str = f"{key[0]}|{key[1]}"

                co_access_patterns = self.access_data["co_access_patterns"]
                current_count_raw: object = co_access_patterns.get(key_str, 0)
                try:
                    current_count = int(cast(int | str | float, current_count_raw))
                except (TypeError, ValueError):
                    current_count = 0
                co_access_patterns[key_str] = current_count + 1

    def _update_task_patterns(
        self,
        file_path: str,
        task_id: str,
        task_description: str | None,
        timestamp: str,
    ):
        """Update task patterns with file access information."""
        task_patterns = self.access_data.get("task_patterns", {})

        if task_id not in task_patterns:
            task_patterns[task_id] = {
                "description": task_description,
                "files": [],
                "timestamp": timestamp,
            }

        task_entry = task_patterns[task_id]
        files_list_raw: object = task_entry.get("files", [])
        files_list_items: list[object] = (
            cast(list[object], files_list_raw)
            if isinstance(files_list_raw, list)
            else []
        )
        files_list: list[str] = [str(f) for f in files_list_items if f is not None]
        if file_path not in files_list:
            files_list.append(file_path)
            task_entry["files"] = files_list

    async def record_access(
        self,
        file_path: str,
        task_id: str | None = None,
        task_description: str | None = None,
        context_files: list[str] | None = None,
    ):
        """
        Record a file access event.

        Args:
            file_path: Path to the accessed file
            task_id: Optional task identifier
            task_description: Optional task description
            context_files: Optional list of files accessed in same context
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Record the access
        access_record: AccessRecord = {
            "timestamp": timestamp,
            "file": file_path,
            "task_id": task_id,
            "task_description": task_description,
            "context_files": context_files or [],
        }
        accesses_list = self.access_data["accesses"]
        accesses_list.append(access_record)

        # Update file stats
        self._update_file_stats(file_path, timestamp, task_id)

        # Update co-access patterns
        if context_files:
            self._update_co_access_patterns(file_path, context_files)

        # Update task patterns
        if task_id:
            self._update_task_patterns(file_path, task_id, task_description, timestamp)

        await self._save_access_log()

    async def get_access_frequency(
        self, time_range_days: int = 30, min_access_count: int = 1
    ) -> dict[str, dict[str, object]]:
        """Get file access frequency within a time range.

        Performance optimization: Only processes the most recent ACCESS_LOG_MAX_ENTRIES
        entries to prevent O(n) complexity scaling issues on very large access logs.

        Args:
            time_range_days: Number of days to analyze
            min_access_count: Minimum access count to include

        Returns:
            Dictionary mapping file paths to access statistics
        """
        cutoff_str = _calculate_cutoff_date(time_range_days)

        # Optimization: Only process most recent entries
        accesses = self.access_data["accesses"]
        recent_accesses = (
            accesses[-ACCESS_LOG_MAX_ENTRIES:]
            if len(accesses) > ACCESS_LOG_MAX_ENTRIES
            else accesses
        )

        access_counts = _count_accesses_in_range(recent_accesses, cutoff_str)
        return _format_access_results(access_counts, min_access_count, time_range_days)

    def _get_all_time_patterns(self) -> dict[str, int]:
        """Get all-time co-access patterns."""
        co_access_patterns_raw = self.access_data["co_access_patterns"]
        return dict(co_access_patterns_raw)

    def _calculate_recent_patterns(self, time_range_days: int) -> dict[str, int]:
        """Calculate co-access patterns from recent accesses.

        Performance optimization: Only processes the most recent ACCESS_LOG_MAX_ENTRIES
        entries to prevent O(n²) complexity on very large access logs. For typical
        projects with <10,000 entries, this processes all data. For long-running
        projects, focuses on recent activity which is more relevant.

        Time Complexity: O(min(n, MAX) × k) where:
        - n = total access log entries
        - MAX = ACCESS_LOG_MAX_ENTRIES (10,000)
        - k = average files per task (~5-10 typically)
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_days)
        cutoff_str = cutoff_date.isoformat()

        patterns: defaultdict[str, int] = defaultdict(int)
        task_files: defaultdict[str, set[str]] = defaultdict(set)

        # Optimization: Only process most recent entries (reverse order)
        # This prevents O(n²) complexity on very large access logs
        accesses = self.access_data["accesses"]
        recent_accesses = (
            accesses[-ACCESS_LOG_MAX_ENTRIES:]
            if len(accesses) > ACCESS_LOG_MAX_ENTRIES
            else accesses
        )

        for access in recent_accesses:
            access_timestamp2 = access["timestamp"]
            task_id2 = access["task_id"]
            if access_timestamp2 >= cutoff_str and task_id2:
                task_files[task_id2].add(access["file"])

        for files in task_files.values():
            # Optimize: Use combinations instead of nested loops
            # This is clearer and potentially more efficient
            for file1, file2 in combinations(sorted(files), 2):
                key_str = f"{file1}|{file2}"
                patterns[key_str] += 1

        return patterns

    def _format_co_access_results(
        self, patterns: dict[str, int], min_co_access_count: int
    ) -> list[dict[str, object]]:
        """Format and filter co-access pattern results."""
        result: list[dict[str, object]] = []
        for pattern_key, count in patterns.items():
            if count >= min_co_access_count:
                files = pattern_key.split("|")
                result.append(
                    {
                        "file_1": files[0],
                        "file_2": files[1],
                        "co_access_count": count,
                        "correlation_strength": (
                            "high" if count >= 10 else "medium" if count >= 5 else "low"
                        ),
                    }
                )
        return result

    def _sort_by_co_access_count(
        self, result: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Sort results by co-access count descending."""

        def get_co_access_count(x: dict[str, object]) -> int:
            count_val_raw: object = x.get("co_access_count", 0)
            return int(count_val_raw) if isinstance(count_val_raw, (int, float)) else 0

        result.sort(key=get_co_access_count, reverse=True)
        return result

    async def get_co_access_patterns(
        self, min_co_access_count: int = 3, time_range_days: int | None = None
    ) -> list[dict[str, object]]:
        """
        Get frequently co-accessed file pairs.

        Args:
            min_co_access_count: Minimum co-access count to include
            time_range_days: Optional time range to analyze (None = all time)

        Returns:
            List of co-access patterns sorted by frequency
        """
        if time_range_days is None:
            patterns = self._get_all_time_patterns()
        else:
            patterns = self._calculate_recent_patterns(time_range_days)

        result = self._format_co_access_results(patterns, min_co_access_count)
        return self._sort_by_co_access_count(result)

    async def get_unused_files(
        self, time_range_days: int = 90
    ) -> list[UnusedFileEntry]:
        """
        Identify files that haven't been accessed recently.

        Args:
            time_range_days: Number of days to consider for "unused"

        Returns:
            List of unused files with last access information
        """
        cutoff_str = self._calculate_cutoff_date_str(time_range_days)
        unused: list[UnusedFileEntry] = []

        file_stats = self.access_data["file_stats"]
        for file_path, stats in file_stats.items():
            if self._is_file_unused(stats, cutoff_str):
                unused.append(
                    self._build_unused_file_entry(file_path, stats, cutoff_str)
                )

        return self._sort_unused_files(unused)

    async def get_task_patterns(
        self, time_range_days: int | None = None
    ) -> list[TaskPatternResult]:
        """
        Get task-based access patterns.

        Args:
            time_range_days: Optional time range to analyze

        Returns:
            List of task patterns with file access information
        """
        cutoff_str = (
            self._calculate_cutoff_date_str(time_range_days)
            if time_range_days is not None
            else ""
        )
        result: list[TaskPatternResult] = []
        task_patterns_raw = self.access_data["task_patterns"]

        for task_id, pattern in task_patterns_raw.items():
            pattern_entry: TaskPatternEntry = pattern
            if self._should_skip_task_pattern(
                pattern_entry, time_range_days, cutoff_str
            ):
                continue

            files_list = self._extract_files_from_pattern(pattern_entry)
            description = self._extract_description_from_pattern(pattern_entry)
            pattern_timestamp = pattern_entry.get("timestamp", "") or ""

            result.append(
                {
                    "task_id": str(task_id),
                    "description": description,
                    "file_count": len(files_list),
                    "files": files_list,
                    "timestamp": pattern_timestamp,
                }
            )

        result.sort(key=lambda x: x["timestamp"], reverse=True)
        return result

    def _should_skip_task_pattern(
        self, pattern: TaskPatternEntry, time_range_days: int | None, cutoff_str: str
    ) -> bool:
        """Check if pattern should be skipped based on time range."""
        if time_range_days is None:
            return False
        pattern_timestamp = pattern.get("timestamp", "") or ""
        return pattern_timestamp < cutoff_str

    def _extract_files_from_pattern(self, pattern: TaskPatternEntry) -> list[str]:
        """Extract files list from pattern."""
        files_raw: object = pattern.get("files", [])
        files_list_items: list[object] = (
            cast(list[object], files_raw) if isinstance(files_raw, list) else []
        )
        return [str(f) for f in files_list_items if f is not None]

    def _extract_description_from_pattern(self, pattern: TaskPatternEntry) -> str:
        """Extract description from pattern."""
        description_raw: object = pattern.get("description", "")
        return str(description_raw) if description_raw is not None else ""

    async def get_temporal_patterns(
        self, time_range_days: int = 30
    ) -> TemporalPatternsResult:
        """
        Analyze temporal access patterns (hourly, daily, weekly).

        Args:
            time_range_days: Number of days to analyze

        Returns:
            Dictionary with temporal pattern statistics
        """
        cutoff_str = self._calculate_temporal_cutoff(time_range_days)
        temporal_data = self._collect_temporal_data(cutoff_str)
        peak_times = self._calculate_peak_times(temporal_data)

        return self._build_temporal_result(time_range_days, temporal_data, peak_times)

    def _calculate_temporal_cutoff(self, time_range_days: int) -> str:
        """Calculate cutoff date string for temporal analysis."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_days)
        return cutoff_date.isoformat()

    def _collect_temporal_data(
        self, cutoff_str: str
    ) -> dict[str, defaultdict[int | str, int]]:
        """Collect temporal distribution data."""
        hourly: defaultdict[int, int] = defaultdict(int)
        daily: defaultdict[str, int] = defaultdict(int)
        weekly: defaultdict[str, int] = defaultdict(int)

        accesses_list = self.access_data.get("accesses", [])
        for access in accesses_list:
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

    def _calculate_peak_times(
        self, temporal_data: dict[str, defaultdict[int | str, int]]
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

    def _build_temporal_result(
        self,
        time_range_days: int,
        temporal_data: dict[str, defaultdict[int | str, int]],
        peak_times: dict[str, int | str | None],
    ) -> TemporalPatternsResult:
        """Build temporal patterns result."""
        hourly_dict, daily_dict, weekly_dict = self._build_temporal_dicts(temporal_data)
        peak_hour, peak_day = self._extract_peak_times(peak_times)
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

    def _build_temporal_dicts(
        self, temporal_data: dict[str, defaultdict[int | str, int]]
    ) -> tuple[dict[int, int], dict[str, int], dict[str, int]]:
        """Build temporal distribution dictionaries."""
        hourly = temporal_data["hourly"]
        daily = temporal_data["daily"]
        weekly = temporal_data["weekly"]
        hourly_dict: dict[int, int] = {
            k: v for k, v in hourly.items() if isinstance(k, int)
        }
        daily_dict: dict[str, int] = {
            k: v for k, v in daily.items() if isinstance(k, str)
        }
        weekly_dict: dict[str, int] = {
            k: v for k, v in weekly.items() if isinstance(k, str)
        }
        return hourly_dict, daily_dict, weekly_dict

    def _extract_peak_times(
        self, peak_times: dict[str, int | str | None]
    ) -> tuple[int | None, str | None]:
        """Extract peak hour and day from peak_times dict."""
        peak_hour_val = peak_times.get("peak_hour")
        peak_hour: int | None = (
            int(peak_hour_val) if isinstance(peak_hour_val, (int, float)) else None
        )
        peak_day_val = peak_times.get("peak_day")
        peak_day: str | None = str(peak_day_val) if peak_day_val else None
        return peak_hour, peak_day

    async def cleanup_old_data(self, keep_days: int = 180):
        """
        Clean up old access logs to prevent unbounded growth.

        Args:
            keep_days: Number of days of data to keep
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=keep_days)
        cutoff_str = cutoff_date.isoformat()

        # Filter accesses
        accesses_list = self.access_data.get("accesses", [])
        original_count = len(accesses_list)

        filtered_accesses: list[AccessRecord] = []
        for access in accesses_list:
            access_timestamp_raw: object = access.get("timestamp", "")
            access_timestamp_str = (
                str(access_timestamp_raw) if access_timestamp_raw else ""
            )
            if access_timestamp_str >= cutoff_str:
                filtered_accesses.append(access)

        self.access_data["accesses"] = filtered_accesses
        removed_count = original_count - len(filtered_accesses)

        # Filter task patterns
        task_patterns = self.access_data.get("task_patterns", {})
        filtered_task_patterns: dict[str, TaskPatternEntry] = {}
        for task_id, pattern in task_patterns.items():
            pattern_timestamp_raw: object = pattern.get("timestamp", "")
            pattern_timestamp_str = (
                str(pattern_timestamp_raw) if pattern_timestamp_raw else ""
            )
            if pattern_timestamp_str >= cutoff_str:
                filtered_task_patterns[task_id] = pattern

        self.access_data["task_patterns"] = filtered_task_patterns

        await self._save_access_log()

        return {
            "removed_accesses": removed_count,
            "remaining_accesses": len(filtered_accesses),
            "remaining_tasks": len(filtered_task_patterns),
        }

    def _calculate_cutoff_date_str(self, time_range_days: int) -> str:
        """Calculate cutoff date string for unused file detection."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_days)
        return cutoff_date.isoformat()

    def _is_file_unused(self, stats: FileStatsEntry, cutoff_str: str) -> bool:
        """Check if a file is unused based on stats and cutoff date."""
        last_access_raw = stats.get("last_access")
        last_access_str = last_access_raw if isinstance(last_access_raw, str) else ""
        return not last_access_str or last_access_str < cutoff_str

    def _build_unused_file_entry(
        self, file_path: str, stats: FileStatsEntry, cutoff_str: str
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
            int(total_accesses_raw)
            if isinstance(total_accesses_raw, (int, float))
            else 0
        )

        return {
            "file": file_path,
            "last_access": last_access_str if last_access_str else None,
            "days_since_access": days_since_access,
            "total_accesses": total_accesses_int,
            "status": ("never_accessed" if not last_access_str else "stale"),
        }

    def _sort_unused_files(
        self, unused: list[UnusedFileEntry]
    ) -> list[UnusedFileEntry]:
        """Sort unused files by days since access (most stale first)."""

        def get_days_since_access(x: UnusedFileEntry) -> float:
            days_val = x["days_since_access"]
            if days_val is not None:
                return float(days_val)
            return float("inf")

        unused.sort(key=get_days_since_access, reverse=True)
        return unused


def create_default_access_log() -> AccessLog:
    """Create a default empty access log structure.

    Returns:
        Empty AccessLog with default values
    """
    return {
        "version": "1.0",
        "accesses": [],
        "file_stats": {},
        "co_access_patterns": {},
        "task_patterns": {},
    }


def _normalize_accesses(accesses_raw: object) -> list[AccessRecord]:
    """Normalize raw accesses data into AccessRecord list."""
    accesses: list[AccessRecord] = []
    if not isinstance(accesses_raw, list):
        return accesses

    accesses_list: list[object] = cast(list[object], accesses_raw)
    for access_item in accesses_list:
        if isinstance(access_item, dict):
            access_dict: dict[str, object] = cast(dict[str, object], access_item)
            context_files_raw: object = access_dict.get("context_files")
            context_files_list: list[object] = (
                cast(list[object], context_files_raw)
                if isinstance(context_files_raw, list)
                else []
            )
            access: AccessRecord = {
                "timestamp": str(access_dict.get("timestamp", "")),
                "file": str(access_dict.get("file", "")),
                "task_id": (
                    str(task_id_raw)
                    if (task_id_raw := access_dict.get("task_id")) is not None
                    else None
                ),
                "task_description": (
                    str(desc_raw)
                    if (desc_raw := access_dict.get("task_description")) is not None
                    else None
                ),
                "context_files": [str(f) for f in context_files_list],
            }
            accesses.append(access)
    return accesses


def _normalize_file_stats(file_stats_raw: object) -> dict[str, FileStatsEntry]:
    """Normalize raw file stats data into FileStatsEntry dict."""
    file_stats: dict[str, FileStatsEntry] = {}
    if not isinstance(file_stats_raw, dict):
        return file_stats

    file_stats_dict: dict[str, object] = cast(dict[str, object], file_stats_raw)
    for file_path_raw, stats_dict_raw in file_stats_dict.items():
        file_path = str(file_path_raw)
        if isinstance(stats_dict_raw, dict):
            stats_dict: dict[str, object] = cast(dict[str, object], stats_dict_raw)
            tasks_raw: object = stats_dict.get("tasks")
            tasks_list: list[object] = (
                cast(list[object], tasks_raw) if isinstance(tasks_raw, list) else []
            )
            file_stats[file_path] = {
                "total_accesses": (
                    int(total_raw)
                    if isinstance(
                        total_raw := stats_dict.get("total_accesses", 0),
                        (int, float),
                    )
                    else 0
                ),
                "first_access": str(stats_dict.get("first_access", "")),
                "last_access": str(stats_dict.get("last_access", "")),
                "tasks": [str(t) for t in tasks_list if t is not None],
            }
    return file_stats


def _normalize_co_access_patterns(co_access_patterns_raw: object) -> dict[str, int]:
    """Normalize raw co-access patterns data into dict."""
    co_access_patterns: dict[str, int] = {}
    if not isinstance(co_access_patterns_raw, dict):
        return co_access_patterns

    co_access_dict: dict[str, object] = cast(dict[str, object], co_access_patterns_raw)
    for key_item, value_item in co_access_dict.items():
        key_str = str(key_item)
        value = int(value_item) if isinstance(value_item, (int, float)) else 0
        co_access_patterns[key_str] = value
    return co_access_patterns


def _normalize_task_patterns(
    task_patterns_raw: object,
) -> dict[str, TaskPatternEntry]:
    """Normalize raw task patterns data into TaskPatternEntry dict."""
    task_patterns: dict[str, TaskPatternEntry] = {}
    if not isinstance(task_patterns_raw, dict):
        return task_patterns

    task_patterns_dict: dict[str, object] = cast(dict[str, object], task_patterns_raw)
    for task_id_key, pattern_item in task_patterns_dict.items():
        task_id_str = str(task_id_key)
        if isinstance(pattern_item, dict):
            pattern_dict: dict[str, object] = cast(dict[str, object], pattern_item)
            files_raw: object = pattern_dict.get("files")
            files_list: list[object] = (
                cast(list[object], files_raw) if isinstance(files_raw, list) else []
            )
            task_patterns[task_id_str] = {
                "description": (
                    str(desc_raw)
                    if (desc_raw := pattern_dict.get("description")) is not None
                    else None
                ),
                "files": [str(f) for f in files_list],
                "timestamp": str(pattern_dict.get("timestamp", "")),
            }
    return task_patterns


def normalize_access_log(data_raw: object) -> AccessLog:
    """Normalize raw JSON data into AccessLog format.

    Args:
        data_raw: Raw JSON data from file

    Returns:
        Normalized AccessLog structure

    Raises:
        MemoryBankError: If data cannot be normalized
    """
    if not isinstance(data_raw, dict):
        return create_default_access_log()

    data: dict[str, object] = cast(dict[str, object], data_raw)

    return {
        "version": str(data.get("version", "1.0")),
        "accesses": _normalize_accesses(data.get("accesses", [])),
        "file_stats": _normalize_file_stats(data.get("file_stats", {})),
        "co_access_patterns": _normalize_co_access_patterns(
            data.get("co_access_patterns", {})
        ),
        "task_patterns": _normalize_task_patterns(data.get("task_patterns", {})),
    }


def _calculate_cutoff_date(time_range_days: int) -> str:
    """Calculate cutoff date string for time range.

    Args:
        time_range_days: Number of days to look back

    Returns:
        ISO format cutoff date string
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range_days)
    return cutoff_date.isoformat()


def _count_accesses_in_range(
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
                _update_access_stats(access_counts[file_path], access)

    return access_counts


def _update_access_stats(stats: dict[str, object], access: AccessRecord) -> None:
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


def _format_access_results(
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
            if isinstance(tasks_raw, (set, list)):
                tasks_collection: set[str] | list[str] = cast(
                    set[str] | list[str], tasks_raw
                )
                task_count = len(tasks_collection)
            else:
                task_count = 0
            result[file_path] = {
                "access_count": count,
                "last_access": stats.get("last_access"),
                "task_count": task_count,
                "avg_accesses_per_day": count / time_range_days,
            }
    return result
