"""Comprehensive tests for benchmark framework and operations.

This module provides extensive test coverage for:
- BenchmarkResult class and methods
- Benchmark base class and lifecycle hooks
- BenchmarkSuite and benchmark collection
- BenchmarkRunner execution and reporting
- Core operation benchmarks (token counting, file I/O, dependency graph)
- Analysis operation benchmarks (pattern analysis, structure analysis)
"""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from cortex.benchmarks.analysis_benchmarks import (
    CoAccessPatternBenchmark,
    PatternAnalysisBenchmark,
    StructureAnalysisBenchmark,
    create_analysis_benchmark_suite,
)
from cortex.benchmarks.core_benchmarks import (
    DependencyGraphBenchmark,
    DependencyGraphToDictBenchmark,
    FileIOBenchmark,
    TokenCountingBenchmark,
    create_core_benchmark_suite,
)
from cortex.benchmarks.framework import (
    Benchmark,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkSuite,
)

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def sample_benchmark_result() -> BenchmarkResult:
    """Create a sample benchmark result for testing."""
    return BenchmarkResult(
        name="Test Benchmark",
        iterations=100,
        total_time=10.5,
        min_time=0.08,
        max_time=0.15,
        mean_time=0.105,
        median_time=0.104,
        std_dev=0.012,
        p95_time=0.13,
        p99_time=0.14,
        metadata={"description": "Test benchmark description"},
    )


@pytest.fixture
def temp_output_dir() -> Generator[Path]:
    """Create a temporary directory for benchmark outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ==============================================================================
# Test BenchmarkResult
# ==============================================================================


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_benchmark_result_creation(
        self, sample_benchmark_result: BenchmarkResult
    ) -> None:
        """Test creating a BenchmarkResult instance."""
        # Arrange/Act - using fixture
        result = sample_benchmark_result

        # Assert
        assert result.name == "Test Benchmark"
        assert result.iterations == 100
        assert result.total_time == 10.5
        assert result.min_time == 0.08
        assert result.max_time == 0.15
        assert result.mean_time == 0.105
        assert result.median_time == 0.104
        assert result.std_dev == 0.012
        assert result.p95_time == 0.13
        assert result.p99_time == 0.14
        assert result.metadata == {"description": "Test benchmark description"}

    def test_benchmark_result_ops_per_second(
        self, sample_benchmark_result: BenchmarkResult
    ) -> None:
        """Test ops_per_second calculation."""
        # Arrange/Act
        ops_per_sec = sample_benchmark_result.ops_per_second

        # Assert
        expected = 100 / 10.5  # iterations / total_time
        assert abs(ops_per_sec - expected) < 0.01

    def test_benchmark_result_ops_per_second_zero_time(self):
        """Test ops_per_second with zero total time."""
        # Arrange
        result = BenchmarkResult(
            name="Test",
            iterations=100,
            total_time=0.0,
            min_time=0.0,
            max_time=0.0,
            mean_time=0.0,
            median_time=0.0,
            std_dev=0.0,
            p95_time=0.0,
            p99_time=0.0,
        )

        # Act
        ops_per_sec = result.ops_per_second

        # Assert
        assert ops_per_sec == 0.0

    def test_benchmark_result_to_dict(
        self, sample_benchmark_result: BenchmarkResult
    ) -> None:
        """Test converting BenchmarkResult to dictionary."""
        # Arrange/Act
        result_dict = sample_benchmark_result.to_dict()

        # Assert
        assert isinstance(result_dict, dict)
        assert result_dict["name"] == "Test Benchmark"
        assert result_dict["iterations"] == 100
        assert result_dict["total_time"] == 10.5
        assert result_dict["min_time"] == 0.08
        assert result_dict["max_time"] == 0.15
        assert result_dict["mean_time"] == 0.105
        assert result_dict["median_time"] == 0.104
        assert result_dict["std_dev"] == 0.012
        assert result_dict["p95_time"] == 0.13
        assert result_dict["p99_time"] == 0.14
        assert "ops_per_second" in result_dict
        assert result_dict["metadata"] == {"description": "Test benchmark description"}


# ==============================================================================
# Test Benchmark Base Class
# ==============================================================================


class ConcreteBenchmark(Benchmark):
    """Concrete benchmark implementation for testing."""

    def __init__(self):
        super().__init__(
            name="Concrete Test",
            description="Test benchmark",
            iterations=10,
            warmup_iterations=2,
        )
        self.setup_called = False
        self.teardown_called = False
        self.before_each_called = 0
        self.after_each_called = 0
        self.run_iteration_called = 0

    async def setup(self):
        """Track setup calls."""
        self.setup_called = True

    async def teardown(self):
        """Track teardown calls."""
        self.teardown_called = True

    async def before_each(self):
        """Track before_each calls."""
        self.before_each_called += 1

    async def after_each(self):
        """Track after_each calls."""
        self.after_each_called += 1

    async def run_iteration(self):
        """Track run_iteration calls."""
        self.run_iteration_called += 1


class TestBenchmark:
    """Tests for Benchmark base class."""

    def test_benchmark_initialization(self):
        """Test benchmark initialization."""
        # Arrange/Act
        benchmark = ConcreteBenchmark()

        # Assert
        assert benchmark.name == "Concrete Test"
        assert benchmark.description == "Test benchmark"
        assert benchmark.iterations == 10
        assert benchmark.warmup_iterations == 2

    @pytest.mark.asyncio
    async def test_benchmark_run_lifecycle(self):
        """Test benchmark run lifecycle hooks."""
        # Arrange
        benchmark = ConcreteBenchmark()

        # Act
        result = await benchmark.run()

        # Assert - setup and teardown called once
        assert benchmark.setup_called
        assert benchmark.teardown_called

        # Assert - before_each and after_each called for warmup + iterations
        expected_calls = benchmark.warmup_iterations + benchmark.iterations
        assert benchmark.before_each_called == expected_calls
        assert benchmark.after_each_called == expected_calls

        # Assert - run_iteration called for warmup + iterations
        assert benchmark.run_iteration_called == expected_calls

        # Assert - result is valid
        assert isinstance(result, BenchmarkResult)
        assert result.name == "Concrete Test"
        assert result.iterations == 10

    @pytest.mark.asyncio
    async def test_benchmark_not_implemented(self):
        """Test that abstract run_iteration raises NotImplementedError."""
        # Arrange
        benchmark = Benchmark(
            name="Abstract",
            description="Test",
            iterations=1,
            warmup_iterations=0,
        )

        # Act/Assert
        with pytest.raises(NotImplementedError, match="must implement run_iteration"):
            _ = await benchmark.run()

    @pytest.mark.asyncio
    async def test_benchmark_statistics_calculation(self):
        """Test that benchmark calculates statistics correctly."""
        # Arrange
        benchmark = ConcreteBenchmark()

        # Act
        result = await benchmark.run()

        # Assert - statistics are calculated
        assert result.min_time > 0
        assert result.max_time >= result.min_time
        assert result.mean_time > 0
        assert result.median_time > 0
        assert result.std_dev >= 0
        assert result.p95_time > 0
        assert result.p99_time > 0
        assert result.total_time > 0


# ==============================================================================
# Test BenchmarkSuite
# ==============================================================================


class TestBenchmarkSuite:
    """Tests for BenchmarkSuite class."""

    def test_suite_initialization(self):
        """Test suite initialization."""
        # Arrange/Act
        suite = BenchmarkSuite(name="Test Suite", description="Test description")

        # Assert
        assert suite.name == "Test Suite"
        assert suite.description == "Test description"
        assert suite.benchmarks == []

    def test_suite_add_benchmark(self):
        """Test adding benchmarks to suite."""
        # Arrange
        suite = BenchmarkSuite(name="Test Suite", description="Test description")
        benchmark1 = ConcreteBenchmark()
        benchmark2 = ConcreteBenchmark()

        # Act
        suite.add_benchmark(benchmark1)
        suite.add_benchmark(benchmark2)

        # Assert
        assert len(suite.benchmarks) == 2
        assert suite.benchmarks[0] == benchmark1
        assert suite.benchmarks[1] == benchmark2

    @pytest.mark.asyncio
    async def test_suite_run_all(self):
        """Test running all benchmarks in suite."""
        # Arrange
        suite = BenchmarkSuite(name="Test Suite", description="Test description")
        benchmark1 = ConcreteBenchmark()
        benchmark2 = ConcreteBenchmark()
        suite.add_benchmark(benchmark1)
        suite.add_benchmark(benchmark2)

        # Act
        results = await suite.run_all()

        # Assert
        assert len(results) == 2
        assert all(isinstance(r, BenchmarkResult) for r in results)
        assert benchmark1.setup_called
        assert benchmark1.teardown_called
        assert benchmark2.setup_called
        assert benchmark2.teardown_called


# ==============================================================================
# Test BenchmarkRunner
# ==============================================================================


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner class."""

    def test_runner_initialization(self, temp_output_dir: Path) -> None:
        """Test runner initialization."""
        # Arrange/Act
        runner = BenchmarkRunner(output_dir=temp_output_dir)

        # Assert
        assert runner.output_dir == temp_output_dir
        assert runner.output_dir.exists()
        assert runner.suites == []

    def test_runner_initialization_default_dir(self):
        """Test runner initialization with default output directory."""
        # Arrange/Act
        runner = BenchmarkRunner()

        # Assert
        assert runner.output_dir == Path("benchmark_results")
        assert runner.suites == []

    def test_runner_add_suite(self, temp_output_dir: Path) -> None:
        """Test adding suites to runner."""
        # Arrange
        runner = BenchmarkRunner(output_dir=temp_output_dir)
        suite1 = BenchmarkSuite(name="Suite 1", description="Test 1")
        suite2 = BenchmarkSuite(name="Suite 2", description="Test 2")

        # Act
        runner.add_suite(suite1)
        runner.add_suite(suite2)

        # Assert
        assert len(runner.suites) == 2
        assert runner.suites[0] == suite1
        assert runner.suites[1] == suite2

    @pytest.mark.asyncio
    async def test_runner_run_all(
        self, temp_output_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test running all suites."""
        # Arrange
        runner = BenchmarkRunner(output_dir=temp_output_dir)
        suite = BenchmarkSuite(name="Test Suite", description="Test description")
        benchmark = ConcreteBenchmark()
        suite.add_benchmark(benchmark)
        runner.add_suite(suite)

        # Act
        results = await runner.run_all()

        # Assert
        assert "Test Suite" in results
        assert len(results["Test Suite"]) == 1
        assert isinstance(results["Test Suite"][0], BenchmarkResult)

        # Assert - output was printed
        captured = capsys.readouterr()
        assert "Running benchmark suite: Test Suite" in captured.out
        assert "Concrete Test" in captured.out

    def test_runner_save_results(
        self, temp_output_dir: Path, sample_benchmark_result: BenchmarkResult
    ) -> None:
        """Test saving results to JSON."""
        # Arrange
        runner = BenchmarkRunner(output_dir=temp_output_dir)
        results = {"Test Suite": [sample_benchmark_result]}
        filename = "test_results.json"

        # Act
        runner.save_results(results, filename=filename)

        # Assert
        output_path = temp_output_dir / filename
        assert output_path.exists()

        with open(output_path) as f:
            saved_data = json.load(f)

        assert "Test Suite" in saved_data
        assert len(saved_data["Test Suite"]) == 1
        assert saved_data["Test Suite"][0]["name"] == "Test Benchmark"

    def test_runner_generate_markdown_report(
        self, temp_output_dir: Path, sample_benchmark_result: BenchmarkResult
    ) -> None:
        """Test generating markdown report."""
        # Arrange
        runner = BenchmarkRunner(output_dir=temp_output_dir)
        results = {"Test Suite": [sample_benchmark_result]}
        filename = "test_report.md"

        # Act
        runner.generate_markdown_report(results, filename=filename)

        # Assert
        output_path = temp_output_dir / filename
        assert output_path.exists()

        content = output_path.read_text()
        assert "# Performance Benchmark Report" in content
        assert "## Test Suite" in content
        assert "Test Benchmark" in content
        assert "100" in content  # iterations
        assert "Ops/sec" in content


# ==============================================================================
# Test Core Benchmarks
# ==============================================================================


class TestTokenCountingBenchmark:
    """Tests for TokenCountingBenchmark."""

    @pytest.mark.asyncio
    async def test_token_counting_benchmark_setup(self):
        """Test token counting benchmark setup."""
        # Arrange
        benchmark = TokenCountingBenchmark(content_size=100)

        # Act
        await benchmark.setup()

        # Assert
        assert benchmark.counter is not None
        assert benchmark.test_content != ""
        assert benchmark.test_content.count("\n") == 100

    @pytest.mark.asyncio
    async def test_token_counting_benchmark_run_iteration(self):
        """Test token counting benchmark iteration."""
        # Arrange
        benchmark = TokenCountingBenchmark(content_size=10)
        await benchmark.setup()

        # Act
        await benchmark.run_iteration()

        # Assert - no exception raised


class TestFileIOBenchmark:
    """Tests for FileIOBenchmark."""

    @pytest.mark.asyncio
    async def test_file_io_benchmark_setup(self):
        """Test file I/O benchmark setup."""
        # Arrange
        benchmark = FileIOBenchmark(num_files=5)

        # Act
        await benchmark.setup()

        # Assert
        assert benchmark.fs_manager is not None
        assert benchmark.temp_dir is not None
        assert benchmark.test_content != ""

        # Cleanup
        await benchmark.teardown()

    @pytest.mark.asyncio
    async def test_file_io_benchmark_teardown(self):
        """Test file I/O benchmark teardown."""
        # Arrange
        benchmark = FileIOBenchmark(num_files=5)
        await benchmark.setup()
        assert benchmark.temp_dir is not None
        temp_path = Path(benchmark.temp_dir.name)

        # Act
        await benchmark.teardown()

        # Assert - temp directory cleaned up
        assert not temp_path.exists()


class TestDependencyGraphBenchmark:
    """Tests for DependencyGraphBenchmark."""

    @pytest.mark.asyncio
    async def test_dependency_graph_benchmark_setup(self):
        """Test dependency graph benchmark setup."""
        # Arrange
        benchmark = DependencyGraphBenchmark(num_nodes=10)

        # Act
        await benchmark.setup()

        # Assert
        assert benchmark.graph is not None
        # Verify graph has nodes by checking dependencies were added
        from typing import cast

        graph_dict = benchmark.graph.to_dict()
        assert "nodes" in graph_dict
        nodes = cast(list[object], graph_dict["nodes"])
        assert len(nodes) > 0

    @pytest.mark.asyncio
    async def test_dependency_graph_benchmark_run_iteration(self):
        """Test dependency graph benchmark iteration."""
        # Arrange
        benchmark = DependencyGraphBenchmark(num_nodes=5)
        await benchmark.setup()

        # Act
        await benchmark.run_iteration()

        # Assert - no exception raised


class TestDependencyGraphToDictBenchmark:
    """Tests for DependencyGraphToDictBenchmark."""

    @pytest.mark.asyncio
    async def test_dependency_graph_to_dict_benchmark_setup(self):
        """Test graph to_dict benchmark setup."""
        # Arrange
        benchmark = DependencyGraphToDictBenchmark(num_nodes=10)

        # Act
        await benchmark.setup()

        # Assert
        assert benchmark.graph is not None

    @pytest.mark.asyncio
    async def test_dependency_graph_to_dict_benchmark_run_iteration(self):
        """Test graph to_dict benchmark iteration."""
        # Arrange
        benchmark = DependencyGraphToDictBenchmark(num_nodes=5)
        await benchmark.setup()

        # Act
        await benchmark.run_iteration()

        # Assert - no exception raised


class TestCreateCoreBenchmarkSuite:
    """Tests for create_core_benchmark_suite function."""

    def test_create_core_benchmark_suite(self):
        """Test creating core benchmark suite."""
        # Arrange/Act
        suite = create_core_benchmark_suite()

        # Assert
        assert suite.name == "Core Operations"
        assert suite.description != ""
        # 3 token + 3 file IO + 3 graph + 3 to_dict = 12 benchmarks
        assert len(suite.benchmarks) == 12


# ==============================================================================
# Test Analysis Benchmarks
# ==============================================================================


class TestPatternAnalysisBenchmark:
    """Tests for PatternAnalysisBenchmark."""

    @pytest.mark.asyncio
    async def test_pattern_analysis_benchmark_setup(self):
        """Test pattern analysis benchmark setup."""
        # Arrange
        benchmark = PatternAnalysisBenchmark(num_files=5)

        # Act
        await benchmark.setup()

        # Assert
        assert benchmark.analyzer is not None
        assert benchmark.temp_dir is not None

        # Cleanup
        await benchmark.teardown()

    @pytest.mark.asyncio
    async def test_pattern_analysis_benchmark_teardown(self):
        """Test pattern analysis benchmark teardown."""
        # Arrange
        benchmark = PatternAnalysisBenchmark(num_files=5)
        await benchmark.setup()
        assert benchmark.temp_dir is not None
        temp_path = Path(benchmark.temp_dir.name)

        # Act
        await benchmark.teardown()

        # Assert - temp directory cleaned up
        assert not temp_path.exists()


class TestStructureAnalysisBenchmark:
    """Tests for StructureAnalysisBenchmark."""

    @pytest.mark.asyncio
    async def test_structure_analysis_benchmark_setup(self):
        """Test structure analysis benchmark setup."""
        # Arrange
        benchmark = StructureAnalysisBenchmark(num_files=3)

        # Act
        await benchmark.setup()

        # Assert
        assert benchmark.analyzer is not None
        assert benchmark.temp_dir is not None
        assert benchmark.fs_manager is not None

        # Cleanup
        await benchmark.teardown()

    @pytest.mark.asyncio
    async def test_structure_analysis_benchmark_teardown(self):
        """Test structure analysis benchmark teardown."""
        # Arrange
        benchmark = StructureAnalysisBenchmark(num_files=3)
        await benchmark.setup()
        assert benchmark.temp_dir is not None
        temp_path = Path(benchmark.temp_dir.name)

        # Act
        await benchmark.teardown()

        # Assert - temp directory cleaned up
        assert not temp_path.exists()


class TestCoAccessPatternBenchmark:
    """Tests for CoAccessPatternBenchmark."""

    @pytest.mark.asyncio
    async def test_co_access_pattern_benchmark_setup(self):
        """Test co-access pattern benchmark setup."""
        # Arrange
        benchmark = CoAccessPatternBenchmark(num_files=10)

        # Act
        await benchmark.setup()

        # Assert
        assert benchmark.analyzer is not None
        assert benchmark.temp_dir is not None

        # Cleanup
        await benchmark.teardown()

    @pytest.mark.asyncio
    async def test_co_access_pattern_benchmark_teardown(self):
        """Test co-access pattern benchmark teardown."""
        # Arrange
        benchmark = CoAccessPatternBenchmark(num_files=10)
        await benchmark.setup()
        assert benchmark.temp_dir is not None
        temp_path = Path(benchmark.temp_dir.name)

        # Act
        await benchmark.teardown()

        # Assert - temp directory cleaned up
        assert not temp_path.exists()


class TestCreateAnalysisBenchmarkSuite:
    """Tests for create_analysis_benchmark_suite function."""

    def test_create_analysis_benchmark_suite(self):
        """Test creating analysis benchmark suite."""
        # Arrange/Act
        suite = create_analysis_benchmark_suite()

        # Assert
        assert suite.name == "Analysis Operations"
        assert suite.description != ""
        # 3 pattern + 3 structure + 3 co-access = 9 benchmarks
        assert len(suite.benchmarks) == 9


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestBenchmarkIntegration:
    """Integration tests for complete benchmark workflows."""

    @pytest.mark.asyncio
    async def test_complete_benchmark_workflow(self, temp_output_dir: Path) -> None:
        """Test complete workflow from benchmark creation to report generation."""
        # Arrange
        runner = BenchmarkRunner(output_dir=temp_output_dir)
        suite = BenchmarkSuite(name="Integration Test", description="Test suite")
        benchmark = ConcreteBenchmark()
        suite.add_benchmark(benchmark)
        runner.add_suite(suite)

        # Act
        results = await runner.run_all()
        runner.save_results(results, filename="integration_results.json")
        runner.generate_markdown_report(results, filename="integration_report.md")

        # Assert - results are valid
        assert "Integration Test" in results
        assert len(results["Integration Test"]) == 1

        # Assert - JSON file created
        json_path = temp_output_dir / "integration_results.json"
        assert json_path.exists()

        # Assert - Markdown report created
        md_path = temp_output_dir / "integration_report.md"
        assert md_path.exists()

    @pytest.mark.asyncio
    async def test_multiple_suites_workflow(self, temp_output_dir: Path) -> None:
        """Test workflow with multiple benchmark suites."""
        # Arrange
        runner = BenchmarkRunner(output_dir=temp_output_dir)

        suite1 = BenchmarkSuite(name="Suite 1", description="First suite")
        suite1.add_benchmark(ConcreteBenchmark())

        suite2 = BenchmarkSuite(name="Suite 2", description="Second suite")
        suite2.add_benchmark(ConcreteBenchmark())

        runner.add_suite(suite1)
        runner.add_suite(suite2)

        # Act
        results = await runner.run_all()

        # Assert
        assert len(results) == 2
        assert "Suite 1" in results
        assert "Suite 2" in results
        assert len(results["Suite 1"]) == 1
        assert len(results["Suite 2"]) == 1
