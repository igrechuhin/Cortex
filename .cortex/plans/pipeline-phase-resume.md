---
title: "Add Phase Status Tracking and Resume Capability to Pipeline Agents"
component: "pipeline"
work_type: "feature"
status: BLOCKED
priority: "High"
created: "2026-04-20"
depends_on: ["pipeline-event-log.md"]
---

## Goal

Add `status` field (`pending|running|completed|failed`) to pipeline phase results so agents can skip completed phases and retry only failed ones on resume, eliminating full-restart requirements after mid-pipeline crashes.

## Context

When a Cortex pipeline agent (e.g., `commit-phase-b`) crashes or is interrupted, there is no mechanism to resume. The orchestrator stops and the user must re-run from scratch — even if earlier phases completed successfully. Agents don't check "did I already complete this phase?" before re-running.

This maps to the Managed Agents `wake(sessionId)` + `getSession(id)` + resume-from-last-event pattern. Once the event log from Plan 1 exists, adding a `status` field to phase results gives agents a deterministic way to know what work is still needed.

## Scope

**in_scope**

- `status` field on phase result JSON (`pending|running|completed|failed`)
- `pipeline_handoff(operation="mark_running", pipeline=..., phase=...)` — atomic status write before agent begins work
- `pipeline_handoff(operation="status", pipeline=...)` — returns `{phase: status}` dict for all phases
- Updated commit pipeline agents (preflight, phase-a, phase-b, phase-c, final-gate) to call `mark_running` at start and check `status` before re-running
- Updated fix pipeline agents (fix-quality, fix-tests, fix-coverage, fix-docs) similarly
- Unit tests for all new paths

**out_of_scope**

- UI or dashboard for pipeline status
- Cross-session status queries
- Automatic orchestrator retry logic (agents check status themselves via prompts)
- Implement pipeline (`implement-code` agent) — lower risk, tackled separately

## Approach

Extend `pipeline_handoff` with two new operations. `mark_running` writes `{"status": "running", "started_at": "<iso>"}` to `{phase}-result.json` atomically (using a temp file + rename). The existing `write` operation is updated to merge `{"status": "completed", "completed_at": "<iso>"}` into the result automatically.

`status` returns a dict by reading all `{phase}-result.json` files in the pipeline dir and extracting the `status` field. Phases with no result file are reported as `pending`.

Agent prompts are updated with a short "resume check" block: at the start of each phase, call `pipeline_handoff(operation="status")`, check if own phase is `completed` — if so, skip and return prior result. This is a prompt-level change, not a Python change.

## Implementation Steps

1. Add `mark_running` branch to `pipeline_handoff` dispatch in `src/cortex/tools/pipeline_handoff.py`: writes `{"status": "running", "started_at": "<iso>", "phase": phase}` to `{phase}-result.json` atomically (write to temp file, rename).
2. In the `write` operation branch, merge `{"status": "completed", "completed_at": "<iso>"}` into the data before writing to `{phase}-result.json` and `pipeline.json`.
3. Add `status` branch to `pipeline_handoff` dispatch: reads all `{phase}-result.json` files in pipeline dir, extracts `status` field, returns `{phase_name: status_str}` dict. Phases with no file → `"pending"`.
4. Update event log (`_append_event_log` from Plan 1) to include `status` in log entries for `mark_running` and `write` calls.
5. Add resume-check instructions to commit pipeline agent prompts in `.cortex/synapse/cursor-agents/`: at start of each phase, call `status` operation and skip if `completed`.
6. Add resume-check instructions to fix pipeline agent prompts similarly.
7. Unit tests in `tests/unit/tools/test_pipeline_phase_resume.py`: mark_running sets status, write sets completed, status query returns correct dict, resume simulation (completed phase → skip), failed phase → retry.

## Verification Checklist

- Step 1: grep `mark_running` in `src/cortex/tools/pipeline_handoff.py`; confirm atomic write via temp+rename
- Step 2: grep `completed` merge in `write` branch; confirm `completed_at` timestamp added
- Step 3: grep `status` dispatch branch; confirm returns dict with `pending` for missing files
- Step 4: grep `status` param in `_append_event_log` calls; confirm mark_running and write both log
- Step 5: read `.cortex/synapse/cursor-agents/commit-phase-a.md`; confirm resume-check block present
- Step 6: read `.cortex/synapse/cursor-agents/fix-quality.md`; confirm resume-check block present
- Step 7: run `pytest tests/unit/tools/test_pipeline_phase_resume.py -v`; all pass

## Dependencies

- [pipeline-event-log.md](archive/Other/pipeline-event-log.md) — requires `_append_event_log` and `pipeline.log` infrastructure

## Success Criteria

- `pipeline_handoff(operation="mark_running")` writes `status: running` atomically before agent begins
- `pipeline_handoff(operation="write")` always includes `status: completed` in result
- `pipeline_handoff(operation="status")` returns correct status for all phases including `pending` for untouched phases
- Commit and fix pipeline agents skip already-completed phases on re-run
- All new code paths covered by unit tests; quality gate passes

## Testing Strategy

Target: 95% coverage on new code paths. AAA pattern throughout.

- **Unit — mark_running**: Arrange: pipeline dir, no phase file. Act: `mark_running`. Assert: result file contains `status: running`, `started_at` present.
- **Unit — write sets completed**: Arrange: pipeline dir with mark_running result. Act: `write` with data. Assert: result file contains `status: completed`, `completed_at` present, original data merged.
- **Unit — status query all phases**: Arrange: pipeline dir with 3 phases in various states. Act: `status`. Assert: dict matches expected `{phase: status}` including `pending` for missing phase.
- **Unit — resume simulation**: Arrange: pipeline dir with phase-a `completed`. Act: agent calls `status`, sees `completed`. Assert: agent returns prior result without re-running (mock agent call).
- **Unit — failed phase retry**: Arrange: pipeline dir with phase-a `failed`. Act: agent calls `status`, sees `failed`. Assert: agent re-runs phase-a.
- **Integration — full commit pipeline resume**: Arrange: run preflight + phase-a, simulate crash before phase-b. Act: re-invoke orchestrator. Assert: phase-b starts from `pending`, phase-a not re-run.

## Risks and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent prompts get out of sync with new status API | Medium | Medium | Add `status` call to shared agent preamble so all agents inherit it |
| `mark_running` + crash leaves `running` state permanently | Medium | Low | Plan 1's incomplete detection flags `running` without `completed` in the log; operator can clear manually |
| Atomic rename not available on some filesystems | Low | Medium | Fall back to direct write with a completion sentinel file if rename fails |
| Resume logic skips a phase that needs re-running due to upstream change | Low | High | Agents should check `status` only for their own phase, not assume upstream phases are still valid |
