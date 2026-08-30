---
title: "Task-Level Stuck-Loop Constraints Monitor Beyond MCP Circuit Breaker"
component: "orchestration"
work_type: feature
status: PENDING
priority: Medium
created: 2026-07-23
depends_on: []
---

## Goal

Add detection for when a task-executing subagent (e.g. `fix-tests`, `implement-code`) repeats a failing action against the same target (same file/test/error signature) a bounded number of times without progress, and surface that state via `pipeline_handoff` so the orchestrator pauses for re-plan/human check-in — distinct from, and complementary to, the existing MCP-transport circuit breaker.

## Context

An external proposal ("Self-Play Workflow Autoconstruction") suggested a `Constraints Monitor` that pauses execution and adjusts the workflow path when an actor agent fails to resolve an issue across 2 consecutive tool calls, as part of a much larger dynamic task-decomposer/sub-agent-topology-construction redesign. Investigation (2026-07-23) found Cortex already has a circuit breaker, but it is scoped to MCP transport failures specifically: `src/cortex/core/mcp_stability_retry.py` (`MCPConnectionState`, Phase 86) trips on consecutive **connection** failures at the code level, and `.cortex/synapse/agents/shared-conventions.md` / `pipeline-state-tracker.md` document a prompt-level convention that trips after **3 consecutive MCP tool-call failures** (checkpoint, abort, resume from `last_successful_step`). Neither covers the case the proposal actually describes: a subagent whose tool calls all *succeed* (no MCP error) but keep failing to make progress on the same underlying problem — e.g. `fix-tests` re-running the same fix against the same failing test 5 times with the same assertion error each time. Full dynamic per-task sub-agent topology construction (the rest of the proposal) is a deliberate departure from Cortex's intentional fixed-schema pipeline architecture (`workflow_schema`/`schema_loader.py`, `pipeline_handoff`) and is out of scope here as a much larger, separate architectural decision.

**Why**: The existing circuit breaker protects against MCP infrastructure instability; it does not protect against an agent looping on the same unproductive fix, which burns budget and context without the infra-level signal (connection failure) that would trip the existing breaker.

**How to apply**: This is an extension of CRI-3's circuit-breaker convention to a second, independent failure class (no-progress loops), not a replacement, and not a rearchitecture of pipeline orchestration.

## Scope

**in_scope**:

- A no-progress detector: given a bounded window of a subagent's consecutive attempts against the same target (same file path + same test name/error signature, or equivalent task-specific identity), flag when N consecutive attempts (N configurable, default matching the existing "3 consecutive" convention for consistency) produce the same failure signature with no change in outcome.
- A `pipeline_handoff` write (new or extended phase data field) that the fix-*/implement-code subagents populate after each attempt, recording target identity + outcome signature, so the detector can be evaluated from existing session state rather than requiring new persistent storage.
- Updating the relevant Synapse agent prompts (`fix-tests.md`, `fix-quality.md`, `implement-code.md` and mirrors) to check this signal before each retry and pause/report to the orchestrator when it trips, following the same "checkpoint, report, await resume" pattern already used for the MCP circuit breaker in `shared-conventions.md`.
- Documentation in `shared-conventions.md` distinguishing this task-level monitor from the existing MCP-transport circuit breaker so agents don't conflate the two.

**out_of_scope**:

- Any dynamic task-decomposer or per-task sub-agent topology construction — orchestration remains the fixed `workflow_schema`-driven pipeline; this plan does not introduce a `TaskDecomposer` module or alternate graph layouts.
- Replacing or modifying the existing MCP-transport circuit breaker (`mcp_stability_retry.py`, the 3-consecutive-MCP-failure convention) — it is left as-is; this plan adds a second, independent signal.
- Automatic workflow-path rerouting on trip — for this slice, tripping the monitor means pause-and-report (consistent with existing circuit-breaker behavior), not automatic re-routing to a different agent/strategy, which would require the out-of-scope decomposer.

## Approach

Extend the existing `pipeline_handoff` phase-data mechanism (already used for checkpointing) with a small structured record of "last attempt against target X had outcome Y," written by task-executing subagents after each fix/implement attempt. Add a lightweight comparison step (same target, same outcome signature, N times) that those subagents check before retrying, reusing the exact "checkpoint + report + await resume" UX already documented for the MCP circuit breaker so the behavior is familiar rather than a new mental model.

## Implementation Steps

1. Read `.cortex/synapse/agents/shared-conventions.md` and `pipeline-state-tracker.md` in full to confirm the exact checkpoint/report/resume mechanics used by the existing MCP circuit breaker, so the new monitor reuses the same UX pattern.
2. Read `src/cortex/tools/session/pipeline_handoff.py` and related files (`pipeline_handoff_io.py`, `pipeline_handoff_analytics.py`) to identify where to add a new phase-data field for per-attempt target+outcome records without breaking existing phase schemas.
3. Define an attempt-record model (Pydantic `BaseModel`, no `Any`): target identity (file path + test/error signature or task-specific key), outcome signature, attempt number.
4. Implement the no-progress comparison: given the last N attempt records for the same target, detect identical outcome signatures.
5. Update `.cortex/synapse/agents/fix-tests.md`, `fix-quality.md`, `implement-code.md` (and `.claude/agents/`/`.cursor/agents/` mirrors) to write an attempt record after each fix/implement iteration and check the no-progress detector before retrying, pausing and reporting per the existing circuit-breaker report format when tripped.
6. Update `shared-conventions.md` with a clearly separated section distinguishing this task-level monitor from the MCP-transport circuit breaker.
7. Add unit tests for the attempt-record model and no-progress detector; add an integration test simulating N identical-outcome attempts and asserting the pause/report path triggers.
8. Run `run_quality_gate()` and confirm no regression in existing `pipeline_handoff` tests.

## Verification Checklist

- Step 2: re-read `pipeline_handoff_validation.py` after schema changes to confirm the new phase-data field doesn't break existing phase-allowlist validation (relevant given the currently-pending `fix-analyze-pipeline-phase-allowlist-and-subagent-tool-grant-gaps.md` plan touches the same allowlist).
- Step 4: re-read the comparison logic and confirm it correctly resets on a genuinely different target (no false-positive trip when an agent moves on to a new file/test).
- Step 5: re-read all three subagent prompt files plus mirrors to confirm identical wording/behavior (no drift between `.claude/agents/`, `.cortex/synapse/agents/`, `.cursor/agents/`).
- Step 8: re-run `run_quality_gate()` after tests added; confirm coverage threshold met.

## Dependencies

- Should be sequenced after (or coordinated with) the already-pending `fix-analyze-pipeline-phase-allowlist-and-subagent-tool-grant-gaps.md` plan if both touch `pipeline_handoff` phase-allowlist validation, to avoid merge conflicts in the same validation logic — not a hard blocker, but check that plan's status before starting Step 2.

## Success Criteria

- A no-progress detector exists and is independent of the MCP-transport circuit breaker (verified: a scenario with only successful-but-unproductive tool calls trips this monitor without ever tripping the MCP breaker).
- `fix-tests`, `fix-quality`, and `implement-code` subagents (and mirrors) all check the detector before retrying and follow the same pause/report format as the existing circuit breaker.
- No dynamic task-decomposer or topology-construction code is introduced.
- `run_quality_gate()` passes with new code covered.

## Testing Strategy

Target 95% coverage on new code. Unit tests (AAA pattern) for: attempt-record model validation, no-progress detector true positive (N identical outcomes on same target), true negative (different target resets the count), true negative (outcome changes between attempts even on same target). Integration test: simulate a subagent loop writing N identical attempt records via `pipeline_handoff` and assert the pause/report signal is raised at the configured threshold, not before. Negative case: fewer than N attempts, or attempts against different targets, must not trip the monitor.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Outcome-signature comparison is too strict (e.g. includes a timestamp or line number that changes trivially) and never detects true no-progress loops | Define outcome signature explicitly as error type + assertion message shape, excluding volatile fields (line numbers, timestamps); cover with a dedicated test |
| Outcome-signature comparison is too loose and false-positives on legitimately different failures at the same target | Require exact signature match, not fuzzy similarity, for this first slice; document as a known limitation rather than over-engineering a similarity threshold |
| Confusion between this monitor and the existing MCP circuit breaker leads agents to conflate the two failure classes | `shared-conventions.md` update explicitly separates the two with distinct trigger conditions and report wording |
| Scope creep toward the out-of-scope dynamic task-decomposer during implementation | Implementation Steps and out_of_scope explicitly exclude any `TaskDecomposer`/topology-assignment code; a reviewer should reject any PR introducing it under this plan |

## Change History

*No revisions recorded yet — enrich or edit implementation steps to append history.*
