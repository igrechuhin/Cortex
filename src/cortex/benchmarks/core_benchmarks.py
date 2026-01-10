"""Benchmarks for core MCP Memory Bank operations.

This module contains benchmarks for fundamental operations like file I/O,
token counting, and dependency graph operations.
"""

import tempfile
from pathlib import Path

from ..core.dependency_graph import DependencyGraph
from ..core.file_system import FileSystemManager
from ..core.token_counter import TokenCounter
from .framework import Benchmark, BenchmarkSuite


class TokenCountingBenchmark(Benchmark):
    """Benchmark token counting operations."""

    def __init__(self, content_size: int = 1000):
        """Initialize token counting benchmark.

        Args:
            content_size: Number of lines in test content
        """
        super().__init__(
            name=f"Token Counting ({content_size} lines)",
            description=f"Measure token counting performance with {content_size} lines",
            iterations=100,
            warmup_iterations=10,
        )
        self.content_size = content_size
        self.counter: TokenCounter | None = None
        self.test_content: str = ""

    async def setup(self) -> None:
        """Set up token counter and test content."""
        self.counter = TokenCounter()
        self.test_content = "# Test\n" * self.content_size

    async def run_iteration(self) -> None:
        """Run single token counting iteration."""
        if self.counter:
            _ = self.counter.count_tokens(self.test_content)


class FileIOBenchmark(Benchmark):
    """Benchmark file I/O operations."""

    def __init__(self, num_files: int = 50):
        """Initialize file I/O benchmark.

        Args:
            num_files: Number of files to read/write
        """
        super().__init__(
            name=f"File I/O ({num_files} files)",
            description=f"Measure file I/O performance with {num_files} files",
            iterations=50,
            warmup_iterations=5,
        )
        self.num_files = num_files
        self.fs_manager: FileSystemManager | None = None
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.test_content: str = "# Test Content\n" * 100

    async def setup(self) -> None:
        """Set up file system manager and temp directory."""
        self.temp_dir = tempfile.TemporaryDirectory[str]()
        base_path = Path(self.temp_dir.name)
        self.fs_manager = FileSystemManager(base_path)

    async def teardown(self) -> None:
        """Clean up temp directory."""
        if self.temp_dir:
            self.temp_dir.cleanup()

    async def run_iteration(self) -> None:
        """Run single file I/O iteration."""
        if self.fs_manager and self.temp_dir:
            base_path = Path(self.temp_dir.name)
            for i in range(self.num_files):
                file_path = base_path / f"test_{i}.md"
                _ = await self.fs_manager.write_file(file_path, self.test_content)
                _ = await self.fs_manager.read_file(file_path)


class DependencyGraphBenchmark(Benchmark):
    """Benchmark dependency graph operations."""

    def __init__(self, num_nodes: int = 100):
        """Initialize dependency graph benchmark.

        Args:
            num_nodes: Number of nodes in graph
        """
        super().__init__(
            name=f"Dependency Graph ({num_nodes} nodes)",
            description=f"Measure graph operations with {num_nodes} nodes",
            iterations=100,
            warmup_iterations=10,
        )
        self.num_nodes = num_nodes
        self.graph: DependencyGraph | None = None

    async def setup(self) -> None:
        """Set up dependency graph."""
        self.graph = DependencyGraph()

        # Build graph
        for i in range(self.num_nodes):
            for j in range(i % 10):
                self.graph.add_dynamic_dependency(f"file_{i}.md", f"file_{j}.md")

    async def run_iteration(self) -> None:
        """Run single graph operation iteration."""
        if self.graph:
            for i in range(self.num_nodes):
                _ = self.graph.get_dependencies(f"file_{i}.md")
                _ = self.graph.get_dependents(f"file_{i}.md")


class DependencyGraphToDictBenchmark(Benchmark):
    """Benchmark dependency graph to_dict operation."""

    def __init__(self, num_nodes: int = 100):
        """Initialize to_dict benchmark.

        Args:
            num_nodes: Number of nodes in graph
        """
        super().__init__(
            name=f"Graph to_dict ({num_nodes} nodes)",
            description=f"Measure to_dict performance with {num_nodes} nodes",
            iterations=100,
            warmup_iterations=10,
        )
        self.num_nodes = num_nodes
        self.graph: DependencyGraph | None = None

    async def setup(self) -> None:
        """Set up dependency graph."""
        self.graph = DependencyGraph()

        # Build graph
        for i in range(self.num_nodes):
            for j in range(i % 10):
                self.graph.add_dynamic_dependency(f"file_{i}.md", f"file_{j}.md")

    async def run_iteration(self) -> None:
        """Run single to_dict iteration."""
        if self.graph:
            _ = self.graph.to_dict()


def create_core_benchmark_suite() -> BenchmarkSuite:
    """Create benchmark suite for core operations."""
    suite = BenchmarkSuite(
        name="Core Operations",
        description="Benchmarks for fundamental MCP Memory Bank operations",
    )

    # Token counting benchmarks
    suite.add_benchmark(TokenCountingBenchmark(content_size=100))
    suite.add_benchmark(TokenCountingBenchmark(content_size=1000))
    suite.add_benchmark(TokenCountingBenchmark(content_size=10000))

    # File I/O benchmarks
    suite.add_benchmark(FileIOBenchmark(num_files=10))
    suite.add_benchmark(FileIOBenchmark(num_files=50))
    suite.add_benchmark(FileIOBenchmark(num_files=100))

    # Dependency graph benchmarks
    suite.add_benchmark(DependencyGraphBenchmark(num_nodes=50))
    suite.add_benchmark(DependencyGraphBenchmark(num_nodes=100))
    suite.add_benchmark(DependencyGraphBenchmark(num_nodes=200))

    # Graph to_dict benchmarks
    suite.add_benchmark(DependencyGraphToDictBenchmark(num_nodes=50))
    suite.add_benchmark(DependencyGraphToDictBenchmark(num_nodes=100))
    suite.add_benchmark(DependencyGraphToDictBenchmark(num_nodes=200))

    return suite
