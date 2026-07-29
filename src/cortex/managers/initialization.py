#!/usr/bin/env python3
"""Manager initialization and lifecycle management for MCP Memory Bank."""

import logging
import time
from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.path_resolver import (
    CortexResourceType,
    get_cortex_path,
    has_memory_bank,
    is_memory_bank_fully_initialized,
)
from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.factory import (
    add_analysis_managers,
    add_execution_managers,
    add_linking_managers,
    add_optimization_managers,
    add_refactoring_managers,
    add_usage_tracker,
    add_validation_managers,
)
from cortex.managers.types import CoreManagersDict, ManagersDict

logger = logging.getLogger(__name__)


def _detect_root_from(path: Path) -> Path | None:
    """Walk up from path to find first directory with .cortex/memory-bank."""
    for candidate in [path, *path.parents]:
        if has_memory_bank(candidate):
            return candidate
    return None


def _topmost_cortex_root(candidates: set[Path]) -> Path | None:
    """Return the topmost Cortex root (not contained in any other candidate)."""
    if not candidates:
        return None
    for c in candidates:
        if not any(d != c and c.is_relative_to(d) for d in candidates):
            return c
    return next(iter(candidates))


def _reject_package_subdir_as_root(path: Path) -> Path:
    """Prefer topmost Cortex root over a subdir that has .cortex/memory-bank.

    When path has .cortex/memory-bank, walk up and return the first ancestor that
    also has .cortex/memory-bank (layout-agnostic; no assumption about src/).

    Updated to stop walking once we reach a path that looks like a real project
    root (has language/build markers like pyproject.toml). This prevents
    accidentally treating a higher-level ~/.cortex as the root when the actual
    project lives in a nested repo with its own .cortex/.
    """
    p = path.resolve()
    if not has_memory_bank(p):
        return path
    # Track the last path in the chain that has a memory bank; if we never find
    # a path with language markers, fall back to that.
    last_with_memory_bank = p
    # If this path already looks like a project root, don't walk past it to
    # higher-level directories (e.g., ~/.cortex).
    if _has_language_markers(p):
        return p
    for ancestor in [p.parent, *p.parents]:
        if not has_memory_bank(ancestor):
            continue
        last_with_memory_bank = ancestor
        if _has_language_markers(ancestor):
            return ancestor
    return last_with_memory_bank


def _collect_candidate_roots(resolved: Path) -> set[Path]:
    """Collect candidate Cortex roots from resolved, cwd, and script location."""
    candidates: set[Path] = {resolved}
    cwd_root = _detect_root_from(Path.cwd().resolve())
    if cwd_root is not None:
        candidates.add(cwd_root)
    try:
        import sys

        if sys.argv and sys.argv[0]:
            script_path = Path(sys.argv[0]).resolve().parent
            script_root = _detect_root_from(script_path)
            if script_root is not None:
                candidates.add(script_root)
    except (OSError, ValueError) as e:
        logger.debug("_collect_candidate_roots: %s", e)
    return candidates


def _resolve_given_root_restricted_to_tree(resolved: Path) -> Path:
    """Resolve a provided root using topmost among resolved and its ancestors only.

    Use when the caller explicitly passed a path: never return a path outside
    that tree (e.g. ~/.cortex when the user passed /path/to/repo).
    """
    candidates = _collect_candidate_roots(resolved)
    in_tree = {
        c
        for c in candidates
        if c == resolved or (c != resolved and resolved.is_relative_to(c))
    }
    if not in_tree:
        return _reject_package_subdir_as_root(resolved)
    topmost = _topmost_cortex_root(in_tree)
    if topmost is not None and topmost != resolved and resolved.is_relative_to(topmost):
        return _reject_package_subdir_as_root(topmost)
    return _reject_package_subdir_as_root(resolved)


def _find_root_from_script() -> Path | None:
    """Try to find Cortex root from script location."""
    try:
        import sys

        if sys.argv and sys.argv[0]:
            script_path = Path(sys.argv[0]).resolve()
            for path in [script_path.parent, *script_path.parent.parents]:
                if has_memory_bank(path):
                    return _reject_package_subdir_as_root(path)
    except (OSError, ValueError) as e:
        logger.debug("_find_root_from_script: %s", e)
    return None


def _find_root_from_cwd() -> Path | None:
    """Try to find Cortex root from current working directory."""
    home = Path.home().resolve()
    current = Path.cwd().resolve()
    for path in [current, *current.parents]:
        if not has_memory_bank(path):
            continue
        # Skip a partially-initialized home dir — a common leftover from when
        # Cortex was configured globally (user-level) and ran with CWD = ~.
        if path == home and not is_memory_bank_fully_initialized(path):
            continue
        return _reject_package_subdir_as_root(path)
    return None


def _has_language_markers(path: Path) -> bool:
    """Return True if path looks like a project (has language/build markers)."""
    return (
        (path / "pyproject.toml").exists()
        or (path / "package.json").exists()
        or (path / "Cargo.toml").exists()
        or (path / "go.mod").exists()
        or (path / "go.sum").exists()
        or (path / "Package.swift").exists()
        or _has_xcode_project(path)
    )


def _has_xcode_project(path: Path) -> bool:
    """Return True if path contains an Xcode project/workspace bundle.

    Xcode bundles are named after the project, so they need a glob rather than
    a fixed filename lookup. Swift repos without a Package.swift (app targets)
    would otherwise go unrecognized and the caller would walk up past the real
    project root into a higher-level ~/.cortex.
    """
    try:
        return any(path.glob("*.xcodeproj")) or any(path.glob("*.xcworkspace"))
    except OSError:
        return False


def _is_subdir_of_cortex_root(resolved: Path) -> bool:
    """True if resolved path is a direct subdirectory of a Cortex root.

    When the client passes a segment like 'optimization' or 'validation',
    resolve() yields repo/optimization; that path has no .cortex/memory-bank
    but its parent does. Using it as project_root would create repo/optimization/.cortex/
    and thus pollute the repo root with segment dirs. Callers should treat
    this as invalid and fall back to auto-detection.
    """
    try:
        return bool(resolved.parent and has_memory_bank(resolved.parent))
    except (OSError, ValueError):
        return False


def get_project_root(project_root: str | None = None) -> Path:
    """Get project root directory.

    When project_root is provided, returns that path (resolved) only if it
    is a Cortex root or an unrelated path. If it resolves to a subdirectory
    of a Cortex root (e.g. client passed 'optimization'), falls back to
    auto-detection to avoid creating spurious dirs at repo root. When
    project_root is None, detects the project root by walking up from cwd
    or script to find .cortex/memory-bank.

    Args:
        project_root: Optional project root path. If provided, returns its
                     resolved path when it is a valid Cortex root. If None,
                     attempts to detect from .cortex/.

    Returns:
        Resolved absolute path to project root
    """
    if project_root:
        resolved = Path(project_root).resolve()
        if has_memory_bank(resolved):
            return _resolve_given_root_restricted_to_tree(resolved)
        if _is_subdir_of_cortex_root(resolved):
            return get_project_root(None)
        return resolved
    script_root = _find_root_from_script()
    cwd_root = _find_root_from_cwd()
    candidates: list[Path] = []
    if script_root is not None:
        candidates.append(script_root)
    if cwd_root is not None and cwd_root not in candidates:
        candidates.append(cwd_root)
    if not candidates:
        return Path.cwd().resolve()
    # Prefer a root with fully initialized memory bank (all 7 core files) so we
    # don't pick e.g. ~/.cortex when the real workspace is the repo.
    for c in candidates:
        if is_memory_bank_fully_initialized(c):
            return _reject_package_subdir_as_root(c)
    # Else prefer a Cortex root that has language markers (actual project)
    for c in candidates:
        if _has_language_markers(c):
            return _reject_package_subdir_as_root(c)
    return _reject_package_subdir_as_root(candidates[0])


async def get_managers(project_root: Path) -> ManagersDict:
    """Get or initialize managers for a project with lazy loading.

    Core managers (priority 1) are initialized immediately for reliability.
    Other managers are wrapped in LazyManager for on-demand initialization.
    Sets current managers in contextvar for Phase 29 usage tracking.

    Args:
        project_root: Project root directory

    Returns:
        ManagersDict model with manager instances (or LazyManager wrappers)
    """
    from cortex.core.manager_registry import get_process_registry
    from cortex.core.usage_context import set_current_managers, set_current_project_root

    registry = get_process_registry()
    t0 = time.monotonic()
    managers_dict = await registry.get_managers(project_root)
    elapsed = time.monotonic() - t0
    logger.debug(
        "get_managers: registry.get_managers(%s) took %.3fs",
        project_root,
        elapsed,
    )
    if elapsed > 2.0:
        logger.info(
            "get_managers: initialize_managers(%s) took %.2fs",
            project_root,
            elapsed,
        )
    result = ManagersDict.model_validate(managers_dict)
    set_current_managers(managers_dict.model_dump())
    set_current_project_root(project_root)
    return result


async def initialize_managers(project_root: Path) -> ManagersDict:
    """Initialize all managers with core managers eager and others lazy.

    Args:
        project_root: Project root directory

    Returns:
        ManagersDict model with manager instances and LazyManager wrappers
    """
    t0 = time.monotonic()
    core_managers = await _init_core_managers(project_root)
    logger.debug(
        "initialize_managers: _init_core_managers took %.3fs",
        time.monotonic() - t0,
    )
    builders_dict = core_managers.model_dump()

    add_linking_managers(builders_dict, core_managers)
    add_validation_managers(builders_dict, project_root)
    add_optimization_managers(builders_dict, project_root, core_managers)
    add_analysis_managers(builders_dict, project_root, core_managers)
    add_refactoring_managers(builders_dict, project_root)
    add_execution_managers(builders_dict, project_root, core_managers)
    add_usage_tracker(builders_dict, project_root)

    t1 = time.monotonic()
    await _post_init_setup(project_root, builders_dict)
    post_elapsed = time.monotonic() - t1
    logger.debug(
        "initialize_managers: _post_init_setup took %.3fs",
        post_elapsed,
    )
    if post_elapsed > 2.0:
        logger.info(
            "initialize_managers: _post_init_setup took %.2fs (index.load + cleanup_locks)",
            post_elapsed,
        )
    return ManagersDict.model_validate(builders_dict)


async def _init_core_managers(project_root: Path) -> CoreManagersDict:
    """Initialize core managers that are always needed (priority 1).

    Args:
        project_root: Project root directory

    Returns:
        Dictionary of initialized core managers
    """
    from cortex.core.dependency_graph import DependencyGraph
    from cortex.core.file_system import FileSystemManager
    from cortex.core.file_watcher import FileWatcherManager
    from cortex.core.metadata_index import MetadataIndex
    from cortex.core.migration import MigrationManager
    from cortex.core.token_counter import TokenCounter
    from cortex.core.version_manager import VersionManager

    fs = FileSystemManager(project_root)
    index = MetadataIndex(project_root)
    tokens = TokenCounter()
    graph = DependencyGraph()
    versions = VersionManager(project_root)
    migration = MigrationManager(project_root)
    watcher = FileWatcherManager()

    return CoreManagersDict(
        fs=fs,
        index=index,
        tokens=tokens,
        graph=graph,
        versions=versions,
        migration=migration,
        watcher=watcher,
    )


async def _post_init_setup(project_root: Path, managers: ManagersBuilder) -> None:
    """Perform post-initialization setup tasks for core managers.

    Args:
        project_root: Project root directory
        managers: Manager builder dict with core and lazy managers
    """
    index = cast(MetadataIndex, managers["index"])
    fs_manager = cast(FileSystemManager, managers["fs"])

    index_path = get_cortex_path(project_root, CortexResourceType.INDEX)
    if index_path.exists():
        try:
            t0 = time.monotonic()
            _ = await index.load()
            logger.debug(
                "_post_init_setup: index.load() took %.3fs",
                time.monotonic() - t0,
            )
        except Exception as e:
            logger.debug("_post_init_setup: index.load() failed: %s", e)

    t0 = time.monotonic()
    await fs_manager.cleanup_locks()
    logger.debug(
        "_post_init_setup: cleanup_locks() took %.3fs",
        time.monotonic() - t0,
    )

    # Rules manager init is deferred to first use (rules tool) so the first
    # tool call (e.g. manage_file) is not blocked by ~30s rules indexing.


async def handle_file_change(file_path: Path, event_type: str) -> None:
    """Callback for file watcher to handle external file changes.

    This function is called when files are modified externally (outside MCP).
    It updates metadata and creates version snapshots if needed.

    Args:
        file_path: Path to changed file
        event_type: Type of change ('created', 'modified', 'deleted')
    """
    from cortex.managers.initialization_health import handle_file_change as _do_handle

    await _do_handle(file_path, event_type)
