"""
Pattern Analyzer - Analyze usage patterns and access frequency.

This module derives file access patterns from the `load_context` session logs
Cortex already writes, identifies frequently co-accessed files, detects unused
content, and analyzes task-based access patterns.
"""

from pathlib import Path

from cortex.analysis.models import CoAccessPattern
from cortex.analysis.pattern_analysis import AccessFrequencyResult
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
from cortex.analysis.pattern_types import (
    AccessLog,
    AccessRecord,
    FileStatsEntry,
    TaskPatternEntry,
    TaskPatternResult,
    TemporalPatternsResult,
    UnusedFileEntry,
    create_default_access_log,
)
from cortex.analysis.session_access_source import build_access_records

# Re-export types for convenience
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

    def __init__(
        self,
        project_root: Path,
        pattern_window_days: int = 30,
        min_access_count: int = 5,
        track_usage_patterns: bool = True,
        track_task_patterns: bool = True,
    ):
        """
        Initialize pattern analyzer.

        Args:
            project_root: Root directory of the project
            pattern_window_days: Analysis window in days (from config)
            min_access_count: Minimum access count for pattern analysis (from config)
            track_usage_patterns: Enable usage pattern tracking (from config)
            track_task_patterns: Enable task pattern tracking (from config)
        """
        self.project_root: Path = Path(project_root)

        # Store config values for use in analysis methods
        self.pattern_window_days: int = pattern_window_days
        self.min_access_count: int = min_access_count
        self.track_usage_patterns: bool = track_usage_patterns
        self.track_task_patterns: bool = track_task_patterns

        # AI: usage patterns are projected from session logs on construction;
        # the flag being false must yield an empty log, not stale data.
        records = (
            build_access_records(self.project_root, pattern_window_days)
            if track_usage_patterns
            else []
        )
        self.access_data: AccessLog = self._build_access_log(records)

    def _build_access_log(self, records: list[AccessRecord]) -> AccessLog:
        """Replay projected access records into an aggregated access log."""
        self.access_data = create_default_access_log()
        for record in records:
            self.access_data.accesses.append(record)
            self._update_file_stats(record.file, record.timestamp, record.task_id)
            # AI: every file of a call carries all its siblings as context, so
            # counting only siblings that sort after it increments each
            # unordered pair exactly once per call instead of twice.
            later_siblings = [f for f in record.context_files if f > record.file]
            if later_siblings:
                self._update_co_access_patterns(record.file, later_siblings)
            if record.task_id and self.track_task_patterns:
                self._update_task_patterns(
                    record.file,
                    record.task_id,
                    record.task_description,
                    record.timestamp,
                )
        return self.access_data

    def _update_file_stats(self, file_path: str, timestamp: str, task_id: str | None):
        """Update file statistics for an access event."""
        stats = self.access_data.file_stats.get(file_path)
        if stats is None:
            stats = FileStatsEntry(
                total_accesses=0,
                first_access=timestamp,
                last_access=timestamp,
                tasks=[],
            )
            self.access_data.file_stats[file_path] = stats

        stats.total_accesses += 1
        stats.last_access = timestamp
        if task_id and task_id not in stats.tasks:
            stats.tasks.append(task_id)

    def _update_co_access_patterns(self, file_path: str, context_files: list[str]):
        """Update co-access patterns for files accessed together."""
        update_co_access_patterns(
            self.access_data.co_access_patterns, file_path, context_files
        )

    def _update_task_patterns(
        self,
        file_path: str,
        task_id: str,
        task_description: str | None,
        timestamp: str,
    ):
        """Update task patterns with file access information."""
        update_task_patterns(
            self.access_data.task_patterns,
            file_path,
            task_id,
            task_description,
            timestamp,
        )

    async def get_access_frequency(
        self, time_range_days: int = 30, min_access_count: int = 1
    ) -> AccessFrequencyResult:
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
            self.access_data.accesses, time_range_days, min_access_count
        )

    async def get_co_access_patterns(
        self, min_co_access_count: int = 3, time_range_days: int | None = None
    ) -> list[CoAccessPattern]:
        """
        Get frequently co-accessed file pairs.

        Args:
            min_co_access_count: Minimum co-access count to include
            time_range_days: Optional time range to analyze (None = all time)

        Returns:
            List of co-access patterns sorted by frequency
        """
        return detect_co_access_patterns(
            self.access_data.co_access_patterns,
            self.access_data.accesses,
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
        return analyze_unused_files(self.access_data.file_stats, time_range_days)

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
            self.access_data.task_patterns, time_range_days, cutoff_str
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
        return analyze_temporal_patterns(self.access_data.accesses, time_range_days)
