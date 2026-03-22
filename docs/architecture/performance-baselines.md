# Performance baselines

**Status**: Evidence-backed (regression tests + sample measurement)  
**Created**: 2026-03-22

## Purpose

The product goal in [productContext.md](../../.cortex/memory-bank/productContext.md) calls for **context loading under 100ms** for typical projects. This page records how that goal is enforced and gives **concrete latency figures** from a representative local run so reviews are not limited to “assumed acceptable.”

## Targets

| Path | Target | Enforcement |
| --- | --- | --- |
| `load_context_impl` (Memory Bank → assembled context) | Median wall time **&lt; 100ms** after warmup | `tests/unit/test_context_load_perf.py::test_context_load_meets_100ms_target` |
| `TokenCounter.count_tokens_with_cache` (warm hash hit, ~5k-token body) | Median wall time **&lt; 5ms** | `tests/unit/test_tiktoken_cache_perf.py::test_token_counter_warm_cache_median_under_5ms` |

Warmup for the context test performs one load before sampling so the first-call cold effects (tiktoken, caches) do not dominate the median.

## Sample measurement (maintainer laptop, not a SLA)

One **uncommitted** spot check on **2026-03-22** on **macOS**, **Python 3.13**, repo root `/Users/i.grechukhin/Repo/Cortex`, using the same parameters as `test_context_load_meets_100ms_target` (token budget 50_000, `dependency_aware`, seven post-warmup samples):

- **Context load median**: ~**5.5ms**
- **Tiktoken warm-cache median** (same ~5k-token document as the unit test, 100 samples): ~**0.08µs** (hash-cache hit; dominated by timer resolution and in-process overhead)

Absolute milliseconds **will vary** by CPU, disk, and repository size. The **unit tests above** are the contract: they fail CI/local runs when medians cross the published thresholds.

## Related code

- Context assembly: `src/cortex/tools/context/load_operations.py` (`load_context_impl`)
- Token counting + cache: `src/cortex/core/tiktoken_cache.py`, `src/cortex/core/token_counter.py`

## Preflight registry probe

`registry_reachable()` in `src/cortex/cli/preflight.py` uses a single HTTP round-trip with a **10s** upper bound. It is not on the same sub-100ms path as in-process context loading; operators should treat it as a connectivity check, not a latency benchmark.
