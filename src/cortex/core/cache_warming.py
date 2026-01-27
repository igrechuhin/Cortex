"""
Cache warming strategies for optimizing cold start performance.

This module provides strategies to pre-populate caches based on:
- Historical access patterns
- File dependencies
- Frequently accessed hot paths
"""

from collections.abc import Callable
from pathlib import Path

from pydantic import ConfigDict, Field

from cortex.core.advanced_cache import AdvancedCacheManager
from cortex.core.models import DictLikeModel, JsonValue, ModelDict


class WarmingStrategy(DictLikeModel):
    """Cache warming strategy configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field(description="Strategy name")
    enabled: bool = Field(description="Whether strategy is enabled")
    priority: int = Field(ge=0, description="Priority (higher = more important)")
    max_items: int = Field(ge=0, description="Maximum items to warm")


class CacheWarmingResult(DictLikeModel):
    """Result of cache warming operation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    strategy: str = Field(description="Strategy name")
    items_warmed: int = Field(ge=0, description="Number of items warmed")
    time_ms: float = Field(ge=0.0, description="Time taken in milliseconds")
    success: bool = Field(description="Whether operation succeeded")


class CacheWarmer:
    """
    Manages cache warming strategies for optimal cold start performance.

    Strategies:
    1. Hot path warming: Pre-load most frequently accessed files
    2. Dependency warming: Pre-load files with many dependents
    3. Recent warming: Pre-load recently accessed files
    4. Mandatory warming: Pre-load critical system files
    """

    def __init__(self, cache_manager: AdvancedCacheManager, project_root: Path):
        """
        Initialize cache warmer.

        Args:
            cache_manager: Advanced cache manager instance
            project_root: Root directory of the project
        """
        self.cache_manager: AdvancedCacheManager = cache_manager
        self.project_root: Path = Path(project_root)
        self._strategy_key_getters = self._build_strategy_key_getters()
        self.strategies = self._build_default_strategies()

    def _build_strategy_key_getters(
        self,
    ) -> dict[str, Callable[[int], list[str]]]:
        """Build strategy key retrieval dispatch table."""
        return {
            "hot_path": self.get_hot_path_keys,
            "dependency": self._get_dependency_keys,
            "recent": self._get_recent_keys,
            "mandatory": self.get_mandatory_keys,
        }

    def _build_default_strategies(self) -> dict[str, WarmingStrategy]:
        """Build default warming strategies."""
        return {
            "hot_path": WarmingStrategy(
                name="Hot Path Warming",
                enabled=True,
                priority=1,
                max_items=20,
            ),
            "dependency": WarmingStrategy(
                name="Dependency Warming",
                enabled=True,
                priority=2,
                max_items=15,
            ),
            "recent": WarmingStrategy(
                name="Recent Access Warming",
                enabled=True,
                priority=3,
                max_items=10,
            ),
            "mandatory": WarmingStrategy(
                name="Mandatory Files Warming",
                enabled=True,
                priority=0,
                max_items=5,
            ),
        }

    async def warm_all(
        self, loader: Callable[[str], JsonValue]
    ) -> list[CacheWarmingResult]:
        """
        Execute all enabled warming strategies in priority order.

        Args:
            loader: Sync function that loads a value for a key (run in a thread)

        Returns:
            List of warming results for each strategy
        """
        results: list[CacheWarmingResult] = []

        # Sort strategies by priority
        sorted_strategies = sorted(self.strategies.items(), key=lambda x: x[1].priority)

        for strategy_name, strategy in sorted_strategies:
            if not strategy.enabled:
                continue

            result = await self._warm_strategy(strategy_name, strategy, loader)
            results.append(result)

        return results

    async def _warm_strategy(
        self,
        strategy_name: str,
        strategy: WarmingStrategy,
        loader: Callable[[str], JsonValue],
    ) -> CacheWarmingResult:
        """
        Execute a single warming strategy.

        Reduced nesting: Used strategy dispatch pattern for key retrieval.
        Nesting: 2 levels (down from 5 levels)

        Args:
            strategy_name: Name of the strategy
            strategy: Strategy configuration
            loader: Sync function that loads a value for a key (run in a thread)

        Returns:
            Warming result
        """
        import time

        start_time = time.time()

        try:
            keys = self._get_strategy_keys(strategy_name, strategy.max_items)
            items_warmed = await self.cache_manager.warm_cache(keys, loader)
            time_ms = (time.time() - start_time) * 1000

            return CacheWarmingResult(
                strategy=strategy.name,
                items_warmed=items_warmed,
                time_ms=time_ms,
                success=True,
            )

        except Exception:
            time_ms = (time.time() - start_time) * 1000
            return CacheWarmingResult(
                strategy=strategy.name,
                items_warmed=0,
                time_ms=time_ms,
                success=False,
            )

    def _get_strategy_keys(self, strategy_name: str, max_items: int) -> list[str]:
        """
        Get keys for a warming strategy using dispatch table.

        Args:
            strategy_name: Name of the warming strategy
            max_items: Maximum number of items to retrieve

        Returns:
            List of cache keys to warm
        """
        key_getter = self._strategy_key_getters.get(strategy_name)
        if key_getter is None:
            return []
        return key_getter(max_items)

    def get_hot_path_keys(self, max_items: int) -> list[str]:
        """
        Get keys for hot path warming (most frequently accessed).

        Args:
            max_items: Maximum number of keys to return

        Returns:
            List of keys to warm
        """
        # Get hot keys from cache manager's access patterns
        return self.cache_manager.get_hot_keys(limit=max_items)

    def _get_dependency_keys(self, max_items: int) -> list[str]:
        """
        Get keys for dependency warming (files with many dependents).

        Args:
            max_items: Maximum number of keys to return

        Returns:
            List of keys to warm
        """
        # This would integrate with DependencyGraph to find high-fanout files
        # For now, return empty list (to be integrated later)
        return []

    def _get_recent_keys(self, max_items: int) -> list[str]:
        """
        Get keys for recent access warming (recently accessed files).

        Args:
            max_items: Maximum number of keys to return

        Returns:
            List of keys to warm
        """
        # This would integrate with PatternAnalyzer to find recent accesses
        # For now, return empty list (to be integrated later)
        return []

    def get_mandatory_keys(self, max_items: int) -> list[str]:
        """
        Get keys for mandatory warming (critical system files).

        Args:
            max_items: Maximum number of keys to return

        Returns:
            List of keys to warm
        """
        # Common mandatory files in memory bank
        mandatory_files = [
            "memorybankinstructions.md",
            "projectBrief.md",
            "activeContext.md",
            "systemPatterns.md",
            "techContext.md",
        ]

        return mandatory_files[:max_items]

    def configure_strategy(
        self, strategy_name: str, config: WarmingStrategy | ModelDict
    ) -> None:
        """
        Configure a warming strategy.

        Args:
            strategy_name: Name of the strategy to configure
            config: Configuration updates as a WarmingStrategy model or dict
        """
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]
            config_dict = (
                config.model_dump() if isinstance(config, WarmingStrategy) else config
            )
            # Update strategy, ignoring unknown keys
            strategy_dict = strategy.model_dump()
            strategy_dict.update(
                {k: v for k, v in config_dict.items() if k in strategy_dict}
            )
            self.strategies[strategy_name] = WarmingStrategy.model_validate(
                strategy_dict
            )

    def disable_strategy(self, strategy_name: str) -> None:
        """
        Disable a warming strategy.

        Args:
            strategy_name: Name of the strategy to disable
        """
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]
            self.strategies[strategy_name] = WarmingStrategy.model_validate(
                {**strategy.model_dump(), "enabled": False}
            )

    def enable_strategy(self, strategy_name: str) -> None:
        """
        Enable a warming strategy.

        Args:
            strategy_name: Name of the strategy to enable
        """
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]
            self.strategies[strategy_name] = WarmingStrategy.model_validate(
                {**strategy.model_dump(), "enabled": True}
            )


async def warm_cache_on_startup(
    cache_manager: AdvancedCacheManager,
    project_root: Path,
    loader: Callable[[str], JsonValue],
) -> list[CacheWarmingResult]:
    """
    Convenience function to warm cache on application startup.

    Args:
        cache_manager: Advanced cache manager instance
        project_root: Root directory of the project
        loader: Sync function that loads a value for a key (run in a thread)

    Returns:
        List of warming results
    """
    warmer = CacheWarmer(cache_manager, project_root)
    return await warmer.warm_all(loader)
