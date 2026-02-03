"""Tests for path resolver utilities."""

from pathlib import Path

from cortex.core.cache_utils import CacheType
from cortex.core.path_resolver import (
    CortexResourceType,
    get_cache_path,
    get_cortex_path,
    is_memory_bank_fully_initialized,
)


class TestGetCortexPath:
    """Tests for get_cortex_path function."""

    def test_get_cortex_dir(self, tmp_path: Path) -> None:
        """Test getting cortex directory path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.CORTEX_DIR)

        # Assert
        expected = tmp_path / CortexResourceType.CORTEX_DIR.value
        assert result == expected

    def test_get_memory_bank_path(self, tmp_path: Path) -> None:
        """Test getting memory bank path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)

        # Assert
        expected = (
            tmp_path
            / CortexResourceType.CORTEX_DIR.value
            / CortexResourceType.MEMORY_BANK.value
        )
        assert result == expected

    def test_get_index_path(self, tmp_path: Path) -> None:
        """Test getting index file path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.INDEX)

        # Assert
        expected = (
            tmp_path
            / CortexResourceType.CORTEX_DIR.value
            / CortexResourceType.INDEX.value
        )
        assert result == expected

    def test_get_cache_path(self, tmp_path: Path) -> None:
        """Test getting cache directory path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.CACHE)

        # Assert
        expected = (
            tmp_path
            / CortexResourceType.CORTEX_DIR.value
            / CortexResourceType.CACHE.value
        )
        assert result == expected

    def test_get_plans_path(self, tmp_path: Path) -> None:
        """Test getting plans directory path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.PLANS)

        # Assert
        expected = (
            tmp_path
            / CortexResourceType.CORTEX_DIR.value
            / CortexResourceType.PLANS.value
        )
        assert result == expected

    def test_get_script_capture_path(self, tmp_path: Path) -> None:
        """Test getting script-capture directory path."""
        # Act
        result = get_cortex_path(tmp_path, CortexResourceType.SCRIPT_CAPTURE)

        # Assert
        expected = (
            tmp_path
            / CortexResourceType.CORTEX_DIR.value
            / CortexResourceType.SCRIPT_CAPTURE.value
        )
        assert result == expected


class TestGetCachePath:
    """Tests for get_cache_path function."""

    def test_get_cache_path_without_type(self, tmp_path: Path) -> None:
        """Test getting base cache directory path."""
        # Act
        result = get_cache_path(tmp_path)

        # Assert
        expected = get_cortex_path(tmp_path, CortexResourceType.CACHE)
        assert result == expected

    def test_get_cache_path_with_type(self, tmp_path: Path) -> None:
        """Test getting cache subdirectory path."""
        # Act
        result = get_cache_path(tmp_path, CacheType.SUMMARIES.value)

        # Assert
        expected = (
            get_cortex_path(tmp_path, CortexResourceType.CACHE)
            / CacheType.SUMMARIES.value
        )
        assert result == expected

    def test_get_cache_path_with_nested_type(self, tmp_path: Path) -> None:
        """Test getting nested cache subdirectory path."""
        # Act
        result = get_cache_path(tmp_path, "relevance/scores")

        # Assert
        expected = (
            get_cortex_path(tmp_path, CortexResourceType.CACHE) / "relevance" / "scores"
        )
        assert result == expected


class TestIsMemoryBankFullyInitialized:
    """Tests for is_memory_bank_fully_initialized function."""

    def test_returns_false_when_no_memory_bank_dir(self, tmp_path: Path) -> None:
        """When .cortex/memory-bank does not exist, returns False."""
        assert is_memory_bank_fully_initialized(tmp_path) is False

    def test_returns_false_when_some_core_files_missing(self, tmp_path: Path) -> None:
        """When memory-bank exists but not all 7 core files, returns False."""
        mb = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mb.mkdir(parents=True)
        _ = (mb / "projectBrief.md").write_text("#")
        _ = (mb / "productContext.md").write_text("#")
        assert is_memory_bank_fully_initialized(tmp_path) is False

    def test_returns_true_when_all_seven_core_files_present(
        self, tmp_path: Path
    ) -> None:
        """When all 7 core files exist, returns True."""
        mb = get_cortex_path(tmp_path, CortexResourceType.MEMORY_BANK)
        mb.mkdir(parents=True)
        for f in (
            "projectBrief.md",
            "productContext.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
            "progress.md",
            "roadmap.md",
        ):
            _ = (mb / f).write_text("#")
        assert is_memory_bank_fully_initialized(tmp_path) is True
