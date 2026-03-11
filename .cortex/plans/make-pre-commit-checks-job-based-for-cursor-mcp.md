---
title: Make pre-commit checks job-based for Cursor MCP
component: pre-commit-pipeline
work_type: blocker
status: IN_PROGRESS
priority: HIGH
created: 2026-03-10
depends_on: []
---

## Goal

Ensure `execute_pre_commit_checks` and related commit-pipeline flows run reliably inside Cursor by replacing long in-flight MCP calls with a job-based, short-call protocol that fits Cursor’s connection and timeout behavior (no more `MCP error -32000: Connection closed` during Phase A / Step 12).

## Context

- Current design runs full Phase A / Step 12 as a single MCP tool call (`execute_pre_commit_checks`), backed by a detached worker that writes `pre_commit_result_<hash>.json`.
- The MCP wrapper sends regular progress notifications, but Cursor/anyio still closes the write stream with `ClosedResourceError` while responses are being sent, causing `-32000` errors and temporary loss of tool offerings for `user-cortex`.
- Cursor is effectively enforcing a maximum call lifetime independent of these heartbeats.
- Cortex must adapt by exposing long-running pre-commit work as a job-based API (start + poll) composed of short, bounded MCP calls, while reusing the existing detached worker and result files.

## Implementation Steps

1. **Design job-based MCP API for pre-commit runs**
   - Define new tools:
     - `start_pre_commit_job(phase, test_timeout, coverage_threshold, strict_mode, include_untracked_markdown)` → `{ job_id, status }`.
     - `get_pre_commit_job_status(job_id)` → `{ status, preflight_passed?, docs_phase_passed?, coverage?, error? }`.
     - Optional `cancel_pre_commit_job(job_id)` for future use.
   - Specify that `job_id` reuses the existing `args_hash` computed from checks/timeout/coverage/strict/markdown flags.

2. **Extend detached worker/status helpers to support job IDs**
   - In `pre_commit_detached.py`, treat `compute_args_hash` as the canonical `job_id` and ensure result/log paths are consistently derived from it.
   - In `pre_commit_status.py`, add helpers to:
     - Load a result for a specific `job_id` (hash), not just “latest overall”.
     - Build `PreCommitRunSummary` for that `job_id` and return a JSON-serializable dict for `get_pre_commit_job_status`.

3. **Implement new MCP tools using existing infrastructure**
   - Add `start_pre_commit_job` and `get_pre_commit_job_status` as `typed_mcp_tool`s with `mcp_tool_wrapper` + `ensure_usage_context`.
   - `start_pre_commit_job`:
     - Resolves project root.
     - Computes `args_hash` from arguments.
     - If a fresh result already exists and is `completed`, return `{ job_id, status: "completed" }` early (cached).
     - If a worker is already running for that hash, return `{ job_id, status: "already_running" }` without spawning another.
     - Otherwise, spawn the detached worker and return `{ job_id, status: "started" }` quickly.
   - `get_pre_commit_job_status`:
     - Resolves project root and reads `pre_commit_result_<job_id>.json`.
     - Uses `PreCommitRunSummary` to map to `{ status: "running"|"completed"|"error"|"no_runs", preflight_passed?, docs_phase_passed?, coverage?, error? }`.
     - Must be fast and side-effect free (no new workers spawned here).

4. **Adapt existing `execute_pre_commit_checks` to use the job API internally**
   - Keep `execute_pre_commit_checks` as the public MCP entry point to avoid breaking callers immediately.
   - For Phase-based runs (Phase A/B/Step 12):
     - Internally call `start_pre_commit_job(...)` once to get `job_id`.
     - Loop with a bounded polling pattern:
       - Sleep 1–3 seconds.
       - Call `get_pre_commit_job_status(job_id)`.
       - Emit progress events to the client based on elapsed time or status changes.
       - Exit the loop when `status != "running"` or a global timeout is reached.
     - Return a result shaped like the current pre-commit response by:
       - Reading the worker result file directly (existing code), or
       - Translating the `PreCommitRunSummary` into the expected `ModelDict`.
   - Ensure `fix_quality` mode keeps using the existing `fix_quality_issues_impl` path (no job abstraction needed there unless future issues arise).

5. **Update commit/fix prompts to orchestrate via job tools**
   - In `/user-cortex/commit` prompt:
     - Replace direct calls to `execute_pre_commit_checks(phase="A"/"B"/Step 12)` with:
       - `start_pre_commit_job(...)` (explicit Phase A/B parameters) → `job_id`.
       - A small loop of `get_pre_commit_job_status(job_id)` calls until `status != "running"`.
     - Interpret final status:
       - If `status="completed"` with `preflight_passed/docs_phase_passed` flags: proceed.
       - If `status="error"` or `status="no_runs"`: treat as pipeline failure with clear messaging.
   - Update any other prompts or tools that rely on long-running `execute_pre_commit_checks` (e.g., fix-quality flows, doc sync) to the same start + poll pattern, or to the updated wrapper.

6. **Add tests for job-based behavior and robustness**
   - Unit tests for `start_pre_commit_job`:
     - New run: spawns worker and returns `status="started"`.
     - Existing running run: returns `status="already_running"` and does not spawn a second worker.
     - Completed run in cache: returns `status="completed"` quickly.
   - Unit tests for `get_pre_commit_job_status`:
     - No result file: `status="no_runs"`.
     - `running` status in file: `status="running"`, preserves `job_id`.
     - `completed` status: correct `preflight_passed`, `docs_phase_passed`, `coverage`, `completed_at`.
     - `error` status: `status="error"` with meaningful `error` text.
   - Integration-style tests:
     - Simulate a Phase A run where worker sleeps for longer than Cursor’s typical timeout; verify:
       - Each MCP call to job tools is short.
       - No `MCP error -32000` is observed for job tools.
       - Final pipeline behavior matches current semantics (gates on `preflight_passed`, coverage, etc.).

7. **Migration and compatibility safeguards**
   - Initially, keep both:
     - New job tools (`start_pre_commit_job`, `get_pre_commit_job_status`),
     - Legacy `execute_pre_commit_checks` wrapper (refactored to use job tools internally).
   - Update documentation and internal guidance to prefer the job API for new flows.
   - Once prompts and tests are fully aligned and stable, consider de-emphasizing or deprecating direct “one long call” usage patterns, but only after verifying Cursor behavior across multiple sessions.

## Verification Checklist

- **What to search for**: New job-based pre-commit tools are registered and discoverable.  
  **Search scope**: MCP tool descriptors / `cortex.tools.execution.pre_commit_tools`.  
  **Files to re-read**: `pre_commit_tools.py`, FastMCP tool list logs.

- **What to search for**: Detached worker still writes and reads `pre_commit_result_<hash>.json`.  
  **Search scope**: `.cortex/.session/` behavior and logs.  
  **Files to re-read**: `pre_commit_detached.py`, `pre_commit_worker.py`, `pre_commit_status.py`.

- **What to search for**: Commit prompt uses start + poll pattern instead of single long call.  
  **Search scope**: `/user-cortex/commit` prompt, related Synapse prompts.  
  **Files to re-read**: `commit.md`, any prompt-specific tooling docs.

- **What to search for**: No `MCP error -32000: Connection closed` during Phase A/Step 12 in Cursor logs.  
  **Search scope**: Recent MCP logs after running commit pipeline.  
  **Files to re-read**: `anysphere.cursor-mcp.MCP user-cortex` logs, new diagnostics.

- **What to search for**: Tests cover job tools and pass reliably.  
  **Search scope**: `tests/tools/`, `tests/integration/` around pre-commit and MCP stability.  
  **Files to re-read**: `test_phase1_foundation.py`, any new test modules for job tools.

## Dependencies

- Existing detached worker and result file infrastructure must remain stable.
- MCP stability layer (`mcp_stability_*`) and logging must continue to classify and log connection errors correctly.
- Cursor MCP client behavior (timeouts, connection management) remains as currently observed.

## Success Criteria

- Commit pipeline (Phase A, Phase B, Step 12) completes in Cursor without `MCP error -32000: Connection closed` for pre-commit-related tools.
- All long-running pre-commit work is expressed as a set of short, bounded MCP calls (start + poll) that fit within Cursor’s hosting behavior.
- Existing pre-commit semantics (gates, coverage threshold, fix-quality behavior) are preserved.
- Relevant unit/integration tests are updated and passing.

## Testing Strategy (95% coverage target)

- Add focused unit tests for new job tools and status helpers to reach high coverage in:
  - `pre_commit_detached.py`,
  - `pre_commit_status.py`,
  - new job-based MCP tool implementations.
- Extend integration tests to simulate:
  - Long-running Phase A with job-based calls in Cursor-like conditions.
  - Repeated polling, error states, and concurrent commit sessions.
- Run full pre-commit suite (`format`, `lint`, `type_check`, `tests`) and verify no regressions in unrelated tools or flows.
