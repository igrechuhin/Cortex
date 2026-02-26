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

### Async Optimization (Phase 9.3 Task 3)

**When to use `asyncio.gather` vs `asyncio.TaskGroup`:**

- **`asyncio.gather`**: Use when tasks are independent and you want partial results (e.g. session brief components: health, project name, handoff, concurrency). Continues even if one task fails (with `return_exceptions=True`) or fails fast (default). Best when all results are needed and failures are handled per-task.
- **`asyncio.TaskGroup`** (Python 3.11+): Use for structured concurrency where you want all siblings cancelled if one raises. Main process uses anyio TaskGroup for stdio-to-HTTP forwarding. Prefer gather for tool hot paths where resilience (partial success) matters.

**Parallelized hot paths:**

- `session_brief._load_brief_async`: health, project name, handoff, concurrency loaded in parallel via `gather`
- `session_brief._load_concurrency_info`: concurrent sessions and locked tasks loaded in parallel
- `session_brief.load_memory_bank_files`: activeContext.md and roadmap.md loaded in parallel

**Connection pooling:** N/A for current architecture. Cortex MCP is a server that receives requests; it does not make outgoing HTTP client connections in hot paths. Subprocess tools (e.g. ruff, black) are spawned per-request; pooling would apply only if we introduced a persistent client connection pool (e.g. for external APIs).

### Memory Optimization (Phase 9.3 Task 4)

**Target:** <50MB for typical projects (7 memory bank files, ~100KB total content).

**Known allocations:**

| Component | Location | Typical Size | Notes |
|-----------|----------|--------------|-------|
| `read_all_files_for_context_loading` | phase4_context_operations_content | ~70KB (7 files × 10KB) | `dict[str, str]` for content, `dict[str, ModelDict]` for metadata |
| `read_all_files_for_loading` | progressive_loader_relevance | Same | Used by progressive loader |
| MetadataIndex | core/metadata_index | ~50–200KB | Index + dependency graph for typical project |
| LearningDataManager | refactoring/learning_data_manager | Variable | feedback_records, learned_patterns, user_preferences |
| AccessLog (PatternAnalyzer) | analysis/pattern_analyzer | ~10–50KB | Per-project access log |

**Streaming opportunities:** For typical projects (≤20 memory bank files), in-memory loading is acceptable. For very large projects (100+ files), consider streaming or chunked loading; this is deferred until a concrete use case arises.

**Memory benchmarks:** Run via `create_memory_benchmark_suite()` — measures peak memory for context-load-style and index-style operations using `tracemalloc` (stdlib). Suite includes:

- Context load memory (7 files, 20 files)
- Index memory (50 nodes, 100 nodes)

```python
from cortex.benchmarks.memory_benchmarks import create_memory_benchmark_suite
from cortex.benchmarks.framework import BenchmarkRunner
import asyncio

async def run():
    runner = BenchmarkRunner(output_dir=Path(".cortex/benchmark_results"))
    runner.add_suite(create_memory_benchmark_suite())
    return await runner.run_all()

asyncio.run(run())
```

Results include `peak_memory_mb` in each benchmark's metadata (target: <50MB).
