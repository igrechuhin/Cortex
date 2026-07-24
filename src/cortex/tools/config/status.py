"""
Project Configuration Status Checker

This module provides synchronous functions to check project configuration status
at import time. Used for conditional prompt registration.
"""

import json
from pathlib import Path

from pydantic import ConfigDict, Field

from cortex.core.models import DictLikeModel
from cortex.core.path_resolver import (
    CortexResourceType,
    get_cortex_path,
    is_memory_bank_fully_initialized,
)
from cortex.core.pydantic_extra import EXTRA_FORBID
from cortex.core.tiktoken_cache import ensure_bundled_cache_available
from cortex.managers.initialization import get_project_root


class ProjectConfigStatus(DictLikeModel):
    """Project configuration status flags."""

    model_config = ConfigDict(extra=EXTRA_FORBID, validate_assignment=True)

    memory_bank_initialized: bool = Field(
        description="Whether memory bank is initialized"
    )
    structure_configured: bool = Field(
        description="Whether project structure is configured"
    )
    migration_needed: bool = Field(description="Whether migration is needed")
    tiktoken_cache_available: bool = Field(
        description="Whether tiktoken cache is available"
    )
    codegraph_configured: bool = Field(
        description="Whether CodeGraph MCP server is present in .mcp.json"
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


def _has_codegraph_in_mcp_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("mcpServers", {}).get("codegraph"))
    except Exception:
        return False


def _check_codegraph_configured(project_root: Path) -> bool:
    """Check if CodeGraph MCP server is present in .mcp.json."""
    return _has_codegraph_in_mcp_file(project_root / ".mcp.json")


def _check_migration_needed(project_root: Path, memory_bank_initialized: bool) -> bool:
    """Check if migration is needed from legacy formats."""
    if memory_bank_initialized:
        return False
    legacy_locations = [
        project_root / "memory-bank",
        project_root / ".memory-bank",
    ]
    return any(
        legacy_path.exists() and legacy_path.is_dir() and not legacy_path.is_symlink()
        for legacy_path in legacy_locations
    )


def _get_fail_safe_status() -> ProjectConfigStatus:
    """Return fail-safe status when config check fails."""
    return ProjectConfigStatus(
        memory_bank_initialized=True,
        structure_configured=True,
        migration_needed=False,
        tiktoken_cache_available=True,
        codegraph_configured=True,  # Assume configured in fail-safe mode
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
        migration_needed, tiktoken_cache_available.
    """
    try:
        root = project_root if project_root is not None else get_project_root()
        cortex_dir = get_cortex_path(root, CortexResourceType.CORTEX_DIR)

        memory_bank_initialized = _check_memory_bank_initialized(root)
        structure_configured = check_structure_configured(cortex_dir)
        migration_needed = _check_migration_needed(root, memory_bank_initialized)
        tiktoken_cache_available = ensure_bundled_cache_available()
        codegraph_configured = _check_codegraph_configured(root)
        return ProjectConfigStatus(
            memory_bank_initialized=memory_bank_initialized,
            structure_configured=structure_configured,
            migration_needed=migration_needed,
            tiktoken_cache_available=tiktoken_cache_available,
            codegraph_configured=codegraph_configured,
        )
    except Exception as e:
        from cortex.core.logging_config import logger

        logger.warning(
            f"Config status check failed, assuming configured (fail-safe): {e}",
            exc_info=True,
        )
        return _get_fail_safe_status()
