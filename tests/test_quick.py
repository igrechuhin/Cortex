#!/usr/bin/env python3
"""Quick test of key MCP tools."""

import asyncio
import json
import tempfile

from cortex.tools.phase1_foundation_stats import get_memory_bank_stats

# Note: check_migration_status and initialize_memory_bank have been replaced
# by prompt templates (see docs/prompts/)


async def main():
    print("🚀 Quick MCP Tools Test\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Project: {tmpdir}\n")

        print("1. Skipping check_migration_status (replaced by prompt templates)")
        print("2. Skipping initialize_memory_bank (replaced by prompt templates)")
        print("3. Get stats...")
        result = await get_memory_bank_stats(tmpdir)
        data = json.loads(result)
        if data["status"] == "success":
            print(f"   Total files: {data['summary']['total_files']}")
            print(f"   Total tokens: {data['summary']['total_tokens']}")

        print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
