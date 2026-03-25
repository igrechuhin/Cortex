"""
Project Configuration Status Checker

This module provides synchronous functions to check project configuration status
at import time. Used for conditional prompt registration.
"""

from pathlib import Path

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel
from cortex.core.path_resolver import (
    CortexResourceType,
    CursorResourceType,
    get_cortex_path,
    get_cursor_path,
    is_memory_bank_fully_initialized,
)
from cortex.core.tiktoken_cache import ensure_bundled_cache_available
from cortex.managers.initialization import get_project_root


class ProjectConfigStatus(DictLikeModel):
    """Project configuration status flags."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    memory_bank_initialized: bool = Field(
        description="Whether memory bank is initialized"
    )
    structure_configured: bool = Field(
        description="Whether project structure is configured"
    )
    cursor_integration_configured: bool = Field(
        description="Whether Cursor integration is configured"
    )
    migration_needed: bool = Field(description="Whether migration is needed")
    tiktoken_cache_available: bool = Field(
        description="Whether tiktoken cache is available"
    )


def _check_memory_bank_initialized(project_root: Path) -> bool:
    """Check if memory bank is initialized with core files."""
    return is_memory_bank_fully_initialized(project_root)


def check_structure_configured(cortex_dir: Path) -> bool:
    """Check if .cortex/ structure is configured."""
    required_dirs = ["memory-bank", "plans"]
    return cortex_dir.is_dir() and all(
        (cortex_dir / subdir).is_dir() for subdir in required_dirs
    )


def check_cursor_integration(cursor_dir: Path, cortex_dir: Path) -> bool:
    """Check if Cursor integration is configured with valid symlinks."""
    if not cursor_dir.is_dir():
        return False
    required_symlinks = ["memory-bank", "synapse", "plans"]
    for symlink_name in required_symlinks:
        symlink_path = cursor_dir / symlink_name
        if not (symlink_path.exists() and symlink_path.is_symlink()):
            return False
        try:
            target = symlink_path.resolve()
            expected_target = cortex_dir / symlink_name
            if target != expected_target.resolve():
                return False
        except Exception:
            return False
    return True


def _check_migration_needed(project_root: Path, memory_bank_initialized: bool) -> bool:
    """Check if migration is needed from legacy formats."""
    if memory_bank_initialized:
        return False
    legacy_locations = [
        get_cursor_path(project_root, CursorResourceType.MEMORY_BANK),
        project_root / "memory-bank",
        project_root / ".memory-bank",
    ]
    return any(
        legacy_path.exists() and legacy_path.is_dir()
        for legacy_path in legacy_locations
    )


def _get_fail_safe_status() -> ProjectConfigStatus:
    """Return fail-safe status when config check fails."""
    return ProjectConfigStatus(
        memory_bank_initialized=True,
        structure_configured=True,
        cursor_integration_configured=True,
        migration_needed=False,
        tiktoken_cache_available=True,  # Assume available in fail-safe mode
    )


def get_project_config_status(
    project_root: Path | None = None,
) -> ProjectConfigStatus:
    """Check project configuration status synchronously.

    Args:
        project_root: Explicit project root path. When ``None``, auto-detected
            from CWD and ``sys.argv[0]`` via :func:`get_project_root`.

    Returns:
        Dictionary with status flags: memory_bank_initialized, structure_configured,
        cursor_integration_configured, migration_needed, tiktoken_cache_available.
    """
    try:
        root = project_root if project_root is not None else get_project_root()
        cortex_dir = get_cortex_path(root, CortexResourceType.CORTEX_DIR)
        cursor_dir = get_cursor_path(root, CursorResourceType.CURSOR_DIR)

        memory_bank_initialized = _check_memory_bank_initialized(root)
        structure_configured = check_structure_configured(cortex_dir)
        cursor_integration_configured = check_cursor_integration(cursor_dir, cortex_dir)
        migration_needed = _check_migration_needed(root, memory_bank_initialized)
        tiktoken_cache_available = ensure_bundled_cache_available()
        return ProjectConfigStatus(
            memory_bank_initialized=memory_bank_initialized,
            structure_configured=structure_configured,
            cursor_integration_configured=cursor_integration_configured,
            migration_needed=migration_needed,
            tiktoken_cache_available=tiktoken_cache_available,
        )
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.warning(
            f"Config status check failed, assuming configured (fail-safe): {e}",
            exc_info=True,
        )
        return _get_fail_safe_status()
