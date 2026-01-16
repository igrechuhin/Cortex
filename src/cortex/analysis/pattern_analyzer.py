"""
Pattern Analyzer - Analyze usage patterns and access frequency.

This module tracks file access patterns, identifies frequently co-accessed files,
detects unused content, and analyzes task-based access patterns.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from cortex.analysis.pattern_analysis import (
    get_access_frequency as analyze_access_frequency,
)
from cortex.analysis.pattern_analysis import (
    get_temporal_patterns as analyze_temporal_patterns,
)
from cortex.analysis.pattern_analysis import (
    get_unused_files as analyze_unused_files,
)
from cortex.analysis.pattern_detection import (
    get_co_access_patterns as detect_co_access_patterns,
)
from cortex.analysis.pattern_detection import (
    get_task_patterns as detect_task_patterns,
)
from cortex.analysis.pattern_detection import (
    update_co_access_patterns,
    update_task_patterns,
)
from cortex.analysis.pattern_normalization import (
    create_default_access_log,
    normalize_access_log,
)
from cortex.analysis.pattern_types import (
    AccessLog,
    AccessRecord,
    FileStatsEntry,
    TaskPatternEntry,
    TaskPatternResult,
    TemporalPatternsResult,
    UnusedFileEntry,
)
from cortex.core.async_file_utils import open_async_text_file
from cortex.core.exceptions import MemoryBankError

# Re-export types for backward compatibility
__all__ = [
    "PatternAnalyzer",
    "AccessRecord",
    "FileStatsEntry",
    "TaskPatternEntry",
    "UnusedFileEntry",
    "TaskPatternResult",
    "TemporalPatternsResult",
    "AccessLog",
    "create_default_access_log",
    "normalize_access_log",
]


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
        self.access_log_path: Path = self.project_root / ".cortex" / "access-log.json"
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
            # Ensure parent directory exists
            self.access_log_path.parent.mkdir(parents=True, exist_ok=True)
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
        update_co_access_patterns(
            self.access_data["co_access_patterns"], file_path, context_files
        )

    def _update_task_patterns(
        self,
        file_path: str,
        task_id: str,
        task_description: str | None,
        timestamp: str,
    ):
        """Update task patterns with file access information."""
        task_patterns = self.access_data.get("task_patterns", {})
        update_task_patterns(
            task_patterns, file_path, task_id, task_description, timestamp
        )

    def _create_access_record(
        self,
        file_path: str,
        timestamp: str,
        task_id: str | None,
        task_description: str | None,
        context_files: list[str] | None,
    ) -> AccessRecord:
        """Create an access record from parameters."""
        return {
            "timestamp": timestamp,
            "file": file_path,
            "task_id": task_id,
            "task_description": task_description,
            "context_files": context_files or [],
        }

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
        access_record = self._create_access_record(
            file_path, timestamp, task_id, task_description, context_files
        )
        self.access_data["accesses"].append(access_record)
        self._update_file_stats(file_path, timestamp, task_id)
        if context_files:
            self._update_co_access_patterns(file_path, context_files)
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
        return analyze_access_frequency(
            self.access_data["accesses"], time_range_days, min_access_count
        )

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
        return detect_co_access_patterns(
            self.access_data["co_access_patterns"],
            self.access_data["accesses"],
            min_co_access_count,
            time_range_days,
        )

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
        return analyze_unused_files(self.access_data["file_stats"], time_range_days)

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
        from cortex.analysis.pattern_analysis import calculate_cutoff_date_str

        cutoff_str = (
            calculate_cutoff_date_str(time_range_days)
            if time_range_days is not None
            else ""
        )
        return detect_task_patterns(
            self.access_data["task_patterns"], time_range_days, cutoff_str
        )

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
        return analyze_temporal_patterns(self.access_data["accesses"], time_range_days)

    def _filter_accesses_by_cutoff(
        self, accesses_list: list[AccessRecord], cutoff_str: str
    ) -> list[AccessRecord]:
        """Filter accesses by cutoff timestamp."""
        return [
            access
            for access in accesses_list
            if (
                access_timestamp_str := (
                    str(access_timestamp_raw)
                    if (access_timestamp_raw := access.get("timestamp", ""))
                    else ""
                )
            )
            and access_timestamp_str >= cutoff_str
        ]

    def _filter_task_patterns_by_cutoff(
        self, task_patterns: dict[str, TaskPatternEntry], cutoff_str: str
    ) -> dict[str, TaskPatternEntry]:
        """Filter task patterns by cutoff timestamp."""
        filtered: dict[str, TaskPatternEntry] = {}
        for task_id, pattern in task_patterns.items():
            pattern_timestamp_raw: object = pattern.get("timestamp", "")
            pattern_timestamp_str = (
                str(pattern_timestamp_raw) if pattern_timestamp_raw else ""
            )
            if pattern_timestamp_str >= cutoff_str:
                filtered[task_id] = pattern
        return filtered

    async def cleanup_old_data(self, keep_days: int = 180):
        """
        Clean up old access logs to prevent unbounded growth.

        Args:
            keep_days: Number of days of data to keep
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=keep_days)
        cutoff_str = cutoff_date.isoformat()

        accesses_list = self.access_data.get("accesses", [])
        original_count = len(accesses_list)
        filtered_accesses = self._filter_accesses_by_cutoff(accesses_list, cutoff_str)
        self.access_data["accesses"] = filtered_accesses
        removed_count = original_count - len(filtered_accesses)

        task_patterns = self.access_data.get("task_patterns", {})
        filtered_task_patterns = self._filter_task_patterns_by_cutoff(
            task_patterns, cutoff_str
        )
        self.access_data["task_patterns"] = filtered_task_patterns

        await self._save_access_log()

        return {
            "removed_accesses": removed_count,
            "remaining_accesses": len(filtered_accesses),
            "remaining_tasks": len(filtered_task_patterns),
        }
