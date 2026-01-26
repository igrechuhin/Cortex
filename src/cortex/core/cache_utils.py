"""Cache management utilities for Cortex.

This module provides utilities for managing cache directories and files
across Cortex MCP tools.
"""

from enum import Enum
from pathlib import Path

from cortex.core.path_resolver import get_cache_path


class CacheType(str, Enum):
    """Enumeration of cache subdirectory types for structured access."""

    SUMMARIES = "summaries"
    RELEVANCE = "relevance"
    PATTERNS = "patterns"
    REFACTORING = "refactoring"


def get_cache_dir(
    project_root: Path, cache_type: CacheType | str | None = None
) -> Path:
    """Get cache directory path.

    Args:
        project_root: Root directory of the project
        cache_type: Optional cache subdirectory type (CacheType enum or string)

    Returns:
        Path to cache directory or cache subdirectory

    Examples:
        >>> root = Path("/project")
        >>> get_cache_dir(root)
        Path("/project/.cortex/.cache")
        >>> get_cache_dir(root, CacheType.SUMMARIES)
        Path("/project/.cortex/.cache/summaries")
    """
    cache_type_str = (
        cache_type.value if isinstance(cache_type, CacheType) else cache_type
    )
    return get_cache_path(project_root, cache_type_str)


def clear_cache(project_root: Path, cache_type: CacheType | str | None = None) -> int:
    """Clear cache files.

    Args:
        project_root: Root directory of the project
        cache_type: Optional cache subdirectory type to clear (CacheType enum or string)

    Returns:
        Number of files deleted

    Examples:
        >>> root = Path("/project")
        >>> clear_cache(root, CacheType.SUMMARIES)
        5  # 5 files deleted
    """
    cache_dir = get_cache_dir(project_root, cache_type)

    if not cache_dir.exists():
        return 0

    deleted_count = 0

    cache_type_str = (
        cache_type.value if isinstance(cache_type, CacheType) else cache_type
    )
    if cache_type_str:
        # Clear specific cache subdirectory
        for cache_file in cache_dir.iterdir():
            if cache_file.is_file():
                cache_file.unlink()
                deleted_count += 1
            elif cache_file.is_dir():
                for sub_file in cache_file.rglob("*"):
                    if sub_file.is_file():
                        sub_file.unlink()
                        deleted_count += 1
    else:
        # Clear entire cache directory
        for cache_file in cache_dir.rglob("*"):
            if cache_file.is_file():
                cache_file.unlink()
                deleted_count += 1

    return deleted_count


def get_cache_size(
    project_root: Path, cache_type: CacheType | str | None = None
) -> int:
    """Get total cache size in bytes.

    Args:
        project_root: Root directory of the project
        cache_type: Optional cache subdirectory type (CacheType enum or string)

    Returns:
        Total size in bytes

    Examples:
        >>> root = Path("/project")
        >>> get_cache_size(root, CacheType.SUMMARIES)
        102400  # 100 KB
    """
    cache_dir = get_cache_dir(project_root, cache_type)

    if not cache_dir.exists():
        return 0

    total_size = 0

    for cache_file in cache_dir.rglob("*"):
        if cache_file.is_file():
            total_size += cache_file.stat().st_size

    return total_size


def list_cache_files(
    project_root: Path, cache_type: CacheType | str | None = None
) -> list[Path]:
    """List all cache files.

    Args:
        project_root: Root directory of the project
        cache_type: Optional cache subdirectory type (CacheType enum or string)

    Returns:
        List of cache file paths

    Examples:
        >>> root = Path("/project")
        >>> list_cache_files(root, CacheType.SUMMARIES)
        [Path("/project/.cortex/.cache/summaries/file1.json"), ...]
    """
    cache_dir = get_cache_dir(project_root, cache_type)

    if not cache_dir.exists():
        return []

    cache_files: list[Path] = []

    for cache_file in cache_dir.rglob("*"):
        if cache_file.is_file():
            cache_files.append(cache_file)

    return sorted(cache_files)
