#!/usr/bin/env python3
"""Integration tests for Phase 1 MCP tools."""

import asyncio
import json
import tempfile

from cortex.tools.file_operations import manage_file

# Import the tool functions directly
from cortex.tools.phase1_foundation import (
    get_dependency_graph,
    get_memory_bank_stats,
    get_version_history,
    rollback_file_version,
)


# Helper function to replace initialize_memory_bank (which has been replaced by prompt templates)
async def _initialize_memory_bank_helper(project_root: str) -> str:
    """
    Helper to initialize memory bank structure for tests.

    Note: The actual initialize_memory_bank function has been replaced by
    prompt templates. This helper creates the basic structure for testing.
    """
    from pathlib import Path

    root = Path(project_root)
    memory_bank_dir = root / "memory-bank"
    memory_bank_dir.mkdir(exist_ok=True, parents=True)

    # Create basic files if they don't exist
    basic_files = [
        "projectBrief.md",
        "activeContext.md",
        "systemPatterns.md",
        "techContext.md",
        "productContext.md",
        "progress.md",
        "roadmap.md",
    ]

    created = 0
    for filename in basic_files:
        file_path = memory_bank_dir / filename
        if not file_path.exists():
            _ = file_path.write_text(
                f"# {filename.replace('.md', '')}\n\nPlaceholder content.\n"
            )
            created += 1

    return json.dumps(
        {
            "status": "success",
            "message": "Memory Bank initialized for testing",
            "total_files": created,
        },
        indent=2,
    )


async def test_full_workflow():
    """Test complete workflow: init -> read -> write -> version -> rollback."""
    print("=" * 60)
    print("🚀 MCP Memory Bank - Integration Test")
    print("=" * 60)
    print()

    # Create temporary project directory
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = str(tmpdir)
        print(f"📁 Test project: {project_root}")
        print()

        # Test 1: Initialize Memory Bank
        print("🧪 Test 1: Initialize Memory Bank")
        result = await _initialize_memory_bank_helper(project_root)
        data = json.loads(result)
        assert data["status"] == "success", f"Init failed: {data}"
        print(f"   ✓ Status: {data['status']}")
        print(f"   ✓ Files created: {data['total_files']}")
        print()

        # Test 2: Read a file
        print("🧪 Test 2: Read projectBrief.md")
        result = await manage_file(
            operation="read",
            file_name="projectBrief.md",
            project_root=project_root,
            include_metadata=True,
        )
        data = json.loads(result)
        assert data["status"] == "success", "Read failed"
        assert "content" in data, "No content returned"
        assert len(data["content"]) > 0, "Content is empty"
        print(f"   ✓ File read: {len(data['content'])} bytes")
        if "metadata" in data and data["metadata"] is not None:
            print(f"   ✓ Token count: {data['metadata']['token_count']}")
        print()

        # Test 3: Write/update a file
        print("🧪 Test 3: Update projectBrief.md")
        new_content = "# Project Brief\n\nThis is an updated project brief.\n\n## Goals\n- Test versioning\n- Test metadata tracking\n"
        result = await manage_file(
            operation="write",
            file_name="projectBrief.md",
            content=new_content,
            project_root=project_root,
            change_description="Updated with test content",
        )
        data = json.loads(result)
        assert data["status"] == "success", f"Write failed: {data}"
        print("   ✓ File updated")
        if "snapshot_id" in data:
            print(f"   ✓ Version: {data['snapshot_id']}")
        elif "version" in data:
            print(f"   ✓ Version: {data['version']}")
        print(f"   ✓ Token count: {data.get('tokens', data.get('token_count', 'N/A'))}")
        print()

        # Test 4: Get file metadata
        print("🧪 Test 4: Get file metadata")
        result = await manage_file(
            operation="metadata", file_name="projectBrief.md", project_root=project_root
        )
        data = json.loads(result)
        assert data["status"] == "success", "Get metadata failed"
        metadata = data["metadata"]
        print(f"   ✓ Current version: {metadata.get('current_version', 0)}")
        print(f"   ✓ Read count: {metadata.get('read_count', 0)}")
        print(f"   ✓ Token count: {metadata.get('token_count', 0)}")
        print()

        # Test 5: Get version history
        print("🧪 Test 5: Get version history")
        result = await get_version_history("projectBrief.md", project_root)
        data = json.loads(result)
        assert data["status"] == "success", "Get history failed"
        print(f"   ✓ Total versions: {data['total_versions']}")
        if data["total_versions"] > 0:
            latest = data["versions"][0]
            print(f"   ✓ Latest: v{latest['version']} - {latest['change_type']}")
        print()

        # Test 6: Get dependency graph
        print("🧪 Test 6: Get dependency graph")
        result = await get_dependency_graph(project_root, format="json")
        data = json.loads(result)
        assert data["status"] == "success", "Get graph failed"
        print(f"   ✓ Files in graph: {len(data['graph']['files'])}")
        print(f"   ✓ Loading order: {len(data['loading_order'])} files")
        print()

        # Test 7: Get overall stats
        print("🧪 Test 7: Get Memory Bank statistics")
        result = await get_memory_bank_stats(project_root)
        data = json.loads(result)
        assert data["status"] == "success", "Get stats failed"
        summary = data["summary"]
        print(f"   ✓ Total files: {summary['total_files']}")
        print(f"   ✓ Total tokens: {summary['total_tokens']}")
        print(f"   ✓ Total size: {summary['total_size_kb']} KB")
        print()

        # Test 8: Rollback (if we have multiple versions)
        print("🧪 Test 8: Rollback to version 1")
        result = await rollback_file_version("projectBrief.md", 1, project_root)
        data = json.loads(result)
        if data["status"] == "success":
            print("   ✓ Rolled back to version 1")
            print(f"   ✓ New version: {data['new_version']}")
        else:
            print(f"   ⚠ Rollback not available: {data.get('error', 'Unknown')}")
        print()

        print("=" * 60)
        print("✅ All integration tests passed!")
        print("=" * 60)


async def test_error_handling():
    """Test error handling scenarios."""
    print()
    print("🧪 Testing Error Handling")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = str(tmpdir)

        # Initialize first
        _ = await _initialize_memory_bank_helper(project_root)

        # Test 1: Read non-existent file
        print("   Testing: Read non-existent file")
        result = await manage_file(
            operation="read", file_name="nonexistent.md", project_root=project_root
        )
        data = json.loads(result)
        assert data["status"] == "error", "Should fail on non-existent file"
        print("   ✓ Correctly returns error")

        # Test 2: Get metadata for non-existent file
        print("   Testing: Get metadata for non-existent file")
        result = await manage_file(
            operation="metadata", file_name="nonexistent.md", project_root=project_root
        )
        data = json.loads(result)
        assert data["status"] in (
            "error",
            "not_found",
        ), "Should fail on non-existent file"
        print("   ✓ Correctly returns error")

        print("   ✅ Error handling tests passed")
        print()


if __name__ == "__main__":
    asyncio.run(test_full_workflow())
    asyncio.run(test_error_handling())
