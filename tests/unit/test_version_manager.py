"""Unit tests for version_manager module."""

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from cortex.core.models import ModelDict
from cortex.core.version_manager import VersionManager


class TestVersionManagerInitialization:
    """Tests for VersionManager initialization."""

    def test_initializes_with_default_keep_versions(self, tmp_path: Path) -> None:
        """Test initialization with default keep_versions parameter."""
        # Act
        manager = VersionManager(tmp_path)

        # Assert
        assert manager.project_root == tmp_path
        assert manager.history_dir == tmp_path / ".cortex/history"
        assert manager.keep_versions == 10

    def test_initializes_with_custom_keep_versions(self, tmp_path: Path) -> None:
        """Test initialization with custom keep_versions parameter."""
        # Act
        manager = VersionManager(tmp_path, keep_versions=5)

        # Assert
        assert manager.keep_versions == 5

    def test_history_dir_path_is_correct(self, tmp_path: Path) -> None:
        """Test history directory path is set correctly."""
        # Act
        manager = VersionManager(tmp_path)

        # Assert
        assert manager.history_dir.name == "history"
        assert manager.history_dir.parent == tmp_path / ".cortex"


@pytest.mark.asyncio
class TestCreateSnapshot:
    """Tests for create_snapshot method."""

    async def test_creates_snapshot_file(self, tmp_path: Path) -> None:
        """Test creates snapshot file with correct name."""
        # Arrange
        manager = VersionManager(tmp_path, keep_versions=10)
        file_path = tmp_path / "test.md"
        content = "# Test Content"

        # Act
        _ = await manager.create_snapshot(
            file_path=file_path,
            version=1,
            content=content,
            size_bytes=len(content),
            token_count=10,
            content_hash="abc123",
        )

        # Assert
        snapshot_path = manager.history_dir / "test_v1.md"
        assert snapshot_path.exists()

    async def test_creates_history_directory_if_not_exists(
        self, tmp_path: Path
    ) -> None:
        """Test creates history directory when it doesn't exist."""
        # Arrange
        manager = VersionManager(tmp_path)
        file_path = tmp_path / "test.md"
        assert not manager.history_dir.exists()

        # Act
        _ = await manager.create_snapshot(
            file_path=file_path,
            version=1,
            content="# Test",
            size_bytes=6,
            token_count=5,
            content_hash="abc123",
        )

        # Assert
        assert manager.history_dir.exists()

    async def test_writes_content_to_snapshot_file(self, tmp_path: Path) -> None:
        """Test writes correct content to snapshot file."""
        # Arrange
        manager = VersionManager(tmp_path)
        file_path = tmp_path / "test.md"
        content = "# Test Content\n\nThis is a test."

        # Act
        _ = await manager.create_snapshot(
            file_path=file_path,
            version=1,
            content=content,
            size_bytes=len(content),
            token_count=15,
            content_hash="abc123",
        )

        # Assert
        snapshot_path = manager.history_dir / "test_v1.md"
        written_content = snapshot_path.read_text()
        assert written_content == content

    async def test_returns_correct_metadata(self, tmp_path: Path) -> None:
        """Test returns metadata with all expected fields."""
        # Arrange
        manager = VersionManager(tmp_path)
        file_path = tmp_path / "test.md"

        # Act
        metadata = await manager.create_snapshot(
            file_path=file_path,
            version=2,
            content="# Test",
            size_bytes=6,
            token_count=5,
            content_hash="def456",
            change_type="modified",
        )

        # Assert
        assert metadata["version"] == 2
        assert metadata["content_hash"] == "def456"
        assert metadata["size_bytes"] == 6
        assert metadata["token_count"] == 5
        assert metadata["change_type"] == "modified"
        assert "timestamp" in metadata
        assert "snapshot_path" in metadata

    async def test_includes_optional_changed_sections(self, tmp_path: Path) -> None:
        """Test includes changed_sections in metadata when provided."""
        # Arrange
        manager = VersionManager(tmp_path)
        file_path = tmp_path / "test.md"

        # Act
        metadata = await manager.create_snapshot(
            file_path=file_path,
            version=1,
            content="# Test",
            size_bytes=6,
            token_count=5,
            content_hash="abc123",
            changed_sections=["Overview", "Features"],
        )

        # Assert
        assert "changed_sections" in metadata
        assert metadata["changed_sections"] == ["Overview", "Features"]

    async def test_includes_optional_change_description(self, tmp_path: Path) -> None:
        """Test includes change_description in metadata when provided."""
        # Arrange
        manager = VersionManager(tmp_path)
        file_path = tmp_path / "test.md"

        # Act
        metadata = await manager.create_snapshot(
            file_path=file_path,
            version=1,
            content="# Test",
            size_bytes=6,
            token_count=5,
            content_hash="abc123",
            change_description="Updated features section",
        )

        # Assert
        assert "change_description" in metadata
        assert metadata["change_description"] == "Updated features section"

    async def test_prunes_old_versions_when_limit_exceeded(
        self, tmp_path: Path
    ) -> None:
        """Test removes old snapshots when keep_versions limit exceeded."""
        # Arrange
        manager = VersionManager(tmp_path, keep_versions=3)
        file_path = tmp_path / "test.md"

        # Create 5 versions
        for version in range(1, 6):
            _ = await manager.create_snapshot(
                file_path=file_path,
                version=version,
                content=f"# Version {version}",
                size_bytes=10,
                token_count=5,
                content_hash=f"hash{version}",
            )

        # Assert - only last 3 versions should exist
        assert not (manager.history_dir / "test_v1.md").exists()
        assert not (manager.history_dir / "test_v2.md").exists()
        assert (manager.history_dir / "test_v3.md").exists()
        assert (manager.history_dir / "test_v4.md").exists()
        assert (manager.history_dir / "test_v5.md").exists()

    async def test_handles_files_with_different_extensions(
        self, tmp_path: Path
    ) -> None:
        """Test handles files with .md extension correctly."""
        # Arrange
        manager = VersionManager(tmp_path)
        file_path = tmp_path / "document.md"

        # Act
        _ = await manager.create_snapshot(
            file_path=file_path,
            version=1,
            content="# Test",
            size_bytes=6,
            token_count=5,
            content_hash="abc123",
        )

        # Assert
        snapshot_path = manager.history_dir / "document_v1.md"
        assert snapshot_path.exists()


@pytest.mark.asyncio
class TestGetSnapshotContent:
    """Tests for get_snapshot_content method."""

    async def test_reads_snapshot_content(self, tmp_path: Path) -> None:
        """Test reads content from snapshot file."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = manager.history_dir / "test_v1.md"
        content = "# Test Snapshot Content"
        _ = snapshot_path.write_text(content)

        # Act
        read_content = await manager.get_snapshot_content(snapshot_path)

        # Assert
        assert read_content == content

    async def test_handles_relative_snapshot_paths(self, tmp_path: Path) -> None:
        """Test resolves relative snapshot paths correctly."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = manager.history_dir / "test_v1.md"
        content = "# Test Content"
        _ = snapshot_path.write_text(content)

        # Act - use relative path
        relative_path = Path(".cortex/history/test_v1.md")
        read_content = await manager.get_snapshot_content(relative_path)

        # Assert
        assert read_content == content

    async def test_raises_file_not_found_for_missing_snapshot(
        self, tmp_path: Path
    ) -> None:
        """Test raises FileNotFoundError when snapshot doesn't exist."""
        # Arrange
        manager = VersionManager(tmp_path)
        snapshot_path = manager.history_dir / "nonexistent_v1.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Snapshot not found"):
            _ = await manager.get_snapshot_content(snapshot_path)

    async def test_handles_unicode_content(self, tmp_path: Path) -> None:
        """Test handles Unicode content correctly."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = manager.history_dir / "test_v1.md"
        content = "# Test\n\n文字化け test émojis 🎉"
        _ = snapshot_path.write_text(content, encoding="utf-8")

        # Act
        read_content = await manager.get_snapshot_content(snapshot_path)

        # Assert
        assert read_content == content


@pytest.mark.asyncio
class TestRollbackToVersion:
    """Tests for rollback_to_version method."""

    async def test_returns_snapshot_content_and_metadata(self, tmp_path: Path) -> None:
        """Test returns correct snapshot content and metadata."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = manager.history_dir / "test_v2.md"
        content = "# Version 2 Content"
        _ = snapshot_path.write_text(content)

        def make_version(version: int, snapshot: Path) -> MagicMock:
            meta = MagicMock()
            meta.version = version
            meta.snapshot_path = str(snapshot)
            meta.model_dump = MagicMock(
                return_value={"version": version, "snapshot_path": str(snapshot)}
            )
            return meta

        version_history = [
            make_version(1, manager.history_dir / "test_v1.md"),
            make_version(2, snapshot_path),
            make_version(3, manager.history_dir / "test_v3.md"),
        ]

        # Act
        from typing import cast

        from cortex.core.models import VersionMetadata

        result = await manager.rollback_to_version(
            "test.md", cast(list[VersionMetadata], version_history), 2
        )  # type: ignore[arg-type]

        # Assert
        assert result is not None
        assert result["content"] == content
        metadata = cast(dict[str, object], result["metadata"])
        assert metadata["version"] == 2

    async def test_returns_none_when_version_not_found(self, tmp_path: Path) -> None:
        """Test returns None when target version not in history."""
        # Arrange
        manager = VersionManager(tmp_path)

        def make_version(version: int) -> MagicMock:
            meta = MagicMock()
            meta.version = version
            meta.snapshot_path = f".cortex/history/test_v{version}.md"
            meta.model_dump = MagicMock(
                return_value={
                    "version": version,
                    "snapshot_path": f".cortex/history/test_v{version}.md",
                }
            )
            return meta

        version_history = [make_version(1), make_version(2)]

        # Act
        from typing import cast

        from cortex.core.models import VersionMetadata

        result = await manager.rollback_to_version(
            "test.md", cast(list[VersionMetadata], version_history), 5
        )  # type: ignore[arg-type]

        # Assert
        assert result is None

    async def test_returns_none_when_snapshot_file_missing(
        self, tmp_path: Path
    ) -> None:
        """Test returns None when snapshot file doesn't exist."""
        # Arrange
        manager = VersionManager(tmp_path)
        version_meta = MagicMock()
        version_meta.version = 1
        version_meta.snapshot_path = str(tmp_path / ".cortex/history/missing_v1.md")
        version_meta.model_dump = MagicMock(
            return_value={
                "version": 1,
                "snapshot_path": str(tmp_path / ".cortex/history/missing_v1.md"),
            }
        )
        version_history = [version_meta]

        # Act
        from typing import cast

        from cortex.core.models import VersionMetadata

        result = await manager.rollback_to_version(
            "missing.md", cast(list[VersionMetadata], version_history), 1
        )  # type: ignore[arg-type]

        # Assert
        assert result is None

    async def test_handles_empty_version_history(self, tmp_path: Path) -> None:
        """Test handles empty version history."""
        # Arrange
        manager = VersionManager(tmp_path)
        version_history = cast(list[ModelDict], [])

        # Act
        from typing import cast as cast_func

        from cortex.core.models import VersionMetadata

        result = await manager.rollback_to_version(
            "test.md", cast_func(list[VersionMetadata], version_history), 1
        )  # type: ignore[arg-type]

        # Assert
        assert result is None


@pytest.mark.asyncio
class TestPruneVersions:
    """Tests for prune_versions method."""

    async def test_removes_oldest_snapshots_when_limit_exceeded(
        self, tmp_path: Path
    ) -> None:
        """Test removes oldest snapshots when limit exceeded."""
        # Arrange
        manager = VersionManager(tmp_path, keep_versions=2)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create 4 snapshots
        for version in range(1, 5):
            snapshot_path = manager.history_dir / f"test_v{version}.md"
            _ = snapshot_path.write_text(f"Version {version}")

        # Act
        await manager.prune_versions("test.md")

        # Assert - only last 2 should remain
        assert not (manager.history_dir / "test_v1.md").exists()
        assert not (manager.history_dir / "test_v2.md").exists()
        assert (manager.history_dir / "test_v3.md").exists()
        assert (manager.history_dir / "test_v4.md").exists()

    async def test_keeps_all_versions_when_under_limit(self, tmp_path: Path) -> None:
        """Test keeps all versions when count is under limit."""
        # Arrange
        manager = VersionManager(tmp_path, keep_versions=5)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create 3 snapshots
        for version in range(1, 4):
            snapshot_path = manager.history_dir / f"test_v{version}.md"
            _ = snapshot_path.write_text(f"Version {version}")

        # Act
        _ = await manager.prune_versions("test.md")

        # Assert - all 3 should remain
        assert (manager.history_dir / "test_v1.md").exists()
        assert (manager.history_dir / "test_v2.md").exists()
        assert (manager.history_dir / "test_v3.md").exists()

    async def test_handles_nonexistent_history_directory(self, tmp_path: Path) -> None:
        """Test handles case where history directory doesn't exist."""
        # Arrange
        manager = VersionManager(tmp_path)

        # Act & Assert - should not raise
        await manager.prune_versions("test.md")

    async def test_handles_inaccessible_snapshot_files(self, tmp_path: Path) -> None:
        """Test handles OS errors when removing snapshot files."""
        # Arrange
        manager = VersionManager(tmp_path, keep_versions=1)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create snapshots
        for version in range(1, 3):
            snapshot_path = manager.history_dir / f"test_v{version}.md"
            _ = snapshot_path.write_text(f"Version {version}")

        # Act & Assert - should not raise even if file removal fails
        _ = await manager.prune_versions("test.md")


@pytest.mark.asyncio
class TestGetVersionCount:
    """Tests for get_version_count method."""

    async def test_returns_correct_count(self, tmp_path: Path) -> None:
        """Test returns correct count of version snapshots."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create 3 snapshots
        for version in range(1, 4):
            snapshot_path = manager.history_dir / f"test_v{version}.md"
            _ = snapshot_path.write_text(f"Version {version}")

        # Act
        count = await manager.get_version_count("test.md")

        # Assert
        assert count == 3

    async def test_returns_zero_when_no_snapshots(self, tmp_path: Path) -> None:
        """Test returns 0 when no snapshots exist."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Act
        count = await manager.get_version_count("test.md")

        # Assert
        assert count == 0

    async def test_returns_zero_when_history_directory_not_exists(
        self, tmp_path: Path
    ) -> None:
        """Test returns 0 when history directory doesn't exist."""
        # Arrange
        manager = VersionManager(tmp_path)

        # Act
        count = await manager.get_version_count("test.md")

        # Assert
        assert count == 0

    async def test_counts_only_matching_file_snapshots(self, tmp_path: Path) -> None:
        """Test counts only snapshots for the specified file."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create snapshots for different files
        _ = (manager.history_dir / "test_v1.md").write_text("Version 1")
        _ = (manager.history_dir / "test_v2.md").write_text("Version 2")
        _ = (manager.history_dir / "other_v1.md").write_text("Other")

        # Act
        count = await manager.get_version_count("test.md")

        # Assert
        assert count == 2


@pytest.mark.asyncio
class TestGetDiskUsage:
    """Tests for get_disk_usage method."""

    async def test_returns_total_bytes_and_file_count(self, tmp_path: Path) -> None:
        """Test returns correct total bytes and file count."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create snapshots with known sizes
        _ = (manager.history_dir / "test_v1.md").write_text("Version 1")  # 9 bytes
        _ = (manager.history_dir / "test_v2.md").write_text("Version 2")  # 9 bytes

        # Act
        usage = await manager.get_disk_usage()

        # Assert
        assert usage["file_count"] == 2
        assert usage["total_bytes"] == 18

    async def test_returns_zero_when_no_snapshots(self, tmp_path: Path) -> None:
        """Test returns zeros when no snapshots exist."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Act
        usage = await manager.get_disk_usage()

        # Assert
        assert usage["total_bytes"] == 0
        assert usage["file_count"] == 0

    async def test_returns_zero_when_history_directory_not_exists(
        self, tmp_path: Path
    ) -> None:
        """Test returns zeros when history directory doesn't exist."""
        # Arrange
        manager = VersionManager(tmp_path)

        # Act
        usage = await manager.get_disk_usage()

        # Assert
        assert usage["total_bytes"] == 0
        assert usage["file_count"] == 0

    async def test_handles_inaccessible_snapshot_files(self, tmp_path: Path) -> None:
        """Test handles OS errors when checking file sizes."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)
        _ = (manager.history_dir / "test_v1.md").write_text("Version 1")

        # Act - should not raise
        usage = await manager.get_disk_usage()

        # Assert - should return valid results for accessible files
        from cortex.core.models import DiskUsageInfo

        assert isinstance(usage, DiskUsageInfo)
        assert usage.file_count >= 0


@pytest.mark.asyncio
class TestCleanupOrphanedSnapshots:
    """Tests for cleanup_orphaned_snapshots method."""

    async def test_removes_snapshots_for_nonexistent_files(
        self, tmp_path: Path
    ) -> None:
        """Test removes snapshots for files not in valid_files list."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create snapshots
        _ = (manager.history_dir / "current_v1.md").write_text("Version 1")
        _ = (manager.history_dir / "deleted_v1.md").write_text("Version 1")

        valid_files = ["current.md"]

        # Act
        await manager.cleanup_orphaned_snapshots(valid_files)

        # Assert
        assert (manager.history_dir / "current_v1.md").exists()
        assert not (manager.history_dir / "deleted_v1.md").exists()

    async def test_keeps_snapshots_for_valid_files(self, tmp_path: Path) -> None:
        """Test keeps snapshots for files in valid_files list."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create snapshots
        _ = (manager.history_dir / "file1_v1.md").write_text("Version 1")
        _ = (manager.history_dir / "file2_v1.md").write_text("Version 1")

        valid_files = ["file1.md", "file2.md"]

        # Act
        await manager.cleanup_orphaned_snapshots(valid_files)

        # Assert
        assert (manager.history_dir / "file1_v1.md").exists()
        assert (manager.history_dir / "file2_v1.md").exists()

    async def test_handles_nonexistent_history_directory(self, tmp_path: Path) -> None:
        """Test handles case where history directory doesn't exist."""
        # Arrange
        manager = VersionManager(tmp_path)
        valid_files = ["test.md"]

        # Act & Assert - should not raise
        await manager.cleanup_orphaned_snapshots(valid_files)

    async def test_handles_multiple_versions_of_same_file(self, tmp_path: Path) -> None:
        """Test removes all versions of orphaned file."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)

        # Create multiple versions of an orphaned file
        _ = (manager.history_dir / "orphan_v1.md").write_text("Version 1")
        _ = (manager.history_dir / "orphan_v2.md").write_text("Version 2")
        _ = (manager.history_dir / "orphan_v3.md").write_text("Version 3")

        valid_files: list[str] = []

        # Act
        await manager.cleanup_orphaned_snapshots(valid_files)

        # Assert
        assert not (manager.history_dir / "orphan_v1.md").exists()
        assert not (manager.history_dir / "orphan_v2.md").exists()
        assert not (manager.history_dir / "orphan_v3.md").exists()

    async def test_handles_inaccessible_snapshot_files(self, tmp_path: Path) -> None:
        """Test handles OS errors when removing snapshot files."""
        # Arrange
        manager = VersionManager(tmp_path)
        manager.history_dir.mkdir(parents=True, exist_ok=True)
        _ = (manager.history_dir / "orphan_v1.md").write_text("Version 1")

        # Act & Assert - should not raise even if file removal fails
        await manager.cleanup_orphaned_snapshots([])


@pytest.mark.asyncio
class TestExportVersionHistory:
    """Tests for export_version_history method."""

    async def test_returns_formatted_version_history(self, tmp_path: Path) -> None:
        """Test returns formatted version history."""
        # Arrange
        manager = VersionManager(tmp_path)
        version_history = cast(
            list[ModelDict],
            [
                {
                    "version": 1,
                    "timestamp": "2024-01-01T10:00:00",
                    "change_type": "created",
                    "size_bytes": 100,
                    "token_count": 50,
                    "content_hash": "abc123def456ghi789",
                    "snapshot_path": ".cortex/history/test.md.v1.snapshot",
                },
                {
                    "version": 2,
                    "timestamp": "2024-01-02T10:00:00",
                    "change_type": "modified",
                    "size_bytes": 120,
                    "token_count": 60,
                    "content_hash": "xyz789uvw456rst123",
                    "snapshot_path": ".cortex/history/test.md.v2.snapshot",
                },
            ],
        )

        # Act
        from cortex.core.models import VersionMetadata

        formatted = await manager.export_version_history(
            "test.md", cast(list[VersionMetadata | ModelDict], version_history)
        )

        # Assert
        assert len(formatted) == 2
        assert formatted[0]["version"] == 2  # Most recent first
        assert formatted[0]["timestamp"] == "2024-01-02T10:00:00"
        assert formatted[0]["content_hash"] == "xyz789uvw456rst1..."

    async def test_sorts_by_version_descending(self, tmp_path: Path) -> None:
        """Test sorts versions in descending order (newest first)."""
        # Arrange
        manager = VersionManager(tmp_path)
        version_history = cast(
            list[ModelDict],
            [
                {
                    "version": 1,
                    "timestamp": "2024-01-01T10:00:00",
                    "change_type": "created",
                    "size_bytes": 100,
                    "token_count": 50,
                    "content_hash": "abc123",
                    "snapshot_path": ".cortex/history/test.md.v1.snapshot",
                },
                {
                    "version": 3,
                    "timestamp": "2024-01-03T10:00:00",
                    "change_type": "modified",
                    "size_bytes": 120,
                    "token_count": 60,
                    "content_hash": "xyz789",
                    "snapshot_path": ".cortex/history/test.md.v3.snapshot",
                },
                {
                    "version": 2,
                    "timestamp": "2024-01-02T10:00:00",
                    "change_type": "modified",
                    "size_bytes": 110,
                    "token_count": 55,
                    "content_hash": "def456",
                    "snapshot_path": ".cortex/history/test.md.v2.snapshot",
                },
            ],
        )

        # Act
        from cortex.core.models import VersionMetadata

        formatted = await manager.export_version_history(
            "test.md", cast(list[VersionMetadata | ModelDict], version_history)
        )

        # Assert
        assert formatted[0]["version"] == 3
        assert formatted[1]["version"] == 2
        assert formatted[2]["version"] == 1

    async def test_limits_results_to_specified_count(self, tmp_path: Path) -> None:
        """Test limits results to specified limit."""
        # Arrange
        manager = VersionManager(tmp_path)
        version_history = [
            {
                "version": i,
                "timestamp": f"2024-01-0{i}T10:00:00",
                "change_type": "modified",
                "size_bytes": 100,
                "token_count": 50,
                "content_hash": f"hash{i}",
                "snapshot_path": f".cortex/history/test.md.v{i}.snapshot",
            }
            for i in range(1, 6)
        ]

        # Act
        from cortex.core.models import VersionMetadata

        formatted = await manager.export_version_history(
            "test.md", cast(list[VersionMetadata | ModelDict], version_history), limit=2
        )

        # Assert
        assert len(formatted) == 2
        assert formatted[0]["version"] == 5
        assert formatted[1]["version"] == 4

    async def test_includes_optional_fields_when_present(self, tmp_path: Path) -> None:
        """Test includes optional fields in formatted output."""
        # Arrange
        manager = VersionManager(tmp_path)
        version_history = cast(
            list[ModelDict],
            [
                {
                    "version": 1,
                    "timestamp": "2024-01-01T10:00:00",
                    "change_type": "modified",
                    "size_bytes": 100,
                    "token_count": 50,
                    "content_hash": "abc123",
                    "snapshot_path": ".cortex/history/test.md.v1.snapshot",
                    "changed_sections": ["Overview", "Features"],
                    "change_description": "Updated features section",
                }
            ],
        )

        # Act
        from cortex.core.models import VersionMetadata

        formatted = await manager.export_version_history(
            "test.md", cast(list[VersionMetadata | ModelDict], version_history)
        )

        # Assert
        assert "changed_sections" in formatted[0]
        assert formatted[0]["changed_sections"] == ["Overview", "Features"]
        assert "description" in formatted[0]
        assert formatted[0]["description"] == "Updated features section"

    async def test_truncates_content_hash(self, tmp_path: Path) -> None:
        """Test truncates content hash to 16 characters + ellipsis."""
        # Arrange
        manager = VersionManager(tmp_path)
        version_history = cast(
            list[ModelDict],
            [
                {
                    "version": 1,
                    "timestamp": "2024-01-01T10:00:00",
                    "change_type": "created",
                    "size_bytes": 100,
                    "token_count": 50,
                    "content_hash": "abcdefghijklmnopqrstuvwxyz123456",
                    "snapshot_path": ".cortex/history/test.md.v1.snapshot",
                }
            ],
        )

        # Act
        from cortex.core.models import VersionMetadata

        formatted = await manager.export_version_history(
            "test.md", cast(list[VersionMetadata | ModelDict], version_history)
        )

        # Assert
        content_hash = formatted[0]["content_hash"]
        assert isinstance(content_hash, str)
        assert content_hash == "abcdefghijklmnop..."
        assert len(content_hash) == 19


class TestGetSnapshotPath:
    """Tests for get_snapshot_path method."""

    def test_returns_correct_snapshot_path(self, tmp_path: Path) -> None:
        """Test returns correct path for snapshot file."""
        # Arrange
        manager = VersionManager(tmp_path)

        # Act
        snapshot_path = manager.get_snapshot_path("test.md", 3)

        # Assert
        expected_path = tmp_path / ".cortex/history" / "test_v3.md"
        assert snapshot_path == expected_path

    def test_removes_md_extension_from_base_name(self, tmp_path: Path) -> None:
        """Test removes .md extension when constructing snapshot name."""
        # Arrange
        manager = VersionManager(tmp_path)

        # Act
        snapshot_path = manager.get_snapshot_path("document.md", 1)

        # Assert
        assert snapshot_path.name == "document_v1.md"
        assert "document.md_v1" not in str(snapshot_path)

    def test_handles_different_version_numbers(self, tmp_path: Path) -> None:
        """Test handles different version numbers correctly."""
        # Arrange
        manager = VersionManager(tmp_path)

        # Act
        path1 = manager.get_snapshot_path("test.md", 1)
        path10 = manager.get_snapshot_path("test.md", 10)
        path100 = manager.get_snapshot_path("test.md", 100)

        # Assert
        assert path1.name == "test_v1.md"
        assert path10.name == "test_v10.md"
        assert path100.name == "test_v100.md"
