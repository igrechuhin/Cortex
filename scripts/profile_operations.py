#!/usr/bin/env python3
"""Performance profiling script for MCP Memory Bank operations.

This script profiles key operations to identify performance bottlenecks:
- Token counting operations
- File I/O operations
- Dependency graph operations
- Structure analysis operations
- Transclusion resolution
"""

import asyncio
import cProfile
import io
import pstats

# Add src to path
import sys
import tempfile
import time
from collections.abc import Callable, Coroutine
from pathlib import Path
from pstats import SortKey
from typing import cast

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.analysis.structure_analyzer import StructureAnalyzer
from cortex.core.dependency_graph import DependencyGraph
from cortex.core.file_system import FileSystemManager
from cortex.core.token_counter import TokenCounter
from cortex.linking.link_parser import LinkParser
from cortex.linking.transclusion_engine import TransclusionEngine


async def profile_token_counting() -> float:
    """Profile token counting operations."""
    print("\n=== Profiling Token Counting ===")

    counter = TokenCounter()
    test_content = "# Test\n" * 1000  # Large content

    start = time.perf_counter()
    for _ in range(100):
        _ = counter.count_tokens(test_content)
    elapsed = time.perf_counter() - start

    print(f"100 token counting operations: {elapsed:.3f}s")
    print(f"Average per operation: {elapsed/100*1000:.2f}ms")
    return elapsed


async def profile_file_operations() -> float:
    """Profile file I/O operations."""
    print("\n=== Profiling File Operations ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        fs_manager = FileSystemManager(base_path)

        test_content = "# Test Content\n" * 100

        start = time.perf_counter()
        for i in range(50):
            _ = await fs_manager.write_file(Path(f"test_{i}.md"), test_content)
            _, _ = await fs_manager.read_file(Path(f"test_{i}.md"))
        elapsed = time.perf_counter() - start

        print(f"50 write+read operations: {elapsed:.3f}s")
        print(f"Average per operation: {elapsed/50*1000:.2f}ms")
        return elapsed


async def profile_dependency_graph() -> float:
    """Profile dependency graph operations."""
    print("\n=== Profiling Dependency Graph ===")

    graph = DependencyGraph()

    # Build a large graph
    start = time.perf_counter()
    for i in range(100):
        for j in range(i % 10):
            graph.add_dynamic_dependency(f"file_{i}.md", f"file_{j}.md")

    # Test operations
    for i in range(100):
        _ = graph.get_dependencies(f"file_{i}.md")
        _ = graph.get_dependents(f"file_{i}.md")

    elapsed = time.perf_counter() - start

    print(f"Built 100 nodes + 200 queries: {elapsed:.3f}s")
    print(f"Average per operation: {elapsed/300*1000:.2f}ms")
    return elapsed


async def profile_structure_analysis() -> float:
    """Profile structure analysis operations."""
    print("\n=== Profiling Structure Analysis ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        fs_manager = FileSystemManager(base_path)

        # Create test files
        for i in range(20):
            content = f"# File {i}\n" + ("Content line\n" * 100)
            _ = await fs_manager.write_file(Path(f"file_{i}.md"), content)

        dep_graph = DependencyGraph()
        for i in range(20):
            if i > 0:
                dep_graph.add_dynamic_dependency(f"file_{i}.md", f"file_{i-1}.md")

        from cortex.core.metadata_index import MetadataIndex

        metadata_index = MetadataIndex(base_path)
        analyzer = StructureAnalyzer(base_path, dep_graph, fs_manager, metadata_index)

        start = time.perf_counter()
        result = await analyzer.analyze_file_organization()
        elapsed = time.perf_counter() - start

        print(f"Structure analysis (20 files): {elapsed:.3f}s")
        if "organization" in result:
            org: object = result["organization"]
            if isinstance(org, dict) and "total_files" in org:
                org_dict = cast(dict[str, object], org)
                total_value = org_dict["total_files"]
                if isinstance(total_value, int):
                    print(f"Files analyzed: {total_value}")
                else:
                    print("Files analyzed: N/A")
            else:
                print("Files analyzed: N/A")
        else:
            print("Files analyzed: N/A")
        return elapsed


async def profile_transclusion() -> float:
    """Profile transclusion resolution operations."""
    print("\n=== Profiling Transclusion Resolution ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        fs_manager = FileSystemManager(base_path)

        # Create source files
        _ = await fs_manager.write_file(Path("source.md"), "# Source\nSource content\n")

        # Create file with transclusions
        transclusion_content = (
            "# Main\n" + "{{include: source.md}}\n" * 10 + "More content\n"
        )
        _ = await fs_manager.write_file(Path("main.md"), transclusion_content)

        link_parser = LinkParser()
        engine = TransclusionEngine(fs_manager, link_parser)

        start = time.perf_counter()
        for _ in range(50):
            content, _ = await fs_manager.read_file(Path("main.md"))
            _ = await engine.resolve_content(content, "main.md")
        elapsed = time.perf_counter() - start

        print(f"50 transclusion resolutions: {elapsed:.3f}s")
        print(f"Average per operation: {elapsed/50*1000:.2f}ms")
        return elapsed


def run_profiled(func: Callable[[], Coroutine[object, object, float]]) -> float:
    """Run a function with cProfile and display results."""
    profiler = cProfile.Profile()
    profiler.enable()

    result = asyncio.run(func())

    profiler.disable()

    # Print profiler statistics
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats(SortKey.CUMULATIVE)
    _ = ps.print_stats(20)  # Top 20 functions
    print(s.getvalue())

    return result


async def main():
    """Run all profiling tests."""
    print("=" * 60)
    print("MCP Memory Bank Performance Profiling")
    print("=" * 60)

    total_start = time.perf_counter()

    # Run each profiling test
    tests = [
        ("Token Counting", profile_token_counting),
        ("File Operations", profile_file_operations),
        ("Dependency Graph", profile_dependency_graph),
        ("Structure Analysis", profile_structure_analysis),
        ("Transclusion Resolution", profile_transclusion),
    ]

    results: dict[str, float] = {}
    for name, test_func in tests:
        print(f"\n{'='*60}")
        elapsed = await test_func()
        results[name] = elapsed

    total_elapsed = time.perf_counter() - total_start

    # Print summary
    print("\n" + "=" * 60)
    print("PROFILING SUMMARY")
    print("=" * 60)
    for name, elapsed in results.items():
        print(f"{name:30s}: {elapsed:.3f}s")
    print(f"{'Total Time':30s}: {total_elapsed:.3f}s")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
