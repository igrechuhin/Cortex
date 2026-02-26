"""Memory benchmarks for Phase 9.3 optimization.

Measures peak memory usage for typical hot paths using tracemalloc (stdlib).
Target: <50MB for typical projects (7 memory bank files, ~100KB total content).
"""

import tracemalloc

from .framework import Benchmark, BenchmarkResult, BenchmarkSuite


def _get_tracemalloc_mb() -> float:
    """Return current tracemalloc peak in MB."""
    _current, peak = tracemalloc.get_traced_memory()
    return peak / (1024 * 1024)


class ContextLoadMemoryBenchmark(Benchmark):
    """Benchmark peak memory during context-load-style file reads.

    Simulates loading all memory bank files into dicts (read_all_files_for_loading).
    Typical projects: 7 files, ~10KB each = ~70KB content + metadata.
    Target: peak < 50MB.
    """

    def __init__(self, num_files: int = 7, content_lines: int = 500):
        """Initialize memory benchmark.

        Args:
            num_files: Number of simulated memory bank files
            content_lines: Lines per file (each ~50 bytes)
        """
        super().__init__(
            name=f"Context load memory ({num_files} files, {content_lines} lines each)",
            description="Peak memory during file content load into dicts",
            iterations=5,
            warmup_iterations=2,
        )
        self.num_files = num_files
        self.content_lines = content_lines

    async def setup(self) -> None:
        """Start tracemalloc."""
        tracemalloc.start()

    async def teardown(self) -> None:
        """Stop tracemalloc."""
        tracemalloc.stop()

    async def run_iteration(self) -> None:
        """Simulate read_all_files_for_loading: load files into dicts."""
        files_content: dict[str, str] = {}
        files_metadata: dict[str, dict[str, object]] = {}
        line = "# Test content line for memory benchmark.\n"
        content = line * self.content_lines

        for i in range(self.num_files):
            name = f"file_{i}.md"
            files_content[name] = content
            files_metadata[name] = {
                "token_count": len(content.split()),
                "file_name": name,
            }

        # Simulate optimization pass: build result from content
        _ = sum(len(c) for c in files_content.values())
        _ = len(files_metadata)

    async def run(self) -> BenchmarkResult:
        """Run and record peak memory in metadata."""
        result = await super().run()
        peak_mb = _get_tracemalloc_mb()
        result.metadata["peak_memory_mb"] = round(peak_mb, 2)
        result.metadata["target_mb"] = 50
        result.metadata["description"] = self.description
        return result


class IndexLoadMemoryBenchmark(Benchmark):
    """Benchmark peak memory for index-like structures.

    Simulates MetadataIndex + dependency graph for typical project.
    Target: peak < 50MB.
    """

    def __init__(self, num_files: int = 50, edges_per_file: int = 5):
        """Initialize index memory benchmark.

        Args:
            num_files: Number of files in simulated index
            edges_per_file: Dependency edges per file
        """
        super().__init__(
            name=f"Index memory ({num_files} files, {edges_per_file} edges each)",
            description="Peak memory for index + dependency graph",
            iterations=5,
            warmup_iterations=2,
        )
        self.num_files = num_files
        self.edges_per_file = edges_per_file

    async def setup(self) -> None:
        """Start tracemalloc."""
        tracemalloc.start()

    async def teardown(self) -> None:
        """Stop tracemalloc."""
        tracemalloc.stop()

    async def run_iteration(self) -> None:
        """Simulate index structures: file metadata + dependency dicts."""
        files: dict[str, dict[str, object]] = {}
        dependencies: dict[str, set[str]] = {}

        for i in range(self.num_files):
            name = f"activeContext{i}.md" if i else "activeContext.md"
            files[name] = {
                "token_count": 1000,
                "sections": ["## Section A", "## Section B"],
            }
            deps: set[str] = set()
            for j in range(self.edges_per_file):
                other = (i + j + 1) % self.num_files
                other_name = f"file_{other}.md"
                deps.add(other_name)
            dependencies[name] = deps

        _ = len(files)
        _ = sum(len(d) for d in dependencies.values())

    async def run(self) -> BenchmarkResult:
        """Run and record peak memory in metadata."""
        result = await super().run()
        peak_mb = _get_tracemalloc_mb()
        result.metadata["peak_memory_mb"] = round(peak_mb, 2)
        result.metadata["target_mb"] = 50
        result.metadata["description"] = self.description
        return result


def create_memory_benchmark_suite() -> BenchmarkSuite:
    """Create memory benchmark suite for Phase 9.3."""
    suite = BenchmarkSuite(
        name="Memory Usage",
        description="Peak memory for typical MCP Memory Bank hot paths (Phase 9.3)",
    )
    suite.add_benchmark(ContextLoadMemoryBenchmark(num_files=7, content_lines=500))
    suite.add_benchmark(ContextLoadMemoryBenchmark(num_files=20, content_lines=1000))
    suite.add_benchmark(IndexLoadMemoryBenchmark(num_files=50, edges_per_file=5))
    suite.add_benchmark(IndexLoadMemoryBenchmark(num_files=100, edges_per_file=10))
    return suite
