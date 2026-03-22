---
title: "Profile and verify performance of context loading and preflight hot paths"
component: tools/context
work_type: quality
status: PENDING
priority: medium
created: 2026-03-22
depends_on: []
---

## Goal

Move the Performance score from 7/10 (assumed-acceptable) to 8/10 (verified-fast)
by profiling the two paths reviewers consistently mark as "no data": context loading
(`cortex://context` resource) and the preflight registry probe. Produce concrete
evidence (timing figures or benchmark assertions) that these paths meet the
`<100ms` target from `productContext.md`.

## Context

All three 2026-03-22 reviews score Performance at 7 with the same reason: "no
profiling data; no known hot paths, but unverified." The `productContext.md` goal is
`<100ms for context loading for typical projects`. No benchmark or timing test
enforces this today.

Key paths to profile:

- `cortex://context` resource → `load_context()` in
  `src/cortex/tools/context/load_operations.py` (and its metadata helpers).
- `registry_reachable()` in `src/cortex/cli/preflight.py` — single HTTP round-trip
  with 10s timeout; already bounded, but not asserted.
- Token-counting via `tiktoken` in `src/cortex/core/tiktoken_cache.py` — used in
  every context load; cache hit vs miss latency unknown.

## Implementation Steps

### Step 1: Measure baseline for context loading

Read `src/cortex/tools/context/load_operations.py` and its imports to identify the
call graph for `load_context()`. Use `pytest-benchmark` or a simple
`time.perf_counter()` fixture to measure wall time for a representative memory bank
(use the Cortex `.cortex/memory-bank/` itself as the fixture data).

**Verification checklist:**

- Locate `load_context` entry point and its callers.
- Identify which sub-steps dominate: file I/O, tiktoken encoding, strategy selection.
- Record baseline median time.

### Step 2: Measure tiktoken cache hit/miss latency

Read `src/cortex/core/tiktoken_cache.py`. Write a targeted microbenchmark (or extend
an existing test) that measures:

- Cold (cache miss) token count for a 5,000-token document.
- Warm (cache hit) token count for the same document.

Assert warm path is `< 5ms`.

**Verification checklist:**

- Test in `tests/unit/test_tiktoken_cache_perf.py` (create if missing).
- Uses `time.perf_counter()` or `pytest-benchmark`; not `time.sleep()`.
- Asserts warm-path latency, not just cold.

### Step 3: Write a timing regression test for context loading

Add `tests/unit/test_context_load_perf.py`:

- Load context from the real `.cortex/memory-bank/` (or a small fixture copy).
- Assert median wall time `< 100ms` for the default token budget.
- Skip if running in CI without the memory bank (use `pytest.importorskip` or
  `@pytest.mark.skipif` with a clear reason + `see: productContext.md#success-metrics`).

**Verification checklist:**

- Test name: `test_context_load_meets_100ms_target`.
- AAA pattern with explicit Arrange (fixture), Act (`load_context()`), Assert (timing).
- Skip reason references ticket/spec if memory bank is absent.

### Step 4: Fix any discovered bottleneck

If Step 1 or 2 reveals a path exceeding its target:

- If tiktoken cold path dominates: ensure the cache is warmed at server start in
  `src/cortex/setup/server.py`.
- If file I/O dominates: confirm reads use `aiofiles` (async); if not, migrate.
- If strategy selection dominates: profile `src/cortex/optimization/` and apply
  `@lru_cache` to pure deterministic helpers.

**Verification checklist:**

- Re-run the timing test after any fix.
- `run_quality_gate()` passes (no regressions).

### Step 5: Document results

Add a `## Performance baselines` section to `docs/architecture/tool-usage-tracking.md`
(or a new `docs/architecture/performance-baselines.md`) with the measured figures and
the 100ms target. Link from `productContext.md` success metrics.

**Verification checklist:**

- Doc section exists with actual numbers (not "TBD").
- `run_docs_gate()` passes.

## Dependencies

- No code-functionality changes required if paths already meet targets (Step 5 alone
  closes the gap).
- If bottlenecks are found, fixes are scoped to `tiktoken_cache.py` or
  `load_operations.py` — no public API changes.

## Success Criteria

1. At least one timing assertion exists in the test suite covering context loading.
2. Measured median context-load time is `< 100ms` for the Cortex memory bank.
3. tiktoken warm-path assertion passes.
4. Performance metric has concrete evidence in the next review (not "assumed").
5. `run_quality_gate()` passes with no coverage regression.

## Testing Strategy (95% coverage target)

- `tests/unit/test_tiktoken_cache_perf.py`: 2 tests (cold, warm).
- `tests/unit/test_context_load_perf.py`: 1 test with skip guard for CI.
- No new production code unless a bottleneck is found; coverage impact minimal.
