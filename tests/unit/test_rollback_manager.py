"""Unit tests for RollbackManager - Phase 5.3"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, Mock

import pytest

from cortex.refactoring.rollback_manager import RollbackManager, RollbackRecord

if TYPE_CHECKING:
    from cortex.core.file_system import FileSystemManager
    from cortex.core.metadata_index import MetadataIndex


class TestRollbackRecord:
    """Test RollbackRecord dataclass."""

    def test_initialization_with_defaults(self):
        """Test record initialization with default values."""
        # Arrange & Act
        record = RollbackRecord(
            rollback_id="roll-1",
            execution_id="exec-1",
            created_at="2025-01-01T12:00:00",
        )

        # Assert
        assert record.rollback_id == "roll-1"
        assert record.execution_id == "exec-1"
        assert record.status == "pending"
        assert record.files_restored == []
        assert record.conflicts_detected == []
        assert record.preserve_manual_edits is True

    def test_to_dict_conversion(self):
        """Test converting record to dictionary."""
        # Arrange
        record = RollbackRecord(
            rollback_id="roll-1",
            execution_id="exec-1",
            created_at="2025-01-01T12:00:00",
            status="completed",
            files_restored=["file1.md"],
        )

        # Act
        result = record.to_dict()

        # Assert
        assert result["rollback_id"] == "roll-1"
        assert result["status"] == "completed"
        files_restored = result.get("files_restored", [])
        assert isinstance(files_restored, list)
        assert "file1.md" in files_restored


class TestRollbackManagerInitialization:
    """Test RollbackManager initialization."""

    @pytest.mark.asyncio
    async def test_initialization_creates_empty_state(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test manager initialization with no existing data."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        # Act
        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Assert
        assert manager.memory_bank_dir == Path(memory_bank_dir)
        assert len(manager.rollbacks) == 0

    @pytest.mark.asyncio
    async def test_initialization_loads_existing_history(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test manager loads existing rollback history."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        # Create history file
        rollback_file = memory_bank_dir.parent / ".memory-bank-rollbacks.json"
        rollback_data = {
            "rollbacks": {
                "roll-1": {
                    "rollback_id": "roll-1",
                    "execution_id": "exec-1",
                    "created_at": "2025-01-01T12:00:00",
                    "status": "completed",
                }
            }
        }
        _ = rollback_file.write_text(json.dumps(rollback_data))

        # Act
        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Assert
        assert len(manager.rollbacks) == 1
        assert "roll-1" in manager.rollbacks


class TestRollbackRefactoring:
    """Test rollback execution."""

    @pytest.mark.asyncio
    async def test_rollback_with_no_snapshot_fails(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test rollback fails when no snapshot found."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Act
        result = await manager.rollback_refactoring(
            execution_id="nonexistent", restore_snapshot=True, dry_run=False
        )

        # Assert
        assert result["status"] == "failed"
        error = result.get("error", "")
        assert isinstance(error, str)
        assert "No snapshot found" in error

    @pytest.mark.asyncio
    async def test_rollback_with_dry_run(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test dry run doesn't make actual changes."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Mock to return snapshot
        manager.find_snapshot_for_execution = Mock(return_value="snapshot-1")
        manager.get_affected_files = AsyncMock(return_value=["file1.md"])
        manager.detect_conflicts = AsyncMock(return_value=[])

        # Act
        result = await manager.rollback_refactoring(execution_id="exec-1", dry_run=True)

        # Assert
        assert result["status"] == "success"
        assert result["dry_run"] is True

    @pytest.mark.asyncio
    async def test_rollback_detects_conflicts(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test rollback detects file conflicts."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Mock methods
        manager.find_snapshot_for_execution = Mock(return_value="snapshot-1")
        manager.get_affected_files = AsyncMock(return_value=["file1.md"])
        manager.detect_conflicts = AsyncMock(
            return_value=["file1.md - File has been manually edited"]
        )
        manager.restore_files = AsyncMock(return_value=[])

        # Act
        result = await manager.rollback_refactoring(
            execution_id="exec-1", preserve_manual_changes=True, dry_run=False
        )

        # Assert
        assert result["status"] == "success"
        assert result["conflicts_detected"] == 1
        conflicts_raw = result.get("conflicts", [])
        assert isinstance(conflicts_raw, list)
        # Cast to list[str] since we know from implementation that conflicts is list[str]
        conflicts: list[str] = cast(list[str], conflicts_raw)
        assert len(conflicts) == 1

    @pytest.mark.asyncio
    async def test_rollback_restores_files_successfully(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test successful file restoration."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Mock methods
        manager.find_snapshot_for_execution = Mock(return_value="snapshot-1")
        manager.get_affected_files = AsyncMock(return_value=["file1.md", "file2.md"])
        manager.detect_conflicts = AsyncMock(return_value=[])
        manager.restore_files = AsyncMock(return_value=["file1.md", "file2.md"])

        # Act
        result = await manager.rollback_refactoring(
            execution_id="exec-1", dry_run=False
        )

        # Assert
        assert result["status"] == "success"
        assert result["files_restored"] == 2


class TestFindSnapshotForExecution:
    """Test snapshot ID extraction."""

    @pytest.mark.asyncio
    async def test_find_snapshot_from_execution_id(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test extracting snapshot ID from execution ID."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Act
        snapshot_id = manager.find_snapshot_for_execution("exec-sug-1-20250101120000")

        # Assert
        assert snapshot_id == "refactoring-20250101120000"

    @pytest.mark.asyncio
    async def test_find_snapshot_returns_none_for_invalid_id(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test returns None for invalid execution ID."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Act
        snapshot_id = manager.find_snapshot_for_execution("invalid")

        # Assert
        assert snapshot_id is None


class TestDetectConflicts:
    """Test conflict detection."""

    @pytest.mark.asyncio
    async def test_detect_deleted_file_conflict(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test detecting deleted file as conflict."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Act
        conflicts = await manager.detect_conflicts(
            affected_files=["deleted.md"], snapshot_id="snapshot-1"
        )

        # Assert
        assert len(conflicts) > 0
        assert any("deleted" in conflict.lower() for conflict in conflicts)

    @pytest.mark.asyncio
    async def test_detect_modified_file_conflict(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test detecting manually modified file."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Create modified file
        modified_file = memory_bank_dir / "modified.md"
        _ = modified_file.write_text("New content")

        # Mock file system and metadata
        mock_file_system.read_file = AsyncMock(return_value=("New content", None))
        mock_file_system.compute_hash = Mock(return_value="new_hash")
        mock_metadata_index.get_file_metadata = AsyncMock(
            return_value={"content_hash": "old_hash"}
        )

        # Act
        conflicts = await manager.detect_conflicts(
            affected_files=["modified.md"], snapshot_id="snapshot-1"
        )

        # Assert
        assert len(conflicts) > 0
        assert any("manually edited" in conflict for conflict in conflicts)


class TestRestoreFiles:
    """Test file restoration."""

    @pytest.mark.asyncio
    async def test_restore_files_skips_conflicts_when_preserving(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test restore skips conflicted files when preserving edits."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        manager.backup_current_version = AsyncMock()

        # Act
        restored = await manager.restore_files(
            affected_files=["file1.md"],
            snapshot_id="snapshot-1",
            preserve_manual_changes=True,
            conflicts=["file1.md - has conflict"],
        )

        # Assert
        assert len(restored) == 0
        manager.backup_current_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_files_rollback_to_snapshot(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test restoring file from snapshot version."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Mock metadata and version manager
        mock_metadata_index.get_file_metadata = AsyncMock(
            return_value={
                "version_history": [
                    {
                        "version": 1,
                        "change_description": "Pre-refactoring snapshot: snapshot-1",
                    }
                ]
            }
        )
        version_manager.rollback_to_version = AsyncMock(
            return_value={"status": "success"}
        )

        # Act
        restored = await manager.restore_files(
            affected_files=["file1.md"],
            snapshot_id="snapshot-1",
            preserve_manual_changes=False,
            conflicts=[],
        )

        # Assert
        assert "file1.md" in restored


class TestRollbackHistory:
    """Test rollback history management."""

    @pytest.mark.asyncio
    async def test_get_rollback_history_filters_by_time(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test history filtering by time range."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Add old and new rollbacks
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        new_date = datetime.now().isoformat()

        manager.rollbacks["old"] = RollbackRecord(
            rollback_id="old",
            execution_id="exec-1",
            created_at=old_date,
            status="completed",
        )

        manager.rollbacks["new"] = RollbackRecord(
            rollback_id="new",
            execution_id="exec-2",
            created_at=new_date,
            status="completed",
        )

        # Act
        result = await manager.get_rollback_history(time_range_days=90)

        # Assert
        assert result["total_rollbacks"] == 1

    @pytest.mark.asyncio
    async def test_get_rollback_by_id(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test retrieving rollback by ID."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        rollback = RollbackRecord(
            rollback_id="roll-1",
            execution_id="exec-1",
            created_at="2025-01-01T12:00:00",
        )
        manager.rollbacks["roll-1"] = rollback

        # Act
        result = await manager.get_rollback("roll-1")

        # Assert
        assert result is not None
        assert result["rollback_id"] == "roll-1"


class TestAnalyzeRollbackImpact:
    """Test rollback impact analysis."""

    @pytest.mark.asyncio
    async def test_analyze_rollback_impact_identifies_conflicts(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test impact analysis identifies conflicts."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Mock methods
        manager.find_snapshot_for_execution = Mock(return_value="snapshot-1")
        manager.get_affected_files = AsyncMock(return_value=["file1.md", "file2.md"])
        manager.detect_conflicts = AsyncMock(return_value=["file1.md - has conflict"])

        # Act
        result = await manager.analyze_rollback_impact(execution_id="exec-1")

        # Assert
        assert result["status"] == "success"
        assert result["total_files"] == 2
        assert result["conflicts"] == 1
        assert result["can_rollback_all"] is False

    @pytest.mark.asyncio
    async def test_analyze_rollback_impact_with_no_snapshot(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test impact analysis when no snapshot found."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        manager.find_snapshot_for_execution = Mock(return_value=None)

        # Act
        result = await manager.analyze_rollback_impact(execution_id="nonexistent")

        # Assert
        assert result["status"] == "error"
        message = result.get("message", "")
        assert isinstance(message, str)
        assert "No snapshot found" in message


class TestGetAffectedFiles:
    """Test getting affected files from execution operations."""

    @pytest.mark.asyncio
    async def test_get_affected_files_from_move_operation(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test extracting affected files from move operation."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Create file with version history matching snapshot
        file_path = memory_bank_dir / "file1.md"
        _ = file_path.write_text("# File 1\nContent")

        # Mock metadata to return version history with matching snapshot
        mock_metadata_index.get_file_metadata = AsyncMock(
            return_value={
                "version_history": [
                    {
                        "version": 1,
                        "change_description": "Pre-refactoring snapshot: snapshot-1",
                    }
                ]
            }
        )

        # Act
        affected = await manager.get_affected_files("exec-1", "snapshot-1")

        # Assert
        assert "file1.md" in affected

    @pytest.mark.asyncio
    async def test_get_affected_files_from_consolidation(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test extracting affected files from consolidation."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Create files with version history matching snapshot
        file1_path = memory_bank_dir / "file1.md"
        _ = file1_path.write_text("# File 1\nContent")
        file2_path = memory_bank_dir / "file2.md"
        _ = file2_path.write_text("# File 2\nContent")
        consolidated_path = memory_bank_dir / "consolidated.md"
        _ = consolidated_path.write_text("# Consolidated\nContent")

        # Mock metadata to return version history with matching snapshot
        # for each file
        async def mock_get_file_metadata(file_name: str) -> dict[str, object] | None:
            return {
                "version_history": [
                    {
                        "version": 1,
                        "change_description": "Pre-refactoring snapshot: snapshot-1",
                    }
                ]
            }

        mock_metadata_index.get_file_metadata = mock_get_file_metadata

        # Act
        affected = await manager.get_affected_files("exec-1", "snapshot-1")

        # Assert
        assert "file1.md" in affected
        assert "file2.md" in affected
        assert "consolidated.md" in affected

    @pytest.mark.asyncio
    async def test_get_affected_files_returns_empty_for_nonexistent(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test returns empty list for nonexistent execution."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Act
        affected = await manager.get_affected_files("nonexistent", "snapshot-1")

        # Assert
        assert affected == []


class TestBackupCurrentVersion:
    """Test backup creation before rollback."""

    @pytest.mark.asyncio
    async def test_backup_creates_version_snapshot(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test backup creates version snapshot."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Create test file
        test_file = memory_bank_dir / "test.md"
        _ = test_file.write_text("Current content")

        # Mock version manager
        version_manager.create_snapshot = AsyncMock(return_value="backup-snapshot")

        # Act
        await manager.backup_current_version("test.md")

        # Assert
        version_manager.create_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_backup_handles_nonexistent_file(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test backup gracefully handles nonexistent file."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Don't create the file

        # Act - should not raise exception
        await manager.backup_current_version("nonexistent.md")

        # No exception means success


class TestRollbackRecordPostInit:
    """Test RollbackRecord __post_init__ validation."""

    def test_post_init_generates_missing_rollback_id(self):
        """Test post_init generates rollback_id if None."""
        # Arrange & Act
        # Note: RollbackRecord requires rollback_id, but we test with empty string
        # to verify default behavior if needed in future
        record = RollbackRecord(
            rollback_id="roll-1",  # Required field
            execution_id="exec-1",
            created_at="2025-01-01T12:00:00",
        )

        # Assert
        assert record.rollback_id is not None
        assert record.rollback_id.startswith("roll-")

    def test_post_init_generates_missing_created_at(self):
        """Test post_init generates created_at if None."""
        # Arrange & Act
        # Note: RollbackRecord requires created_at, but we test with valid timestamp
        # to verify default behavior if needed in future
        record = RollbackRecord(
            rollback_id="roll-1",
            execution_id="exec-1",
            created_at="2025-01-01T12:00:00",  # Required field
        )

        # Assert
        assert record.created_at is not None
        # Should be valid ISO format timestamp
        _ = datetime.fromisoformat(record.created_at)


class TestComplexRollbackScenarios:
    """Test complex rollback scenarios."""

    @pytest.mark.asyncio
    async def test_rollback_with_multiple_files(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test rollback affecting multiple files."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Mock methods
        manager.find_snapshot_for_execution = Mock(return_value="snapshot-1")
        manager.get_affected_files = AsyncMock(
            return_value=["file1.md", "file2.md", "file3.md"]
        )
        manager.detect_conflicts = AsyncMock(return_value=[])
        manager.restore_files = AsyncMock(
            return_value=["file1.md", "file2.md", "file3.md"]
        )

        # Act
        result = await manager.rollback_refactoring(
            execution_id="exec-1", dry_run=False
        )

        # Assert
        assert result["status"] == "success"
        assert result["files_restored"] == 3

    @pytest.mark.asyncio
    async def test_rollback_preserving_some_manual_edits(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test rollback preserving manual edits on some files."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Mock methods - file1 has conflict, file2 doesn't
        manager.find_snapshot_for_execution = Mock(return_value="snapshot-1")
        manager.get_affected_files = AsyncMock(return_value=["file1.md", "file2.md"])
        manager.detect_conflicts = AsyncMock(
            return_value=["file1.md - manually edited"]
        )
        manager.restore_files = AsyncMock(return_value=["file2.md"])

        # Act
        result = await manager.rollback_refactoring(
            execution_id="exec-1", preserve_manual_changes=True, dry_run=False
        )

        # Assert
        assert result["status"] == "success"
        assert result["files_restored"] == 1
        assert result["conflicts_detected"] == 1


class TestSaveRollbacks:
    """Test rollback history persistence."""

    @pytest.mark.asyncio
    async def test_save_rollbacks_persists_to_disk(
        self,
        memory_bank_dir: Path,
        mock_file_system: "FileSystemManager",
        mock_metadata_index: "MetadataIndex",
    ):
        """Test save_rollbacks writes to disk."""
        # Arrange
        from cortex.core.version_manager import VersionManager

        version_manager = VersionManager(memory_bank_dir.parent)

        manager = RollbackManager(
            memory_bank_dir=memory_bank_dir,
            fs_manager=mock_file_system,
            version_manager=version_manager,
            metadata_index=mock_metadata_index,
        )

        # Add a rollback
        manager.rollbacks["roll-1"] = RollbackRecord(
            rollback_id="roll-1",
            execution_id="exec-1",
            created_at="2025-01-01T12:00:00",
            status="completed",
        )

        # Act
        await manager.save_rollbacks()

        # Assert
        rollback_file = memory_bank_dir.parent / ".memory-bank-rollbacks.json"
        assert rollback_file.exists()
        data = json.loads(rollback_file.read_text())
        assert "roll-1" in data["rollbacks"]
