"""
Pattern Types - Shared type definitions for pattern analysis.

This module contains TypedDict definitions used across pattern analysis modules.
"""

from typing import TypedDict


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
