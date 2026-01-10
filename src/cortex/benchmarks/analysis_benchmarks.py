"""Benchmarks for analysis operations.

This module contains benchmarks for pattern analysis, structure analysis,
and other analytical operations.
"""

import tempfile
from pathlib import Path

from ..analysis.pattern_analyzer import PatternAnalyzer
from ..analysis.structure_analyzer import StructureAnalyzer
from ..core.dependency_graph import DependencyGraph
from ..core.file_system import FileSystemManager
from .framework import Benchmark, BenchmarkSuite


class PatternAnalysisBenchmark(Benchmark):
    """Benchmark pattern analysis operations."""

    def __init__(self, num_files: int = 20):
        """Initialize pattern analysis benchmark.

        Args:
            num_files: Number of files to analyze
        """
        super().__init__(
            name=f"Pattern Analysis ({num_files} files)",
            description=f"Measure pattern analysis with {num_files} files",
            iterations=20,
            warmup_iterations=5,
        )
        self.num_files = num_files
        self.analyzer: PatternAnalyzer | None = None
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None

    async def setup(self) -> None:
        """Set up pattern analyzer."""
        self.temp_dir = tempfile.TemporaryDirectory[str]()
        base_path = Path(self.temp_dir.name)
        self.analyzer = PatternAnalyzer(base_path)

        # Record some access patterns
        for i in range(self.num_files):
            filename = f"file_{i}.md"
            for _ in range(10):
                await self.analyzer.record_access(filename, "read")

    async def teardown(self) -> None:
        """Clean up temp directory."""
        if self.temp_dir:
            self.temp_dir.cleanup()

    async def run_iteration(self) -> None:
        """Run single pattern analysis iteration."""
        if self.analyzer:
            _ = await self.analyzer.get_co_access_patterns()


class StructureAnalysisBenchmark(Benchmark):
    """Benchmark structure analysis operations."""

    def __init__(self, num_files: int = 20):
        """Initialize structure analysis benchmark.

        Args:
            num_files: Number of files to analyze
        """
        super().__init__(
            name=f"Structure Analysis ({num_files} files)",
            description=f"Measure structure analysis with {num_files} files",
            iterations=10,
            warmup_iterations=3,
        )
        self.num_files = num_files
        self.analyzer: StructureAnalyzer | None = None
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.fs_manager: FileSystemManager | None = None

    async def setup(self) -> None:
        """Set up structure analyzer."""
        self.temp_dir = tempfile.TemporaryDirectory[str]()
        base_path = Path(self.temp_dir.name)
        self.fs_manager = FileSystemManager(base_path)

        # Create test files
        for i in range(self.num_files):
            content = f"# File {i}\n" + ("Content line\n" * 100)
            file_path = base_path / f"file_{i}.md"
            _ = await self.fs_manager.write_file(file_path, content)

        # Create dependency graph
        dep_graph = DependencyGraph()
        for i in range(self.num_files):
            if i > 0:
                dep_graph.add_dynamic_dependency(f"file_{i}.md", f"file_{i-1}.md")

        # StructureAnalyzer requires project_root, dependency_graph, file_system, and metadata_index
        from ..core.metadata_index import MetadataIndex

        metadata_index = MetadataIndex(base_path)
        self.analyzer = StructureAnalyzer(
            project_root=base_path,
            dependency_graph=dep_graph,
            file_system=self.fs_manager,
            metadata_index=metadata_index,
        )

    async def teardown(self) -> None:
        """Clean up temp directory."""
        if self.temp_dir:
            self.temp_dir.cleanup()

    async def run_iteration(self) -> None:
        """Run single structure analysis iteration."""
        if self.analyzer:
            _ = await self.analyzer.analyze_file_organization()


class CoAccessPatternBenchmark(Benchmark):
    """Benchmark co-access pattern calculation."""

    def __init__(self, num_files: int = 50):
        """Initialize co-access pattern benchmark.

        Args:
            num_files: Number of files to analyze
        """
        super().__init__(
            name=f"Co-Access Patterns ({num_files} files)",
            description=f"Measure co-access pattern calculation with {num_files} files",
            iterations=50,
            warmup_iterations=10,
        )
        self.num_files = num_files
        self.analyzer: PatternAnalyzer | None = None
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None

    async def setup(self) -> None:
        """Set up pattern analyzer with co-access data."""
        self.temp_dir = tempfile.TemporaryDirectory[str]()
        base_path = Path(self.temp_dir.name)
        self.analyzer = PatternAnalyzer(base_path)

        # Record co-access patterns
        for i in range(self.num_files):
            for j in range(i + 1, min(i + 5, self.num_files)):
                await self.analyzer.record_access(f"file_{i}.md", "read")
                await self.analyzer.record_access(f"file_{j}.md", "read")

    async def teardown(self) -> None:
        """Clean up temp directory."""
        if self.temp_dir:
            self.temp_dir.cleanup()

    async def run_iteration(self) -> None:
        """Run single co-access pattern calculation."""
        if self.analyzer:
            _ = await self.analyzer.get_co_access_patterns()


def create_analysis_benchmark_suite() -> BenchmarkSuite:
    """Create benchmark suite for analysis operations."""
    suite = BenchmarkSuite(
        name="Analysis Operations",
        description="Benchmarks for pattern and structure analysis",
    )

    # Pattern analysis benchmarks
    suite.add_benchmark(PatternAnalysisBenchmark(num_files=10))
    suite.add_benchmark(PatternAnalysisBenchmark(num_files=20))
    suite.add_benchmark(PatternAnalysisBenchmark(num_files=50))

    # Structure analysis benchmarks
    suite.add_benchmark(StructureAnalysisBenchmark(num_files=10))
    suite.add_benchmark(StructureAnalysisBenchmark(num_files=20))
    suite.add_benchmark(StructureAnalysisBenchmark(num_files=30))

    # Co-access pattern benchmarks
    suite.add_benchmark(CoAccessPatternBenchmark(num_files=20))
    suite.add_benchmark(CoAccessPatternBenchmark(num_files=50))
    suite.add_benchmark(CoAccessPatternBenchmark(num_files=100))

    return suite
