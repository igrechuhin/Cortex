#!/usr/bin/env python3
"""Manager registry for dependency injection and lifecycle management.

This module provides a centralized registry for manager instances, replacing
the previous module-level global cache. This improves testability and follows
proper dependency injection patterns.
"""

from pathlib import Path


class ManagerRegistry:
    """Registry for manager instances with project-scoped caching.

    The ManagerRegistry eliminates global state by providing an injectable
    container for manager instances. Each registry instance maintains its own
    cache of managers per project root.

    Example:
        >>> registry = ManagerRegistry()
        >>> managers = await registry.get_managers(project_root)
        >>> fs = managers["fs"]
    """

    def __init__(self) -> None:
        """Initialize an empty manager registry."""
        self._managers: dict[str, dict[str, object]] = {}

    async def get_managers(self, project_root: Path) -> dict[str, object]:
        """Get or initialize managers for a project with lazy loading.

        Core managers (priority 1) are initialized immediately for reliability.
        Other managers are wrapped in LazyManager for on-demand initialization.

        Args:
            project_root: Project root directory

        Returns:
            Dictionary of manager instances (or LazyManager wrappers)
        """
        from cortex.managers.initialization import initialize_managers

        root_str = str(project_root)

        if root_str not in self._managers:
            managers = await initialize_managers(project_root)
            self._managers[root_str] = managers

        return self._managers[root_str]

    def clear_cache(self, project_root: Path | None = None) -> None:
        """Clear cached managers for testing or cleanup.

        Args:
            project_root: Optional project root to clear. If None, clears all.
        """
        if project_root is None:
            self._managers.clear()
        else:
            root_str = str(project_root)
            _ = self._managers.pop(root_str, None)

    def has_managers(self, project_root: Path) -> bool:
        """Check if managers are cached for a project root.

        Args:
            project_root: Project root directory

        Returns:
            True if managers are cached for this project
        """
        return str(project_root) in self._managers
