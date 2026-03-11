# Phase: Investigate execute_pre_commit_checks MCP Tool Failure

**Status**: IN_PROGRESS
**Priority**: ASAP (Blocker)
**Created**: 2026-03-10
**Target Completion**: 2026-03-10

## Goal

Investigate and fix MCP tool failure that occurred during commit procedure execution.

## Context

**Problem**: The `execute_pre_commit_checks` MCP tool fails and/or hangs during the commit pipeline (Phase A and Step 12), blocking commits in Cursor.

**Observed behavior and timeline**:

- The commit prompt calls `execute_pre_commit_checks(phase="A", ...)` and expects a single long-running call that returns results.
- In practice, the LLM agent often issues **two calls in rapid succession** (e.g. at 13:31:40 and 13:31:42), because:
  - The first call returns quickly with a detached/polling-style response that the agent misinterprets as incomplete or failed.
  - The prompt was not explicit about calling the tool exactly once and waiting.
- The Cortex MCP stability layer initially treated `execute_pre_commit_checks` as a **long-running serialized tool** (via `long_running_tools_serialized`), so:
  - Call 1 acquired the long-running semaphore, spawned the detached worker process, and began polling.
  - Call 2 waited up to `LONG_RUNNING_SEMAPHORE_WAIT_SECONDS` (600s) for the semaphore, effectively blocking for minutes and eventually raising a `RuntimeError`:
    - `Another long-running tool is in progress (e.g. execute_pre_commit_checks or fix_markdown_lint). Please wait for it to finish (up to 10 minutes) and retry. If running the commit pipeline, ensure Phase A has completed before Step 12; close other tabs or agents that may be running long-running Cortex tools.`
- While the detached worker was still running, the MCP connection to Cursor **timed out after ~3–4 minutes**. The agent saw:
  - `-32000: Connection closed` or the above `RuntimeError`.
  - Retrying the commit pipeline re-triggered the same pattern.

**Detached pipeline architecture**:

- `execute_pre_commit_checks` uses a **detached worker model** implemented in `pre_commit_detached.py`:
  - `DETACHED_ENABLED` is controlled by `CORTEX_DETACHED_PIPELINE` (defaults to `"1"`, i.e. detached enabled).
  - `run_checks_detached`:
    - Computes an `args_hash` from checks, timeout, coverage threshold, strict mode, and markdown flag.
    - Uses `find_existing_result(project_root, args_hash)` to read a JSON result file under `.cortex/.session/`.
    - If a **fresh completed** result exists, `_cached_detached_result` returns the cached `result` immediately.
    - Otherwise, it spawns `pre_commit_worker` as a detached subprocess, writing:
      - A result JSON file: `pre_commit_result_{args_hash}.json`
      - A worker log file: `pre_commit_worker_{args_hash}.log`
    - It then polls the result file for up to 900 seconds with heartbeats via `report_progress_safe`.
- The worker itself runs the existing pre-commit pipeline:
  - Uses language adapters and `run_checks_pipeline` to invoke format, type check, quality, tests, etc.
  - Produces structured `PreCommitResult` data that gets wrapped into the detached result JSON.

**Large output path and Cursor constraints**:

- The full, detailed output and logs are **not returned inline** to Cursor:
  - They are written to `.cortex/.session/pre_commit_worker_{args_hash}.log` and `pre_commit_result_{args_hash}.json`.
  - The MCP response is structured JSON but may also include references to temporary paths (e.g. under `.cursor/.../agent-tools/`), which Cursor’s agent cannot read directly.
- Cursor’s LLM agent:
  - Cannot safely read arbitrary `.cursor/.../agent-tools/` paths.
  - Needs to rely solely on the JSON payload returned by the MCP tool, not on paths embedded in that payload.

**Interaction with MCP stability semaphores**:

- The long-running error message comes from `mcp_stability_semaphores.py` / `mcp_stability_config.py`:
  - `LONG_RUNNING_SEMAPHORE_WAIT_SECONDS = 600.0` and `LONG_RUNNING_SEMAPHORE_MAX_HOLD_SECONDS = 600.0`.
  - `_LONG_RUNNING_TOOLS_SERIALIZED` originally included `{"execute_pre_commit_checks", "fix_markdown_lint"}`.
  - `execute_pre_commit_checks` was therefore serialized at the MCP layer:
    - Only one such tool call could hold the long-running semaphore at a time.
    - A second call waited for up to 10 minutes (including a short retry), then raised `RuntimeError` if still busy.

**Root cause summary**:

- The **detached worker model itself is sound** for Cursor (survives MCP disconnects, avoids streaming huge results inline).
- The **failure is a compound interaction** of:
  1. The commit prompt not being explicit about:
     - Calling `execute_pre_commit_checks` exactly once for Phase A and Step 12.
     - Treating "detached worker started / already running" as "in progress" rather than a failure to be retried.
     - Ignoring `.cursor/.../agent-tools/` paths.
  2. The MCP stability layer treating `execute_pre_commit_checks` as a **globally serialized long-running tool**, so:
     - A second call blocked on the long-running semaphore for up to 600 seconds, holding up the entire connection.
  3. Cursor’s connection timeout behavior (~3–4 minutes) interacting with (2), leading to:
     - `-32000: Connection closed` errors.
     - Repeated re-invocations that re-triggered the same pattern.

**Impact**:

- `/cortex/commit` became effectively unusable when the agent double-called `execute_pre_commit_checks`:
  - Phase A and/or Step 12 could hang or fail with `RuntimeError` about long-running tools.
  - Users were blocked on committing changes in Cursor, even though the detached worker might still be running successfully in the background.

## Requirements

1. **Investigate**:
   - Map the full execution path for `execute_pre_commit_checks`:
     - From the commit prompt (Phase A and Step 12) and agent behavior.
     - Through the MCP stability layer (long-running semaphores, retries, timeouts).
     - Through detached worker orchestration (`pre_commit_detached.py`).
   - Confirm how and when double-calls are triggered and how they interact with the long-running semaphore and polling.
   - Document the observed connection timeout behavior in Cursor (e.g. ~3–4 minutes) and how it intersects with 600s waits.
2. **Fix (short term / unblock)**:
   - Prevent the second `execute_pre_commit_checks` call from blocking for minutes or holding global semaphores.
   - Make the second call return a **fast, clear, non-retryable error** indicating that a run is already in progress.
   - Update the commit prompt to:
     - Enforce **one call per phase/step** semantics.
     - Explicitly describe the detached model and required waiting behavior.
     - Instruct the agent to **not read** `.cursor/.../agent-tools/` paths and to rely only on the JSON result.
3. **Fix (medium term / production-grade)**:
   - Ensure `execute_pre_commit_checks` concurrency is controlled primarily by its detached worker + `args_hash` model, not by the global long-running semaphore.
   - Add a read-only status/summary tool for detached results so agents can introspect previous runs without re-running checks.
   - Refine result size handling so large logs are truncated for MCP but preserved in worker log files.
   - Ensure connection retry logic and heartbeats are tuned for long runs in Cursor.
4. **Verify**:
   - Add and run unit tests:
     - Detached worker behavior and `args_hash` caching.
     - Double-call handling (second call while status is `running`).
     - Interaction with long-running semaphores after configuration changes.
   - Add integration tests:
     - `/cortex/commit` with Phase A and Step 12 in Cursor-like environments.
     - Simulated MCP connection interruptions and retries.
   - Ensure no regressions for `fix_markdown_lint` and other tools using long-running semantics.

## Implementation Steps

### Phase 1: Capture and document architecture and failure mode

1. Read and summarize:
   - `src/cortex/tools/execution/pre_commit_tools.py` (`execute_pre_commit_checks` entrypoint).
   - `src/cortex/tools/execution/pre_commit_detached.py` (detached worker orchestration).
   - `src/cortex/tools/execution/pre_commit_tools_run_helpers.py` (heartbeat and progress).
   - `src/cortex/core/mcp_stability.py` and `src/cortex/core/mcp_stability_config.py` (stability layers, long-running semaphores and retry config).
2. Document:
   - How `execute_pre_commit_checks` chooses detached vs inline (`DETACHED_ENABLED` / `CORTEX_DETACHED_PIPELINE`).
   - How detached workers are named and stored (`args_hash`, `.cortex/.session/pre_commit_result_*.json`, `.log` files).
   - How heartbeats are sent (via `report_progress_safe`) and how this interacts with Cursor timeouts.
   - How the global long-running semaphore is applied (which tools are in `long_running_tools_serialized`).
3. Reproduce the failure scenario in tests or a controlled dev environment:
   - Trigger two `execute_pre_commit_checks(phase="A")` calls within a couple of seconds.
   - Observe semaphore acquisition, worker spawning, and connection behavior.

### Phase 2: Quick unblock (already implemented)

4. **Prompt mitigation**:
   - Update `.cortex/synapse/prompts/commit.md` Phase A and Step 12 to:
     - Call `execute_pre_commit_checks` exactly once per phase/step.
     - Clarify detached behavior: long waits are normal, do not re-call while in progress.
     - Instruct agents not to read `.cursor/.../agent-tools/...` paths; rely on JSON result only.
5. **Global semaphore adjustment**:
   - Update `mcp_stability_config.py` to **remove `execute_pre_commit_checks` from `_LONG_RUNNING_TOOLS_SERIALIZED`**, leaving only `fix_markdown_lint`:
     - Rationale: `execute_pre_commit_checks` already uses its own detached orchestration and does not need global serialization; serializing it causes redundant 600s waits for second calls.
6. **Detached worker double-call handling**:
   - Update `run_checks_detached` in `pre_commit_detached.py`:
     - If a cached completed result exists for `args_hash`, return it (unchanged behavior).
     - If `find_existing_result(...).status == "running"`:
       - Log that a worker is already running for this `args_hash`.
       - **Return immediately** with a clear error dict:
         - `status: "error"`
         - `error: "execute_pre_commit_checks is already running for this configuration; do not start a second run. Wait for the existing run to finish."`
       - Do **not** spawn a new worker and do **not** start another polling loop.
     - Otherwise, spawn a new detached worker and poll as before.
7. Restart Cortex MCP and verify:
   - A single `execute_pre_commit_checks` run still completes successfully in detached mode.
   - A second call during an active run returns the fast in-progress error instead of blocking.

### Phase 3: Production-grade solution

8. **Status/summary tool for detached runs**:
   - Design and implement a new MCP tool, e.g. `get_last_pre_commit_status`:
     - Read the latest `.cortex/.session/pre_commit_result_{args_hash}.json` (or infer the most recent one).
     - Return a compact summary:
       - Last phase and checks run.
       - Pass/fail status, coverage, and any key errors.
       - Timestamps and whether the run appears complete or stale.
   - Update prompts/rules:
     - When the agent needs to inspect recent pre-commit results (especially after reconnects), use this status tool instead of re-running `execute_pre_commit_checks`.
9. **Output shaping and result size limits**:
   - Ensure `build_pre_commit_response` + `truncate_large_logs_in_data` keep MCP responses within safe size limits while:
     - Preserving complete logs in the worker log file for local developer debugging.
   - Add tests to confirm:
     - Large logs are truncated in the MCP-facing JSON.
     - Worker log files still contain full output.
10. **Tune stability and retry behavior**:
    - Review retry overrides in `mcp_stability_config` for `execute_pre_commit_checks`:
      - Confirm attempts and backoff timings are appropriate for 1–3+ minute runs in Cursor.
    - Validate that heartbeats from `pre_commit_tools_run_helpers` and `pre_commit_detached` are sufficient to keep the connection alive during:
      - Long test runs.
      - Type checking and coverage tasks with minimal intermediate output.
11. **Update docs and troubleshooting**:
    - Add/extend documentation in:
      - `docs/guides/troubleshooting.md` for:
        - `execute_pre_commit_checks` double-call behavior.
        - How detached pre-commit works in Cursor.
        - How to recover from `-32000: Connection closed` errors in the commit pipeline.
      - Any design docs for the commit pipeline to reflect:
        - Detached execution.
        - The new status tool.
        - The removal of `execute_pre_commit_checks` from global long-running serialization.
12. **Strengthen tests**:
    - Add unit tests (e.g. `tests/unit/test_pre_commit_detached.py`, `test_mcp_stability_timeouts.py`) for:
      - Second-call fast-fail behavior when `status == "running"`.
      - Cached result reuse when `status == "completed"`.
      - Interaction with the long-running semaphore after configuration changes.
    - Add integration tests (`tests/e2e/test_commit_pipeline.py` or similar) that:
      - Simulate commit pipeline in a Cursor-like environment.
      - Verify no hangs or long semaphore waits when the agent misbehaves.

## Success Criteria

- Root cause of the commit-pipeline hang and `RuntimeError` is fully documented:
  - Double-call behavior.
  - Long-running semaphore configuration.
  - Detached worker polling and result handling.
- Quick unblock is in place:
  - Second `execute_pre_commit_checks` call during an active run returns a clear, fast error instead of blocking.
  - Commit prompt explicitly enforces one-call semantics and detached-mode awareness.
- Production-grade solution is implemented and verified:
  - `execute_pre_commit_checks` concurrency is controlled by its detached worker model and `args_hash` caching, not by the global long-running semaphore.
  - A read-only status/summary tool exists for inspecting detached results.
  - Large outputs are handled safely for MCP while preserving full logs for local debugging.
  - Connection retry and heartbeat behavior keep Cursor sessions stable during 1–3+ minute runs.
- `/cortex/commit` runs reliably in Cursor:
  - Phase A, Phase B, and Step 12 complete without hangs or spurious long-running errors.
  - No regressions for other long-running tools such as `fix_markdown_lint`.

## Notes

Auto-generated on MCP tool failure. Tool: execute_pre_commit_checks, Error:
RuntimeError: Another long-running tool is in progress (e.g. execute_pre_commit_checks or fix_markdown_lint). Please wait for it to finish (up to 10 minutes) and retry. If running the commit pipeline, ensure Phase A has completed before Step 12; close other tabs or agents that may be running long-running Cortex tools.
