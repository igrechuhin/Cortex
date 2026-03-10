# Phase: Investigate commit pipeline hang (Phase A semaphore retry)

**Status**: Complete
**Priority**: ASAP (Blocker)
**Created**: 2026-03-08
**Completed**: 2026-03-09
**Target Completion**: 2026-03-08

## Goal

Investigate and fix the commit pipeline hang observed when Phase A is retried after the orchestrator reports that the long-running semaphore may be stale.

## Context

**Evidence**: Agent transcript `73c0d44b-0b57-467a-85c0-41957e8e1cb5`:

1. User invoked `/user-cortex/commit`.
2. Pre-action checklist passed (MCP healthy, rules loaded, structure info, changes present).
3. Phase A (Steps 0–4) was started.
4. Agent reported: "Retrying Phase A once; the long-running semaphore may be stale."
5. No further progress in the transcript — pipeline appears to hang.

**Related work**: Blocker plans for "Investigate execute_pre_commit_checks MCP Tool Failure" address the **RuntimeError** when the long-running semaphore wait times out. This plan addresses the **hang** (pipeline does not complete) when the orchestrator retries Phase A in that semaphore-related scenario.

**Relevant code**: `src/cortex/core/mcp_stability_semaphores.py` (acquire/release, `LONG_RUNNING_SEMAPHORE_WAIT_SECONDS` 600s, auto-release); commit prompt Phase A retry behavior; `execute_pre_commit_checks` serialization.

## Investigation Results

- Root cause: long-running semaphore wait and release behavior could leave an apparently stale holder after cancellations or crashes, so a subsequent Phase A retry could block behind that holder instead of failing fast.
- Fix: factored long-running semaphore logic into `mcp_stability_semaphores.py` with bounded wait plus retry, auto-release after a maximum hold time, and release-on-cancellation; updated troubleshooting docs to describe long-running tool serialization behavior and guidance.
- Verification: new and existing semaphore/timeouts tests in `tests/unit/test_mcp_stability_timeouts.py` pass; commit pipeline now surfaces a clear `RuntimeError` instead of hanging when a second long-running tool arrives while the first is stuck.

## Requirements

1. **Reproduce**: Identify conditions that lead to "Retrying Phase A once; the long-running semaphore may be stale" and subsequent hang (no completion).
2. **Root cause**: Determine whether the hang is due to: semaphore wait blocking for full timeout, deadlock, retry loop that never completes, MCP/connection timeout after retry, or orchestrator logic not progressing after retry.
3. **Fix**: Resolve root cause so the pipeline either completes Phase A or fails fast with a clear error instead of hanging.
4. **Verify**: Confirm commit pipeline can complete or fail deterministically; no regressions in semaphore or Phase A behavior.

## Implementation Steps

1. **Triage**: Locate where "long-running semaphore may be stale" (or equivalent) is decided in commit flow; confirm whether retry is in prompt narrative only or in tooling.
2. **Reproduce**: Document steps or scenarios that trigger Phase A retry and hang (e.g., concurrent tool, stale holder, timeout path).
3. **Instrument**: Add or use logging to observe semaphore holder, wait duration, and release paths during Phase A and retry.
4. **Fix**: Implement changes (e.g., timeout cap on retry wait, clear stale holder on timeout, or fail-fast with actionable message) so the pipeline does not hang.
5. **Tests**: Add or extend tests for semaphore timeout and retry behavior; ensure 95% coverage for any new code.
6. **Docs**: Update troubleshooting or commit runbook if new behavior or recovery steps are introduced.

## Success Criteria

- Root cause of the hang (after "Retrying Phase A once; the long-running semaphore may be stale") is identified and documented.
- Pipeline no longer hangs in that scenario: it either completes Phase A or fails with a clear, actionable error.
- Existing execute_pre_commit_checks and semaphore tests pass; new code meets 95% coverage target.
- Related blocker plans (execute_pre_commit_checks RuntimeError) are referenced or consolidated as needed.

## Testing Strategy

- **Unit**: Cover new/updated semaphore or Phase A retry logic (timeout, release, retry decision) with 95% coverage target for changed code.
- **Integration**: If possible, add a test that simulates semaphore contention or stale holder and asserts pipeline does not hang (e.g., completes or raises within a bounded time).
- **Regression**: Run full pre-commit and commit pipeline checks after the fix.

## Notes

- Transcript reference: [73c0d44b](agent-transcripts/73c0d44b-0b57-467a-85c0-41957e8e1cb5).
- Related: `.cortex/plans/phase-investigate-execute_pre_commit_checks-failure-20260308-225655.md` (RuntimeError when semaphore wait times out).
