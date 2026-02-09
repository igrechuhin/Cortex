# Investigation: Commit Pipeline “Hanged?” and “Didn’t Finish”

**Date:** 2026-02-08  
**Transcripts:**  

- First run (user asked “hanged?”): `4348b303-cd4a-4483-95e5-9d9c753dee57.txt`  
- Second run (agent reported “didn’t finish”): `18b4a58b-a2b3-40b7-84b2-54df891c398f.txt`

---

## Summary

Two separate issues explain what you saw:

1. **“Hanged?” (first run):** The agent called `execute_pre_commit_checks(checks=["fix_errors","format"])`. No progress is sent for fix_errors/format, so the UI can look frozen for 1–3+ minutes until the tool returns. The transcript also shows no `[Tool result]` before your message—so either the call was still in progress or the response was slow/lost.
2. **“Didn’t finish” (second run):** The test step cannot complete because the **MCP tool** is hard-limited to **600 seconds**. The full test suite with current timeouts needs **~900 seconds**, so the tool always hits the 600s limit and returns a timeout error. The pipeline correctly reports that it didn’t finish.

---

## Issue 1: Perceived hang (first transcript)

### What happened (Issue 1)

- The agent invoked:
  - `execute_pre_commit_checks(checks=["fix_errors","format"], test_timeout=300, ...)`  
- The transcript ends with `[Tool result] mcp_cortex_execute_pre_commit_checks` **empty** (no body), then your message: “hanged?”

### Root cause (Issue 1)

1. **No progress for fix_errors/format**  
   - Progress reporting in `execute_pre_commit_checks` is only used for the **tests** check (test count updates).  
   - For **fix_errors** and **format**, the pipeline runs ruff/black/isort on the whole codebase and does **not** send any progress.  
   - So for 1–3+ minutes the client sees no update and it can look like a hang.

2. **Possible MCP/connection behavior**  
   - If the tool takes longer than the client’s idle/connection timeout, the connection might drop and the response may never be delivered, which would also look like a hang.

### Evidence (code) (Issue 1)

- `src/cortex/core/mcp_stability.py`: `_TOOLS_WITH_OWN_PROGRESS` includes `execute_pre_commit_checks`, so the generic time-based progress loop is **disabled** for this tool (to avoid mixing with the tool’s own progress).
- `src/cortex/tools/pre_commit_tools.py` / `pre_commit_pipeline.py`: The progress callback is only passed into the **tests** path (`_make_test_progress_callback`). Fix_errors and format run with no progress reporting.

### Recommendations (Issue 1)

1. **Short term:** When running only fix_errors/format, expect 1–3+ minutes with no progress; avoid assuming a hang before that.
2. **Code change:** Add progress reporting for fix_errors and format (e.g. “Running fix_errors…”, “Running format…”, or per-check completion) so the client shows activity and the commit step doesn’t appear to hang.

---

## Issue 2: Test step “didn’t finish” (second transcript)

### What happened (Issue 2)

- The agent ran the commit pipeline and reached Step 4 (tests).
- Multiple calls to `execute_pre_commit_checks(checks=["tests"], test_timeout=300|600, ...)` returned:
  - **“exceeded timeout of 600.0s”**
- The agent correctly concluded that the pipeline **didn’t finish** because the test step never completes successfully within the tool’s limit.

### Root cause (Issue 2)

- **MCP wrapper timeout:** `execute_pre_commit_checks` is decorated with  
  `@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)`.
- In `src/cortex/core/constants.py`:  
  `MCP_TOOL_TIMEOUT_VERY_COMPLEX = 600.0` (10 minutes).
- So the **entire** tool call (including running pytest) is capped at **600 seconds**. The `test_timeout` argument only controls the **pytest subprocess** timeout; it does not extend the MCP wrapper.
- With `pytest.ini` `session_timeout = 900` and a large suite (3600+ tests, many with 60s per-test timeouts), the full run needs **~900 seconds**. The wrapper therefore cancels the tool at 600s every time.

### Evidence (code) (Issue 2)

- `src/cortex/tools/pre_commit_tools.py` line 227:  
  `@mcp_tool_wrapper(timeout=MCP_TOOL_TIMEOUT_VERY_COMPLEX)`
- `src/cortex/core/constants.py` line 94:  
  `MCP_TOOL_TIMEOUT_VERY_COMPLEX = 600.0`
- `docs/mcp-tool-timeouts.md`: Very complex operations documented as 600s.

### Recommendations (Issue 2)

1. **Option A – Increase tool timeout for this tool only**  
   - Introduce a constant, e.g. `MCP_TOOL_TIMEOUT_PRE_COMMIT_TESTS = 960` (16 minutes), and use it for `execute_pre_commit_checks` so the full test run can complete. Document in `docs/mcp-tool-timeouts.md`.

2. **Option B – Keep 600s and accept partial runs**  
   - Keep the 600s limit; run tests in CI with a longer timeout. The commit prompt would need to allow “tests run in CI only” or “partial test run within 600s” and not require full local completion for Step 4.

3. **Option C – Shorten test run so it fits in 600s**  
   - Reduce `session_timeout` and/or per-test timeouts so the full suite finishes in under 600s (e.g. faster timeouts, or running a subset in the commit pipeline and full suite in CI).

---

## Summary table

| Observation        | Transcript   | Cause                                                                 | Fix direction                                      |
|-------------------|-------------|-----------------------------------------------------------------------|----------------------------------------------------|
| “Hanged?”         | First (4348…) | No progress for fix_errors/format; long run with no UI feedback       | Add progress for fix_errors/format                  |
| “Didn’t finish”   | Second (18b4…) | MCP wrapper 600s &lt; full test run (~900s)                          | Raise timeout for this tool, or shorten test run   |

---

## Files referenced

- `src/cortex/core/constants.py` – `MCP_TOOL_TIMEOUT_VERY_COMPLEX = 600.0`
- `src/cortex/core/mcp_stability.py` – `_TOOLS_WITH_OWN_PROGRESS`, progress loop
- `src/cortex/tools/pre_commit_tools.py` – `execute_pre_commit_checks`, progress callback only for tests
- `src/cortex/tools/pre_commit_pipeline.py` – check execution, no progress for fix_errors/format
- `docs/mcp-tool-timeouts.md` – timeout categories
