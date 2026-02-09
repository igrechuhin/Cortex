# Why Tests Are Slow and Why the Commit Pipeline Didn’t Increase Coverage

**Date:** 2026-02-08

---

## 1. Why do these tests run so slowly?

The slowest tests are slow **by design**: they exercise retries, timeouts, and backoff, so they include real sleeps.

### `test_rollback_file_version_error_handling` (3.02 s)

**What it does:** Patches `_execute_rollback` to raise `RuntimeError("Test error")` and calls `rollback_file_version` (an MCP tool). It asserts that the tool returns an error and that the error is wrapped as `ConnectionError`.

**Why it’s slow:** The tool runs under `with_mcp_stability`, which treats **all `RuntimeError`** as connection-related (see `_is_connection_error` in `mcp_stability.py`, which includes `RuntimeError` for MCP connection closure). So:

- Attempt 1: `RuntimeError` → connection retry path → **sleep(1.0 × 1) = 1 s**
- Attempt 2: `RuntimeError` → connection retry path → **sleep(1.0 × 2) = 2 s**
- Attempt 3: raise final `ConnectionError`

Total sleep is **1 + 2 = 3 s** (`MCP_CONNECTION_RETRY_DELAY_SECONDS = 1.0`, delay = `delay * attempt`). The ~3.02 s is that retry delay, plus a tiny bit of work and `check_connection_health()` between attempts.

**Constants:** `src/cortex/core/constants.py`:  
`MCP_CONNECTION_RETRY_ATTEMPTS = 3`, `MCP_CONNECTION_RETRY_DELAY_SECONDS = 1.0`  
`src/cortex/core/mcp_stability.py`: `await asyncio.sleep(MCP_CONNECTION_RETRY_DELAY_SECONDS * attempt)` (line 237).

---

### Other slow tests (same idea)

| Test | Duration | Cause |
|------|----------|--------|
| `test_max_retries_exhausted` / `test_connection_error_causes_retry` | ~3 s | Same MCP retry path: 1 s + 2 s sleep between three attempts. |
| `test_load_tiktoken_handles_network_unavailable_gracefully` | 2.01 s | Token counter retry: one failed attempt then **retry_delay = 2.0 * (2^0) = 2 s** before giving up (`token_counter.py` ~151, 189). |
| `test_retry_async_exhausts_retries` | 1.66 s | `retry_async` with exponential backoff: 3 attempts, delays ~0.5 s and ~1 s (`retry.py` backoff + sleep). |
| `test_decorator_enforces_timeout` / `test_timeout_error_message_is_clear` / `test_slow_operation_times_out` | 1.51 s | They run `slow_operation(delay=timeout+0.5)` with `timeout=0.5`, so **asyncio.sleep(1.0)** to trigger the timeout. |
| `test_suggest_refactoring_consolidation` | 1.43 s | Real work: calls refactoring/suggest logic (no intentional sleep). |
| `test_get_from_lru_cache_when_ttl_expired` | 1.11 s | Likely TTL/sleep or cache expiry delay. |

So: the **~3 s** tests are MCP retry sleeps; the **~2 s** one is token-counter retry delay; the **~1.5 s** ones are timeout or backoff sleeps; the rest are a mix of real work and small delays.

---

## 2. Why didn’t the commit pipeline increase coverage?

The commit pipeline **never got a successful test run** in the run you’re looking at, so it never reached the step where it would add tests to raise coverage.

- **Step 4 (tests)** is run via `execute_pre_commit_checks(checks=["tests"], ...)`.
- That tool is wrapped with **`@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)`** = **600 s**.
- In that session, the **full test run took longer than 600 s** (e.g. different load, or `session_timeout=900` and many tests with 60 s each). So the MCP wrapper **killed the tool** and returned “exceeded timeout of 600.0s”.
- The pipeline therefore **never** saw a successful Step 4 result or a coverage value. It correctly reported that the pipeline “didn’t finish” and blocked commit.
- The instructions say: if coverage &lt; 90%, add tests and re-run in the same run until ≥ 90%. That only works **after** a successful test run that reports coverage. Because the test step kept timing out, the agent never got to the “add tests and re-run” loop, so it **could not** increase coverage in that run.

So: **coverage wasn’t increased because the test step never completed inside the 600 s limit**, not because the pipeline chose to skip coverage fixes.

---

## Optional: Making the slow tests faster

If you want to shorten the ~3 s tests without changing production retry behavior:

- **Option A:** In tests only, mock or bypass the retry layer (e.g. patch `_handle_connection_error` / `asyncio.sleep` so no real sleep runs), and assert that the right exception is raised and that retries are attempted.
- **Option B:** Reduce delay in tests via env or constant (e.g. a test-only `MCP_CONNECTION_RETRY_DELAY_SECONDS = 0.01`) so the test still exercises retry count and error wrapping with minimal wait.

That would bring the slowest tests down to well under a second while keeping the “why” (retries and timeouts) intact.
