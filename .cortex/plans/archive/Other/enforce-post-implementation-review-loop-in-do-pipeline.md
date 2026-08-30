---
title: "Enforce Post-Implementation Review Loop in /do Pipeline"
component: "do-review-pipeline"
work_type: feature
status: PENDING
priority: High
created: 2026-04-16
depends_on: []
---

## Goal

Ensure `/cortex/do` automatically triggers a review pass after plan completion, and when review reports implementation gaps, those gaps are recorded in the plan and the plan is returned to `PENDING`.

## Context

Current workflow requires explicit manual review invocation after implementation. This allows plans to be marked complete even when the implementation leaves detectable gaps. The request requires a closed-loop pipeline behavior in `do.md`: complete implementation, run `review.md` via subagent, then either confirm completion (no gaps) or reopen plan state with tracked follow-up gaps.

## Scope

**in_scope**

- Update `.cortex/synapse/prompts/do.md` orchestration to invoke review as an automatic post-implementation step.
- Define and enforce a structured review-result contract that distinguishes `no_gaps` vs `gaps_found` outcomes.
- Add logic to append review-detected gaps into the active plan file in a deterministic section/format.
- Add logic to transition the affected plan status back to `PENDING` when gaps are found.
- Add verification checks/tests for no-gap and gap-found branches, including idempotent plan updates.

**out_of_scope**

- Broad redesign of `/cortex/review` scoring heuristics or metric definitions.
- Changes to unrelated `/cortex/commit` or `/cortex/fix` orchestration behavior.
- Introducing new roadmap sections or nonstandard plan file schema.

## Approach

Introduce an explicit post-implementation review phase in the `/cortex/do` prompt contract. After implementation marks tasks complete, orchestration launches a dedicated subagent to run `.cortex/synapse/prompts/review.md` against the implemented plan scope. The review output must be normalized into a compact structured result (for example: `status`, `gaps[]`, `evidence`).

When the normalized result is `no_gaps`, the plan remains completed and the pipeline proceeds as usual. When `gaps_found`, orchestration writes a bounded, de-duplicated gap list into the same plan under a canonical follow-up area, flips plan status to `PENDING`, and exits with a clear "reopened for remediation" result. This creates a finite, binary gate at end-of-plan execution while preserving traceable feedback.

## Implementation Steps

1. Inspect current `/cortex/do` completion flow and identify exact hook point where plan completion is finalized.
2. Add a mandatory post-completion review invocation step that runs `.cortex/synapse/prompts/review.md` via subagent with plan-context inputs.
3. Define/update review result normalization schema used by `/do` to parse `gaps_found` versus `no_gaps` deterministically.
4. Implement plan mutation path that appends review gaps (deduplicated, actionable) and reverts plan `status` to `PENDING` when gaps exist.
5. Implement no-gap path that preserves completed status and records review success evidence without reopening work.
6. Add regression tests/evals for both branches and for repeated execution (no duplicate gap spam, stable state transitions).
7. Update prompt documentation/guardrails so `/do` describes this automatic review loop and finite completion gate.

## Verification Checklist

- **Completion hook exists**: search `.cortex/synapse/prompts/do.md` for post-implementation phase that explicitly invokes review.
- **Subagent review invocation**: search orchestration prompts/helpers for `.cortex/synapse/prompts/review.md` call path and required inputs.
- **Gap normalization contract**: search for schema keys such as `gaps_found`, `gaps`, `status`, and verify both branches are handled.
- **Plan reopen logic**: re-read plan lifecycle handlers to confirm `status: PENDING` is written only when gaps are present.
- **Plan gap recording**: verify gap entries are appended once per unique gap and remain actionable.
- **Files to re-read after changes**: `.cortex/synapse/prompts/do.md`, review invocation helper/prompt wiring, plan lifecycle tool logic, and related tests/evals.

## Dependencies

- Existing `/cortex/do` pipeline orchestration and plan lifecycle operations (`plan` tool create/get/complete semantics).
- Existing `.cortex/synapse/prompts/review.md` execution contract and result format.
- Test/eval harness used for prompt-orchestration regression validation.

## Success Criteria

- Running `/cortex/do` on a completed plan automatically triggers review without manual intervention.
- If review returns no gaps, the plan remains completed and pipeline exits success.
- If review returns one or more gaps, the plan is updated with those gaps and `status` is set to `PENDING`.
- Re-running the same scenario does not duplicate identical recorded gaps.
- Behavior is binary and finite: each run ends in exactly one of `{completed_no_gaps, reopened_with_gaps}`.

## Testing Strategy

Target: 95% coverage on newly introduced orchestration and state-transition logic.

- **Unit tests**: result normalization, branch routing, deduplication, and plan status transition helpers.
- **Integration tests**: end-to-end `/cortex/do` flow that stubs review output for both `no_gaps` and `gaps_found` outcomes.
- **Negative cases**: malformed/empty review output, duplicate gap payloads, and subagent failure path handling.
- **AAA pattern**: Arrange (plan + mocked review result), Act (run `/do` completion path), Assert (plan status and gap section state).
- No blanket skips; each new branch must include explicit positive and negative assertions.

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| Review output shape drifts and breaks `/do` parsing | Define a strict normalized adapter with validation + fallback error classification |
| Reopen loop creates noisy repeated gaps | Deduplicate by stable gap key and persist last-seen marker before append |
| Plan status toggles incorrectly on transient review failures | Treat transport/runtime errors as explicit blocked/error state, not `gaps_found` |
| Prompt coupling causes fragile cross-prompt behavior | Keep a minimal interface contract and cover with integration regression tests |
