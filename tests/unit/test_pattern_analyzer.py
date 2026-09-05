"""
Tests for pattern_analyzer.py - Pattern analysis functionality.

This test module covers:
- PatternAnalyzer initialization and session-log projection
- Access frequency analysis
- Co-access pattern detection
- Unused file identification
- Task pattern analysis
- Temporal pattern analysis
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cortex.analysis.pattern_analyzer import PatternAnalyzer
from cortex.analysis.pattern_types import (
    AccessRecord,
    FileStatsEntry,
    TaskPatternEntry,
    create_default_access_log,
)
from tests.helpers.session_log_fixtures import recent_stamp, write_session_log


class TestPatternAnalyzerInitialization:
    """Tests for PatternAnalyzer initialization and session-log projection."""

    def test_initializes_with_empty_log_when_no_session_data(
        self, temp_project_root: Path
    ):
        """Test initialization yields an empty log when no session logs exist."""
        # Arrange / Act
        analyzer = PatternAnalyzer(temp_project_root)

        # Assert
        assert analyzer.project_root == Path(temp_project_root)
        assert analyzer.access_data.version == "1.0"
        assert analyzer.access_data.accesses == []
        assert analyzer.access_data.file_stats == {}
        assert analyzer.access_data.co_access_patterns == {}
        assert analyzer.access_data.task_patterns == {}

    def test_projects_session_log_into_access_records(self, temp_project_root: Path):
        """Test each selected file of each call becomes one access record."""
        # Arrange
        _ = write_session_log(
            temp_project_root,
            "aaa",
            [
                (recent_stamp(20), "fix auth", ["a.md", "b.md"]),
                (recent_stamp(10), "write docs", ["b.md"]),
            ],
        )

        # Act
        analyzer = PatternAnalyzer(temp_project_root)

        # Assert
        assert len(analyzer.access_data.accesses) == 3
        assert analyzer.access_data.file_stats["b.md"].total_accesses == 2
        assert analyzer.access_data.file_stats["a.md"].total_accesses == 1

    def test_projection_records_sibling_files_as_context(self, temp_project_root: Path):
        """Test co-selected files of one call become each other's context."""
        # Arrange
        _ = write_session_log(
            temp_project_root, "bbb", [(recent_stamp(5), "task", ["a.md", "b.md"])]
        )

        # Act
        analyzer = PatternAnalyzer(temp_project_root)

        # Assert
        record_a = next(r for r in analyzer.access_data.accesses if r.file == "a.md")
        assert record_a.context_files == ["b.md"]
        assert analyzer.access_data.co_access_patterns == {"a.md|b.md": 1}

    def test_projection_matches_incremental_aggregation(self, temp_project_root: Path):
        """Test replayed aggregates match record-by-record aggregation."""
        # Arrange
        _ = write_session_log(
            temp_project_root,
            "ccc",
            [
                (recent_stamp(30), "one", ["a.md", "b.md"]),
                (recent_stamp(15), "two", ["b.md", "c.md"]),
            ],
        )
        analyzer = PatternAnalyzer(temp_project_root)
        expected_stats = {
            "a.md": 1,
            "b.md": 2,
            "c.md": 1,
        }

        # Act
        actual_stats = {
            path: stats.total_accesses
            for path, stats in analyzer.access_data.file_stats.items()
        }

        # Assert
        assert actual_stats == expected_stats
        assert analyzer.access_data.co_access_patterns == {
            "a.md|b.md": 1,
            "b.md|c.md": 1,
        }

    def test_projects_task_patterns_per_call(self, temp_project_root: Path):
        """Test each load_context call becomes one task pattern entry."""
        # Arrange
        _ = write_session_log(
            temp_project_root,
            "ddd",
            [
                (recent_stamp(20), "fix auth", ["a.md", "b.md"]),
                (recent_stamp(10), "write docs", ["c.md"]),
            ],
        )

        # Act
        analyzer = PatternAnalyzer(temp_project_root)

        # Assert
        patterns = analyzer.access_data.task_patterns
        assert set(patterns) == {"ddd:0", "ddd:1"}
        assert patterns["ddd:0"].description == "fix auth"
        assert patterns["ddd:0"].files == ["a.md", "b.md"]

    def test_tracking_disabled_yields_empty_log(self, temp_project_root: Path):
        """Test track_usage_patterns=False skips the projection entirely."""
        # Arrange
        _ = write_session_log(
            temp_project_root, "eee", [(recent_stamp(1), "task", ["a.md"])]
        )

        # Act
        analyzer = PatternAnalyzer(temp_project_root, track_usage_patterns=False)

        # Assert
        assert analyzer.access_data.accesses == []
        assert analyzer.access_data.file_stats == {}

    def test_task_tracking_disabled_keeps_file_stats(self, temp_project_root: Path):
        """Test track_task_patterns=False suppresses only task patterns."""
        # Arrange
        _ = write_session_log(
            temp_project_root, "fff", [(recent_stamp(1), "task", ["a.md"])]
        )

        # Act
        analyzer = PatternAnalyzer(temp_project_root, track_task_patterns=False)

        # Assert
        assert analyzer.access_data.task_patterns == {}
        assert analyzer.access_data.file_stats["a.md"].total_accesses == 1

    def test_ignores_corrupted_session_log(self, temp_project_root: Path):
        """Test a corrupted session log is skipped instead of raising."""
        # Arrange
        log_path = write_session_log(
            temp_project_root, "ggg", [(recent_stamp(1), "task", ["a.md"])]
        )
        _ = log_path.write_text("{not json", encoding="utf-8")

        # Act
        analyzer = PatternAnalyzer(temp_project_root)

        # Assert
        assert analyzer.access_data.accesses == []

    def test_ignores_schema_invalid_session_log(self, temp_project_root: Path):
        """Test a schema-invalid session log is skipped instead of raising."""
        # Arrange
        log_path = write_session_log(
            temp_project_root, "hhh", [(recent_stamp(1), "task", ["a.md"])]
        )
        _ = log_path.write_text(json.dumps({"unexpected": True}), encoding="utf-8")

        # Act
        analyzer = PatternAnalyzer(temp_project_root)

        # Assert
        assert analyzer.access_data.accesses == []

    def test_excludes_calls_outside_window(self, temp_project_root: Path):
        """Test calls older than the pattern window are not projected."""
        # Arrange
        old_stamp = (datetime.now() - timedelta(days=90)).isoformat(timespec="minutes")
        _ = write_session_log(
            temp_project_root,
            "iii",
            [(old_stamp, "ancient", ["old.md"]), (recent_stamp(1), "now", ["new.md"])],
        )

        # Act
        analyzer = PatternAnalyzer(temp_project_root, pattern_window_days=30)

        # Assert
        assert set(analyzer.access_data.file_stats) == {"new.md"}

    def test_empty_selected_files_contributes_nothing(self, temp_project_root: Path):
        """Test a call that selected no files yields no records or co-access edges."""
        # Arrange
        _ = write_session_log(
            temp_project_root, "jjj", [(recent_stamp(1), "empty", [])]
        )

        # Act
        analyzer = PatternAnalyzer(temp_project_root)

        # Assert
        assert analyzer.access_data.accesses == []
        assert analyzer.access_data.co_access_patterns == {}


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


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_create_default_access_log(self):
        """Test creates an empty access log with default values."""
        # Arrange / Act
        log = create_default_access_log()

        # Assert
        assert log.version == "1.0"
        assert log.accesses == []
        assert log.file_stats == {}
        assert log.co_access_patterns == {}
        assert log.task_patterns == {}
