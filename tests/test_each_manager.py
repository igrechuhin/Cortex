#!/usr/bin/env python3
"""Test each manager initialization individually."""

import asyncio
import tempfile
from pathlib import Path

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.file_watcher import FileWatcherManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.migration import MigrationManager
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager


async def test_each_manager():
    """Test each manager one by one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        print(f"Project root: {project_root}\n")

        print("1. FileSystemManager...")
        fs_manager = FileSystemManager(project_root)
        print("   ✓ Initialized")

        print("2. MetadataIndex...")
        _ = MetadataIndex(project_root)
        print("   ✓ Initialized")

        print("3. TokenCounter...")
        _ = TokenCounter()
        print("   ✓ Initialized")

        print("4. DependencyGraph...")
        _ = DependencyGraph()
        print("   ✓ Initialized")

        print("5. VersionManager...")
        _ = VersionManager(project_root)
        print("   ✓ Initialized")

        print("6. MigrationManager...")
        _ = MigrationManager(project_root)
        print("   ✓ Initialized")

        print("7. FileWatcherManager...")
        _ = FileWatcherManager()
        print("   ✓ Initialized")

        print("\n8. Testing cleanup_locks()...")
        await fs_manager.cleanup_locks()
        print("   ✓ cleanup_locks() completed")

        print("\n✅ All managers initialized successfully!")


if __name__ == "__main__":
    asyncio.run(test_each_manager())
