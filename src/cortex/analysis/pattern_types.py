"""
Pattern Types - Shared type definitions for pattern analysis.

This module contains Pydantic model definitions used across pattern analysis modules.
"""

from pydantic import BaseModel, ConfigDict, Field


class AccessRecord(BaseModel):
    """Single file access event record."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    timestamp: str = Field(description="ISO format timestamp")
    file: str = Field(description="File path")
    task_id: str | None = Field(default=None, description="Task identifier")
    task_description: str | None = Field(default=None, description="Task description")
    context_files: list[str] = Field(
        default_factory=list, description="Files accessed in same context"
    )


class FileStatsEntry(BaseModel):
    """Aggregated statistics for a single file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_accesses: int = Field(ge=0, description="Total number of accesses")
    first_access: str = Field(description="First access timestamp")
    last_access: str = Field(description="Last access timestamp")
    tasks: list[str] = Field(default_factory=list, description="List of task IDs")


class TaskPatternEntry(BaseModel):
    """Task-based access pattern entry."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    description: str | None = Field(default=None, description="Task description")
    files: list[str] = Field(default_factory=list, description="Files accessed in task")
    timestamp: str = Field(description="Task timestamp")


class UnusedFileEntry(BaseModel):
    """Unused file entry with access information."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File path")
    last_access: str | None = Field(default=None, description="Last access timestamp")
    days_since_access: int | None = Field(
        default=None, ge=0, description="Days since last access"
    )
    total_accesses: int = Field(ge=0, description="Total number of accesses")
    status: str = Field(description="File status")


class TaskPatternResult(BaseModel):
    """Task pattern result entry."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    task_id: str = Field(description="Task identifier")
    description: str = Field(description="Task description")
    file_count: int = Field(ge=0, description="Number of files accessed")
    files: list[str] = Field(default_factory=list, description="List of file paths")
    timestamp: str = Field(description="Task timestamp")


class TemporalPatternsResult(BaseModel):
    """Temporal patterns result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    time_range_days: int = Field(ge=1, description="Time range in days")
    total_accesses: int = Field(ge=0, description="Total number of accesses")
    hourly_distribution: dict[int, int] = Field(
        default_factory=lambda: dict[int, int](),
        description="Accesses by hour (0-23)",
    )
    daily_distribution: dict[str, int] = Field(
        default_factory=lambda: dict[str, int](),
        description="Accesses by day of week",
    )
    weekly_distribution: dict[str, int] = Field(
        default_factory=lambda: dict[str, int](),
        description="Accesses by week",
    )
    peak_hour: int | None = Field(
        default=None, ge=0, le=23, description="Peak access hour"
    )
    peak_day: str | None = Field(default=None, description="Peak access day")
    avg_accesses_per_day: float = Field(ge=0.0, description="Average accesses per day")


class AccessLog(BaseModel):
    """Structured access log stored on disk."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    version: str = Field(description="Log format version")
    accesses: list[AccessRecord] = Field(
        default_factory=lambda: list[AccessRecord](),
        description="List of access records",
    )
    file_stats: dict[str, FileStatsEntry] = Field(
        default_factory=lambda: dict[str, FileStatsEntry](),
        description="Statistics by file",
    )
    co_access_patterns: dict[str, int] = Field(
        default_factory=lambda: dict[str, int](),
        description="Co-access pattern frequencies",
    )
    task_patterns: dict[str, TaskPatternEntry] = Field(
        default_factory=lambda: dict[str, TaskPatternEntry](),
        description="Task-based patterns",
    )
