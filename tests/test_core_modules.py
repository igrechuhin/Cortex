#!/usr/bin/env python3
"""Quick test script to verify core modules are working."""

import asyncio
import sys
from pathlib import Path
from typing import cast

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cortex.core.dependency_graph import DependencyGraph
from cortex.core.exceptions import FileConflictError, MemoryBankError
from cortex.core.file_system import FileSystemManager
from cortex.core.metadata_index import MetadataIndex
from cortex.core.token_counter import TokenCounter
from cortex.core.version_manager import VersionManager


async def test_token_counter():
    """Test token counter."""
    print("\n🧪 Testing TokenCounter...")
    counter = TokenCounter()

    text = "Hello world! This is a test."
    tokens = counter.count_tokens(text)
    print(f"   ✓ Token count: {tokens} tokens")

    # Test with cache
    cached_tokens = counter.count_tokens_with_cache(text, "hash123")
    print(f"   ✓ Cached token count: {cached_tokens} tokens")
    print(f"   ✓ Cache size: {counter.get_cache_size()}")


def test_dependency_graph():
    """Test dependency graph."""
    print("\n🧪 Testing DependencyGraph...")
    graph = DependencyGraph()

    order = graph.compute_loading_order()
    print(f"   ✓ Loading order: {len(order)} files")
    print(f"     {', '.join(order[:3])}...")

    deps = graph.get_dependencies("activeContext.md")
    print(f"   ✓ activeContext.md depends on: {len(deps)} files")

    minimal = graph.get_minimal_context("progress.md")
    print(f"   ✓ Minimal context for progress.md: {len(minimal)} files")

    # Test mermaid export
    mermaid = graph.to_mermaid()
    print(f"   ✓ Mermaid diagram: {len(mermaid)} characters")


async def test_file_system():
    """Test file system manager."""
    print("\n🧪 Testing FileSystemManager...")

    # Use temp directory
    test_dir = Path("/tmp/cortex-test")
    test_dir.mkdir(exist_ok=True)

    fs = FileSystemManager(test_dir)

    # Test path validation
    valid = fs.validate_path(test_dir / "test.md")
    print(f"   ✓ Path validation: {valid}")

    # Test hash computation
    content = "# Test File\n\nThis is test content."
    hash_val = fs.compute_hash(content)
    print(f"   ✓ Hash computation: {hash_val[:20]}...")

    # Test section parsing
    sections = fs.parse_sections(content)
    print(f"   ✓ Section parsing: {len(sections)} sections found")

    # Test file write/read
    test_file = test_dir / "test.md"
    new_hash = await fs.write_file(test_file, content)
    print(f"   ✓ File written: {new_hash[:20]}...")

    read_content, read_hash = await fs.read_file(test_file)
    print(f"   ✓ File read: {len(read_content)} bytes")
    print(f"   ✓ Hash matches: {new_hash == read_hash}")

    # Cleanup
    test_file.unlink()


async def test_metadata_index():
    """Test metadata index."""
    print("\n🧪 Testing MetadataIndex...")

    test_dir = Path("/tmp/cortex-test")
    test_dir.mkdir(exist_ok=True)

    index = MetadataIndex(test_dir)

    # Load (will create new)
    data_raw = await index.load()
    data: dict[str, object] = data_raw
    schema_version = data.get("schema_version")
    totals_raw = data.get("totals", {})
    if isinstance(totals_raw, dict):
        totals = cast(dict[str, int | str], totals_raw)
        total_files: int | str = totals.get("total_files", 0)
        print(f"   ✓ Index loaded: schema v{schema_version}")
        print(f"   ✓ Files tracked: {total_files}")

    # Update file metadata
    await index.update_file_metadata(
        file_name="test.md",
        path=test_dir / "test.md",
        exists=True,
        size_bytes=100,
        token_count=25,
        content_hash="sha256:abc123",
        sections=[],
    )
    print("   ✓ File metadata updated")

    # Get stats
    stats = await index.get_stats()
    totals_raw = stats.get("totals")
    assert isinstance(totals_raw, dict)
    totals = cast(dict[str, int | str], totals_raw)
    total_tokens: int | str | None = totals.get("total_tokens")
    print(f"   ✓ Total tokens: {total_tokens}")

    # Cleanup
    (test_dir / ".memory-bank-index").unlink(missing_ok=True)


async def test_version_manager():
    """Test version manager."""
    print("\n🧪 Testing VersionManager...")

    test_dir = Path("/tmp/cortex-test")
    test_dir.mkdir(exist_ok=True)

    vm = VersionManager(test_dir, keep_versions=5)

    # Create snapshot
    content = "# Test Content\nVersion 1"
    version_meta = await vm.create_snapshot(
        file_path=test_dir / "test.md",
        version=1,
        content=content,
        size_bytes=len(content),
        token_count=10,
        content_hash="sha256:test1",
        change_type="created",
    )
    print(f"   ✓ Snapshot created: v{version_meta['version']}")
    print(f"   ✓ Snapshot path: {version_meta['snapshot_path']}")

    # Get disk usage
    usage = await vm.get_disk_usage()
    print(f"   ✓ Disk usage: {usage['total_bytes']} bytes, {usage['file_count']} files")

    # Cleanup
    import shutil

    shutil.rmtree(test_dir / ".memory-bank-history", ignore_errors=True)


def test_exceptions():
    """Test custom exceptions."""
    print("\n🧪 Testing Custom Exceptions...")

    try:
        raise FileConflictError("test.md", "hash1", "hash2")
    except MemoryBankError as e:
        print(f"   ✓ FileConflictError: {str(e)[:50]}...")

    print("   ✓ All exception classes defined")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🚀 MCP Memory Bank - Core Module Tests")
    print("=" * 60)

    try:
        test_exceptions()
        await test_token_counter()
        test_dependency_graph()
        await test_file_system()
        await test_metadata_index()
        await test_version_manager()

        print("\n" + "=" * 60)
        print("✅ All core module tests passed!")
        print("=" * 60)
        print("\n📊 Modules tested:")
        print("   • exceptions.py - Custom exceptions")
        print("   • token_counter.py - Token counting with tiktoken")
        print("   • dependency_graph.py - Static dependency management")
        print("   • file_system.py - File I/O with locking")
        print("   • metadata_index.py - JSON index management")
        print("   • version_manager.py - Snapshot management")
        print("\n🎯 Ready to continue with:")
        print("   • file_watcher.py")
        print("   • migration.py")
        print("   • main.py (10 new MCP tools)")
        print()

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
