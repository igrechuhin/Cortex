"""Tests for path resolver utilities."""

from pathlib import Path

from cortex.core.cache_utils import CacheType
from cortex.core.path_resolver import (
    CortexResourceType,
    get_cache_path,
    get_cortex_path,
)


class TestGetCortexPath:
    """Tests for get_cortex_path function."""

    def test_get_cortex_dir(self, tmp_path: Path) -> None:
        """Test getting cortex directory path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)

        # Assert
        assert result == tmp_path / ".cortex"

    def test_get_memory_bank_path(self, tmp_path: Path) -> None:
        """Test getting memory bank path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)

        # Assert
        assert result == tmp_path / ".cortex" / "memory-bank"

    def test_get_index_path(self, tmp_path: Path) -> None:
        """Test getting index file path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.INDEX)

        # Assert
        assert result == tmp_path / ".cortex" / "index.json"

    def test_get_cache_path(self, tmp_path: Path) -> None:
        """Test getting cache directory path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.CACHE)

        # Assert
        assert result == tmp_path / ".cortex" / ".cache"

    def test_get_plans_path(self, tmp_path: Path) -> None:
        """Test getting plans directory path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.PLANS)

        # Assert
        assert result == tmp_path / ".cortex" / "plans"


class TestGetCachePath:
    """Tests for get_cache_path function."""

    def test_get_cache_path_without_type(self, tmp_path: Path) -> None:
        """Test getting base cache directory path."""
        # Act
        result = get_cache_path(tmp_path)

        # Assert
        assert result == tmp_path / ".cortex" / ".cache"

    def test_get_cache_path_with_type(self, tmp_path: Path) -> None:
        """Test getting cache subdirectory path."""
        # Act
        result = get_cache_path(tmp_path, CacheType.SUMMARIES.value)

        # Assert
        assert result == tmp_path / ".cortex" / ".cache" / "summaries"

    def test_get_cache_path_with_nested_type(self, tmp_path: Path) -> None:
        """Test getting nested cache subdirectory path."""
        # Act
        result = get_cache_path(tmp_path, "relevance/scores")

        # Assert
        assert result == tmp_path / ".cortex" / ".cache" / "relevance" / "scores"
