"""
Unit tests for rollback helper modules.

Tests for:
- rollback_initialization.py
- rollback_history.py
- rollback_history_loader.py
- rollback_analysis.py
- version_snapshots.py
"""

# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cortex.refactoring.models import RefactoringStatus, RollbackRecordModel


class TestRollbackInitialization:
    """Tests for rollback_initialization module."""

    def test_generate_rollback_id(self) -> None:
        """Test generating a rollback ID."""
        from cortex.refactoring.rollback_initialization import generate_rollback_id

        # Arrange
        execution_id = "exec-123"

        # Act
        result = generate_rollback_id(execution_id)

        # Assert
        assert result.startswith("rollback-exec-123-")
        assert len(result) > len("rollback-exec-123-")

    def test_create_rollback_record(self) -> None:
        """Test creating a rollback record."""
        from cortex.refactoring.rollback_initialization import create_rollback_record

        # Arrange
        rollback_id = "rollback-exec-123-20260120123045"
        execution_id = "exec-123"
        preserve_manual_changes = True

        # Act
        record = create_rollback_record(
            rollback_id, execution_id, preserve_manual_changes
        )

        # Assert
        assert record.rollback_id == rollback_id
        assert record.execution_id == execution_id
        assert record.preserve_manual_edits is True
        assert record.created_at is not None

    def test_initialize_rollback(self) -> None:
        """Test initializing a rollback."""
        from cortex.refactoring.rollback_initialization import initialize_rollback

        # Arrange
        execution_id = "exec-456"
        preserve_manual_changes = False

        # Act
        rollback_id, record = initialize_rollback(execution_id, preserve_manual_changes)

        # Assert
        assert rollback_id.startswith("rollback-exec-456-")
        assert record.execution_id == execution_id
        assert record.preserve_manual_edits is False


class TestRollbackHistory:
    """Tests for rollback_history module."""

    def test_filter_rollbacks_by_date(self) -> None:
        """Test filtering rollbacks by date."""
        from cortex.refactoring.rollback_history import filter_rollbacks_by_date

        # Arrange
        now = datetime.now()
        old_date = (now - timedelta(days=10)).isoformat()
        recent_date = (now - timedelta(days=1)).isoformat()
        cutoff = now - timedelta(days=5)

        rollbacks = [
            RollbackRecordModel(
                rollback_id="old-1",
                execution_id="exec-1",
                created_at=old_date,
            ),
            RollbackRecordModel(
                rollback_id="recent-1",
                execution_id="exec-2",
                created_at=recent_date,
            ),
        ]

        # Act
        result = filter_rollbacks_by_date(rollbacks, cutoff)

        # Assert
        assert len(result) == 1
        assert result[0].rollback_id == "recent-1"

    def test_calculate_rollback_statistics(self) -> None:
        """Test calculating rollback statistics."""
        from cortex.refactoring.rollback_history import calculate_rollback_statistics

        # Arrange
        rollbacks = [
            RollbackRecordModel(
                rollback_id="r1",
                execution_id="e1",
                created_at=datetime.now().isoformat(),
                status=RefactoringStatus.COMPLETED,
            ),
            RollbackRecordModel(
                rollback_id="r2",
                execution_id="e2",
                created_at=datetime.now().isoformat(),
                status=RefactoringStatus.COMPLETED,
            ),
            RollbackRecordModel(
                rollback_id="r3",
                execution_id="e3",
                created_at=datetime.now().isoformat(),
                status=RefactoringStatus.FAILED,
            ),
        ]

        # Act
        stats = calculate_rollback_statistics(rollbacks)

        # Assert
        assert stats.total == 3
        assert stats.successful == 2
        assert stats.failed == 1
        assert stats.success_rate == pytest.approx(2 / 3)

    def test_calculate_rollback_statistics_empty(self) -> None:
        """Test statistics with empty list."""
        from cortex.refactoring.rollback_history import calculate_rollback_statistics

        # Act
        stats = calculate_rollback_statistics([])

        # Assert
        assert stats.total == 0
        assert stats.success_rate == 0.0

    def test_build_rollback_history_result(self) -> None:
        """Test building rollback history result."""
        from cortex.refactoring.rollback_history import (
            RollbackStatistics,
            build_rollback_history_result,
        )

        # Arrange
        rollbacks = [
            RollbackRecordModel(
                rollback_id="r1",
                execution_id="e1",
                created_at="2026-01-20T12:00:00",
            ),
        ]
        stats = RollbackStatistics(total=1, successful=1, failed=0, success_rate=1.0)

        # Act
        result = build_rollback_history_result(30, rollbacks, stats)

        # Assert
        assert result.time_range_days == 30
        assert result.total_rollbacks == 1
        assert len(result.rollbacks) == 1


class TestRollbackHistoryLoader:
    """Tests for rollback_history_loader module."""

    def test_load_rollbacks_file_not_found(self, tmp_path: Path) -> None:
        """Test loading rollbacks when file doesn't exist."""
        from cortex.refactoring.rollback_history_loader import load_rollbacks

        # Act
        result = load_rollbacks(tmp_path / "nonexistent.json")

        # Assert
        assert result == {}

    def test_load_rollbacks_valid_file(self, tmp_path: Path) -> None:
        """Test loading rollbacks from valid file."""
        from cortex.refactoring.rollback_history_loader import load_rollbacks

        # Arrange
        rollback_file = tmp_path / "rollbacks.json"
        data = {
            "rollbacks": {
                "rollback-1": {
                    "rollback_id": "rollback-1",
                    "execution_id": "exec-1",
                    "created_at": "2026-01-20T12:00:00",
                }
            }
        }
        _ = rollback_file.write_text(json.dumps(data))

        # Act
        result = load_rollbacks(rollback_file)

        # Assert
        assert "rollback-1" in result
        assert result["rollback-1"].execution_id == "exec-1"

    def test_load_rollbacks_invalid_json(self, tmp_path: Path) -> None:
        """Test loading corrupted rollback file."""
        from cortex.refactoring.rollback_history_loader import load_rollbacks

        # Arrange
        rollback_file = tmp_path / "rollbacks.json"
        _ = rollback_file.write_text("not valid json")

        # Act
        result = load_rollbacks(rollback_file)

        # Assert
        assert result == {}

    @pytest.mark.asyncio
    async def test_save_rollbacks(self, tmp_path: Path) -> None:
        """Test saving rollbacks to file."""
        from cortex.refactoring.rollback_history_loader import (
            load_rollbacks,
            save_rollbacks,
        )

        # Arrange
        rollback_file = tmp_path / "rollbacks.json"
        rollbacks = {
            "rollback-1": RollbackRecordModel(
                rollback_id="rollback-1",
                execution_id="exec-1",
                created_at="2026-01-20T12:00:00",
            )
        }

        # Act
        await save_rollbacks(rollback_file, rollbacks)
        loaded = load_rollbacks(rollback_file)

        # Assert
        assert "rollback-1" in loaded


class TestRollbackAnalysis:
    """Tests for rollback_analysis module."""

    @pytest.mark.asyncio
    async def test_analyze_rollback_impact_no_snapshot(self) -> None:
        """Test analysis when no snapshot found."""
        from cortex.refactoring.rollback_analysis import analyze_rollback_impact

        # Arrange
        async def find_no_snapshot(_: str) -> str | None:
            return None

        async def get_affected(_: str, __: str) -> list[str]:
            return []

        async def detect_conflicts(_: list[str], __: str) -> list[str]:
            return []

        # Act
        result = await analyze_rollback_impact(
            "exec-123",
            Path("/tmp"),
            find_no_snapshot,
            get_affected,
            detect_conflicts,
        )

        # Assert
        assert result.status == "error"
        assert "No snapshot found" in (result.message or "")

    @pytest.mark.asyncio
    async def test_analyze_rollback_impact_success(self, tmp_path: Path) -> None:
        """Test successful impact analysis."""
        from cortex.refactoring.rollback_analysis import analyze_rollback_impact

        # Arrange
        # Create test file
        test_file = tmp_path / "test.md"
        _ = test_file.write_text("test content")

        async def find_snapshot(_: str) -> str | None:
            return "snapshot-123"

        async def get_affected(_: str, __: str) -> list[str]:
            return ["test.md"]

        async def detect_conflicts(_: list[str], __: str) -> list[str]:
            return []

        # Act
        result = await analyze_rollback_impact(
            "exec-123",
            tmp_path,
            find_snapshot,
            get_affected,
            detect_conflicts,
        )

        # Assert
        assert result.status == "success"
        assert result.total_files == 1
        assert result.can_rollback_all is True

    @pytest.mark.asyncio
    async def test_analyze_rollback_impact_with_conflicts(self, tmp_path: Path) -> None:
        """Test impact analysis with conflicts."""
        from cortex.refactoring.rollback_analysis import analyze_rollback_impact

        # Arrange
        test_file = tmp_path / "test.md"
        _ = test_file.write_text("test content")

        async def find_snapshot(_: str) -> str | None:
            return "snapshot-123"

        async def get_affected(_: str, __: str) -> list[str]:
            return ["test.md"]

        async def detect_conflicts(_: list[str], __: str) -> list[str]:
            return ["test.md - File has been manually edited"]

        # Act
        result = await analyze_rollback_impact(
            "exec-123",
            tmp_path,
            find_snapshot,
            get_affected,
            detect_conflicts,
        )

        # Assert
        assert result.status == "success"
        assert result.conflicts == 1
        assert result.can_rollback_all is False


class TestVersionSnapshots:
    """Tests for version_snapshots module."""

    @pytest.mark.asyncio
    async def test_find_snapshot_for_execution_valid(self) -> None:
        """Test finding snapshot for valid execution ID."""
        from cortex.refactoring.version_snapshots import find_snapshot_for_execution

        # Act
        result = await find_snapshot_for_execution("exec-suggestion-20260120123045")

        # Assert
        assert result is not None
        assert "refactoring-" in result

    @pytest.mark.asyncio
    async def test_find_snapshot_for_execution_invalid(self) -> None:
        """Test finding snapshot for invalid execution ID."""
        from cortex.refactoring.version_snapshots import find_snapshot_for_execution

        # Act
        result = await find_snapshot_for_execution("invalid-id")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_find_snapshot_for_execution_short_parts(self) -> None:
        """Test finding snapshot with too few parts."""
        from cortex.refactoring.version_snapshots import find_snapshot_for_execution

        # Act
        result = await find_snapshot_for_execution("exec-only")

        # Assert - less than 3 parts after split
        assert result is None

    def test_find_snapshot_version_found(self) -> None:
        """Test finding version number for snapshot."""
        from cortex.refactoring.version_snapshots import find_snapshot_version

        # Arrange
        version_history: list[dict[str, object]] = [
            {"version": 1, "change_description": "Initial"},
            {"version": 2, "change_description": "Pre-refactoring snapshot: snap-123"},
            {"version": 3, "change_description": "Update"},
        ]

        # Act
        result = find_snapshot_version(version_history, "snap-123")

        # Assert
        assert result == 2

    def test_find_snapshot_version_not_found(self) -> None:
        """Test when snapshot version not found."""
        from cortex.refactoring.version_snapshots import find_snapshot_version

        # Arrange
        version_history: list[dict[str, object]] = [
            {"version": 1, "change_description": "Initial"},
        ]

        # Act
        result = find_snapshot_version(version_history, "snap-nonexistent")

        # Assert
        assert result is None

    def test_find_snapshot_version_invalid_version(self) -> None:
        """Test when version number is not an int."""
        from cortex.refactoring.version_snapshots import find_snapshot_version

        # Arrange
        version_history: list[dict[str, object]] = [
            {
                "version": "not-int",
                "change_description": "Pre-refactoring snapshot: snap-123",
            },
        ]

        # Act
        result = find_snapshot_version(version_history, "snap-123")

        # Assert - version is string, not int
        assert result is None

    @pytest.mark.asyncio
    async def test_get_version_history(self) -> None:
        """Test getting version history from metadata."""
        from cortex.refactoring.version_snapshots import get_version_history

        # Arrange
        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={
                "version_history": [
                    {"version": 1, "change_description": "Initial"},
                    {"version": 2, "change_description": "Update"},
                ]
            }
        )

        # Act
        result = await get_version_history("test.md", mock_index)

        # Assert
        assert result is not None
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_version_history_not_found(self) -> None:
        """Test getting version history when file not found."""
        from cortex.refactoring.version_snapshots import get_version_history

        # Arrange
        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(return_value=None)

        # Act
        result = await get_version_history("nonexistent.md", mock_index)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_version_history_not_list(self) -> None:
        """Test getting version history when not a list."""
        from cortex.refactoring.version_snapshots import get_version_history

        # Arrange
        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"version_history": "not a list"}
        )

        # Act
        result = await get_version_history("test.md", mock_index)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_affected_files_empty_snapshot(self) -> None:
        """Test getting affected files with empty snapshot."""
        from cortex.refactoring.version_snapshots import get_affected_files

        # Arrange
        mock_index = MagicMock()

        # Act
        result = await get_affected_files(Path("/tmp"), "exec-1", "", mock_index)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_affected_files_with_snapshot(self, tmp_path: Path) -> None:
        """Test getting affected files with valid snapshot."""
        from cortex.refactoring.version_snapshots import get_affected_files

        # Arrange
        # Create a test file
        test_file = tmp_path / "test.md"
        _ = test_file.write_text("# Test")

        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={
                "version_history": [
                    {
                        "version": 1,
                        "change_description": "Pre-refactoring snapshot: snap-123",
                    },
                ]
            }
        )

        # Act
        result = await get_affected_files(tmp_path, "exec-1", "snap-123", mock_index)

        # Assert
        assert "test.md" in result

    @pytest.mark.asyncio
    async def test_file_has_snapshot_no_metadata(self) -> None:
        """Test _file_has_snapshot with no metadata."""
        from cortex.refactoring.version_snapshots import _file_has_snapshot

        # Arrange
        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(return_value=None)

        # Act
        result = await _file_has_snapshot("test.md", "snap-123", mock_index)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_file_has_snapshot_not_list(self) -> None:
        """Test _file_has_snapshot when version_history is not a list."""
        from cortex.refactoring.version_snapshots import _file_has_snapshot

        # Arrange
        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"version_history": "not a list"}
        )

        # Act
        result = await _file_has_snapshot("test.md", "snap-123", mock_index)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_file_has_snapshot_non_dict_item(self) -> None:
        """Test _file_has_snapshot with non-dict items in list."""
        from cortex.refactoring.version_snapshots import _file_has_snapshot

        # Arrange
        mock_index = MagicMock()
        mock_index.get_file_metadata = AsyncMock(
            return_value={"version_history": ["not a dict", 123]}
        )

        # Act
        result = await _file_has_snapshot("test.md", "snap-123", mock_index)

        # Assert
        assert result is False
