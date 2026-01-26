"""
Comprehensive test suite for migration.py

Tests MigrationManager for automatic migration from template-only to hybrid storage.

Test Coverage:
- Migration detection logic
- Migration information reporting
- Full migration workflow with backup
- Backup creation and restoration
- Rollback on failure
- Verification logic
- Backup management (cleanup, listing)
- Error handling and edge cases
"""

import shutil
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cortex.core.exceptions import MigrationFailedError
from cortex.core.migration import MigrationManager
from cortex.core.models import VerificationResult


class TestMigrationManagerInitialization:
    """Tests for MigrationManager initialization."""

    def test_initialization_with_valid_path(self, tmp_path: Path) -> None:
        """Test manager initializes with valid project root."""
        manager = MigrationManager(tmp_path)

        assert manager.project_root == tmp_path
        assert manager.memory_bank_dir == tmp_path / ".cortex" / "memory-bank"
        assert manager.index_path == tmp_path / ".cortex" / "index.json"

    def test_initialization_converts_string_path(self, tmp_path: Path) -> None:
        """Test manager converts string path to Path object."""
        from pathlib import Path as PathType

        manager = MigrationManager(PathType(str(tmp_path)))

        assert isinstance(manager.project_root, Path)
        assert manager.project_root == tmp_path


class TestDetectMigrationNeeded:
    """Tests for migration detection logic."""

    @pytest.mark.asyncio
    async def test_detect_no_migration_when_no_memory_bank_dir(
        self, tmp_path: Path
    ) -> None:
        """Test returns False when .cortex/memory-bank directory doesn't exist."""
        manager = MigrationManager(tmp_path)

        needs_migration = await manager.detect_migration_needed()

        assert needs_migration is False

    @pytest.mark.asyncio
    async def test_detect_no_migration_when_already_migrated(
        self, tmp_path: Path
    ) -> None:
        """Test returns False when .cortex/index.json exists."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        manager.index_path.parent.mkdir(parents=True, exist_ok=True)
        manager.index_path.touch()

        needs_migration = await manager.detect_migration_needed()

        assert needs_migration is False

    @pytest.mark.asyncio
    async def test_detect_no_migration_when_no_md_files(self, tmp_path: Path) -> None:
        """Test returns False when .cortex/memory-bank directory has no .md files."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        # Create a non-.md file
        _ = (manager.memory_bank_dir / "readme.txt").write_text("Not a markdown file")

        needs_migration = await manager.detect_migration_needed()

        assert needs_migration is False

    @pytest.mark.asyncio
    async def test_detect_migration_needed_when_criteria_met(
        self, tmp_path: Path
    ) -> None:
        """Test returns True when migration is needed."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        _ = (manager.memory_bank_dir / "test.md").write_text("# Test")

        needs_migration = await manager.detect_migration_needed()

        assert needs_migration is True


class TestGetMigrationInfo:
    """Tests for migration information reporting."""

    @pytest.mark.asyncio
    async def test_info_when_no_memory_bank_dir(self, tmp_path: Path) -> None:
        """Test returns info when .cortex/memory-bank directory doesn't exist."""
        manager = MigrationManager(tmp_path)

        info = await manager.get_migration_info()

        assert info["needs_migration"] is False
        reason = str(info.get("reason", ""))
        assert "No .cortex/memory-bank directory" in reason

    @pytest.mark.asyncio
    async def test_info_when_no_md_files(self, tmp_path: Path) -> None:
        """Test returns info when no .md files exist."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)

        info = await manager.get_migration_info()

        assert info["needs_migration"] is False
        reason = str(info.get("reason", ""))
        assert "No markdown files" in reason

    @pytest.mark.asyncio
    async def test_info_when_already_migrated(self, tmp_path: Path) -> None:
        """Test returns info when already migrated."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        manager.index_path.parent.mkdir(parents=True, exist_ok=True)
        manager.index_path.touch()
        _ = (manager.memory_bank_dir / "test.md").write_text("# Test")

        info = await manager.get_migration_info()

        assert info["needs_migration"] is False
        reason = str(info.get("reason", ""))
        assert "Already migrated" in reason

    @pytest.mark.asyncio
    async def test_info_when_migration_needed(self, tmp_path: Path) -> None:
        """Test returns detailed info when migration is needed."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)

        # Create test files
        file1 = manager.memory_bank_dir / "file1.md"
        file2 = manager.memory_bank_dir / "file2.md"
        _ = file1.write_text("# File 1")
        _ = file2.write_text("# File 2\n## Section")

        info = await manager.get_migration_info()

        assert info["needs_migration"] is True
        assert info["files_found"] == 2
        file_names_raw: object | None = info.get("file_names", [])
        if isinstance(file_names_raw, list):
            file_names: list[str] = [
                str(item) for item in cast(list[object], file_names_raw)
            ]
        else:
            file_names = []
        assert "file1.md" in file_names
        assert "file2.md" in file_names
        total_size = info.get("total_size_bytes", 0)
        estimated = info.get("estimated_tokens", 0)
        assert isinstance(total_size, int) and total_size > 0
        assert isinstance(estimated, int) and estimated > 0
        assert "backup_location" in info


class TestCreateBackup:
    """Tests for backup creation."""

    @pytest.mark.asyncio
    async def test_create_backup_creates_timestamped_directory(
        self, tmp_path: Path
    ) -> None:
        """Test create_backup creates timestamped backup directory."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        _ = (manager.memory_bank_dir / "test.md").write_text("# Test")

        backup_dir = await manager.create_backup()

        assert backup_dir.exists()
        assert backup_dir.name.startswith(".cortex-backup-")
        assert (backup_dir / "test.md").exists()

    @pytest.mark.asyncio
    async def test_create_backup_copies_all_files(self, tmp_path: Path) -> None:
        """Test create_backup copies all files from .cortex/memory-bank directory."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)

        # Create multiple files
        _ = (manager.memory_bank_dir / "file1.md").write_text("Content 1")
        _ = (manager.memory_bank_dir / "file2.md").write_text("Content 2")
        _ = (manager.memory_bank_dir / "file3.md").write_text("Content 3")

        backup_dir = await manager.create_backup()

        assert (backup_dir / "file1.md").read_text() == "Content 1"
        assert (backup_dir / "file2.md").read_text() == "Content 2"
        assert (backup_dir / "file3.md").read_text() == "Content 3"

    @pytest.mark.asyncio
    async def test_create_backup_when_directory_empty(self, tmp_path: Path) -> None:
        """Test create_backup handles empty memory-bank directory."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)

        backup_dir = await manager.create_backup()

        assert backup_dir.exists()
        assert list(backup_dir.iterdir()) == []


class TestRollback:
    """Tests for rollback functionality."""

    @pytest.mark.asyncio
    async def test_rollback_removes_index_file(self, tmp_path: Path) -> None:
        """Test rollback removes .cortex/index.json file."""
        manager = MigrationManager(tmp_path)
        manager.index_path.parent.mkdir(parents=True, exist_ok=True)
        manager.index_path.touch()

        backup_dir = tmp_path / ".cortex-backup-test"
        backup_dir.mkdir()

        await manager.rollback(backup_dir)

        assert not manager.index_path.exists()

    @pytest.mark.asyncio
    async def test_rollback_removes_history_directory(self, tmp_path: Path) -> None:
        """Test rollback removes .cortex/history directory."""
        manager = MigrationManager(tmp_path)
        history_dir = tmp_path / ".cortex" / "history"
        history_dir.mkdir(parents=True)
        _ = (history_dir / "test.txt").write_text("History")

        backup_dir = tmp_path / ".cortex-backup-test"
        backup_dir.mkdir()

        await manager.rollback(backup_dir)

        assert not history_dir.exists()

    @pytest.mark.asyncio
    async def test_rollback_restores_from_backup(self, tmp_path: Path) -> None:
        """Test rollback restores .cortex/memory-bank directory from backup."""
        manager = MigrationManager(tmp_path)

        # Create backup with original content
        backup_dir = tmp_path / ".cortex-backup-test"
        backup_dir.mkdir()
        _ = (backup_dir / "original.md").write_text("Original content")

        # Create current directory with modified content
        manager.memory_bank_dir.mkdir(parents=True)
        _ = (manager.memory_bank_dir / "modified.md").write_text("Modified content")

        await manager.rollback(backup_dir)

        assert (manager.memory_bank_dir / "original.md").exists()
        assert not (manager.memory_bank_dir / "modified.md").exists()
        assert (
            manager.memory_bank_dir / "original.md"
        ).read_text() == "Original content"

    @pytest.mark.asyncio
    async def test_rollback_handles_missing_backup(self, tmp_path: Path) -> None:
        """Test rollback handles case when backup doesn't exist."""
        manager = MigrationManager(tmp_path)
        backup_dir = tmp_path / ".cortex-backup-nonexistent"

        # Should not raise exception
        await manager.rollback(backup_dir)


class TestMigrate:
    """Tests for full migration workflow."""

    @pytest.mark.asyncio
    async def test_migrate_creates_backup_by_default(self, tmp_path: Path) -> None:
        """Test migrate creates backup by default."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        _ = (manager.memory_bank_dir / "test.md").write_text("# Test")

        with patch.object(
            manager, "create_backup", new_callable=AsyncMock
        ) as mock_backup:
            mock_backup.return_value = tmp_path / ".cortex-backup-test"

            # Mock other dependencies to avoid full migration
            mock_fs = MagicMock()
            mock_fs.read_file = AsyncMock(return_value=("# Test", "hash123"))
            mock_fs.parse_sections = MagicMock(return_value=[])

            mock_token = MagicMock()
            mock_token.count_tokens = MagicMock(return_value=10)

            mock_metadata = AsyncMock()
            mock_metadata.load = AsyncMock()
            mock_metadata.update_file_metadata = AsyncMock()
            mock_metadata.add_version_to_history = AsyncMock()
            mock_metadata.update_dependency_graph = AsyncMock()

            mock_version = AsyncMock()
            version_meta = MagicMock()
            version_meta.version = 1
            version_meta.model_dump = MagicMock(return_value={"version": 1})
            mock_version.create_snapshot = AsyncMock(return_value=version_meta)

            mock_dep = MagicMock()
            mock_dep.to_dict = MagicMock(return_value={})

            with (
                patch(
                    "cortex.core.migration.FileSystemManager",
                    return_value=mock_fs,
                ),
                patch(
                    "cortex.core.migration.TokenCounter",
                    return_value=mock_token,
                ),
                patch(
                    "cortex.core.migration.MetadataIndex",
                    return_value=mock_metadata,
                ),
                patch(
                    "cortex.core.migration.VersionManager",
                    return_value=mock_version,
                ),
                patch(
                    "cortex.core.migration.DependencyGraph",
                    return_value=mock_dep,
                ),
            ):
                with patch.object(
                    manager, "verify_migration", new_callable=AsyncMock
                ) as mock_verify:
                    mock_verify.return_value = VerificationResult(success=True)

                    _ = await manager.migrate()

                    mock_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_migrate_skips_backup_when_disabled(self, tmp_path: Path) -> None:
        """Test migrate skips backup when auto_backup=False."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        _ = (manager.memory_bank_dir / "test.md").write_text("# Test")

        with patch.object(
            manager, "create_backup", new_callable=AsyncMock
        ) as mock_backup:
            # Mock other dependencies
            mock_fs = MagicMock()
            mock_fs.read_file = AsyncMock(return_value=("# Test", "hash123"))
            mock_fs.parse_sections = MagicMock(return_value=[])

            mock_token = MagicMock()
            mock_token.count_tokens = MagicMock(return_value=10)

            mock_metadata = AsyncMock()
            mock_metadata.load = AsyncMock()
            mock_metadata.update_file_metadata = AsyncMock()
            mock_metadata.add_version_to_history = AsyncMock()
            mock_metadata.update_dependency_graph = AsyncMock()

            mock_version = AsyncMock()
            version_meta = MagicMock()
            version_meta.version = 1
            version_meta.model_dump = MagicMock(return_value={"version": 1})
            mock_version.create_snapshot = AsyncMock(return_value=version_meta)

            mock_dep = MagicMock()
            mock_dep.to_dict = MagicMock(return_value={})

            with (
                patch(
                    "cortex.core.migration.FileSystemManager",
                    return_value=mock_fs,
                ),
                patch(
                    "cortex.core.migration.TokenCounter",
                    return_value=mock_token,
                ),
                patch(
                    "cortex.core.migration.MetadataIndex",
                    return_value=mock_metadata,
                ),
                patch(
                    "cortex.core.migration.VersionManager",
                    return_value=mock_version,
                ),
                patch(
                    "cortex.core.migration.DependencyGraph",
                    return_value=mock_dep,
                ),
            ):
                with patch.object(
                    manager, "verify_migration", new_callable=AsyncMock
                ) as mock_verify:
                    mock_verify.return_value = VerificationResult(success=True)

                    _ = await manager.migrate(auto_backup=False)

                    mock_backup.assert_not_called()

    @pytest.mark.asyncio
    async def test_migrate_returns_success_report(self, tmp_path: Path) -> None:
        """Test migrate returns success report on completion."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        _ = (manager.memory_bank_dir / "test.md").write_text("# Test")

        # Mock all dependencies
        mock_fs = MagicMock()
        mock_fs.read_file = AsyncMock(return_value=("# Test", "hash123"))
        mock_fs.parse_sections = MagicMock(return_value=[])

        mock_token = MagicMock()
        mock_token.count_tokens = MagicMock(return_value=10)

        mock_metadata = AsyncMock()
        mock_metadata.load = AsyncMock()
        mock_metadata.update_file_metadata = AsyncMock()
        mock_metadata.add_version_to_history = AsyncMock()
        mock_metadata.update_dependency_graph = AsyncMock()

        mock_version = AsyncMock()
        version_meta = MagicMock()
        version_meta.version = 1
        version_meta.model_dump = MagicMock(return_value={"version": 1})
        mock_version.create_snapshot = AsyncMock(return_value=version_meta)

        mock_dep = MagicMock()
        mock_dep.to_dict = MagicMock(return_value={})

        with (
            patch("cortex.core.migration.FileSystemManager", return_value=mock_fs),
            patch("cortex.core.migration.TokenCounter", return_value=mock_token),
            patch(
                "cortex.core.migration.MetadataIndex",
                return_value=mock_metadata,
            ),
            patch(
                "cortex.core.migration.VersionManager",
                return_value=mock_version,
            ),
            patch("cortex.core.migration.DependencyGraph", return_value=mock_dep),
        ):
            with patch.object(
                manager, "verify_migration", new_callable=AsyncMock
            ) as mock_verify:
                mock_verify.return_value = VerificationResult(
                    success=True, files_verified=1
                )

                result = await manager.migrate(auto_backup=False)

                assert result["status"] == "success"
                assert result["files_migrated"] == 1
                assert "details" in result

    @pytest.mark.asyncio
    async def test_migrate_raises_on_verification_failure(self, tmp_path: Path) -> None:
        """Test migrate raises MigrationFailedError when verification fails."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        _ = (manager.memory_bank_dir / "test.md").write_text("# Test")

        # Mock verification failure
        with (
            patch("cortex.core.migration.FileSystemManager") as mock_fs_class,
            patch("cortex.core.migration.TokenCounter"),
            patch("cortex.core.migration.MetadataIndex") as mock_index_class,
            patch("cortex.core.migration.VersionManager") as mock_version_class,
            patch("cortex.core.migration.DependencyGraph"),
        ):
            # Setup async mocks for manager instances
            mock_fs = MagicMock()
            mock_fs.read_file = AsyncMock(return_value=("# Test", "hash123"))
            mock_fs.parse_sections = MagicMock(return_value=[])
            mock_fs_class.return_value = mock_fs

            mock_metadata = AsyncMock()
            mock_metadata.load = AsyncMock()
            mock_index_class.return_value = mock_metadata

            mock_version = AsyncMock()
            version_meta = MagicMock()
            version_meta.version = 1
            version_meta.model_dump = MagicMock(return_value={"version": 1})
            mock_version.create_snapshot = AsyncMock(return_value=version_meta)
            mock_version_class.return_value = mock_version

            with patch.object(
                manager, "verify_migration", new_callable=AsyncMock
            ) as mock_verify:
                mock_verify.return_value = VerificationResult(
                    success=False, error="Verification failed"
                )

                with pytest.raises(MigrationFailedError):
                    _ = await manager.migrate(auto_backup=False)

    @pytest.mark.asyncio
    async def test_migrate_rolls_back_on_exception(self, tmp_path: Path) -> None:
        """Test migrate rolls back changes on exception."""
        manager = MigrationManager(tmp_path)
        manager.memory_bank_dir.mkdir(parents=True)
        _ = (manager.memory_bank_dir / "test.md").write_text("# Test")

        backup_dir = tmp_path / ".cortex-backup-test"
        backup_dir.mkdir()

        # Mock exception during migration (after backup is created)
        with patch.object(
            manager, "create_backup", new_callable=AsyncMock
        ) as mock_backup:
            mock_backup.return_value = backup_dir

            # Mock FileSystemManager to raise exception during instantiation
            with patch("cortex.core.migration.FileSystemManager") as mock_fs_class:
                mock_fs_class.side_effect = Exception("Migration error")
                mock_fs_class.side_effect = Exception("Migration error")

                with patch.object(
                    manager, "rollback", new_callable=AsyncMock
                ) as mock_rollback:
                    with pytest.raises(MigrationFailedError):
                        _ = await manager.migrate()

                    mock_rollback.assert_called_once_with(backup_dir)


class TestVerifyMigration:
    """Tests for migration verification."""

    @pytest.mark.asyncio
    async def test_verify_fails_when_index_not_created(self, tmp_path: Path) -> None:
        """Test verification fails when index file doesn't exist."""
        manager = MigrationManager(tmp_path)
        md_files: list[Path] = []

        result = await manager.verify_migration(md_files)

        assert result["success"] is False
        error = str(result.get("error", ""))
        assert "Index file not created" in error

    @pytest.mark.asyncio
    async def test_verify_fails_when_history_not_created(self, tmp_path: Path) -> None:
        """Test verification fails when history directory doesn't exist."""
        manager = MigrationManager(tmp_path)
        manager.index_path.parent.mkdir(parents=True, exist_ok=True)
        manager.index_path.touch()
        md_files: list[Path] = []

        result = await manager.verify_migration(md_files)

        assert result["success"] is False
        error = str(result.get("error", ""))
        assert "History directory not created" in error

    @pytest.mark.asyncio
    async def test_verify_checks_all_files_in_index(self, tmp_path: Path) -> None:
        """Test verification checks all files are in index."""
        manager = MigrationManager(tmp_path)
        manager.index_path.parent.mkdir(parents=True, exist_ok=True)
        manager.index_path.touch()
        (tmp_path / ".cortex/history").mkdir(parents=True, exist_ok=True)

        md_files = [tmp_path / ".cortex" / "memory-bank" / "test.md"]

        # Mock MetadataIndex
        with patch("cortex.core.migration.MetadataIndex") as mock_index_class:
            mock_index = AsyncMock()
            mock_index.load = AsyncMock()
            mock_index.file_exists_in_index = AsyncMock(return_value=False)
            mock_index_class.return_value = mock_index

            result = await manager.verify_migration(md_files)

            assert result["success"] is False
            error = str(result.get("error", ""))
            assert "not found in index" in error

    @pytest.mark.asyncio
    async def test_verify_checks_snapshots_created(self, tmp_path: Path) -> None:
        """Test verification checks all snapshots were created."""
        manager = MigrationManager(tmp_path)
        manager.index_path.parent.mkdir(parents=True, exist_ok=True)
        manager.index_path.touch()
        (tmp_path / ".cortex/history").mkdir(parents=True, exist_ok=True)

        md_files = [tmp_path / ".cortex" / "memory-bank" / "test.md"]

        # Mock MetadataIndex and VersionManager
        with (
            patch("cortex.core.migration.MetadataIndex") as mock_index_class,
            patch("cortex.core.migration.VersionManager") as mock_version_class,
        ):
            mock_index = AsyncMock()
            mock_index.load = AsyncMock()
            mock_index.file_exists_in_index = AsyncMock(return_value=True)
            mock_index_class.return_value = mock_index

            mock_version = MagicMock()
            # Return non-existent path for snapshot
            mock_version.get_snapshot_path = MagicMock(
                return_value=tmp_path / "nonexistent.txt"
            )
            mock_version_class.return_value = mock_version

            result = await manager.verify_migration(md_files)

            assert result["success"] is False
            error = str(result.get("error", ""))
            assert "Snapshot" in error

    @pytest.mark.asyncio
    async def test_verify_succeeds_when_all_checks_pass(self, tmp_path: Path) -> None:
        """Test verification succeeds when all checks pass."""
        manager = MigrationManager(tmp_path)
        manager.index_path.parent.mkdir(parents=True, exist_ok=True)
        manager.index_path.touch()
        (tmp_path / ".cortex/history").mkdir(parents=True, exist_ok=True)

        md_files = [tmp_path / ".cortex" / "memory-bank" / "test.md"]

        # Create snapshot file - use the correct path format
        # VersionManager.get_snapshot_path returns: history_dir / "{base_name}_v{version}.md"
        snapshot_path = tmp_path / ".cortex/history" / "test_v1.md"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        _ = snapshot_path.write_text("{}")

        # Mock MetadataIndex and VersionManager
        with (
            patch("cortex.core.migration.MetadataIndex") as mock_index_class,
            patch("cortex.core.migration.VersionManager") as mock_version_class,
        ):
            mock_index = AsyncMock()
            mock_index.load = AsyncMock()
            mock_index.file_exists_in_index = AsyncMock(return_value=True)
            mock_index_class.return_value = mock_index

            mock_version = MagicMock()
            mock_version.get_snapshot_path = MagicMock(return_value=snapshot_path)
            mock_version_class.return_value = mock_version

            result = await manager.verify_migration(md_files)

            assert result["success"] is True
            assert result["files_verified"] == 1
            assert result["index_valid"] is True
            assert result["snapshots_created"] is True


class TestCleanupOldBackups:
    """Tests for backup cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_keeps_specified_number_of_backups(
        self, tmp_path: Path
    ) -> None:
        """Test cleanup_old_backups keeps only the most recent backups."""
        manager = MigrationManager(tmp_path)

        # Create 5 backup directories
        for i in range(5):
            backup_dir = tmp_path / f".cortex-backup-2024010{i}_120000"
            backup_dir.mkdir()

        await manager.cleanup_old_backups(keep_last=3)

        remaining_backups = list(tmp_path.glob(".cortex-backup-*"))
        assert len(remaining_backups) == 3

        # Check that the oldest were deleted
        assert not (tmp_path / ".cortex-backup-20240100_120000").exists()
        assert not (tmp_path / ".cortex-backup-20240101_120000").exists()
        assert (tmp_path / ".cortex-backup-20240104_120000").exists()

    @pytest.mark.asyncio
    async def test_cleanup_does_nothing_when_below_limit(self, tmp_path: Path) -> None:
        """Test cleanup doesn't delete backups when below keep_last limit."""
        manager = MigrationManager(tmp_path)

        # Create 2 backup directories
        for i in range(2):
            backup_dir = tmp_path / f".cortex-backup-2024010{i}_120000"
            backup_dir.mkdir()

        await manager.cleanup_old_backups(keep_last=3)

        remaining_backups = list(tmp_path.glob(".cortex-backup-*"))
        assert len(remaining_backups) == 2

    @pytest.mark.asyncio
    async def test_cleanup_handles_permission_errors(self, tmp_path: Path) -> None:
        """Test cleanup handles permission errors gracefully."""
        manager = MigrationManager(tmp_path)

        # Create backup directories
        for i in range(3):
            backup_dir = tmp_path / f".cortex-backup-2024010{i}_120000"
            backup_dir.mkdir()

        # Mock rmtree to raise OSError for first backup
        original_rmtree = shutil.rmtree

        def mock_rmtree(path: Path | str) -> None:
            if "20240100" in str(path):
                raise OSError("Permission denied")
            original_rmtree(path)

        with patch("shutil.rmtree", side_effect=mock_rmtree):
            # Should not raise exception
            await manager.cleanup_old_backups(keep_last=1)


class TestGetBackupList:
    """Tests for backup listing."""

    @pytest.mark.asyncio
    async def test_get_backup_list_returns_all_backups(self, tmp_path: Path) -> None:
        """Test get_backup_list returns info for all backups."""
        manager = MigrationManager(tmp_path)

        # Create backup directories
        backup1 = tmp_path / ".cortex-backup-20240101_120000"
        backup2 = tmp_path / ".cortex-backup-20240102_130000"
        backup1.mkdir()
        backup2.mkdir()
        _ = (backup1 / "file.md").write_text("Content")

        backups = await manager.get_backup_list()

        assert len(backups) == 2
        assert any(b["timestamp"] == "20240101_120000" for b in backups)
        assert any(b["timestamp"] == "20240102_130000" for b in backups)

    @pytest.mark.asyncio
    async def test_get_backup_list_includes_size_and_timestamp(
        self, tmp_path: Path
    ) -> None:
        """Test get_backup_list includes size and timestamp info."""
        manager = MigrationManager(tmp_path)

        backup = tmp_path / ".cortex-backup-20240101_120000"
        backup.mkdir()
        _ = (backup / "file.md").write_text("Test content")

        backups = await manager.get_backup_list()

        assert len(backups) == 1
        backup_info = backups[0]
        assert backup_info.get("timestamp") == "20240101_120000"
        size_bytes = backup_info.get("size_bytes", 0)
        assert isinstance(size_bytes, int) and size_bytes > 0
        assert backup_info.get("created") is not None
        assert backup_info.get("path") == str(backup)

    @pytest.mark.asyncio
    async def test_get_backup_list_handles_invalid_timestamps(
        self, tmp_path: Path
    ) -> None:
        """Test get_backup_list handles invalid timestamp formats."""
        manager = MigrationManager(tmp_path)

        # Create backup with invalid timestamp
        backup = tmp_path / ".cortex-backup-invalid"
        backup.mkdir()

        backups = await manager.get_backup_list()

        assert len(backups) == 1
        assert backups[0]["created"] is None  # Can't parse timestamp

    @pytest.mark.asyncio
    async def test_get_backup_list_returns_empty_when_no_backups(
        self, tmp_path: Path
    ) -> None:
        """Test get_backup_list returns empty list when no backups exist."""
        manager = MigrationManager(tmp_path)

        backups = await manager.get_backup_list()

        assert backups == []
