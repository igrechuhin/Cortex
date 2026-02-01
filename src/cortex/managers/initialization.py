#!/usr/bin/env python3
"""Manager initialization and lifecycle management for MCP Memory Bank."""

from pathlib import Path
from typing import cast

from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.managers.builder_types import ManagersBuilder
from cortex.managers.manager_initialization import (
    add_analysis_managers,
    add_execution_managers,
    add_linking_managers,
    add_optimization_managers,
    add_refactoring_managers,
    add_usage_tracker,
    add_validation_managers,
)
from cortex.managers.types import CoreManagersDict, ManagersDict


def get_project_root(project_root: str | None = None) -> Path:
    """Get project root directory.

    When project_root is None, automatically detects the project root by walking
    up from the current working directory or script location to find a directory
    containing .cortex/. Prefers the .cortex/ closest to the starting point.

    Args:
        project_root: Optional project root path. If provided, returns resolved path.
                     If None, attempts to detect project root from .cortex/ directory.

    Returns:
        Resolved absolute path to project root
    """
    if project_root:
        return Path(project_root).resolve()

    # Try to detect project root by finding .cortex/ directory
    # Prefer script location over CWD to avoid finding wrong .cortex/ in home directory
    current = Path.cwd().resolve()

    # First, try from script location (more reliable for MCP server)
    try:
        import sys

        if sys.argv and sys.argv[0]:
            script_path = Path(sys.argv[0]).resolve()
            for path in [script_path.parent, *script_path.parent.parents]:
                cortex_dir = path / ".cortex"
                if cortex_dir.is_dir():
                    memory_bank_dir = cortex_dir / "memory-bank"
                    if memory_bank_dir.is_dir():
                        return path
    except Exception:
        pass

    # Also try from current working directory
    for path in [current, *current.parents]:
        cortex_dir = path / ".cortex"
        if cortex_dir.is_dir():
            memory_bank_dir = cortex_dir / "memory-bank"
            if memory_bank_dir.is_dir():
                return path

    return current


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
    from cortex.core.manager_registry import ManagerRegistry
    from cortex.core.usage_context import set_current_managers

    registry = ManagerRegistry()
    managers_dict = await registry.get_managers(project_root)
    result = ManagersDict.model_validate(managers_dict)
    set_current_managers(managers_dict.model_dump())
    return result


async def initialize_managers(project_root: Path) -> ManagersDict:
    """Initialize all managers with core managers eager and others lazy.

    Args:
        project_root: Project root directory

    Returns:
        ManagersDict model with manager instances and LazyManager wrappers
    """
    core_managers = await _init_core_managers(project_root)
    builders_dict = core_managers.model_dump()

    add_linking_managers(builders_dict, core_managers)
    add_validation_managers(builders_dict, project_root)
    add_optimization_managers(builders_dict, project_root, core_managers)
    add_analysis_managers(builders_dict, project_root, core_managers)
    add_refactoring_managers(builders_dict, project_root)
    add_execution_managers(builders_dict, project_root, core_managers)
    add_usage_tracker(builders_dict, project_root)

    await _post_init_setup(project_root, builders_dict)
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
    from cortex.managers.manager_utils import get_manager
    from cortex.optimization.optimization_config import OptimizationConfig
    from cortex.optimization.rules_manager import RulesManager

    index = cast(MetadataIndex, managers["index"])
    fs_manager = cast(FileSystemManager, managers["fs"])

    index_path = project_root / ".cortex" / "index.json"
    if index_path.exists():
        try:
            _ = await index.load()
        except Exception:
            pass

    await fs_manager.cleanup_locks()

    try:
        optimization_config = await get_manager(
            managers, "optimization_config", OptimizationConfig
        )
        if optimization_config.is_rules_enabled():
            rules_manager = await get_manager(managers, "rules_manager", RulesManager)
            _ = await rules_manager.initialize()
    except Exception:
        pass


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
