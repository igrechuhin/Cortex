"""Lazy initialization wrapper for managers."""

import asyncio
from collections.abc import Awaitable, Callable


class LazyManager[T]:
    """Lazy initialization wrapper for managers.

    Delays manager initialization until first access.
    Thread-safe with async locking.
    """

    def __init__(self, factory: Callable[[], Awaitable[T]], name: str = "") -> None:
        """Initialize lazy manager wrapper.

        Args:
            factory: Async function that creates the manager
            name: Manager name for debugging
        """
        self._factory = factory
        self._name = name
        self._instance: T | None = None
        self._lock = asyncio.Lock()
        self._initializing = False

    async def get(self) -> T:
        """Get manager instance, initializing if needed.

        Returns:
            Initialized manager instance
        """
        if self._instance is not None:
            return self._instance

        async with self._lock:
            # Double-check after acquiring lock
            if self._instance is not None:
                return self._instance

            # Initialize
            self._initializing = True
            try:
                self._instance = await self._factory()
                return self._instance
            finally:
                self._initializing = False

    @property
    def is_initialized(self) -> bool:
        """Check if manager has been initialized."""
        return self._instance is not None

    @property
    def name(self) -> str:
        """Get manager name."""
        return self._name

    async def invalidate(self) -> None:
        """Invalidate cached instance, forcing re-initialization."""
        async with self._lock:
            self._instance = None
