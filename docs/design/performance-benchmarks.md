# Performance Benchmarks

Phase 9.3 performance targets, benchmark coverage, and optimization notes.

## Phase 9.3 Targets

| Metric | Target | Notes |
|--------|--------|------|
| p95 latency | <200ms | Per-operation for hot paths |
| Memory usage | <50MB | Typical projects |
| Algorithm complexity | No O(n²) on large datasets | structure_detection uses O(n×k) window |
| Benchmarks | Documented | Run via `uv run python -m cortex.benchmarks.run_benchmarks` |

## Benchmark Suites

### Analysis Operations

Located in `src/cortex/benchmarks/analysis_benchmarks.py`.

#### Pattern Analysis

- Pattern analysis with 10, 20, 50 files
- Co-access pattern calculation with 20, 50, 100 files

#### Structure Analysis (Phase 9.3 Hot Paths)

- **Structure Analysis**: `analyze_file_organization` with 10, 20, 30, 50 files
- **Anti-Pattern Detection**: `detect_anti_patterns` with 20 files
- **Complexity Metrics**: `measure_complexity_metrics` with 20 files
- **Dependency Chains**: `find_dependency_chains` with 20 files

### Core Operations

Located in `src/cortex/benchmarks/core_benchmarks.py`:

- Token counting
- File I/O
- Dependency graph operations

## Running Benchmarks

**Lightweight suite** (no tiktoken/network, fast):

```bash
uv run .cortex/synapse/scripts/python/run_benchmarks.py
```

**Analysis suite** (includes Phase 9.3 hot paths; may load tiktoken):

```python
from pathlib import Path
from cortex.benchmarks.analysis_benchmarks import create_analysis_benchmark_suite
from cortex.benchmarks.framework import BenchmarkRunner
import asyncio

async def run():
    runner = BenchmarkRunner(output_dir=Path(".cortex/benchmark_results"))
    runner.add_suite(create_analysis_benchmark_suite())
    return await runner.run_all()

asyncio.run(run())
```

Or run via `pytest tests/unit/test_benchmarks.py::TestCreateAnalysisBenchmarkSuite`.

Results are saved to `.cortex/benchmark_results/` (or temp dir in tests) with JSON and Markdown report.

## Optimization Notes

### structure_detection.detect_similar_filenames

- **Original**: O(n²) pairwise comparison
- **Current**: O(n×k) window approach (k=10) by sorting names and comparing adjacent window
- Reduces comparisons for typical memory bank sizes (<100 files)

### structure_metrics.find_all_chains

- DFS from each file; worst case O(V×(V+E))
- Acceptable for sparse graphs; chain length capped (default 10)

### Token Counting

- `TokenCounter` uses content-hash cache (`count_tokens_with_cache`)
- Tiktoken encoding cached; fallback to word estimation if unavailable

### Cache Architecture (Phase 9.3 Advanced Caching)

| Component | Location | Eviction | Notes |
|-----------|----------|----------|-------|
| TTLCache | `core/cache.py` | Time-based (default 5 min) | `cleanup_expired()` for proactive eviction |
| LRUCache | `core/cache.py` | Size-based (default 100) | Least recently used evicted when full |
| AdvancedCacheManager | `core/advanced_cache.py` | Both TTL + LRU | Two-layer: TTL for recency, LRU for frequency |
| CacheWarmer | `core/cache_warming.py` | N/A | Pre-populates on startup (mandatory, hot path, dependency, recent) |

**Eviction policy:**

- TTL entries removed on get (lazy) or via `cleanup_expired()` (proactive)
- LRU evicts least recently used when at `max_size`
- `clear()` counts evictions before clearing both layers

**Prefetching:** `_record_access` infers `co_accessed_files` from keys accessed within 60s; `prefetch_related` loads those when the primary key is accessed.
