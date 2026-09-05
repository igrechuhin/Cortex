"""Benchmarks for analysis operations.

This module contains benchmarks for pattern analysis, structure analysis,
and other analytical operations. Phase 9.3 target: p95 < 200ms for hot paths.
"""

import tempfile
from pathlib import Path

from ..analysis.pattern_analyzer import PatternAnalyzer
from ..analysis.structure_analyzer import StructureAnalyzer
from ..core.dependency_graph import DependencyGraph
from ..core.file_system import FileSystemManager
from ..core.path_resolver import CortexResourceType, get_cortex_path
from ..core.session_logger import log_load_context_call
from .framework import Benchmark, BenchmarkSuite


def _seed_load_context_call(project_root: Path, selected_files: list[str]) -> None:
    """Seed one load_context session-log entry for pattern-analysis benchmarks."""
    log_load_context_call(
        project_root=project_root,
        task_description="benchmark",
        token_budget=1000,
        strategy="balanced",
        selected_files=selected_files,
        selected_sections={},
        total_tokens=500,
        utilization=0.5,
        excluded_files=[],
        relevance_scores={},
    )


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

        # Seed session logs; PatternAnalyzer projects its access log from them
        # at construction time, so seeding must happen first.
        for i in range(self.num_files):
            for _ in range(10):
                _seed_load_context_call(base_path, [f"file_{i}.md"])
        self.analyzer = PatternAnalyzer(base_path)

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
        """Set up structure analyzer with memory bank layout."""
        self.temp_dir = tempfile.TemporaryDirectory[str]()
        base_path = Path(self.temp_dir.name)
        self.fs_manager = FileSystemManager(base_path)
        memory_bank_dir = get_cortex_path(base_path, CortexResourceType.MEMORY_BANK)
        memory_bank_dir.mkdir(parents=True, exist_ok=True)

        # Create test files in memory bank
        for i in range(self.num_files):
            content = f"# File {i}\n" + ("Content line\n" * 100)
            file_path = memory_bank_dir / f"file_{i}.md"
            _ = await self.fs_manager.write_file(file_path, content)

        # Create dependency graph
        dep_graph = DependencyGraph()
        for i in range(self.num_files):
            if i > 0:
                dep_graph.add_dynamic_dependency(f"file_{i}.md", f"file_{i - 1}.md")

        # StructureAnalyzer requires project_root, dependency_graph,
        # file_system, and metadata_index
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


class AntiPatternDetectionBenchmark(StructureAnalysisBenchmark):
    """Benchmark detect_anti_patterns (Phase 9.3 hot path)."""

    def __init__(self, num_files: int = 20):
        """Initialize anti-pattern detection benchmark."""
        super().__init__(num_files=num_files)
        self.name = f"Anti-Pattern Detection ({num_files} files)"
        self.description = f"Measure detect_anti_patterns with {num_files} files"

    async def run_iteration(self) -> None:
        """Run single anti-pattern detection iteration."""
        if self.analyzer:
            _ = await self.analyzer.detect_anti_patterns()


class ComplexityMetricsBenchmark(StructureAnalysisBenchmark):
    """Benchmark measure_complexity_metrics (Phase 9.3 hot path)."""

    def __init__(self, num_files: int = 20):
        """Initialize complexity metrics benchmark."""
        super().__init__(num_files=num_files)
        self.name = f"Complexity Metrics ({num_files} files)"
        self.description = f"Measure measure_complexity_metrics with {num_files} files"

    async def run_iteration(self) -> None:
        """Run single complexity metrics iteration."""
        if self.analyzer:
            _ = await self.analyzer.measure_complexity_metrics()


class DependencyChainsBenchmark(StructureAnalysisBenchmark):
    """Benchmark find_dependency_chains (Phase 9.3 hot path)."""

    def __init__(self, num_files: int = 20):
        """Initialize dependency chains benchmark."""
        super().__init__(num_files=num_files)
        self.name = f"Dependency Chains ({num_files} files)"
        self.description = f"Measure find_dependency_chains with {num_files} files"

    async def run_iteration(self) -> None:
        """Run single dependency chains iteration."""
        if self.analyzer:
            _ = await self.analyzer.find_dependency_chains(max_chain_length=10)


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

        # Seed co-access data: each call selects a pair of files together.
        for i in range(self.num_files):
            for j in range(i + 1, min(i + 5, self.num_files)):
                _seed_load_context_call(base_path, [f"file_{i}.md", f"file_{j}.md"])
        self.analyzer = PatternAnalyzer(base_path)

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
    suite.add_benchmark(StructureAnalysisBenchmark(num_files=50))

    # Phase 9.3 hot-path benchmarks (target: p95 < 200ms)
    suite.add_benchmark(AntiPatternDetectionBenchmark(num_files=20))
    suite.add_benchmark(ComplexityMetricsBenchmark(num_files=20))
    suite.add_benchmark(DependencyChainsBenchmark(num_files=20))

    # Co-access pattern benchmarks
    suite.add_benchmark(CoAccessPatternBenchmark(num_files=20))
    suite.add_benchmark(CoAccessPatternBenchmark(num_files=50))
    suite.add_benchmark(CoAccessPatternBenchmark(num_files=100))

    return suite
