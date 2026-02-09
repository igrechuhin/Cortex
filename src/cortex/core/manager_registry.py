#!/usr/bin/env python3
"""Manager registry for dependency injection and lifecycle management.

This module provides a centralized registry for manager instances, replacing
the previous module-level global cache. This improves testability and follows
proper dependency injection patterns.

Process-scoped registry: get_process_registry() returns a single registry
instance per process so that concurrent MCP tool calls share the same cache
and only one initialization runs (see ensure_usage_context lock).
"""

from pathlib import Path

from cortex.managers.types import ManagersDict


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
        self._managers: dict[str, ManagersDict] = {}

    async def get_managers(self, project_root: Path) -> ManagersDict:
        """Get or initialize managers for a project with lazy loading.

        Core managers (priority 1) are initialized immediately for reliability.
        Other managers are wrapped in LazyManager for on-demand initialization.

        Args:
            project_root: Project root directory

        Returns:
            Managers dictionary with type-safe access
        """
        from cortex.managers.initialization import initialize_managers

        root_str = str(project_root)

        if root_str not in self._managers:
            managers = await initialize_managers(project_root)
            # Convert to ManagersDict if needed
            if isinstance(managers, dict):
                self._managers[root_str] = ManagersDict.model_validate(managers)
            else:
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


# Process-scoped registry (defined after class to avoid forward declarations).
_process_registry: ManagerRegistry | None = None


def get_process_registry() -> ManagerRegistry:
    """Return the process-scoped registry (one init per project root)."""
    global _process_registry
    if _process_registry is None:
        _process_registry = ManagerRegistry()
    return _process_registry
