#!/usr/bin/env python3
"""Test get_managers initialization."""

import asyncio
import tempfile
from pathlib import Path

from cortex.managers import get_managers


async def test_get_managers():
    """Test manager initialization."""
    print("Creating temp directory...")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        print(f"Project root: {project_root}")

        print("\nCalling get_managers()...")
        mgrs = await get_managers(project_root)
        print(f"Managers initialized: {list(mgrs.keys())}")

        print("\n✅ Test complete - no hang!")


if __name__ == "__main__":
    asyncio.run(test_get_managers())
