#!/usr/bin/env python3
"""Simple test to check MCP tool functions."""

import asyncio
import tempfile

# Note: check_migration_status and initialize_memory_bank have been replaced
# by prompt templates (see docs/prompts/)


async def main():
    print("Testing basic MCP tool invocation...")

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Project root: {tmpdir}")

        # Test 1: Check migration status (skipped - replaced by prompt templates)
        print("\n1. Skipping check_migration_status (replaced by prompt templates)")

        # Test 2: Initialize (skipped - replaced by prompt templates)
        print("\n2. Skipping initialize_memory_bank (replaced by prompt templates)")

        print("\n✅ Test complete")


if __name__ == "__main__":
    asyncio.run(main())
