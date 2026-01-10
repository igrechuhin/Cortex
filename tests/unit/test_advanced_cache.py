"""Tests for advanced caching functionality."""

import time

import pytest

from cortex.core.advanced_cache import (
    AdvancedCacheManager,
    create_cache_for_manager,
)


class TestAdvancedCacheManager:
    """Test AdvancedCacheManager functionality."""

    @pytest.fixture
    def cache_manager(self) -> AdvancedCacheManager:
        """Create cache manager instance for testing."""
        return AdvancedCacheManager(ttl_seconds=60, lru_max_size=10)

    def test_cache_initialization(self):
        """Test cache manager initialization."""
        # Arrange & Act
        cache = AdvancedCacheManager(ttl_seconds=120, lru_max_size=50)

        # Assert
        assert cache.ttl_cache.ttl == 120
        assert cache.lru_cache.max_size == 50
        assert cache.enable_prefetch is True

    def test_get_miss_returns_none(self, cache_manager: AdvancedCacheManager):
        """Test cache miss returns None."""
        # Arrange
        key = "nonexistent_key"

        # Act
        result = cache_manager.get(key)

        # Assert
        assert result is None

    def test_set_and_get_value(self, cache_manager: AdvancedCacheManager):
        """Test setting and getting cache value."""
        # Arrange
        key = "test_key"
        value = {"data": "test_value"}

        # Act
        cache_manager.set(key, value)
        result = cache_manager.get(key)

        # Assert
        assert result == value

    def test_get_from_ttl_cache_first(self, cache_manager: AdvancedCacheManager):
        """Test that TTL cache is checked first."""
        # Arrange
        key = "test_key"
        value = "test_value"
        cache_manager.set(key, value)

        # Act
        result = cache_manager.get(key)

        # Assert
        assert result == value
        assert cache_manager.ttl_cache.get(key) == value

    def test_get_from_lru_cache_when_ttl_expired(
        self, cache_manager: AdvancedCacheManager
    ):
        """Test fallback to LRU cache when TTL expires."""
        # Arrange
        cache_manager = AdvancedCacheManager(ttl_seconds=1, lru_max_size=10)
        key = "test_key"
        value = "test_value"
        cache_manager.set(key, value)

        # Act - Wait for TTL to expire
        time.sleep(1.1)
        result = cache_manager.get(key)

        # Assert - Should still get from LRU cache
        assert result == value

    def test_invalidate_removes_from_both_caches(
        self, cache_manager: AdvancedCacheManager
    ):
        """Test invalidation removes from both caches."""
        # Arrange
        key = "test_key"
        value = "test_value"
        cache_manager.set(key, value)

        # Act
        cache_manager.invalidate(key)

        # Assert
        assert cache_manager.get(key) is None
        assert cache_manager.ttl_cache.get(key) is None
        assert cache_manager.lru_cache.get(key) is None

    def test_clear_removes_all_entries(self, cache_manager: AdvancedCacheManager):
        """Test clear removes all cache entries."""
        # Arrange
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")
        cache_manager.set("key3", "value3")

        # Act
        cache_manager.clear()

        # Assert
        assert cache_manager.get("key1") is None
        assert cache_manager.get("key2") is None
        assert cache_manager.get("key3") is None

    def test_get_stats_returns_correct_metrics(
        self, cache_manager: AdvancedCacheManager
    ):
        """Test statistics tracking."""
        # Arrange
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")

        # Act - Generate hits and misses
        _ = cache_manager.get("key1")  # Hit
        _ = cache_manager.get("key2")  # Hit
        _ = cache_manager.get("key3")  # Miss
        _ = cache_manager.get("key4")  # Miss

        stats = cache_manager.get_stats()

        # Assert
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["hit_rate"] == 0.5
        assert stats["size"] > 0

    def test_reset_stats_clears_counters(self, cache_manager: AdvancedCacheManager):
        """Test statistics reset."""
        # Arrange
        cache_manager.set("key1", "value1")
        _ = cache_manager.get("key1")  # Hit
        _ = cache_manager.get("key2")  # Miss

        # Act
        cache_manager.reset_stats()
        stats = cache_manager.get_stats()

        # Assert
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    def test_update_co_access_patterns(self, cache_manager: AdvancedCacheManager):
        """Test updating co-access patterns."""
        # Arrange
        co_access_data = {
            "file1.md": ["file2.md", "file3.md"],
            "file2.md": ["file1.md", "file4.md"],
        }

        # Act
        cache_manager.update_co_access_patterns(co_access_data)

        # Assert
        access_patterns = cache_manager.get_access_patterns()
        assert "file1.md" in access_patterns
        assert access_patterns["file1.md"]["co_accessed_files"] == [
            "file2.md",
            "file3.md",
        ]

    def test_cleanup_expired_removes_old_entries(self):
        """Test cleanup of expired TTL entries."""
        # Arrange
        cache_manager = AdvancedCacheManager(ttl_seconds=1, lru_max_size=10)
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")

        # Act - Wait for expiration
        time.sleep(1.1)
        removed = cache_manager.cleanup_expired()

        # Assert
        assert removed == 2
        assert cache_manager.ttl_cache.get("key1") is None
        assert cache_manager.ttl_cache.get("key2") is None

    def test_get_hot_keys_returns_most_frequent(
        self, cache_manager: AdvancedCacheManager
    ):
        """Test getting most frequently accessed keys."""
        # Arrange
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")
        cache_manager.set("key3", "value3")

        # Access keys with different frequencies
        for _ in range(5):
            _ = cache_manager.get("key1")
        for _ in range(3):
            _ = cache_manager.get("key2")
        _ = cache_manager.get("key3")

        # Act
        hot_keys = cache_manager.get_hot_keys(limit=2)

        # Assert
        assert len(hot_keys) <= 2
        assert "key1" in hot_keys  # Most frequent

    @pytest.mark.asyncio
    async def test_warm_cache_loads_keys(self, cache_manager: AdvancedCacheManager):
        """Test cache warming loads keys."""
        # Arrange
        keys = ["key1", "key2", "key3"]

        def loader(key: str) -> str:
            return f"value_{key}"

        # Act
        warmed = await cache_manager.warm_cache(keys, loader)

        # Assert
        assert warmed == 3
        assert cache_manager.get("key1") == "value_key1"
        assert cache_manager.get("key2") == "value_key2"
        assert cache_manager.get("key3") == "value_key3"

    @pytest.mark.asyncio
    async def test_warm_cache_handles_loader_failures(
        self, cache_manager: AdvancedCacheManager
    ):
        """Test cache warming handles loader failures gracefully."""
        # Arrange
        keys = ["key1", "key2", "key3"]

        def failing_loader(key: str) -> str:
            if key == "key2":
                raise ValueError("Load failed")
            return f"value_{key}"

        # Act
        warmed = await cache_manager.warm_cache(keys, failing_loader)

        # Assert
        assert warmed == 2  # Only 2 succeeded
        assert cache_manager.get("key1") == "value_key1"
        assert cache_manager.get("key2") is None  # Failed to load
        assert cache_manager.get("key3") == "value_key3"

    @pytest.mark.asyncio
    async def test_prefetch_related_loads_co_accessed_files(
        self, cache_manager: AdvancedCacheManager
    ):
        """Test prefetching related files."""
        # Arrange
        cache_manager.update_co_access_patterns(
            {"file1.md": ["file2.md", "file3.md", "file4.md"]}
        )

        def loader(key: str) -> str:
            return f"content_{key}"

        # Act
        prefetched = await cache_manager.prefetch_related("file1.md", loader)

        # Assert
        assert prefetched > 0
        assert cache_manager.get("file2.md") == "content_file2.md"
        assert cache_manager.get("file3.md") == "content_file3.md"

    @pytest.mark.asyncio
    async def test_prefetch_skips_already_cached(
        self, cache_manager: AdvancedCacheManager
    ):
        """Test prefetching skips already cached items."""
        # Arrange
        cache_manager.update_co_access_patterns({"file1.md": ["file2.md", "file3.md"]})
        cache_manager.set("file2.md", "already_cached")

        def loader(key: str) -> str:
            return f"content_{key}"

        # Act
        prefetched = await cache_manager.prefetch_related("file1.md", loader)

        # Assert
        assert prefetched == 1  # Only file3.md was prefetched
        assert cache_manager.get("file2.md") == "already_cached"
        assert cache_manager.get("file3.md") == "content_file3.md"


class TestCreateCacheForManager:
    """Test cache factory function."""

    def test_create_cache_for_token_counter(self):
        """Test creating cache for token counter."""
        # Arrange & Act
        cache = create_cache_for_manager("token_counter")

        # Assert
        assert cache.ttl_cache.ttl == 600
        assert cache.lru_cache.max_size == 200

    def test_create_cache_for_file_system(self):
        """Test creating cache for file system."""
        # Arrange & Act
        cache = create_cache_for_manager("file_system")

        # Assert
        assert cache.ttl_cache.ttl == 300
        assert cache.lru_cache.max_size == 100

    def test_create_cache_with_custom_config(self):
        """Test creating cache with custom configuration."""
        # Arrange
        config: dict[str, object] = {"ttl_seconds": 1800, "lru_max_size": 500}

        # Act
        cache = create_cache_for_manager("token_counter", config)

        # Assert
        assert cache.ttl_cache.ttl == 1800
        assert cache.lru_cache.max_size == 500

    def test_create_cache_for_unknown_manager(self):
        """Test creating cache for unknown manager uses defaults."""
        # Arrange & Act
        cache = create_cache_for_manager("unknown_manager")

        # Assert
        assert cache.ttl_cache.ttl == 300  # Default
        assert cache.lru_cache.max_size == 100  # Default
