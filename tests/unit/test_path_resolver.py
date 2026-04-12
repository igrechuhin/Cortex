"""Tests for path resolver utilities."""

from pathlib import Path

from cortex.core.cache_utils import CacheType
from cortex.core.path_resolver import (
    WIKI_DIR_PROJECT_RELATIVE_POSIX,
    WIKI_SOURCES_DIR_PROJECT_RELATIVE_PREFIX,
    CortexResourceType,
    ProjectResourceType,
    augmented_environ_with_project_venv_bins,
    get_cache_path,
    get_constitution_path,
    get_cortex_path,
    get_legacy_venv_bin_path,
    get_node_modules_bin_dir,
    get_node_modules_bin_path,
    get_project_path,
    get_venv_bin_path,
    is_memory_bank_fully_initialized,
    iter_venv_executable_candidates,
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

    def test_get_constitution_path(self, tmp_path: Path) -> None:
        """Test getting constitution file path."""
        # Act
        result = get_constitution_path(tmp_path)

        # Assert
        expected = (
            tmp_path
            / CortexResourceType.CORTEX_DIR.value
            / CortexResourceType.MEMORY_BANK.value
            / "constitution.md"
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

    def test_get_wiki_path(self, tmp_path: Path) -> None:
        """Test getting project wiki directory path."""
        result = get_cortex_path(tmp_path, CortexResourceType.WIKI)
        expected = (
            tmp_path
            / CortexResourceType.CORTEX_DIR.value
            / CortexResourceType.WIKI.value
        )
        assert result == expected

    def test_wiki_project_relative_constants_match_get_cortex_path(
        self, tmp_path: Path
    ) -> None:
        """Wiki posix constants stay aligned with ``get_cortex_path(..., WIKI)``."""
        wiki = get_cortex_path(tmp_path, CortexResourceType.WIKI)
        assert wiki.relative_to(tmp_path).as_posix() == WIKI_DIR_PROJECT_RELATIVE_POSIX
        sources = wiki / "sources"
        assert (
            f"{sources.relative_to(tmp_path).as_posix()}/"
            == WIKI_SOURCES_DIR_PROJECT_RELATIVE_PREFIX
        )


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


class TestProjectVenvAndNodePaths:
    """Tests for venv and node_modules path helpers."""

    def test_get_legacy_venv_bin_path(self, tmp_path: Path) -> None:
        """Legacy venv uses project_root/venv/bin."""
        assert get_legacy_venv_bin_path(tmp_path) == tmp_path / "venv" / "bin"

    def test_get_node_modules_bin_dir_matches_project_resource_type(
        self, tmp_path: Path
    ) -> None:
        """node_modules/.bin aligns with ProjectResourceType.NODE_MODULES."""
        assert (
            get_node_modules_bin_dir(tmp_path)
            == get_project_path(tmp_path, ProjectResourceType.NODE_MODULES) / ".bin"
        )

    def test_get_node_modules_bin_path_appends_executable(self, tmp_path: Path) -> None:
        """Full CLI path is bin dir + executable name."""
        assert (
            get_node_modules_bin_path(tmp_path, "rumdl")
            == get_node_modules_bin_dir(tmp_path) / "rumdl"
        )

    def test_iter_venv_executable_candidates_order(self, tmp_path: Path) -> None:
        """Yields .venv/bin/name before venv/bin/name."""
        names = list(iter_venv_executable_candidates(tmp_path, "rumdl"))
        assert names == [
            get_venv_bin_path(tmp_path) / "rumdl",
            get_legacy_venv_bin_path(tmp_path) / "rumdl",
        ]

    def test_augmented_environ_prepends_venv_bins_to_path(self, tmp_path: Path) -> None:
        """Prepend order matches iter_venv_executable_candidates (.venv then venv)."""
        dot_venv_bin = tmp_path / ".venv" / "bin"
        legacy_bin = tmp_path / "venv" / "bin"
        _ = dot_venv_bin.mkdir(parents=True)
        _ = legacy_bin.mkdir(parents=True)
        env = augmented_environ_with_project_venv_bins(tmp_path)
        path = env.get("PATH", "")
        assert path.startswith(str(dot_venv_bin.resolve()))
        assert str(legacy_bin.resolve()) in path
        assert path.index(str(dot_venv_bin.resolve())) < path.index(
            str(legacy_bin.resolve())
        )
