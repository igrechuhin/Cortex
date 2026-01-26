"""
Unit tests for MetadataIndex class.

Tests cover:
- Index initialization and schema
- Loading with corruption recovery
- Atomic saving operations
- File metadata updates
- Version history management
- Read/write count tracking
- Dependency graph management
- Statistics and analytics
- File removal and cleanup
"""

import json
from datetime import datetime
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from cortex.core.metadata_index import MetadataIndex
from cortex.core.models import SectionMetadata


class TestMetadataIndexInitialization:
    """Tests for MetadataIndex initialization."""

    def test_initialization_creates_correct_paths(
        self, temp_project_root: Path
    ) -> None:
        """Test MetadataIndex initializes with correct paths."""
        # Arrange & Act
        index = MetadataIndex(temp_project_root)

        # Assert
        assert index.project_root == temp_project_root
        assert index.index_path == temp_project_root / ".cortex" / "index.json"
        assert index.memory_bank_dir == temp_project_root / ".cortex" / "memory-bank"
        assert index.get_data() is None

    def test_schema_version_constant(self):
        """Test schema version is defined."""
        # Assert
        assert MetadataIndex.SCHEMA_VERSION == "1.0.0"


class TestIndexLoading:
    """Tests for index loading operations."""

    @pytest.mark.asyncio
    async def test_load_creates_empty_index_when_not_exists(
        self, temp_project_root: Path
    ) -> None:
        """Test loading creates new empty index when file doesn't exist."""
        # Arrange
        index = MetadataIndex(temp_project_root)

        # Act
        data = await index.load()

        # Assert
        assert data is not None
        assert isinstance(data, dict)
        assert cast(str, data["schema_version"]) == "1.0.0"
        files = cast(dict[str, object], data["files"])
        assert files == {}
        assert "dependency_graph" in data
        assert "usage_analytics" in data
        assert "totals" in data
        assert index.index_path.exists()

    @pytest.mark.asyncio
    async def test_load_reads_existing_valid_index(
        self, temp_project_root: Path
    ) -> None:
        """Test loading reads existing valid index file."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        test_data: dict[str, object] = {
            "schema_version": "1.0.0",
            "files": {"test.md": {"path": "/test.md", "size_bytes": 100}},
            "dependency_graph": {"nodes": [], "edges": []},
            "usage_analytics": {"total_reads": 5},
            "totals": {"total_files": 1},
        }
        _ = index.index_path.write_text(json.dumps(test_data))

        # Act
        data = await index.load()

        # Assert
        assert isinstance(data, dict)
        assert cast(str, data["schema_version"]) == "1.0.0"
        files = cast(dict[str, object], data["files"])
        assert "test.md" in files
        usage_analytics = cast(dict[str, object], data["usage_analytics"])
        assert cast(int, usage_analytics["total_reads"]) == 5

    @pytest.mark.asyncio
    async def test_load_recovers_from_json_corruption(
        self, temp_project_root: Path
    ) -> None:
        """Test loading recovers from corrupted JSON."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = index.index_path.write_text("{invalid json content")

        # Act
        data = await index.load()

        # Assert
        assert data is not None
        assert isinstance(data, dict)
        assert cast(str, data["schema_version"]) == "1.0.0"
        files = cast(dict[str, object], data["files"])
        assert files == {}
        # Should backup corrupted file
        backup_path = index.index_path.with_suffix(".corrupted")
        assert backup_path.exists()

    @pytest.mark.asyncio
    async def test_load_recovers_from_invalid_schema(
        self, temp_project_root: Path
    ) -> None:
        """Test loading recovers from invalid schema."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        invalid_data = {"schema_version": "1.0.0", "missing_required_keys": True}
        _ = index.index_path.write_text(json.dumps(invalid_data))

        # Act
        data = await index.load()

        # Assert
        assert data is not None
        assert "files" in data
        assert "dependency_graph" in data

    @pytest.mark.asyncio
    async def test_load_caches_data_in_memory(self, temp_project_root: Path) -> None:
        """Test loaded data is cached in _data attribute."""
        # Arrange
        index = MetadataIndex(temp_project_root)

        # Act
        _ = await index.load()

        # Assert
        data = index.get_data()
        assert data is not None
        assert isinstance(data, dict)


class TestIndexSaving:
    """Tests for index saving operations."""

    @pytest.mark.asyncio
    async def test_save_writes_to_disk(self, temp_project_root: Path) -> None:
        """Test save writes index to disk."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        await index.save()

        # Assert
        assert index.index_path.exists()
        content = json.loads(index.index_path.read_text())
        assert content["schema_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_save_updates_last_updated_timestamp(
        self, temp_project_root: Path
    ) -> None:
        """Test save updates last_updated field."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        data = index.get_data()
        assert data is not None
        old_timestamp = cast(str, data["last_updated"])

        # Wait a tiny bit to ensure timestamp differs
        import asyncio

        await asyncio.sleep(0.01)

        # Act
        await index.save()

        # Assert
        data = index.get_data()
        assert data is not None
        new_timestamp = cast(str, data["last_updated"])
        assert new_timestamp > old_timestamp

    @pytest.mark.asyncio
    async def test_save_uses_atomic_write(self, temp_project_root: Path) -> None:
        """Test save uses atomic write with temp file."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        await index.save()

        # Assert
        # Temp file should not exist after save
        temp_path = index.index_path.with_suffix(".tmp")
        assert not temp_path.exists()
        # Final file should exist
        assert index.index_path.exists()

    @pytest.mark.asyncio
    async def test_save_does_nothing_when_data_is_none(
        self, temp_project_root: Path
    ) -> None:
        """Test save does nothing when _data is None."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        # Don't load, so _data is None

        # Act
        await index.save()

        # Assert
        assert not index.index_path.exists()

    @pytest.mark.asyncio
    async def test_save_creates_valid_json(self, temp_project_root: Path) -> None:
        """Test saved file contains valid JSON."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        await index.save()

        # Assert
        content = index.index_path.read_text()
        parsed = json.loads(content)  # Should not raise
        assert isinstance(parsed, dict)


class TestFileMetadataUpdates:
    """Tests for file metadata update operations."""

    @pytest.mark.asyncio
    async def test_update_file_metadata_creates_new_entry(
        self, temp_project_root: Path
    ) -> None:
        """Test updating metadata creates new file entry."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        sections = [
            SectionMetadata(title="Introduction", line_start=1, line_end=10),
        ]
        await index.update_file_metadata(
            file_name="test.md",
            path=temp_project_root / "memory-bank/test.md",
            exists=True,
            size_bytes=1024,
            token_count=256,
            content_hash="abc123",
            sections=sections,
            change_source="internal",
        )

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        assert "test.md" in files
        file_meta = cast(dict[str, object], files["test.md"])
        assert cast(int, file_meta["size_bytes"]) == 1024
        assert cast(int, file_meta["token_count"]) == 256
        assert cast(str, file_meta["content_hash"]) == "abc123"
        assert cast(int, file_meta["write_count"]) == 1

    @pytest.mark.asyncio
    async def test_update_file_metadata_increments_write_count(
        self, temp_project_root: Path
    ) -> None:
        """Test updating metadata increments write count for internal changes."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash1",
            [],
            "internal",
        )
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            200,
            100,
            "hash2",
            [],
            "internal",
        )

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        file_meta = cast(dict[str, object], files["test.md"])
        assert cast(int, file_meta["write_count"]) == 2

    @pytest.mark.asyncio
    async def test_update_file_metadata_increments_read_count_for_external(
        self, temp_project_root: Path
    ) -> None:
        """Test external changes increment read count."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        # First create the file
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash1",
            [],
            "internal",
        )

        # Act
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            200,
            100,
            "hash2",
            [],
            "external",
        )

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        file_meta = cast(dict[str, object], files["test.md"])
        assert cast(int, file_meta["read_count"]) == 1

    @pytest.mark.asyncio
    async def test_update_file_metadata_stores_sections(
        self, temp_project_root: Path
    ) -> None:
        """Test metadata update stores section information."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        sections = [
            SectionMetadata(title="Intro", line_start=1, line_end=5),
            SectionMetadata(title="Body", line_start=6, line_end=20),
        ]

        # Act
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            500,
            200,
            "hash",
            sections,
            "internal",
        )

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        file_meta = cast(dict[str, object], files["test.md"])
        assert cast(list[dict[str, object]], file_meta["sections"]) == [
            section.model_dump() for section in sections
        ]

    @pytest.mark.asyncio
    async def test_update_file_metadata_recalculates_totals(
        self, temp_project_root: Path
    ) -> None:
        """Test metadata update recalculates totals."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            1024,
            256,
            "hash",
            [],
            "internal",
        )

        # Assert
        data = index.get_data()
        assert data is not None
        totals = cast(dict[str, object], data["totals"])
        assert cast(int, totals["total_files"]) == 1
        assert cast(int, totals["total_size_bytes"]) == 1024
        assert cast(int, totals["total_tokens"]) == 256


class TestVersionHistory:
    """Tests for version history management."""

    @pytest.mark.asyncio
    async def test_add_version_to_history_appends_version(
        self, temp_project_root: Path
    ) -> None:
        """Test adding version appends to history."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash",
            [],
        )

        version_meta_dict: dict[str, object] = {
            "version": 1,
            "timestamp": datetime.now().isoformat(),
            "content_hash": "hash1",
        }
        version_meta = MagicMock()
        version_meta.version = 1
        version_meta.model_dump = MagicMock(return_value=version_meta_dict)

        # Act
        await index.add_version_to_history("test.md", version_meta)

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        file_meta = cast(dict[str, object], files["test.md"])
        assert cast(int, file_meta["current_version"]) == 1
        version_history = cast(list[dict[str, object]], file_meta["version_history"])
        assert len(version_history) == 1
        assert version_history[0] == version_meta_dict

    @pytest.mark.asyncio
    async def test_add_version_to_history_updates_version_number(
        self, temp_project_root: Path
    ) -> None:
        """Test adding version updates current version number."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash",
            [],
        )

        # Act
        version_meta_dict: dict[str, object] = {
            "version": 5,
            "timestamp": "2025-01-01",
        }
        version_meta = MagicMock()
        version_meta.version = 5
        version_meta.model_dump = MagicMock(return_value=version_meta_dict)
        await index.add_version_to_history("test.md", version_meta)

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        file_meta = cast(dict[str, object], files["test.md"])
        assert cast(int, file_meta["current_version"]) == 5

    @pytest.mark.asyncio
    async def test_add_version_to_nonexistent_file_does_nothing(
        self, temp_project_root: Path
    ) -> None:
        """Test adding version to nonexistent file does nothing."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        version_meta: dict[str, object] = {"version": 1, "timestamp": "2025-01-01"}
        await index.add_version_to_history("nonexistent.md", version_meta)

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        assert "nonexistent.md" not in files


class TestReadCountTracking:
    """Tests for read count tracking."""

    @pytest.mark.asyncio
    async def test_increment_read_count_increases_counter(
        self, temp_project_root: Path
    ) -> None:
        """Test incrementing read count increases counter."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash",
            [],
        )

        # Act
        await index.increment_read_count("test.md")
        await index.increment_read_count("test.md")

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        file_meta = cast(dict[str, object], files["test.md"])
        assert cast(int, file_meta["read_count"]) == 2

    @pytest.mark.asyncio
    async def test_increment_read_count_updates_last_read(
        self, temp_project_root: Path
    ) -> None:
        """Test incrementing read count updates last_read timestamp."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash",
            [],
        )

        # Act
        await index.increment_read_count("test.md")

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        file_meta = cast(dict[str, object], files["test.md"])
        assert "last_read" in file_meta
        # Should be recent timestamp
        last_read = file_meta["last_read"]
        assert last_read is not None

    @pytest.mark.asyncio
    async def test_increment_read_count_updates_analytics(
        self, temp_project_root: Path
    ) -> None:
        """Test incrementing read count updates usage analytics."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash",
            [],
        )
        data = index.get_data()
        assert data is not None
        usage_analytics = cast(dict[str, object], data["usage_analytics"])
        initial_total = cast(int, usage_analytics["total_reads"])

        # Act
        await index.increment_read_count("test.md")

        # Assert
        data = index.get_data()
        assert data is not None
        usage_analytics = cast(dict[str, object], data["usage_analytics"])
        assert cast(int, usage_analytics["total_reads"]) == initial_total + 1

    @pytest.mark.asyncio
    async def test_increment_read_count_for_nonexistent_file(
        self, temp_project_root: Path
    ) -> None:
        """Test incrementing read count for nonexistent file does nothing."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act (should not raise)
        await index.increment_read_count("nonexistent.md")

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        assert "nonexistent.md" not in files


class TestDependencyGraph:
    """Tests for dependency graph management."""

    @pytest.mark.asyncio
    async def test_update_dependency_graph_stores_graph(
        self, temp_project_root: Path
    ) -> None:
        """Test updating dependency graph stores graph data."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        graph_dict: dict[str, object] = {
            "nodes": ["a.md", "b.md"],
            "edges": [{"from": "a.md", "to": "b.md"}],
            "progressive_loading_order": ["a.md", "b.md"],
        }

        # Act
        await index.update_dependency_graph(graph_dict)

        # Assert
        data = index.get_data()
        assert data is not None
        assert data["dependency_graph"] == graph_dict

    @pytest.mark.asyncio
    async def test_get_dependency_graph_returns_graph(
        self, temp_project_root: Path
    ) -> None:
        """Test getting dependency graph returns stored graph."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        graph_dict: dict[str, object] = {"nodes": ["test.md"], "edges": []}
        await index.update_dependency_graph(graph_dict)

        # Act
        result = await index.get_dependency_graph()

        # Assert
        assert result == graph_dict


class TestFileQueries:
    """Tests for file query operations."""

    @pytest.mark.asyncio
    async def test_get_file_metadata_returns_metadata(
        self, temp_project_root: Path
    ) -> None:
        """Test getting file metadata returns correct data."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash",
            [],
        )

        # Act
        meta = await index.get_file_metadata("test.md")

        # Assert
        assert meta is not None
        assert meta["size_bytes"] == 100
        assert meta["token_count"] == 50

    @pytest.mark.asyncio
    async def test_get_file_metadata_returns_none_for_nonexistent(
        self, temp_project_root: Path
    ) -> None:
        """Test getting nonexistent file metadata returns None."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        meta = await index.get_file_metadata("nonexistent.md")

        # Assert
        assert meta is None

    @pytest.mark.asyncio
    async def test_get_all_files_metadata_returns_all_files(
        self, temp_project_root: Path
    ) -> None:
        """Test getting all files metadata returns complete dict."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test1.md",
            temp_project_root / "memory-bank/test1.md",
            True,
            100,
            50,
            "hash",
            [],
        )
        await index.update_file_metadata(
            "test2.md",
            temp_project_root / "memory-bank/test2.md",
            True,
            200,
            100,
            "hash",
            [],
        )

        # Act
        all_files = await index.get_all_files_metadata()

        # Assert
        assert len(all_files) == 2
        assert "test1.md" in all_files
        assert "test2.md" in all_files

    @pytest.mark.asyncio
    async def test_file_exists_in_index_returns_true_for_existing(
        self, temp_project_root: Path
    ) -> None:
        """Test file exists check returns True for existing file."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash",
            [],
        )

        # Act
        exists = await index.file_exists_in_index("test.md")

        # Assert
        assert exists is True

    @pytest.mark.asyncio
    async def test_file_exists_in_index_returns_false_for_nonexistent(
        self, temp_project_root: Path
    ) -> None:
        """Test file exists check returns False for nonexistent file."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act
        exists = await index.file_exists_in_index("nonexistent.md")

        # Assert
        assert exists is False


class TestFileRemoval:
    """Tests for file removal operations."""

    @pytest.mark.asyncio
    async def test_remove_file_deletes_from_index(
        self, temp_project_root: Path
    ) -> None:
        """Test removing file deletes it from index."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            100,
            50,
            "hash",
            [],
        )

        # Act
        await index.remove_file("test.md")

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        assert "test.md" not in files

    @pytest.mark.asyncio
    async def test_remove_file_recalculates_totals(
        self, temp_project_root: Path
    ) -> None:
        """Test removing file recalculates totals."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            1024,
            256,
            "hash",
            [],
        )

        # Act
        await index.remove_file("test.md")

        # Assert
        data = index.get_data()
        assert data is not None
        totals = cast(dict[str, object], data["totals"])
        assert cast(int, totals["total_files"]) == 0
        assert cast(int, totals["total_size_bytes"]) == 0
        assert cast(int, totals["total_tokens"]) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_file_does_nothing(
        self, temp_project_root: Path
    ) -> None:
        """Test removing nonexistent file does nothing."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()

        # Act (should not raise)
        await index.remove_file("nonexistent.md")

        # Assert
        data = index.get_data()
        assert data is not None
        files = cast(dict[str, object], data["files"])
        assert len(files) == 0


class TestStatisticsAndAnalytics:
    """Tests for statistics and analytics operations."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_statistics(self, temp_project_root: Path) -> None:
        """Test getting stats returns totals and analytics."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test.md",
            temp_project_root / "memory-bank/test.md",
            True,
            1024,
            256,
            "hash",
            [],
        )

        # Act
        stats = await index.get_stats()

        # Assert
        assert isinstance(stats, dict)
        assert "totals" in stats
        assert "usage_analytics" in stats
        assert "file_count" in stats
        assert cast(int, stats["file_count"]) == 1
        totals = cast(dict[str, object], stats["totals"])
        assert cast(int, totals["total_files"]) == 1

    @pytest.mark.asyncio
    async def test_update_usage_analytics_sorts_by_read_frequency(
        self, temp_project_root: Path
    ) -> None:
        """Test update usage analytics sorts files by read frequency."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test1.md",
            temp_project_root / "memory-bank/test1.md",
            True,
            100,
            50,
            "hash",
            [],
        )
        await index.update_file_metadata(
            "test2.md",
            temp_project_root / "memory-bank/test2.md",
            True,
            100,
            50,
            "hash",
            [],
        )
        # Make test2 more frequently read
        await index.increment_read_count("test2.md")
        await index.increment_read_count("test2.md")
        await index.increment_read_count("test1.md")

        # Act
        await index.update_usage_analytics()

        # Assert
        data = index.get_data()
        assert data is not None
        usage_analytics = cast(dict[str, object], data["usage_analytics"])
        files_by_reads = cast(
            list[dict[str, object]], usage_analytics["files_by_read_frequency"]
        )
        assert len(files_by_reads) == 2
        assert cast(str, files_by_reads[0]["file"]) == "test2.md"
        assert cast(int, files_by_reads[0]["reads"]) == 2
        assert cast(str, files_by_reads[1]["file"]) == "test1.md"
        assert cast(int, files_by_reads[1]["reads"]) == 1

    @pytest.mark.asyncio
    async def test_update_usage_analytics_sorts_by_write_frequency(
        self, temp_project_root: Path
    ) -> None:
        """Test update usage analytics sorts files by write frequency."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        # test1 gets 1 write
        await index.update_file_metadata(
            "test1.md",
            temp_project_root / "memory-bank/test1.md",
            True,
            100,
            50,
            "hash1",
            [],
            "internal",
        )
        # test2 gets 3 writes
        await index.update_file_metadata(
            "test2.md",
            temp_project_root / "memory-bank/test2.md",
            True,
            100,
            50,
            "hash2",
            [],
            "internal",
        )
        await index.update_file_metadata(
            "test2.md",
            temp_project_root / "memory-bank/test2.md",
            True,
            200,
            100,
            "hash3",
            [],
            "internal",
        )
        await index.update_file_metadata(
            "test2.md",
            temp_project_root / "memory-bank/test2.md",
            True,
            300,
            150,
            "hash4",
            [],
            "internal",
        )

        # Act
        await index.update_usage_analytics()

        # Assert
        data = index.get_data()
        assert data is not None
        usage_analytics = cast(dict[str, object], data["usage_analytics"])
        files_by_writes = cast(
            list[dict[str, object]], usage_analytics["files_by_write_frequency"]
        )
        assert len(files_by_writes) == 2
        assert cast(str, files_by_writes[0]["file"]) == "test2.md"
        assert cast(int, files_by_writes[0]["writes"]) == 3
        assert cast(str, files_by_writes[1]["file"]) == "test1.md"
        assert cast(int, files_by_writes[1]["writes"]) == 1

    @pytest.mark.asyncio
    async def test_update_usage_analytics_limits_to_top_10(
        self, temp_project_root: Path
    ) -> None:
        """Test update usage analytics limits results to top 10."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        # Create 15 files
        for i in range(15):
            await index.update_file_metadata(
                f"test{i}.md",
                temp_project_root / f"memory-bank/test{i}.md",
                True,
                100,
                50,
                f"hash{i}",
                [],
            )

        # Act
        await index.update_usage_analytics()

        # Assert
        data = index.get_data()
        assert data is not None
        usage_analytics = cast(dict[str, object], data["usage_analytics"])
        files_by_reads = cast(
            list[dict[str, object]], usage_analytics["files_by_read_frequency"]
        )
        files_by_writes = cast(
            list[dict[str, object]], usage_analytics["files_by_write_frequency"]
        )
        assert len(files_by_reads) <= 10
        assert len(files_by_writes) <= 10


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_validate_schema_accepts_valid_schema(
        self, temp_project_root: Path
    ) -> None:
        """Test schema validation accepts valid schema."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        valid_data: dict[str, object] = {
            "schema_version": "1.0.0",
            "files": {},
            "dependency_graph": {},
            "usage_analytics": {},
            "totals": {},
        }

        # Act
        is_valid = index.validate_schema(valid_data)

        # Assert
        assert is_valid is True

    def test_validate_schema_rejects_missing_keys(
        self, temp_project_root: Path
    ) -> None:
        """Test schema validation rejects missing required keys."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        invalid_data: dict[str, object] = {"schema_version": "1.0.0", "files": {}}

        # Act
        is_valid = index.validate_schema(invalid_data)

        # Assert
        assert is_valid is False

    def test_validate_schema_rejects_empty_dict(self, temp_project_root: Path) -> None:
        """Test schema validation rejects empty dict."""
        # Arrange
        index = MetadataIndex(temp_project_root)

        # Act
        is_valid = index.validate_schema({})

        # Assert
        assert is_valid is False


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_data_returns_loaded_data(self, temp_project_root: Path) -> None:
        """Test get_data returns _data attribute."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        test_data: dict[str, object] = {"test": "data"}
        # Access protected member for testing purposes
        index._data = test_data  # type: ignore[assignment]

        # Act
        result = index.get_data()

        # Assert
        assert result == test_data

    def test_get_data_returns_none_when_not_loaded(
        self, temp_project_root: Path
    ) -> None:
        """Test get_data returns None when data not loaded."""
        # Arrange
        index = MetadataIndex(temp_project_root)

        # Act
        result = index.get_data()

        # Assert
        assert result is None

    def test_create_empty_index_has_all_required_fields(
        self, temp_project_root: Path
    ) -> None:
        """Test create_empty_index creates properly structured index."""
        # Arrange
        index = MetadataIndex(temp_project_root)

        # Act
        empty = index.create_empty_index()

        # Assert
        assert empty["schema_version"] == "1.0.0"
        assert "created_at" in empty
        assert "last_updated" in empty
        assert "project_root" in empty
        assert "memory_bank_dir" in empty
        assert empty["files"] == {}
        assert "dependency_graph" in empty
        assert "usage_analytics" in empty
        assert "totals" in empty

    def test_create_empty_index_has_valid_timestamps(
        self, temp_project_root: Path
    ) -> None:
        """Test create_empty_index creates valid ISO timestamps."""
        # Arrange
        index = MetadataIndex(temp_project_root)

        # Act
        empty = index.create_empty_index()

        # Assert
        # Should be parseable as ISO format
        _ = datetime.fromisoformat(cast(str, empty["created_at"]))
        _ = datetime.fromisoformat(cast(str, empty["last_updated"]))
        totals = cast(dict[str, object], empty["totals"])
        _ = datetime.fromisoformat(cast(str, totals["last_full_scan"]))


class TestTotalsRecalculation:
    """Tests for totals recalculation."""

    @pytest.mark.asyncio
    async def test_recalculate_totals_sums_files(self, temp_project_root: Path) -> None:
        """Test recalculating totals sums all file stats."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        await index.update_file_metadata(
            "test1.md",
            temp_project_root / "memory-bank/test1.md",
            True,
            1024,
            256,
            "hash1",
            [],
        )
        await index.update_file_metadata(
            "test2.md",
            temp_project_root / "memory-bank/test2.md",
            True,
            2048,
            512,
            "hash2",
            [],
        )

        # Act
        await index.recalculate_totals()

        # Assert
        data = index.get_data()
        assert data is not None
        totals = cast(dict[str, object], data["totals"])
        assert cast(int, totals["total_files"]) == 2
        assert cast(int, totals["total_size_bytes"]) == 3072
        assert cast(int, totals["total_tokens"]) == 768

    @pytest.mark.asyncio
    async def test_recalculate_totals_updates_timestamp(
        self, temp_project_root: Path
    ) -> None:
        """Test recalculating totals updates last_full_scan."""
        # Arrange
        index = MetadataIndex(temp_project_root)
        _ = await index.load()
        data = index.get_data()
        assert data is not None
        totals = cast(dict[str, object], data["totals"])
        old_timestamp = cast(str, totals["last_full_scan"])

        import asyncio

        await asyncio.sleep(0.01)

        # Act
        await index.recalculate_totals()

        # Assert
        data = index.get_data()
        assert data is not None
        totals = cast(dict[str, object], data["totals"])
        new_timestamp = cast(str, totals["last_full_scan"])
        assert new_timestamp > old_timestamp
