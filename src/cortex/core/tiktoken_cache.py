"""Tiktoken cache management for bundled encoding files.

This module provides functionality to use bundled tiktoken encoding files
as fallback when network access is unavailable (e.g., VPN restrictions).
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def get_bundled_cache_dir() -> Path | None:
    """Get path to bundled tiktoken cache directory if available.

    Returns:
        Path to bundled cache directory, or None if not available
    """
    try:
        # Use __file__ to find the package directory
        # This file is in cortex/core/, so go up two levels to get cortex/
        current_file = Path(__file__)
        package_dir = current_file.parent.parent
        bundled_cache = package_dir / "resources" / "tiktoken_cache"

        if bundled_cache.exists() and bundled_cache.is_dir():
            return bundled_cache

        return None
    except Exception:
        return None


def setup_tiktoken_cache(use_bundled: bool = True) -> bool:
    """Configure tiktoken to use bundled cache if available.

    Sets TIKTOKEN_CACHE_DIR environment variable to bundled cache directory
    if it exists and use_bundled is True. This allows tiktoken to work
    offline using pre-bundled encoding files.

    Args:
        use_bundled: Whether to use bundled cache if available (default: True)

    Returns:
        True if bundled cache was configured, False otherwise
    """
    if not use_bundled:
        return False

    bundled_cache = get_bundled_cache_dir()
    if bundled_cache is None:
        return False

    # Only set if not already set by user
    if "TIKTOKEN_CACHE_DIR" not in os.environ:
        os.environ["TIKTOKEN_CACHE_DIR"] = str(bundled_cache)
        logger.debug(f"Configured tiktoken to use bundled cache: {bundled_cache}")
        return True

    return False


def ensure_bundled_cache_available() -> bool:
    """Check if bundled tiktoken cache is available and usable.

    Returns:
        True if bundled cache exists and contains files, False otherwise
    """
    bundled_cache = get_bundled_cache_dir()
    if bundled_cache is None:
        return False

    # Check if directory exists and has files
    if not bundled_cache.exists():
        return False

    try:
        # Check if directory has any files (tiktoken cache files)
        cache_files = list(bundled_cache.glob("*"))
        return len(cache_files) > 0
    except Exception:
        return False
