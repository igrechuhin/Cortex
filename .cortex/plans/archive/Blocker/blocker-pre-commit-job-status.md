---
title: "Blocker: Make Pre-Commit Job Status Observable and Bounded"
component: "Commit/implement pipelines - pre-commit job orchestration"
work_type: "infra"
status: "COMPLETE"
priority: "Blocker"
created: "2026-03-12"
execution_order: 2
depends_on: []
---

## Blocker: Make Pre-Commit Job Status Observable and Bounded

**Status**: COMPLETE (2026-03-14)
**Priority**: Blocker  
**Complexity**: Medium  
**Category**: Infra / Reliability  
**Component**: Commit/implement pipelines - pre-commit job orchestration  
**Work Type**: infra  
**Execution Order**: 2

## Completion Summary (2026-03-14)

All implementation steps were already completed prior to this audit:

- **Step 1**: `PreCommitJobStatus` literal type with all states (`queued`, `running`, `completed`, `error`, `timeout`, `no_runs`, `unknown`) defined in `pre_commit_status.py`.
- **Step 2**: `_MAX_RUNNING_AGE_SECONDS = 1800.0` in `pre_commit_status.py`; running jobs older than 30 min auto-promoted to `timeout`; `_timeout_error()` in `pre_commit_detached.py` with 900s poll cap.
- **Step 3**: `get_pre_commit_job_status` returns `checks_summary`, `coverage`, `preflight_passed`, `docs_phase_passed`, `log_path` in all terminal states.
- **Step 4**: Not applicable — prompts already handle terminal states; no hanging in `running` once bounded.
- **Step 5**: Full test coverage in `tests/unit/test_pre_commit_status.py` — `no_runs`, `running`, `completed`, `error`, `timeout` (age-promoted + explicit), `queued`, and both MCP tool wrappers tested.

## Goal

Ensure that `start_pre_commit_job` + `get_pre_commit_job_status` always reach a clear terminal state (completed/error/timeout) within bounded time, and that implement/commit pipelines can reliably surface results (tests, lint, coverage) instead of hanging indefinitely in `running`.

## Context

- In this session, the implement-code subagent started a Phase A pre-commit job via `start_pre_commit_job`, which returned `{"job_id": "9f8190f9da33", "status": "started"}`.  
- Repeated `get_pre_commit_job_status` calls **never left** `{"status": "running"}` and did not transition to `"completed"` or `"error"`.  
- As a result, the quality gate could not be confirmed; tests and coverage results were unknown, and the implement pipeline had to treat the quality gate as effectively failed/unknown.  
- This behavior undermines the commit/implement contract that Phase A must either pass cleanly or fail with actionable errors.

We need robust timeout, observability, and error reporting for pre-commit jobs.

## Implementation Steps

### Step 1: Define pre-commit job lifecycle and states

1. Enumerate the allowed job states for pre-commit jobs (e.g., `queued`, `running`, `completed`, `failed`, `timeout`).  
2. Define maximum expected durations for common job types (full check, quick check, doc-only session) and how these are configured.  
3. Specify what information `get_pre_commit_job_status` must return in each terminal state (summary of checks, errors, logs/paths, coverage metrics if available).

### Step 2: Implement bounded polling and timeouts

1. Update the job orchestration layer (and MCP wrapper if needed) to:
   - Track the start time and a max allowed duration per job.  
   - Treat jobs that exceed the max duration as `timeout` with a structured status.  
   - Return a clear, machine-readable status to callers (e.g., `{status: "timeout", error: "pre-commit job exceeded 900s", partial_results: ...}`).
2. Ensure that implement/commit pipelines:
   - Stop polling once a terminal state (`completed`, `failed`, or `timeout`) is reported.  
   - Treat `timeout` as a blocking error for commit (Phase A) and as a “fix-path required” condition for implement, with guidance to re-run or investigate.

### Step 3: Improve status payloads and logging

1. Extend `get_pre_commit_job_status` responses to include:
   - High-level summary of check results (pass/fail per category: tests, lint, format, type check, quality).  
   - Pointers to detailed logs/output (file paths under `.cortex/.cache` or similar), not raw logs in the response.  
   - Progress indicators for long-running jobs, if feasible.
2. Add structured logging/metrics around job lifecycle events (start, status transitions, completion, timeout) to make diagnosing hangs or misconfigurations easier.

### Step 4: Update implement/commit prompts and agents

1. Update `/cortex/commit` and `/user-cortex/implement` prompts (and subagents) to:
   - Expect and handle the new `timeout` status explicitly.  
   - Surface clear messages to the user when a job times out, including suggested next steps (e.g., “rerun locally, check job logs, file an issue if recurrent”).
2. Ensure that the implement pipeline’s iteration loop for fix-path work respects the new terminal statuses and does not spin infinitely when jobs don’t progress.

### Step 5: Add tests and simulated long-running jobs

1. Add unit tests for the job orchestration layer to cover:
   - Normal completion within time bounds.  
   - Explicit failure with detailed error reporting.  
   - Timeout path where jobs exceed configured limits.  
2. Add integration tests or fakes that simulate:
   - Very long-running jobs to confirm timeout behavior and user-facing messaging.  
   - Jobs that intermittently report `running` before transitioning to `completed` or `failed`.

## Verification Checklist

| What to search for | Search scope | Expected result |
|---|---|---|
| `timeout` or bounded duration handling in pre-commit job orchestration | Pre-commit job orchestration code | Clear timeout and terminal state handling implemented |
| `get_pre_commit_job_status` payload fields | MCP/job API layer | Includes explicit terminal states and summary info |
| Implement/commit prompts handling of `timeout` | Implement/commit prompts and subagents | Explicit user messaging and fix-path behavior on timeout |

## Dependencies

- Existing `start_pre_commit_job` and `get_pre_commit_job_status` APIs.  
- Access to a test environment where synthetic long-running jobs can be triggered or simulated.

## Success Criteria

- Pre-commit jobs **always** reach a clear terminal status (`completed`, `failed`, or `timeout`) within bounded time.  
- Implement/commit pipelines never hang indefinitely polling `running` without feedback.  
- Users receive clear, actionable status and error messages, with pointers to logs when needed.  
- Tests cover normal, failure, and timeout paths (target ≥95% coverage for new orchestration logic).

## Testing Strategy

- **Coverage Target**: ≥95% for new/modified job orchestration code.  
- Unit tests for state transitions and timeout handling.  
- Integration tests for implement/commit flows that start pre-commit jobs and observe terminal statuses.
