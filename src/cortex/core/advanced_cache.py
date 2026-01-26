"""
Advanced caching layer with warming, prefetching, and statistics.

This module extends the basic caching functionality with:
- Cache warming: Pre-populate caches with frequently accessed data
- Predictive prefetching: Anticipate and load data before it's needed
- Cache statistics: Monitor cache performance and hit rates
- Smart eviction: Optimize cache eviction based on access patterns
"""

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from cortex.core.cache import LRUCache, TTLCache
from cortex.core.models import CacheConfig, JsonValue, ManagerCacheDefaults, ModelDict


class CacheStats(BaseModel):
    """Cache statistics for monitoring performance."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    hits: int = Field(ge=0, description="Number of cache hits")
    misses: int = Field(ge=0, description="Number of cache misses")
    evictions: int = Field(ge=0, description="Number of evictions")
    size: int = Field(ge=0, description="Current cache size")
    hit_rate: float = Field(ge=0.0, le=1.0, description="Hit rate (0-1)")


class AccessPattern(BaseModel):
    """Access pattern for predictive prefetching."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file: str = Field(description="File path")
    co_accessed_files: list[str] = Field(
        default_factory=list, description="Files accessed together"
    )
    frequency: int = Field(ge=0, description="Access frequency")
    last_access: float = Field(ge=0.0, description="Last access timestamp")


class AdvancedCacheManager:
    """
    Advanced cache manager with warming, prefetching, and statistics.

    Features:
    - Multiple cache layers (TTL and LRU)
    - Cache warming from access patterns
    - Predictive prefetching
    - Detailed statistics tracking
    - Smart eviction policies
    """

    def __init__(
        self,
        ttl_seconds: int = 300,
        lru_max_size: int = 100,
        enable_prefetch: bool = True,
    ):
        """
        Initialize advanced cache manager.

        Args:
            ttl_seconds: TTL for time-based cache (default: 5 minutes)
            lru_max_size: Max size for LRU cache (default: 100 entries)
            enable_prefetch: Enable predictive prefetching (default: True)
        """
        self.ttl_cache: TTLCache[JsonValue] = TTLCache(ttl_seconds)
        self.lru_cache: LRUCache[JsonValue] = LRUCache(lru_max_size)
        self.enable_prefetch: bool = enable_prefetch

        # Statistics tracking
        self._stats: dict[str, int] = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "prefetch_hits": 0,
            "prefetch_misses": 0,
        }

        # Access pattern tracking for prefetching
        self._access_patterns: dict[str, AccessPattern] = {}
        self._co_access_tracking: dict[str, list[tuple[str, float]]] = defaultdict(list)

    def get(self, key: str) -> JsonValue | None:
        """
        Get value from cache (tries TTL first, then LRU).

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        # Try TTL cache first (most recent data)
        value = self.ttl_cache.get(key)
        if value is not None:
            self._stats["hits"] += 1
            self._record_access(key)
            return value

        # Try LRU cache second (frequently accessed data)
        value = self.lru_cache.get(key)
        if value is not None:
            self._stats["hits"] += 1
            # Promote to TTL cache for faster access
            self.ttl_cache.set(key, value)
            self._record_access(key)
            return value

        # Cache miss
        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: JsonValue) -> None:
        """
        Set value in both caches.

        Args:
            key: Cache key
            value: Value to cache
        """
        self.ttl_cache.set(key, value)
        self.lru_cache.set(key, value)
        self._record_access(key)

    def invalidate(self, key: str) -> None:
        """
        Invalidate (remove) a specific cache entry from both caches.

        Args:
            key: Cache key to invalidate
        """
        self.ttl_cache.invalidate(key)
        self.lru_cache.invalidate(key)
        self._stats["evictions"] += 1

    def clear(self) -> None:
        """Clear all cache entries from both caches."""
        self.ttl_cache.clear()
        self.lru_cache.clear()
        self._stats["evictions"] += len(self.ttl_cache) + len(self.lru_cache)

    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

        return CacheStats(
            hits=self._stats["hits"],
            misses=self._stats["misses"],
            evictions=self._stats["evictions"],
            size=len(self.ttl_cache) + len(self.lru_cache),
            hit_rate=hit_rate,
        )

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "prefetch_hits": 0,
            "prefetch_misses": 0,
        }

    def _record_access(self, key: str) -> None:
        """
        Record access pattern for predictive prefetching.

        Args:
            key: Cache key that was accessed
        """
        if not self.enable_prefetch:
            return

        now = time.time()

        # Update access pattern
        if key not in self._access_patterns:
            self._access_patterns[key] = AccessPattern(
                file=key,
                co_accessed_files=[],
                frequency=0,
                last_access=now,
            )

        pattern = self._access_patterns[key]
        pattern.frequency += 1
        pattern.last_access = now

        # Track co-accesses (files accessed within 60 seconds)
        recent_accesses = [
            (k, t) for k, t in self._co_access_tracking[key] if now - t < 60
        ]
        self._co_access_tracking[key] = recent_accesses
        self._co_access_tracking[key].append((key, now))

    async def warm_cache(
        self, keys: list[str], loader: Callable[[str], JsonValue]
    ) -> int:
        """
        Warm cache by pre-loading frequently accessed keys.

        Args:
            keys: List of keys to warm
            loader: Async function to load value for a key

        Returns:
            Number of keys successfully warmed
        """
        warmed = 0
        for key in keys:
            try:
                value = await asyncio.to_thread(loader, key)
                self.set(key, value)
                warmed += 1
            except Exception:
                # Skip keys that fail to load
                continue

        return warmed

    async def prefetch_related(
        self, key: str, loader: Callable[[str], JsonValue]
    ) -> int:
        """
        Prefetch files that are frequently co-accessed with the given key.

        Args:
            key: Key that was just accessed
            loader: Async function to load value for a key

        Returns:
            Number of keys successfully prefetched
        """
        if not self.enable_prefetch:
            return 0

        # Get co-accessed files from pattern
        pattern = self._access_patterns.get(key)
        if pattern is None:
            return 0

        prefetched = 0
        for related_key in pattern.co_accessed_files[:5]:  # Limit to top 5
            # Skip if already cached
            if self.get(related_key) is not None:
                self._stats["prefetch_hits"] += 1
                continue

            try:
                value = await asyncio.to_thread(loader, related_key)
                self.set(related_key, value)
                prefetched += 1
            except Exception:
                self._stats["prefetch_misses"] += 1
                continue

        return prefetched

    def update_co_access_patterns(self, co_access_data: dict[str, list[str]]) -> None:
        """
        Update co-access patterns from external data (e.g., PatternAnalyzer).

        Args:
            co_access_data: Dict mapping file to list of co-accessed files
        """
        for file, co_accessed in co_access_data.items():
            if file in self._access_patterns:
                self._access_patterns[file].co_accessed_files = co_accessed
            else:
                self._access_patterns[file] = AccessPattern(
                    file=file,
                    co_accessed_files=co_accessed,
                    frequency=0,
                    last_access=time.time(),
                )

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from TTL cache.

        Returns:
            Number of entries removed
        """
        removed = self.ttl_cache.cleanup_expired()
        self._stats["evictions"] += removed
        return removed

    def get_hot_keys(self, limit: int = 10) -> list[str]:
        """
        Get most frequently accessed keys.

        Args:
            limit: Maximum number of keys to return

        Returns:
            List of hot keys sorted by frequency
        """
        sorted_patterns = sorted(
            self._access_patterns.items(),
            key=lambda x: x[1].frequency,
            reverse=True,
        )
        return [key for key, _ in sorted_patterns[:limit]]

    def get_access_patterns(self) -> dict[str, AccessPattern]:
        """
        Get access patterns for testing and inspection.

        Returns:
            Dictionary of access patterns by key
        """
        return self._access_patterns.copy()


def create_cache_for_manager(
    manager_name: str, config: CacheConfig | ModelDict | None = None
) -> AdvancedCacheManager:
    """
    Create cache instance for a specific manager with optimized settings.

    Args:
        manager_name: Name of the manager (e.g., 'token_counter', 'file_system')
        config: Optional configuration overrides

    Returns:
        Configured AdvancedCacheManager instance
    """

    # Default configurations per manager type
    defaults = ManagerCacheDefaults()
    manager_config = defaults.get_manager_config(manager_name)

    # Update with config overrides if provided
    if config is not None:
        overrides = (
            config
            if isinstance(config, CacheConfig)
            else CacheConfig.model_validate(config)
        )
        manager_config = manager_config.model_copy(update=overrides.model_dump())

    return AdvancedCacheManager(
        ttl_seconds=manager_config.ttl_seconds,
        lru_max_size=manager_config.lru_max_size,
        enable_prefetch=True,
    )
