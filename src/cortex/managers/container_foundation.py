"""Factory methods for creating Phase 1 foundation manager instances."""

from pathlib import Path

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.migration import MigrationManager
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager


def create_foundation_managers(
    project_root: Path,
) -> tuple[
    FileSystemManager,
    MetadataIndex,
    TokenCounter,
    DependencyGraph,
    VersionManager,
    MigrationManager,
    FileWatcherManager,
]:
    """Create Phase 1 foundation managers."""
    file_system = FileSystemManager(project_root)
    metadata_index = MetadataIndex(project_root)
    token_counter = TokenCounter()
    dependency_graph = DependencyGraph()
    version_manager = VersionManager(project_root)
    migration_manager = MigrationManager(project_root)
    file_watcher = FileWatcherManager()

    return (
        file_system,
        metadata_index,
        token_counter,
        dependency_graph,
        version_manager,
        migration_manager,
        file_watcher,
    )
