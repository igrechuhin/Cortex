"""Tests for cache utilities."""

from pathlib import Path

from cortex.core.cache_utils import (
    CacheType,
    clear_cache,
    get_cache_dir,
    get_cache_size,
    list_cache_files,
)


class TestGetCacheDir:
    """Tests for get_cache_dir function."""

    def test_get_cache_dir_without_type(self, tmp_path: Path) -> None:
        """Test getting base cache directory."""
        # Act
        result = get_cache_dir(tmp_path)

        # Assert
        assert result == tmp_path / ".cortex" / ".cache"

    def test_get_cache_dir_with_type(self, tmp_path: Path) -> None:
        """Test getting cache subdirectory."""
        # Act
        result = get_cache_dir(tmp_path, CacheType.SUMMARIES)

        # Assert
        assert result == tmp_path / ".cortex" / ".cache" / "summaries"


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clear_cache_when_not_exists(self, tmp_path: Path) -> None:
        """Test clearing cache when directory doesn't exist."""
        # Act
        deleted_count = clear_cache(tmp_path, "summaries")

        # Assert
        assert deleted_count == 0

    def test_clear_cache_specific_type(self, tmp_path: Path) -> None:
        """Test clearing specific cache type."""
        # Arrange
        cache_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Create cache files
        (cache_dir / "file1.json").write_text('{"data": "test1"}')
        (cache_dir / "file2.json").write_text('{"data": "test2"}')
        (cache_dir / "file3.json").write_text('{"data": "test3"}')

        # Act
        deleted_count = clear_cache(tmp_path, CacheType.SUMMARIES)

        # Assert
        assert deleted_count == 3
        assert not (cache_dir / "file1.json").exists()
        assert not (cache_dir / "file2.json").exists()
        assert not (cache_dir / "file3.json").exists()

    def test_clear_cache_all_types(self, tmp_path: Path) -> None:
        """Test clearing entire cache directory."""
        # Arrange
        summaries_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        (summaries_dir / "file1.json").write_text('{"data": "test1"}')

        relevance_dir = tmp_path / ".cortex" / ".cache" / "relevance"
        relevance_dir.mkdir(parents=True, exist_ok=True)
        (relevance_dir / "file2.json").write_text('{"data": "test2"}')

        # Act
        deleted_count = clear_cache(tmp_path)

        # Assert
        assert deleted_count == 2
        assert not (summaries_dir / "file1.json").exists()
        assert not (relevance_dir / "file2.json").exists()

    def test_clear_cache_preserves_directories(self, tmp_path: Path) -> None:
        """Test that clearing cache preserves directory structure."""
        # Arrange
        cache_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "file1.json").write_text('{"data": "test1"}')

        # Act
        clear_cache(tmp_path, CacheType.SUMMARIES)

        # Assert
        assert cache_dir.exists()  # Directory still exists
        assert not (cache_dir / "file1.json").exists()  # File removed


class TestGetCacheSize:
    """Tests for get_cache_size function."""

    def test_get_cache_size_when_not_exists(self, tmp_path: Path) -> None:
        """Test getting cache size when directory doesn't exist."""
        # Act
        size = get_cache_size(tmp_path, "summaries")

        # Assert
        assert size == 0

    def test_get_cache_size_specific_type(self, tmp_path: Path) -> None:
        """Test getting size of specific cache type."""
        # Arrange
        cache_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        cache_dir.mkdir(parents=True, exist_ok=True)

        content1 = '{"data": "test1"}' * 10  # ~150 bytes
        content2 = '{"data": "test2"}' * 20  # ~300 bytes
        (cache_dir / "file1.json").write_text(content1)
        (cache_dir / "file2.json").write_text(content2)

        # Act
        size = get_cache_size(tmp_path, CacheType.SUMMARIES)

        # Assert
        assert size > 0
        assert size >= len(content1) + len(content2)

    def test_get_cache_size_all_types(self, tmp_path: Path) -> None:
        """Test getting size of entire cache directory."""
        # Arrange
        summaries_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        (summaries_dir / "file1.json").write_text('{"data": "test1"}')

        relevance_dir = tmp_path / ".cortex" / ".cache" / "relevance"
        relevance_dir.mkdir(parents=True, exist_ok=True)
        (relevance_dir / "file2.json").write_text('{"data": "test2"}')

        # Act
        size = get_cache_size(tmp_path)

        # Assert
        assert size > 0


class TestListCacheFiles:
    """Tests for list_cache_files function."""

    def test_list_cache_files_when_not_exists(self, tmp_path: Path) -> None:
        """Test listing cache files when directory doesn't exist."""
        # Act
        files = list_cache_files(tmp_path, CacheType.SUMMARIES)

        # Assert
        assert files == []

    def test_list_cache_files_specific_type(self, tmp_path: Path) -> None:
        """Test listing files in specific cache type."""
        # Arrange
        cache_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        cache_dir.mkdir(parents=True, exist_ok=True)

        file1 = cache_dir / "file1.json"
        file2 = cache_dir / "file2.json"
        file1.write_text('{"data": "test1"}')
        file2.write_text('{"data": "test2"}')

        # Act
        files = list_cache_files(tmp_path, CacheType.SUMMARIES)

        # Assert
        assert len(files) == 2
        assert file1 in files
        assert file2 in files

    def test_list_cache_files_all_types(self, tmp_path: Path) -> None:
        """Test listing all cache files."""
        # Arrange
        summaries_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)
        file1 = summaries_dir / "file1.json"
        file1.write_text('{"data": "test1"}')

        relevance_dir = tmp_path / ".cortex" / ".cache" / "relevance"
        relevance_dir.mkdir(parents=True, exist_ok=True)
        file2 = relevance_dir / "file2.json"
        file2.write_text('{"data": "test2"}')

        # Act
        files = list_cache_files(tmp_path)

        # Assert
        assert len(files) == 2
        assert file1 in files
        assert file2 in files

    def test_list_cache_files_sorted(self, tmp_path: Path) -> None:
        """Test that cache files are returned sorted."""
        # Arrange
        cache_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        cache_dir.mkdir(parents=True, exist_ok=True)

        file_z = cache_dir / "z_file.json"
        file_a = cache_dir / "a_file.json"
        file_m = cache_dir / "m_file.json"
        file_z.write_text('{"data": "z"}')
        file_a.write_text('{"data": "a"}')
        file_m.write_text('{"data": "m"}')

        # Act
        files = list_cache_files(tmp_path, CacheType.SUMMARIES)

        # Assert
        assert len(files) == 3
        assert files[0] == file_a
        assert files[1] == file_m
        assert files[2] == file_z

    def test_list_cache_files_excludes_directories(self, tmp_path: Path) -> None:
        """Test that directories are excluded from file list."""
        # Arrange
        cache_dir = tmp_path / ".cortex" / ".cache" / "summaries"
        cache_dir.mkdir(parents=True, exist_ok=True)

        file1 = cache_dir / "file1.json"
        file1.write_text('{"data": "test1"}')

        subdir = cache_dir / "subdir"
        subdir.mkdir()
        file2 = subdir / "file2.json"
        file2.write_text('{"data": "test2"}')

        # Act
        files = list_cache_files(tmp_path, CacheType.SUMMARIES)

        # Assert
        assert len(files) == 2  # Both files included (recursive)
        assert file1 in files
        assert file2 in files
