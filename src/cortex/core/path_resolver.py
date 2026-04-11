"""Path resolution utilities for Cortex directory structure.

This module provides a centralized way to resolve paths to Cortex resources,
avoiding hardcoded path construction throughout the codebase.
"""

import os
from collections.abc import Iterator
from enum import Enum
from pathlib import Path


class CortexResourceType(Enum):
    """Enumeration of Cortex resource types for path resolution."""

    CORTEX_DIR = ".cortex"
    MEMORY_BANK = "memory-bank"
    PLANS = "plans"
    PLANS_ARCHIVE = "plans/archive"
    SCRIPT_CAPTURE = "script-capture"
    RULES = "rules"
    HISTORY = "history"
    CONFIG = "config"
    SYNAPSE = "synapse"
    ARCHIVED = "archived"
    REVIEWS = "reviews"
    SCHEMAS = "schemas"
    SESSION = ".session"
    CACHE = ".cache"
    INDEX = "index.json"


class CursorResourceType(Enum):
    """Enumeration of Cursor integration resource types for path resolution."""

    CURSOR_DIR = ".cursor"
    MEMORY_BANK = "memory-bank"
    RULES = "rules"
    PLANS = "plans"


class ProjectResourceType(Enum):
    """Enumeration of project root resource types for path resolution."""

    VENV = ".venv"
    LEGACY_VENV = "venv"
    NODE_MODULES = "node_modules"


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


def get_project_path(project_root: Path, resource_type: ProjectResourceType) -> Path:
    """Get the absolute path for a project root resource type.

    Args:
        project_root: Root directory of the project
        resource_type: Type of project resource

    Returns:
        Absolute path to the resource

    Examples:
        >>> root = Path("/project")
        >>> get_project_path(root, ProjectResourceType.VENV)
        Path("/project/.venv")
    """
    return project_root / resource_type.value


def get_venv_bin_path(project_root: Path) -> Path:
    """Get the virtualenv bin directory path (project_root/.venv/bin).

    Args:
        project_root: Root directory of the project

    Returns:
        Path to .venv/bin

    Examples:
        >>> root = Path("/project")
        >>> get_venv_bin_path(root)
        Path("/project/.venv/bin")
    """
    return get_project_path(project_root, ProjectResourceType.VENV) / "bin"


def get_legacy_venv_bin_path(project_root: Path) -> Path:
    """Get the legacy virtualenv bin directory path (``project_root/venv/bin``).

    Some projects use a non-dot ``venv`` directory instead of ``.venv``.
    """
    return get_project_path(project_root, ProjectResourceType.LEGACY_VENV) / "bin"


def get_node_modules_bin_dir(project_root: Path) -> Path:
    """Return ``project_root/node_modules/.bin`` (npm/yarn/pnpm local CLI layout)."""
    return get_project_path(project_root, ProjectResourceType.NODE_MODULES) / ".bin"


def get_node_modules_bin_path(project_root: Path, executable: str) -> Path:
    """Path to a project-local npm binary (``node_modules/.bin/<executable>``).

    Args:
        project_root: Root directory of the project
        executable: CLI name (e.g. ``\"rumdl\"``, ``\"prettier\"``)

    Returns:
        Absolute path convention; the file may or may not exist.

    Examples:
        >>> root = Path("/project")
        >>> get_node_modules_bin_path(root, "rumdl")
        Path("/project/node_modules/.bin/rumdl")
    """
    return get_node_modules_bin_dir(project_root) / executable


def iter_venv_executable_candidates(
    project_root: Path, executable: str
) -> Iterator[Path]:
    """Yield project-local virtualenv CLI paths (priority: ``.venv/bin`` then ``venv/bin``).

    Matches common uv/pip layouts so callers can probe for CLIs without relying
    on ``PATH``.

    Args:
        project_root: Root directory of the project
        executable: CLI name (e.g. ``\"rumdl\"``, ``\"pytest\"``)

    Yields:
        Candidate paths in probe order.

    Examples:
        >>> root = Path("/project")
        >>> list(iter_venv_executable_candidates(root, "rumdl"))
        [Path('/project/.venv/bin/rumdl'), Path('/project/venv/bin/rumdl')]
    """
    yield get_venv_bin_path(project_root) / executable
    yield get_legacy_venv_bin_path(project_root) / executable


def augmented_environ_with_project_venv_bins(project_root: Path) -> dict[str, str]:
    """Return a copy of ``os.environ`` with project venv ``bin`` dirs prepended to ``PATH``.

    Uses :func:`get_venv_bin_path` and :func:`get_legacy_venv_bin_path` (same order
    as :func:`iter_venv_executable_candidates`) so subprocesses can resolve bare
    executable names (e.g. ``rumdl``) when ``sys.executable`` is not the project
    virtualenv interpreter but CLIs live under ``project_root/.venv/bin``.

    Args:
        project_root: Root directory of the project

    Returns:
        Environment mapping suitable for ``subprocess.run(..., env=...)``.
    """
    env = os.environ.copy()
    prefixes: list[str] = []
    for bin_dir in (
        get_venv_bin_path(project_root),
        get_legacy_venv_bin_path(project_root),
    ):
        # Always prepend conventional locations. Some IDE/agent sandboxes treat
        # ignored virtualenv trees as absent for is_dir()/is_file() even though
        # subprocess can still resolve executables when PATH includes these dirs.
        prefixes.append(str(bin_dir.resolve()))
    env["PATH"] = os.pathsep.join(prefixes) + os.pathsep + env.get("PATH", "")
    return env


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


def get_constitution_path(project_root: Path) -> Path:
    """Return `.cortex/memory-bank/constitution.md` for the project root."""
    memory_bank_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return memory_bank_dir / MemoryBankFile.CONSTITUTION


# Core Memory Bank files; kept in sync with the canonical spec
# in the Memory Bank workflow rule (memory-bank-workflow.mdc).
# Import here to avoid circular dependency (constants imports from path_resolver)
from cortex.core.constants import MemoryBankFile  # noqa: E402


def get_constitution_template_path(project_root: Path) -> Path:
    # AI: Synapse ships the starter template; memory bank holds the project-specific copy.
    """Return `.cortex/synapse/templates/constitution.md` (Synapse template)."""
    synapse_dir = get_cortex_path(project_root, CortexResourceType.SYNAPSE)
    return synapse_dir / "templates" / MemoryBankFile.CONSTITUTION


_MEMORY_BANK_CORE_FILES = (
    MemoryBankFile.PROJECT_BRIEF,
    MemoryBankFile.PRODUCT_CONTEXT,
    MemoryBankFile.ACTIVE_CONTEXT,
    MemoryBankFile.SYSTEM_PATTERNS,
    MemoryBankFile.TECH_CONTEXT,
    MemoryBankFile.PROGRESS,
    MemoryBankFile.ROADMAP,
)


def is_memory_bank_fully_initialized(project_root: Path) -> bool:
    """Return True if .cortex/memory-bank exists and has all 7 core files."""
    mb_dir = get_cortex_path(project_root, CortexResourceType.MEMORY_BANK)
    return mb_dir.is_dir() and all(
        (mb_dir / fname).exists() for fname in _MEMORY_BANK_CORE_FILES
    )
