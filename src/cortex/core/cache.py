"""
Caching layer for frequently accessed data.

This module provides time-based caching with configurable TTL
to improve performance for frequently accessed data.
"""

import time

from cortex.core.constants import CACHE_MAX_SIZE, CACHE_TTL_SECONDS
from cortex.core.models import JsonValue


class TTLCache[T = JsonValue]:
    """Time-based cache with configurable TTL (Time To Live)."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        """
        Initialize TTL cache.

        Design Decision: TTL-based cache eviction
        Context: Need to balance memory usage with cache hit rate
        Decision: Time-based eviction with configurable TTL
        Alternatives Considered: Pure LRU, size-based eviction
        Rationale: TTL prevents stale data while allowing frequent access
        patterns to benefit

        Args:
            ttl_seconds: Time to live for cache entries in seconds (default: 5 minutes)
        """
        self.ttl: int = ttl_seconds
        self._cache: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        """
        Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            # Expired - remove from cache
            del self._cache[key]
        return None

    def set(self, key: str, value: T) -> None:
        """
        Set value in cache with current timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (time.time(), value)

    def invalidate(self, key: str) -> None:
        """
        Invalidate (remove) a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        _ = self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return number of cache entries."""
        return len(self._cache)

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        now = time.time()
        expired_keys = [
            key
            for key, (timestamp, _) in self._cache.items()
            if now - timestamp >= self.ttl
        ]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)


class LRUCache[T = JsonValue]:
    """Least Recently Used (LRU) cache with size limit."""

    def __init__(self, max_size: int = CACHE_MAX_SIZE):
        """
        Initialize LRU cache.

        Design Decision: LRU eviction policy
        Context: Need size-bounded cache with intelligent eviction
        Decision: Least Recently Used (LRU) eviction when full
        Alternatives Considered: FIFO, random eviction, LFU
        Rationale: LRU works well for temporal locality in Memory Bank access patterns

        Args:
            max_size: Maximum number of entries to cache
        """
        self.max_size: int = max_size
        self._cache: dict[str, T] = {}
        self._access_order: list[str] = []

    def get(self, key: str) -> T | None:
        """
        Get value from cache and update access order.

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        if key in self._cache:
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: T) -> None:
        """
        Set value in cache, evicting LRU entry if at capacity.

        Args:
            key: Cache key
            value: Value to cache
        """
        if key in self._cache:
            # Update existing - move to end
            self._access_order.remove(key)
        elif len(self._cache) >= self.max_size:
            # At capacity - evict least recently used
            lru_key = self._access_order.pop(0)
            del self._cache[lru_key]

        self._cache[key] = value
        self._access_order.append(key)

    def invalidate(self, key: str) -> None:
        """
        Invalidate (remove) a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]
            self._access_order.remove(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._access_order.clear()

    def __len__(self) -> int:
        """Return number of cache entries."""
        return len(self._cache)
