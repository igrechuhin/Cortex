#!/usr/bin/env python3
"""Minimal test to isolate the hang."""

import asyncio
import tempfile
from pathlib import Path

# Direct imports
from cortex.core.migration import MigrationManager


async def test_migration_detection():
    """Test just migration detection."""
    print("Creating temp directory...")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        print(f"Project root: {project_root}")

        print("\nInitializing MigrationManager...")
        mgr = MigrationManager(project_root)

        print("Calling detect_migration_needed()...")
        result = await mgr.detect_migration_needed()
        print(f"Result: {result}")

        print("\n✅ Test complete - no hang!")


if __name__ == "__main__":
    asyncio.run(test_migration_detection())
