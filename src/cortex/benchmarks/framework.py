"""Benchmark framework infrastructure.

Provides core classes and utilities for defining, running, and reporting
performance benchmarks.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path

from cortex.core.models import JsonValue, ModelDict


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    iterations: int
    total_time: float
    min_time: float
    max_time: float
    mean_time: float
    median_time: float
    std_dev: float
    p95_time: float
    p99_time: float
    metadata: dict[str, JsonValue] = field(
        default_factory=lambda: dict[str, JsonValue]()
    )

    @property
    def ops_per_second(self) -> float:
        """Calculate operations per second."""
        return self.iterations / self.total_time if self.total_time > 0 else 0.0

    def to_dict(self) -> ModelDict:
        """Convert result to dictionary."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time": self.total_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "mean_time": self.mean_time,
            "median_time": self.median_time,
            "std_dev": self.std_dev,
            "p95_time": self.p95_time,
            "p99_time": self.p99_time,
            "ops_per_second": self.ops_per_second,
            "metadata": self.metadata,
        }


class Benchmark:
    """Base class for performance benchmarks."""

    def __init__(
        self,
        name: str,
        description: str,
        iterations: int = 100,
        warmup_iterations: int = 10,
    ):
        """Initialize benchmark.

        Args:
            name: Benchmark name
            description: Benchmark description
            iterations: Number of iterations to run
            warmup_iterations: Number of warmup iterations
        """
        self.name = name
        self.description = description
        self.iterations = iterations
        self.warmup_iterations = warmup_iterations

    async def setup(self) -> None:
        """Set up benchmark environment (called once before all runs)."""
        pass

    async def teardown(self) -> None:
        """Clean up benchmark environment (called once after all runs)."""
        pass

    async def before_each(self) -> None:
        """Set up before each iteration."""
        pass

    async def after_each(self) -> None:
        """Clean up after each iteration."""
        pass

    async def run_iteration(self) -> None:
        """Run a single benchmark iteration (must be implemented)."""
        raise NotImplementedError("Subclasses must implement run_iteration")

    async def run(self) -> BenchmarkResult:
        """Run the benchmark and return results."""
        await self.setup()
        await self._run_warmup_phase()
        times, total_time = await self._run_measurement_phase()
        await self.teardown()
        stats = self._calculate_statistics(times)

        return BenchmarkResult(
            name=self.name,
            iterations=self.iterations,
            total_time=total_time,
            min_time=stats["min"],
            max_time=stats["max"],
            mean_time=stats["mean"],
            median_time=stats["median"],
            std_dev=stats["std_dev"],
            p95_time=stats["p95"],
            p99_time=stats["p99"],
            metadata={"description": self.description},
        )

    async def _run_warmup_phase(self) -> None:
        """Run warmup phase."""
        for _ in range(self.warmup_iterations):
            await self.before_each()
            await self.run_iteration()
            await self.after_each()

    async def _run_measurement_phase(
        self,
    ) -> tuple[list[float], float]:
        """Run measurement phase and return times and total time."""
        times: list[float] = []
        total_start = time.perf_counter()
        for _ in range(self.iterations):
            await self.before_each()
            start = time.perf_counter()
            await self.run_iteration()
            end = time.perf_counter()
            await self.after_each()
            times.append(end - start)
        total_end = time.perf_counter()
        return times, total_end - total_start

    def _calculate_statistics(self, times: list[float]) -> dict[str, float]:
        """Calculate benchmark statistics."""
        sorted_times = sorted(times)
        mean_time = sum(times) / len(times)
        median_time = sorted_times[len(sorted_times) // 2]
        p95_index = int(len(sorted_times) * 0.95)
        p99_index = int(len(sorted_times) * 0.99)
        variance = sum((t - mean_time) ** 2 for t in times) / len(times)
        std_dev = variance**0.5
        return {
            "min": min(times),
            "max": max(times),
            "mean": mean_time,
            "median": median_time,
            "std_dev": std_dev,
            "p95": sorted_times[p95_index],
            "p99": sorted_times[p99_index],
        }


class BenchmarkSuite:
    """Collection of related benchmarks."""

    def __init__(self, name: str, description: str):
        """Initialize benchmark suite.

        Args:
            name: Suite name
            description: Suite description
        """
        self.name = name
        self.description = description
        self.benchmarks: list[Benchmark] = []

    def add_benchmark(self, benchmark: Benchmark) -> None:
        """Add a benchmark to the suite."""
        self.benchmarks.append(benchmark)

    async def run_all(self) -> list[BenchmarkResult]:
        """Run all benchmarks in the suite."""
        results: list[BenchmarkResult] = []
        for benchmark in self.benchmarks:
            result = await benchmark.run()
            results.append(result)
        return results


class BenchmarkRunner:
    """Runner for executing benchmark suites and generating reports."""

    def __init__(self, output_dir: Path | None = None):
        """Initialize benchmark runner.

        Args:
            output_dir: Directory for benchmark results
        """
        self.output_dir = output_dir or Path("benchmark_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.suites: list[BenchmarkSuite] = []

    def add_suite(self, suite: BenchmarkSuite) -> None:
        """Add a benchmark suite to the runner."""
        self.suites.append(suite)

    async def run_all(self) -> dict[str, list[BenchmarkResult]]:
        """Run all benchmark suites."""
        all_results: dict[str, list[BenchmarkResult]] = {}

        for suite in self.suites:
            print(f"\nRunning benchmark suite: {suite.name}")
            print(f"Description: {suite.description}")
            print("=" * 80)

            results = await suite.run_all()
            all_results[suite.name] = results

            # Print results
            for result in results:
                print(f"\n{result.name}:")
                print(f"  Iterations: {result.iterations}")
                print(f"  Total time: {result.total_time:.3f}s")
                print(f"  Mean time: {result.mean_time * 1000:.2f}ms")
                print(f"  Median time: {result.median_time * 1000:.2f}ms")
                print(f"  Min time: {result.min_time * 1000:.2f}ms")
                print(f"  Max time: {result.max_time * 1000:.2f}ms")
                print(f"  Std dev: {result.std_dev * 1000:.2f}ms")
                print(f"  P95 time: {result.p95_time * 1000:.2f}ms")
                print(f"  P99 time: {result.p99_time * 1000:.2f}ms")
                print(f"  Ops/sec: {result.ops_per_second:.2f}")

        return all_results

    def save_results(
        self, results: dict[str, list[BenchmarkResult]], filename: str = "results.json"
    ) -> None:
        """Save benchmark results to JSON file."""
        import json

        output_path = self.output_dir / filename

        results_dict = {
            suite_name: [result.to_dict() for result in suite_results]
            for suite_name, suite_results in results.items()
        }

        with open(output_path, "w") as f:
            json.dump(results_dict, f, indent=2)

        print(f"\nResults saved to: {output_path}")

    def generate_markdown_report(
        self,
        results: dict[str, list[BenchmarkResult]],
        filename: str = "benchmark_report.md",
    ) -> None:
        """Generate markdown report from benchmark results."""
        output_path = self.output_dir / filename

        with open(output_path, "w") as f:
            _ = f.write("# Performance Benchmark Report\n\n")
            _ = f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for suite_name, suite_results in results.items():
                _ = f.write(f"## {suite_name}\n\n")

                # Create table
                _ = f.write("| Benchmark | Iterations | Mean (ms) | Median (ms) | ")
                _ = f.write("P95 (ms) | P99 (ms) | Ops/sec |\n")
                _ = f.write("|-----------|------------|-----------|-------------|")
                _ = f.write("----------|----------|----------|\n")

                for result in suite_results:
                    _ = f.write(f"| {result.name} | ")
                    _ = f.write(f"{result.iterations} | ")
                    _ = f.write(f"{result.mean_time * 1000:.2f} | ")
                    _ = f.write(f"{result.median_time * 1000:.2f} | ")
                    _ = f.write(f"{result.p95_time * 1000:.2f} | ")
                    _ = f.write(f"{result.p99_time * 1000:.2f} | ")
                    _ = f.write(f"{result.ops_per_second:.2f} |\n")

                _ = f.write("\n")

        print(f"Markdown report saved to: {output_path}")
