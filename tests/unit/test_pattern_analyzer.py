"""
Tests for pattern_analyzer.py - Pattern analysis functionality.

This test module covers:
- PatternAnalyzer initialization and access log management
- File access recording and tracking
- Access frequency analysis
- Co-access pattern detection
- Unused file identification
- Task pattern analysis
- Temporal pattern analysis
- Data cleanup and maintenance
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cortex.analysis.pattern_analyzer import (
    PatternAnalyzer,
    create_default_access_log,
    normalize_access_log,
)
from cortex.analysis.pattern_types import (
    AccessLog,
    AccessRecord,
    FileStatsEntry,
    TaskPatternEntry,
)


class TestPatternAnalyzerInitialization:
    """Tests for PatternAnalyzer initialization."""

    def test_initializes_with_empty_log_when_no_file(self, temp_project_root: Path):
        """Test initialization creates empty log when file doesn't exist."""
        # Arrange
        project_root = temp_project_root

        # Act
        analyzer = PatternAnalyzer(project_root)

        # Assert
        assert analyzer.project_root == Path(project_root)
        assert (
            analyzer.access_log_path == Path(project_root) / ".cortex/access-log.json"
        )
        assert analyzer.access_data.version == "1.0"
        assert analyzer.access_data.accesses == []
        assert analyzer.access_data.file_stats == {}
        assert analyzer.access_data.co_access_patterns == {}
        assert analyzer.access_data.task_patterns == {}

    def test_loads_existing_access_log(self, temp_project_root: Path):
        """Test loads existing access log from disk."""
        # Arrange
        project_root = temp_project_root
        log_path = Path(project_root) / ".cortex/access-log.json"

        # Create sample log
        sample_log = {
            "version": "1.0",
            "accesses": [
                {
                    "timestamp": "2025-01-01T12:00:00Z",
                    "file": "test.md",
                    "task_id": "task1",
                    "task_description": "Test task",
                    "context_files": ["other.md"],
                }
            ],
            "file_stats": {
                "test.md": {
                    "total_accesses": 1,
                    "first_access": "2025-01-01T12:00:00Z",
                    "last_access": "2025-01-01T12:00:00Z",
                    "tasks": ["task1"],
                }
            },
            "co_access_patterns": {"other.md|test.md": 1},
            "task_patterns": {
                "task1": {
                    "description": "Test task",
                    "files": ["test.md"],
                    "timestamp": "2025-01-01T12:00:00Z",
                }
            },
        }

        with open(log_path, "w") as f:
            json.dump(sample_log, f)

        # Act
        analyzer = PatternAnalyzer(project_root)

        # Assert
        assert len(analyzer.access_data.accesses) == 1
        assert "test.md" in analyzer.access_data.file_stats
        assert analyzer.access_data.co_access_patterns["other.md|test.md"] == 1

    def test_handles_corrupted_log_file(self, temp_project_root: Path):
        """Test handles corrupted access log gracefully."""
        # Arrange
        project_root = temp_project_root
        log_path = Path(project_root) / ".cortex/access-log.json"

        # Create corrupted log
        with open(log_path, "w") as f:
            _ = f.write("{ invalid json")

        # Act
        analyzer = PatternAnalyzer(project_root)

        # Assert
        assert analyzer.access_data.version == "1.0"
        assert analyzer.access_data.accesses == []
        # Backup should exist
        backup_path = Path(project_root) / ".cortex/access-log.json.backup"
        assert backup_path.exists()


class TestAccessRecording:
    """Tests for recording file access events."""

    @pytest.mark.asyncio
    async def test_records_basic_access(self, temp_project_root: Path):
        """Test records basic file access without task info."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        file_path = "test.md"

        # Act
        await analyzer.record_access(file_path)

        # Assert
        assert len(analyzer.access_data.accesses) == 1
        access = analyzer.access_data.accesses[0]
        assert access.file == file_path
        assert access.task_id is None
        assert access.task_description is None
        assert access.context_files == []
        assert access.timestamp

    @pytest.mark.asyncio
    async def test_records_access_with_task_info(self, temp_project_root: Path):
        """Test records access with task information."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        file_path = "test.md"
        task_id = "task123"
        task_description = "Fix bug in parser"

        # Act
        await analyzer.record_access(
            file_path, task_id=task_id, task_description=task_description
        )

        # Assert
        access = analyzer.access_data.accesses[0]
        assert access.file == file_path
        assert access.task_id == task_id
        assert access.task_description == task_description

    @pytest.mark.asyncio
    async def test_records_access_with_context_files(self, temp_project_root: Path):
        """Test records access with context files."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        file_path = "test.md"
        context_files = ["other1.md", "other2.md"]

        # Act
        await analyzer.record_access(file_path, context_files=context_files)

        # Assert
        access = analyzer.access_data.accesses[0]
        assert access.context_files == context_files

    @pytest.mark.asyncio
    async def test_updates_file_stats(self, temp_project_root: Path):
        """Test updates file statistics on access."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        file_path = "test.md"

        # Act
        await analyzer.record_access(file_path)
        await analyzer.record_access(file_path)

        # Assert
        stats = analyzer.access_data.file_stats[file_path]
        assert stats.total_accesses == 2
        assert stats.first_access
        assert stats.last_access

    @pytest.mark.asyncio
    async def test_updates_co_access_patterns(self, temp_project_root: Path):
        """Test updates co-access patterns."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        file_path = "test.md"
        context_files = ["other.md"]

        # Act
        await analyzer.record_access(file_path, context_files=context_files)
        await analyzer.record_access(file_path, context_files=context_files)

        # Assert
        key = "other.md|test.md"  # Sorted alphabetically
        assert analyzer.access_data.co_access_patterns[key] == 2

    @pytest.mark.asyncio
    async def test_updates_task_patterns(self, temp_project_root: Path):
        """Test updates task patterns."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        file_path = "test.md"
        task_id = "task1"
        task_description = "Test task"

        # Act
        await analyzer.record_access(
            file_path, task_id=task_id, task_description=task_description
        )
        await analyzer.record_access("other.md", task_id=task_id)

        # Assert
        pattern = analyzer.access_data.task_patterns[task_id]
        assert pattern.description == task_description
        assert len(pattern.files) == 2
        assert file_path in pattern.files
        assert "other.md" in pattern.files

    @pytest.mark.asyncio
    async def test_persists_access_log(self, temp_project_root: Path):
        """Test persists access log to disk."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        file_path = "test.md"

        # Act
        await analyzer.record_access(file_path)

        # Assert
        log_path = Path(temp_project_root) / ".cortex/access-log.json"
        assert log_path.exists()

        with open(log_path) as f:
            data = json.load(f)
        assert len(data["accesses"]) == 1


class TestAccessFrequency:
    """Tests for access frequency analysis."""

    @pytest.mark.asyncio
    async def test_gets_access_frequency_for_time_range(self, temp_project_root: Path):
        """Test gets access frequency within time range."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create accesses - some recent, some old
        analyzer.access_data.accesses = [
            AccessRecord(
                timestamp=(now - timedelta(days=5)).isoformat(),
                file="recent.md",
                task_id=None,
                task_description=None,
                context_files=[],
            ),
            AccessRecord(
                timestamp=(now - timedelta(days=50)).isoformat(),
                file="old.md",
                task_id=None,
                task_description=None,
                context_files=[],
            ),
        ]

        # Act
        result = await analyzer.get_access_frequency(time_range_days=30)

        # Assert
        assert "recent.md" in result
        assert "old.md" not in result

    @pytest.mark.asyncio
    async def test_filters_by_min_access_count(self, temp_project_root: Path):
        """Test filters by minimum access count."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create multiple accesses
        for i in range(5):
            analyzer.access_data.accesses.append(
                AccessRecord(
                    timestamp=(now - timedelta(days=i)).isoformat(),
                    file="frequent.md",
                    task_id=None,
                    task_description=None,
                    context_files=[],
                )
            )

        analyzer.access_data.accesses.append(
            AccessRecord(
                timestamp=(now - timedelta(days=1)).isoformat(),
                file="rare.md",
                task_id=None,
                task_description=None,
                context_files=[],
            )
        )

        # Act
        result = await analyzer.get_access_frequency(min_access_count=3)

        # Assert
        assert "frequent.md" in result
        assert "rare.md" not in result

    @pytest.mark.asyncio
    async def test_calculates_access_statistics(self, temp_project_root: Path):
        """Test calculates access statistics."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create accesses with task IDs
        for i in range(3):
            analyzer.access_data.accesses.append(
                AccessRecord(
                    timestamp=(now - timedelta(days=i)).isoformat(),
                    file="test.md",
                    task_id=f"task{i}",
                    task_description=None,
                    context_files=[],
                )
            )

        # Act
        result = await analyzer.get_access_frequency(time_range_days=30)

        # Assert
        stats = result["test.md"]
        assert stats["access_count"] == 3
        assert stats["task_count"] == 3
        assert "last_access" in stats
        assert "avg_accesses_per_day" in stats


class TestCoAccessPatterns:
    """Tests for co-access pattern detection."""

    @pytest.mark.asyncio
    async def test_gets_co_access_patterns_from_stored_data(
        self, temp_project_root: Path
    ):
        """Test gets co-access patterns from stored data."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        analyzer.access_data.co_access_patterns = {
            "file1.md|file2.md": 5,
            "file1.md|file3.md": 2,
        }

        # Act
        result = await analyzer.get_co_access_patterns(min_co_access_count=3)

        # Assert
        assert len(result) == 1
        assert result[0].file_1 == "file1.md"
        assert result[0].file_2 == "file2.md"
        assert result[0].co_access_count == 5

    @pytest.mark.asyncio
    async def test_calculates_co_access_from_recent_tasks(
        self, temp_project_root: Path
    ):
        """Test calculates co-access patterns from recent tasks."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create task accesses
        for file in ["file1.md", "file2.md"]:
            analyzer.access_data.accesses.append(
                AccessRecord(
                    timestamp=(now - timedelta(days=5)).isoformat(),
                    file=file,
                    task_id="task1",
                    task_description=None,
                    context_files=[],
                )
            )

        # Act
        result = await analyzer.get_co_access_patterns(
            min_co_access_count=1, time_range_days=30
        )

        # Assert
        assert len(result) == 1
        assert result[0].co_access_count == 1

    @pytest.mark.asyncio
    async def test_assigns_correlation_strength(self, temp_project_root: Path):
        """Test assigns correlation strength based on count."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        analyzer.access_data.co_access_patterns = {
            "a.md|b.md": 15,  # high
            "c.md|d.md": 7,  # medium
            "e.md|f.md": 3,  # low
        }

        # Act
        result = await analyzer.get_co_access_patterns(min_co_access_count=1)

        # Assert
        assert result[0].correlation_strength == "high"
        assert result[1].correlation_strength == "medium"
        assert result[2].correlation_strength == "low"

    @pytest.mark.asyncio
    async def test_sorts_by_count_descending(self, temp_project_root: Path):
        """Test sorts results by count descending."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        analyzer.access_data.co_access_patterns = {
            "a.md|b.md": 3,
            "c.md|d.md": 10,
            "e.md|f.md": 5,
        }

        # Act
        result = await analyzer.get_co_access_patterns(min_co_access_count=1)

        # Assert
        assert result[0].co_access_count == 10
        assert result[1].co_access_count == 5
        assert result[2].co_access_count == 3


class TestUnusedFiles:
    """Tests for unused file identification."""

    @pytest.mark.asyncio
    async def test_identifies_never_accessed_files(self, temp_project_root: Path):
        """Test identifies files that were never accessed."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        analyzer.access_data.file_stats = {
            "never.md": FileStatsEntry(
                total_accesses=0, first_access="", last_access="", tasks=[]
            )
        }

        # Act
        result = await analyzer.get_unused_files(time_range_days=90)

        # Assert
        assert len(result) == 1
        assert result[0].file == "never.md"
        assert result[0].status == "never_accessed"

    @pytest.mark.asyncio
    async def test_identifies_stale_files(self, temp_project_root: Path):
        """Test identifies files not accessed recently."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)
        old_access = (now - timedelta(days=100)).isoformat()

        analyzer.access_data.file_stats = {
            "stale.md": FileStatsEntry(
                total_accesses=5,
                first_access=old_access,
                last_access=old_access,
                tasks=[],
            )
        }

        # Act
        result = await analyzer.get_unused_files(time_range_days=90)

        # Assert
        assert len(result) == 1
        assert result[0].file == "stale.md"
        assert result[0].status == "stale"
        days_since = result[0].days_since_access
        assert days_since is not None and days_since >= 90

    @pytest.mark.asyncio
    async def test_excludes_recently_accessed_files(self, temp_project_root: Path):
        """Test excludes files accessed within time range."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)
        recent_access = (now - timedelta(days=30)).isoformat()

        analyzer.access_data.file_stats = {
            "recent.md": FileStatsEntry(
                total_accesses=5,
                first_access=recent_access,
                last_access=recent_access,
                tasks=[],
            )
        }

        # Act
        result = await analyzer.get_unused_files(time_range_days=90)

        # Assert
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_sorts_by_days_since_access(self, temp_project_root: Path):
        """Test sorts results by days since access (most stale first)."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        analyzer.access_data.file_stats = {
            "file1.md": FileStatsEntry(
                total_accesses=1,
                first_access=(now - timedelta(days=150)).isoformat(),
                last_access=(now - timedelta(days=150)).isoformat(),
                tasks=[],
            ),
            "file2.md": FileStatsEntry(
                total_accesses=1,
                first_access=(now - timedelta(days=100)).isoformat(),
                last_access=(now - timedelta(days=100)).isoformat(),
                tasks=[],
            ),
        }

        # Act
        result = await analyzer.get_unused_files(time_range_days=90)

        # Assert
        assert len(result) == 2
        assert result[0].file == "file1.md"  # Older first
        assert result[1].file == "file2.md"


class TestTaskPatterns:
    """Tests for task pattern analysis."""

    @pytest.mark.asyncio
    async def test_gets_all_task_patterns(self, temp_project_root: Path):
        """Test gets all task patterns."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC).isoformat()

        analyzer.access_data.task_patterns = {
            "task1": TaskPatternEntry(
                description="Fix bug",
                files=["file1.md", "file2.md"],
                timestamp=now,
            ),
            "task2": TaskPatternEntry(
                description="Add feature",
                files=["file3.md"],
                timestamp=now,
            ),
        }

        # Act
        result = await analyzer.get_task_patterns()

        # Assert
        assert len(result) == 2
        assert result[0].task_id in ["task1", "task2"]

    @pytest.mark.asyncio
    async def test_filters_task_patterns_by_time_range(self, temp_project_root: Path):
        """Test filters task patterns by time range."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        analyzer.access_data.task_patterns = {
            "recent": TaskPatternEntry(
                description="Recent task",
                files=["file1.md"],
                timestamp=(now - timedelta(days=5)).isoformat(),
            ),
            "old": TaskPatternEntry(
                description="Old task",
                files=["file2.md"],
                timestamp=(now - timedelta(days=50)).isoformat(),
            ),
        }

        # Act
        result = await analyzer.get_task_patterns(time_range_days=30)

        # Assert
        assert len(result) == 1
        assert result[0].task_id == "recent"

    @pytest.mark.asyncio
    async def test_includes_file_count_and_list(self, temp_project_root: Path):
        """Test includes file count and list in results."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC).isoformat()

        analyzer.access_data.task_patterns = {
            "task1": TaskPatternEntry(
                description="Test task",
                files=["file1.md", "file2.md", "file3.md"],
                timestamp=now,
            )
        }

        # Act
        result = await analyzer.get_task_patterns()

        # Assert
        pattern = result[0]
        assert pattern.file_count == 3
        assert len(pattern.files) == 3

    @pytest.mark.asyncio
    async def test_sorts_by_timestamp_descending(self, temp_project_root: Path):
        """Test sorts results by timestamp (most recent first)."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        analyzer.access_data.task_patterns = {
            "task1": TaskPatternEntry(
                description="Older",
                files=["file1.md"],
                timestamp=(now - timedelta(days=10)).isoformat(),
            ),
            "task2": TaskPatternEntry(
                description="Newer",
                files=["file2.md"],
                timestamp=(now - timedelta(days=5)).isoformat(),
            ),
        }

        # Act
        result = await analyzer.get_task_patterns()

        # Assert
        assert result[0].task_id == "task2"  # Newer first
        assert result[1].task_id == "task1"


class TestTemporalPatterns:
    """Tests for temporal pattern analysis."""

    @pytest.mark.asyncio
    async def test_analyzes_hourly_distribution(self, temp_project_root: Path):
        """Test analyzes hourly access distribution."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create accesses at different hours
        for hour in [9, 9, 14, 14, 14]:
            dt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            analyzer.access_data.accesses.append(
                AccessRecord(
                    timestamp=dt.isoformat(),
                    file="test.md",
                    task_id=None,
                    task_description=None,
                    context_files=[],
                )
            )

        # Act
        result = await analyzer.get_temporal_patterns(time_range_days=30)

        # Assert
        hourly = result.hourly_distribution
        assert hourly[9] == 2
        assert hourly[14] == 3

    @pytest.mark.asyncio
    async def test_analyzes_daily_distribution(self, temp_project_root: Path):
        """Test analyzes daily access distribution."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create accesses on different days
        for day_offset in [0, 0, 1, 1, 1]:
            dt = now - timedelta(days=day_offset)
            analyzer.access_data.accesses.append(
                AccessRecord(
                    timestamp=dt.isoformat(),
                    file="test.md",
                    task_id=None,
                    task_description=None,
                    context_files=[],
                )
            )

        # Act
        result = await analyzer.get_temporal_patterns(time_range_days=30)

        # Assert
        assert len(result.daily_distribution) >= 2

    @pytest.mark.asyncio
    async def test_identifies_peak_hour(self, temp_project_root: Path):
        """Test identifies peak access hour."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create more accesses at hour 14
        for hour, count in [(9, 2), (14, 5), (16, 1)]:
            for _ in range(count):
                dt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                analyzer.access_data.accesses.append(
                    AccessRecord(
                        timestamp=dt.isoformat(),
                        file="test.md",
                        task_id=None,
                        task_description=None,
                        context_files=[],
                    )
                )

        # Act
        result = await analyzer.get_temporal_patterns(time_range_days=30)

        # Assert
        assert result.peak_hour == 14

    @pytest.mark.asyncio
    async def test_calculates_average_accesses_per_day(self, temp_project_root: Path):
        """Test calculates average accesses per day."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create 10 accesses
        for _ in range(10):
            analyzer.access_data.accesses.append(
                AccessRecord(
                    timestamp=now.isoformat(),
                    file="test.md",
                    task_id=None,
                    task_description=None,
                    context_files=[],
                )
            )

        # Act
        result = await analyzer.get_temporal_patterns(time_range_days=5)

        # Assert
        assert result.avg_accesses_per_day > 0


class TestDataCleanup:
    """Tests for old data cleanup."""

    @pytest.mark.asyncio
    async def test_removes_old_accesses(self, temp_project_root: Path):
        """Test removes old access records."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        # Create old and recent accesses
        analyzer.access_data.accesses = [
            AccessRecord(
                timestamp=(now - timedelta(days=200)).isoformat(),
                file="old.md",
                task_id=None,
                task_description=None,
                context_files=[],
            ),
            AccessRecord(
                timestamp=(now - timedelta(days=10)).isoformat(),
                file="recent.md",
                task_id=None,
                task_description=None,
                context_files=[],
            ),
        ]

        # Act
        result = await analyzer.cleanup_old_data(keep_days=180)

        # Assert
        assert result["removed_accesses"] == 1
        assert result["remaining_accesses"] == 1
        assert len(analyzer.access_data.accesses) == 1

    @pytest.mark.asyncio
    async def test_removes_old_task_patterns(self, temp_project_root: Path):
        """Test removes old task patterns."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        analyzer.access_data.task_patterns = {
            "old_task": TaskPatternEntry(
                description="Old",
                files=["file.md"],
                timestamp=(now - timedelta(days=200)).isoformat(),
            ),
            "recent_task": TaskPatternEntry(
                description="Recent",
                files=["file.md"],
                timestamp=(now - timedelta(days=10)).isoformat(),
            ),
        }

        # Act
        result = await analyzer.cleanup_old_data(keep_days=180)

        # Assert
        assert result["remaining_tasks"] == 1
        assert "recent_task" in analyzer.access_data.task_patterns
        assert "old_task" not in analyzer.access_data.task_patterns

    @pytest.mark.asyncio
    async def test_persists_cleaned_data(self, temp_project_root: Path):
        """Test persists cleaned data to disk."""
        # Arrange
        analyzer = PatternAnalyzer(temp_project_root)
        now = datetime.now(UTC)

        analyzer.access_data.accesses = [
            AccessRecord(
                timestamp=(now - timedelta(days=200)).isoformat(),
                file="old.md",
                task_id=None,
                task_description=None,
                context_files=[],
            )
        ]

        # Act
        _ = await analyzer.cleanup_old_data(keep_days=180)

        # Assert
        log_path = Path(temp_project_root) / ".cortex/access-log.json"
        with open(log_path) as f:
            data = json.load(f)
        assert len(data["accesses"]) == 0


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_create_default_access_log(self):
        """Test creates default access log structure."""
        # Act
        log = create_default_access_log()

        # Assert
        assert isinstance(log, AccessLog)
        assert log.version == "1.0"
        assert log.accesses == []
        assert log.file_stats == {}
        assert log.co_access_patterns == {}
        assert log.task_patterns == {}

    def test_normalize_access_log_with_valid_data(self):
        """Test normalizes valid access log data."""
        # Arrange
        raw_data = {
            "version": "1.0",
            "accesses": [
                {
                    "timestamp": "2025-01-01T12:00:00Z",
                    "file": "test.md",
                    "task_id": "task1",
                    "task_description": "Test",
                    "context_files": ["other.md"],
                }
            ],
            "file_stats": {
                "test.md": {
                    "total_accesses": 1,
                    "first_access": "2025-01-01T12:00:00Z",
                    "last_access": "2025-01-01T12:00:00Z",
                    "tasks": ["task1"],
                }
            },
            "co_access_patterns": {"other.md|test.md": 1},
            "task_patterns": {
                "task1": {
                    "description": "Test",
                    "files": ["test.md"],
                    "timestamp": "2025-01-01T12:00:00Z",
                }
            },
        }

        # Act
        log = normalize_access_log(raw_data)

        # Assert
        assert isinstance(log, AccessLog)
        assert log.version == "1.0"
        assert len(log.accesses) == 1
        assert "test.md" in log.file_stats

    def test_normalize_access_log_with_invalid_data(self):
        """Test handles invalid data gracefully."""
        # Arrange
        raw_data = "not a dict"

        # Act
        log = normalize_access_log(raw_data)

        # Assert
        assert isinstance(log, AccessLog)
        assert log.version == "1.0"
        assert log.accesses == []
