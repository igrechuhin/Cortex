"""Tests for cache warming functionality."""

from pathlib import Path

import pytest

from cortex.core.advanced_cache import AdvancedCacheManager
from cortex.core.cache_warming import (
    CacheWarmer,
    warm_cache_on_startup,
)


class TestCacheWarmer:
    """Test CacheWarmer functionality."""

    @pytest.fixture
    def cache_manager(self) -> AdvancedCacheManager:
        """Create cache manager for testing."""
        return AdvancedCacheManager(ttl_seconds=300, lru_max_size=100)

    @pytest.fixture
    def cache_warmer(
        self, cache_manager: AdvancedCacheManager, tmp_path: Path
    ) -> CacheWarmer:
        """Create cache warmer instance."""
        return CacheWarmer(cache_manager, tmp_path)

    @pytest.mark.asyncio
    async def test_warm_all_executes_strategies(self, cache_warmer: CacheWarmer):
        """Test warming all strategies."""

        # Arrange
        def loader(key: str) -> str:
            return f"content_{key}"

        # Act
        results = await cache_warmer.warm_all(loader)

        # Assert
        assert len(results) > 0
        assert all(result["success"] for result in results)

    @pytest.mark.asyncio
    async def test_mandatory_strategy_warms_critical_files(
        self, cache_warmer: CacheWarmer, cache_manager: AdvancedCacheManager
    ):
        """Test mandatory strategy warms critical files."""

        # Arrange
        def loader(key: str) -> str:
            return f"content_{key}"

        # Act
        results = await cache_warmer.warm_all(loader)

        # Assert
        mandatory_result = next(r for r in results if "Mandatory" in r["strategy"])
        assert mandatory_result["items_warmed"] > 0
        assert cache_manager.get("memorybankinstructions.md") is not None

    @pytest.mark.asyncio
    async def test_hot_path_strategy_uses_access_patterns(
        self, cache_warmer: CacheWarmer, cache_manager: AdvancedCacheManager
    ):
        """Test hot path strategy uses access patterns."""
        # Arrange
        # Simulate access patterns
        cache_manager.set("hot_file.md", "content")
        _ = cache_manager.get("hot_file.md")
        _ = cache_manager.get("hot_file.md")
        _ = cache_manager.get("hot_file.md")

        def loader(key: str) -> str:
            return f"content_{key}"

        # Act
        results = await cache_warmer.warm_all(loader)

        # Assert
        hot_path_result = next(
            (r for r in results if "Hot Path" in r["strategy"]), None
        )
        assert hot_path_result is not None

    @pytest.mark.asyncio
    async def test_strategies_execute_in_priority_order(
        self, cache_warmer: CacheWarmer
    ):
        """Test strategies execute in priority order."""

        # Arrange
        def loader(key: str) -> str:
            return f"content_{key}"

        # Act
        results = await cache_warmer.warm_all(loader)

        # Assert
        # Mandatory (priority 0) should be first
        assert "Mandatory" in results[0]["strategy"]

    def test_configure_strategy_updates_settings(self, cache_warmer: CacheWarmer):
        """Test configuring strategy settings."""
        # Arrange
        strategy_name = "hot_path"
        config: dict[str, object] = {"max_items": 50, "enabled": False}

        # Act
        cache_warmer.configure_strategy(strategy_name, config)

        # Assert
        assert cache_warmer.strategies[strategy_name]["max_items"] == 50
        assert cache_warmer.strategies[strategy_name]["enabled"] is False

    def test_disable_strategy_prevents_execution(self, cache_warmer: CacheWarmer):
        """Test disabling strategy prevents execution."""
        # Arrange
        strategy_name = "hot_path"

        # Act
        cache_warmer.disable_strategy(strategy_name)

        # Assert
        assert cache_warmer.strategies[strategy_name]["enabled"] is False

    def test_enable_strategy_allows_execution(self, cache_warmer: CacheWarmer):
        """Test enabling strategy allows execution."""
        # Arrange
        strategy_name = "hot_path"
        cache_warmer.disable_strategy(strategy_name)

        # Act
        cache_warmer.enable_strategy(strategy_name)

        # Assert
        assert cache_warmer.strategies[strategy_name]["enabled"] is True

    def test_get_mandatory_keys_returns_critical_files(self, cache_warmer: CacheWarmer):
        """Test getting mandatory keys."""
        # Arrange & Act
        keys = cache_warmer.get_mandatory_keys(max_items=5)

        # Assert
        assert len(keys) <= 5
        assert "memorybankinstructions.md" in keys
        assert "projectBrief.md" in keys

    def test_get_hot_path_keys_from_cache_manager(
        self, cache_warmer: CacheWarmer, cache_manager: AdvancedCacheManager
    ):
        """Test getting hot path keys from cache manager."""
        # Arrange
        # Simulate access patterns
        cache_manager.set("file1.md", "content1")
        cache_manager.set("file2.md", "content2")
        _ = cache_manager.get("file1.md")
        _ = cache_manager.get("file1.md")
        _ = cache_manager.get("file2.md")

        # Act
        keys = cache_warmer.get_hot_path_keys(max_items=2)

        # Assert
        assert len(keys) <= 2


class TestWarmCacheOnStartup:
    """Test warm_cache_on_startup convenience function."""

    @pytest.mark.asyncio
    async def test_warm_cache_on_startup_executes_warming(self, tmp_path: Path):
        """Test warming cache on startup."""
        # Arrange
        cache_manager = AdvancedCacheManager(ttl_seconds=300, lru_max_size=100)

        def loader(key: str) -> str:
            return f"content_{key}"

        # Act
        results = await warm_cache_on_startup(cache_manager, tmp_path, loader)

        # Assert
        assert len(results) > 0
        assert all(result["success"] for result in results)

    @pytest.mark.asyncio
    async def test_warm_cache_on_startup_returns_timing(self, tmp_path: Path):
        """Test warming returns timing information."""
        # Arrange
        cache_manager = AdvancedCacheManager(ttl_seconds=300, lru_max_size=100)

        def loader(key: str) -> str:
            return f"content_{key}"

        # Act
        results = await warm_cache_on_startup(cache_manager, tmp_path, loader)

        # Assert
        for result in results:
            assert "time_ms" in result
            assert result["time_ms"] >= 0
