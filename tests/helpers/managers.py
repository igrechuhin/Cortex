"""Helpers for building typed manager containers in tests.

Many tool-layer functions expect a fully-typed `ManagersDict` (Phase 53 migration).
Tests often only care about 1-2 managers (e.g., `fs`) and mock the rest.
This helper provides a single place to construct a valid `ManagersDict` with
reasonable MagicMock defaults.
"""

from unittest.mock import MagicMock

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.migration import MigrationManager
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager
from cortex.managers.types import ManagersDict


def make_test_managers(
    *,
    fs: FileSystemManager | MagicMock | None = None,
    index: MetadataIndex | MagicMock | None = None,
    tokens: TokenCounter | MagicMock | None = None,
    graph: DependencyGraph | MagicMock | None = None,
    versions: VersionManager | MagicMock | None = None,
    migration: MigrationManager | MagicMock | None = None,
    watcher: FileWatcherManager | MagicMock | None = None,
    **kwargs: MagicMock | None,
) -> ManagersDict:
    """Create a valid `ManagersDict` with MagicMock defaults.

    Callers may override any known ManagersDict field (e.g., `fs=mock_fs`).
    Additional optional fields can be passed via kwargs (e.g., `synapse=mock_synapse`).
    """
    # Tests frequently use mocks/AsyncMocks for managers. `model_construct`
    # bypasses strict instance checks while still providing attribute access.
    return ManagersDict.model_construct(
        fs=fs or MagicMock(name="fs"),
        index=index or MagicMock(name="index"),
        tokens=tokens or MagicMock(name="tokens"),
        graph=graph or MagicMock(name="graph"),
        versions=versions or MagicMock(name="versions"),
        migration=migration or MagicMock(name="migration"),
        watcher=watcher or MagicMock(name="watcher"),
        **kwargs,
    )
