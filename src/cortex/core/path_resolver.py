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
    SCRIPT_CAPTURE = "script-capture"
    RULES = "rules"
    HISTORY = "history"
    CONFIG = "config"
    SYNAPSE = "synapse"
    ARCHIVED = "archived"
    REVIEWS = "reviews"
    SESSION = ".session"
    CACHE = ".cache"
    INDEX = "index.json"


class CursorResourceType(Enum):
    """Enumeration of Cursor integration resource types for path resolution."""

    CURSOR_DIR = ".cursor"
    MEMORY_BANK = "memory-bank"
    RULES = "rules"
    PLANS = "plans"


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
    cortex_dir = project_root / CortexResourceType.CORTEX_DIR.value

    if resource_type == CortexResourceType.CORTEX_DIR:
        return cortex_dir
    if resource_type == CortexResourceType.INDEX:
        return cortex_dir / CortexResourceType.INDEX.value
    return cortex_dir / resource_type.value


def get_cursor_path(project_root: Path, resource_type: CursorResourceType) -> Path:
    """Get the absolute path for a Cursor integration resource type.

    Args:
        project_root: Root directory of the project
        resource_type: Type of Cursor resource

    Returns:
        Absolute path to the resource

    Examples:
        >>> root = Path("/project")
        >>> get_cursor_path(root, CursorResourceType.CURSOR_DIR)
        Path("/project/.cursor")
        >>> get_cursor_path(root, CursorResourceType.MEMORY_BANK)
        Path("/project/.cursor/memory-bank")
        >>> get_cursor_path(root, CursorResourceType.PLANS)
        Path("/project/.cursor/plans")
    """
    cursor_dir = project_root / CursorResourceType.CURSOR_DIR.value

    if resource_type == CursorResourceType.CURSOR_DIR:
        return cursor_dir
    return cursor_dir / resource_type.value


def get_cache_path(project_root: Path, cache_type: str | None = None) -> Path:
    """Get cache directory path.

    Args:
        project_root: Root directory of the project
        cache_type: Optional cache subdirectory type (string value,
        typically from CacheType enum)

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


def has_memory_bank(project_root: Path) -> bool:
    """Return True if project_root has .cortex/memory-bank directory."""
    return get_cortex_path(project_root, CortexResourceType.MEMORY_BANK).is_dir()


_MEMORY_BANK_CORE_FILES = (
    "projectBrief.md",
    "productContext.md",
    "activeContext.md",
    "systemPatterns.md",
    "techContext.md",
    "progress.md",
    "roadmap.md",
)


def is_memory_bank_fully_initialized(project_root: Path) -> bool:
    """Return True if .cortex/memory-bank exists and has all 7 core files."""
    mb_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return mb_dir.is_dir() and all(
        (mb_dir / fname).exists() for fname in _MEMORY_BANK_CORE_FILES
    )
