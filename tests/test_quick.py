#!/usr/bin/env python3
"""Quick checks for memory-bank query entrypoint (pytest + optional manual run)."""

from __future__ import annotations

import asyncio
import json
import tempfile

from cortex.tools.memory.query_memory_bank_operations import query_memory_bank


async def test_query_memory_bank_stats_detailed_json() -> None:
    result = await query_memory_bank(query_type="stats", response_format="detailed")
    data = json.loads(result)
    assert data["status"] == "success"
    assert "summary" in data
    assert "total_files" in data["summary"]
    assert "total_tokens" in data["summary"]


async def _manual_main() -> None:
    print("Quick MCP Tools Test\n")
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Project: {tmpdir}\n")
        print("1. Skipping check_migration_status (replaced by prompt templates)")
        print("2. Skipping initialize_memory_bank (replaced by prompt templates)")
        print("3. Get stats...")
        result = await query_memory_bank(query_type="stats", response_format="detailed")
        data = json.loads(result)
        if data["status"] == "success":
            print(f"   Total files: {data['summary']['total_files']}")
            print(f"   Total tokens: {data['summary']['total_tokens']}")
        print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(_manual_main())
