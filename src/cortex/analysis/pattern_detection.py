"""
Pattern Detection - Detect co-access and task patterns.

This module handles detection of file co-access patterns and task-based access patterns.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from itertools import combinations

from cortex.analysis.models import CoAccessPattern
from cortex.analysis.pattern_types import (
    AccessRecord,
    TaskPatternEntry,
    TaskPatternResult,
)
from cortex.core.constants import ACCESS_LOG_MAX_ENTRIES


def update_co_access_patterns(
    co_access_patterns: dict[str, int], file_path: str, context_files: list[str]
) -> None:
    """Update co-access patterns for files accessed together."""
    for other_file in context_files:
        if other_file != file_path:
            key = tuple(sorted([file_path, other_file]))
            key_str = f"{key[0]}|{key[1]}"
            co_access_patterns[key_str] = co_access_patterns.get(key_str, 0) + 1


def update_task_patterns(
    task_patterns: dict[str, TaskPatternEntry],
    file_path: str,
    task_id: str,
    task_description: str | None,
    timestamp: str,
) -> None:
    """Update task patterns with file access information."""
    if task_id not in task_patterns:
        task_patterns[task_id] = TaskPatternEntry(
            description=task_description, files=[], timestamp=timestamp
        )

    task_entry = task_patterns[task_id]
    files_list = task_entry.files
    if file_path not in files_list:
        files_list.append(file_path)


def get_all_time_patterns(
    co_access_patterns: dict[str, int],
) -> dict[str, int]:
    """Get all-time co-access patterns."""
    return dict(co_access_patterns)


def _calculate_patterns_from_task_files(
    task_files: defaultdict[str, set[str]],
) -> dict[str, int]:
    """Calculate co-access patterns from task files."""
    patterns: defaultdict[str, int] = defaultdict(int)
    for files in task_files.values():
        for file1, file2 in combinations(sorted(files), 2):
            key_str = f"{file1}|{file2}"
            patterns[key_str] += 1
    return patterns


def calculate_recent_patterns(
    accesses: list[AccessRecord], time_range_days: int
) -> dict[str, int]:
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
    cutoff_date = datetime.now(UTC) - timedelta(days=time_range_days)
    cutoff_str = cutoff_date.isoformat()
    task_files: defaultdict[str, set[str]] = defaultdict(set)
    recent_accesses = (
        accesses[-ACCESS_LOG_MAX_ENTRIES:]
        if len(accesses) > ACCESS_LOG_MAX_ENTRIES
        else accesses
    )
    for access in recent_accesses:
        if access.timestamp >= cutoff_str and access.task_id:
            task_files[access.task_id].add(access.file)
    return _calculate_patterns_from_task_files(task_files)


def format_co_access_results(
    patterns: dict[str, int], min_co_access_count: int
) -> list[CoAccessPattern]:
    """Format and filter co-access pattern results."""
    result: list[CoAccessPattern] = []
    for pattern_key, count in patterns.items():
        if count < min_co_access_count:
            continue
        files = pattern_key.split("|")
        if len(files) < 2:
            continue
        file_1, file_2 = files[0], files[1]
        correlation_strength = (
            "high" if count >= 10 else "medium" if count >= 5 else "low"
        )
        result.append(
            CoAccessPattern(
                files=[file_1, file_2],
                file_1=file_1,
                file_2=file_2,
                co_access_count=count,
                occurrences=count,
                correlation=0.0,
                correlation_strength=correlation_strength,
            )
        )
    return result


def sort_by_co_access_count(
    result: list[CoAccessPattern],
) -> list[CoAccessPattern]:
    """Sort results by co-access count descending."""
    result.sort(key=lambda x: x.co_access_count, reverse=True)
    return result


def get_co_access_patterns(
    co_access_patterns: dict[str, int],
    accesses: list[AccessRecord],
    min_co_access_count: int = 3,
    time_range_days: int | None = None,
) -> list[CoAccessPattern]:
    """
    Get frequently co-accessed file pairs.

    Args:
        co_access_patterns: All-time co-access patterns
        accesses: List of access records
        min_co_access_count: Minimum co-access count to include
        time_range_days: Optional time range to analyze (None = all time)

    Returns:
        List of co-access patterns sorted by frequency
    """
    if time_range_days is None:
        patterns = get_all_time_patterns(co_access_patterns)
    else:
        patterns = calculate_recent_patterns(accesses, time_range_days)

    result = format_co_access_results(patterns, min_co_access_count)
    return sort_by_co_access_count(result)


def should_skip_task_pattern(
    pattern: TaskPatternEntry, time_range_days: int | None, cutoff_str: str
) -> bool:
    """Check if pattern should be skipped based on time range."""
    if time_range_days is None:
        return False
    pattern_timestamp = pattern.timestamp
    return pattern_timestamp < cutoff_str


def extract_files_from_pattern(pattern: TaskPatternEntry) -> list[str]:
    """Extract files list from pattern."""
    return pattern.files


def extract_description_from_pattern(pattern: TaskPatternEntry) -> str:
    """Extract description from pattern."""
    return pattern.description or ""


def get_task_patterns(
    task_patterns: dict[str, TaskPatternEntry],
    time_range_days: int | None,
    cutoff_str: str,
) -> list[TaskPatternResult]:
    """
    Get task-based access patterns.

    Args:
        task_patterns: Dictionary of task patterns
        time_range_days: Optional time range to analyze
        cutoff_str: Cutoff date string for filtering

    Returns:
        List of task patterns with file access information
    """
    result: list[TaskPatternResult] = []
    for task_id, pattern_entry in task_patterns.items():
        if should_skip_task_pattern(pattern_entry, time_range_days, cutoff_str):
            continue
        files_list = extract_files_from_pattern(pattern_entry)
        if not files_list:
            continue

        result.append(
            TaskPatternResult(
                task_id=str(task_id),
                description=extract_description_from_pattern(pattern_entry),
                file_count=len(files_list),
                files=files_list,
                timestamp=pattern_entry.timestamp,
            )
        )

    result.sort(key=lambda x: x.timestamp, reverse=True)
    return result
