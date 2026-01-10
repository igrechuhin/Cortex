"""Lightweight benchmarks that don't require network access.

This module contains benchmarks for operations that don't depend on
external resources like tiktoken encodings.
"""

import tempfile
from pathlib import Path

from ..core.dependency_graph import DependencyGraph
from ..core.file_system import FileSystemManager
from .framework import Benchmark, BenchmarkSuite


class FileReadWriteBenchmark(Benchmark):
    """Benchmark file read/write operations."""

    def __init__(self, num_files: int = 50, content_size: int = 100):
        """Initialize file read/write benchmark.

        Args:
            num_files: Number of files to read/write
            content_size: Number of lines in each file
        """
        super().__init__(
            name=f"File Read/Write ({num_files} files, {content_size} lines)",
            description=f"Measure file I/O with {num_files} files of {content_size} lines",
            iterations=50,
            warmup_iterations=5,
        )
        self.num_files = num_files
        self.content_size = content_size
        self.fs_manager: FileSystemManager | None = None
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.test_content: str = ""

    async def setup(self) -> None:
        """Set up file system manager and temp directory."""
        self.temp_dir = tempfile.TemporaryDirectory[str]()
        base_path = Path(self.temp_dir.name)
        self.fs_manager = FileSystemManager(base_path)
        self.test_content = "# Test Content\n" * self.content_size

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


class DependencyGraphQueryBenchmark(Benchmark):
    """Benchmark dependency graph query operations."""

    def __init__(self, num_nodes: int = 100, avg_dependencies: int = 5):
        """Initialize dependency graph query benchmark.

        Args:
            num_nodes: Number of nodes in graph
            avg_dependencies: Average number of dependencies per node
        """
        super().__init__(
            name=f"Graph Queries ({num_nodes} nodes, avg {avg_dependencies} deps)",
            description=f"Measure graph queries with {num_nodes} nodes",
            iterations=100,
            warmup_iterations=10,
        )
        self.num_nodes = num_nodes
        self.avg_dependencies = avg_dependencies
        self.graph: DependencyGraph | None = None

    async def setup(self) -> None:
        """Set up dependency graph."""
        self.graph = DependencyGraph()

        # Build graph with specified average dependencies
        for i in range(self.num_nodes):
            for j in range(i % (self.avg_dependencies * 2)):
                if j < self.num_nodes:
                    self.graph.add_dynamic_dependency(f"file_{i}.md", f"file_{j}.md")

    async def run_iteration(self) -> None:
        """Run single graph query iteration."""
        if self.graph:
            for i in range(self.num_nodes):
                _ = self.graph.get_dependencies(f"file_{i}.md")
                _ = self.graph.get_dependents(f"file_{i}.md")


class DependencyGraphSerializationBenchmark(Benchmark):
    """Benchmark dependency graph serialization (to_dict)."""

    def __init__(self, num_nodes: int = 100):
        """Initialize graph serialization benchmark.

        Args:
            num_nodes: Number of nodes in graph
        """
        super().__init__(
            name=f"Graph Serialization ({num_nodes} nodes)",
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
        """Run single serialization iteration."""
        if self.graph:
            _ = self.graph.to_dict()


class FileMetadataBenchmark(Benchmark):
    """Benchmark file metadata operations."""

    def __init__(self, num_files: int = 50, content_size: int = 100):
        """Initialize file metadata benchmark.

        Args:
            num_files: Number of files to query
            content_size: Number of lines in each file
        """
        super().__init__(
            name=f"File Metadata ({num_files} files, {content_size} lines)",
            description=f"Measure metadata query performance with {num_files} files",
            iterations=50,
            warmup_iterations=5,
        )
        self.num_files = num_files
        self.content_size = content_size
        self.fs_manager: FileSystemManager | None = None
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.test_content: str = ""

    async def setup(self) -> None:
        """Set up file system manager and create test files."""
        self.temp_dir = tempfile.TemporaryDirectory[str]()
        base_path = Path(self.temp_dir.name)
        self.fs_manager = FileSystemManager(base_path)
        self.test_content = "# Test Content\n" * self.content_size

        # Create files
        for i in range(self.num_files):
            file_path = base_path / f"test_{i}.md"
            _ = await self.fs_manager.write_file(file_path, self.test_content)

    async def teardown(self) -> None:
        """Clean up temp directory."""
        if self.temp_dir:
            self.temp_dir.cleanup()

    async def run_iteration(self) -> None:
        """Run single metadata query iteration."""
        if self.fs_manager and self.temp_dir:
            base_path = Path(self.temp_dir.name)
            for i in range(self.num_files):
                file_path = base_path / f"test_{i}.md"
                _ = await self.fs_manager.get_file_size(file_path)
                _ = await self.fs_manager.get_modification_time(file_path)


def create_lightweight_benchmark_suite() -> BenchmarkSuite:
    """Create lightweight benchmark suite without network dependencies."""
    suite = BenchmarkSuite(
        name="Lightweight Benchmarks",
        description="Fast benchmarks without external dependencies",
    )

    # File I/O benchmarks
    suite.add_benchmark(FileReadWriteBenchmark(num_files=10, content_size=50))
    suite.add_benchmark(FileReadWriteBenchmark(num_files=50, content_size=100))
    suite.add_benchmark(FileReadWriteBenchmark(num_files=100, content_size=200))

    # Dependency graph query benchmarks
    suite.add_benchmark(DependencyGraphQueryBenchmark(num_nodes=50, avg_dependencies=3))
    suite.add_benchmark(
        DependencyGraphQueryBenchmark(num_nodes=100, avg_dependencies=5)
    )
    suite.add_benchmark(
        DependencyGraphQueryBenchmark(num_nodes=200, avg_dependencies=7)
    )

    # Graph serialization benchmarks
    suite.add_benchmark(DependencyGraphSerializationBenchmark(num_nodes=50))
    suite.add_benchmark(DependencyGraphSerializationBenchmark(num_nodes=100))
    suite.add_benchmark(DependencyGraphSerializationBenchmark(num_nodes=200))

    # File metadata benchmarks
    suite.add_benchmark(FileMetadataBenchmark(num_files=25, content_size=100))
    suite.add_benchmark(FileMetadataBenchmark(num_files=50, content_size=200))
    suite.add_benchmark(FileMetadataBenchmark(num_files=100, content_size=500))

    return suite
