"""Path resolution utilities for Cortex directory structure.

This module provides a centralized way to resolve paths to Cortex resources,
avoiding hardcoded path construction throughout the codebase.
"""

from enum import Enum
from pathlib import Path


class CortexResourceType(Enum):
    """Enumeration of Cortex resource types for path resolution."""

    CORTEX_DIR = ".cortex"
    MEMORY_BANK = "memory-bank"
    PLANS = "plans"
    RULES = "rules"
    HISTORY = "history"
    CONFIG = "config"
    ARCHIVED = "archived"
    REVIEWS = "reviews"
    SESSION = ".session"
    CACHE = ".cache"
    INDEX = "index.json"


def get_cortex_path(project_root: Path, resource_type: CortexResourceType) -> Path:
    """Get the absolute path for a Cortex resource type.

    Args:
        project_root: Root directory of the project
        resource_type: Type of Cortex resource

    Returns:
        Absolute path to the resource

    Examples:
        >>> root = Path("/project")
        >>> get_cortex_path(root, CortexResourceType.MEMORY_BANK)
        Path("/project/.cortex/memory-bank")
        >>> get_cortex_path(root, CortexResourceType.INDEX)
        Path("/project/.cortex/index.json")
        >>> get_cortex_path(root, CortexResourceType.CACHE)
        Path("/project/.cortex/.cache")
    """
    cortex_dir = project_root / ".cortex"

    if resource_type == CortexResourceType.CORTEX_DIR:
        return cortex_dir
    elif resource_type == CortexResourceType.INDEX:
        return cortex_dir / "index.json"
    else:
        return cortex_dir / resource_type.value


def get_cache_path(project_root: Path, cache_type: str | None = None) -> Path:
    """Get cache directory path.

    Args:
        project_root: Root directory of the project
        cache_type: Optional cache subdirectory type (string value, typically from CacheType enum)

    Returns:
        Path to cache directory or cache subdirectory

    Examples:
        >>> root = Path("/project")
        >>> get_cache_path(root)
        Path("/project/.cortex/.cache")
        >>> from cortex.core.cache_utils import CacheType
        >>> get_cache_path(root, CacheType.SUMMARIES.value)
        Path("/project/.cortex/.cache/summaries")
    """
    cache_dir = get_cortex_path(project_root, CortexResourceType.CACHE)

    if cache_type:
        return cache_dir / cache_type

    return cache_dir
