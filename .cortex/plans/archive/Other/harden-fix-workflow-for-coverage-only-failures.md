---
title: "Harden /fix Workflow for Coverage-Only Failures"
component: "fix-workflow"
work_type: "fix"
status: "PENDING"
priority: "High"
created: "2026-04-16"
depends_on: []
---

## Goal

Deliver a production-grade fix so `/cortex/fix` treats "coverage below threshold with zero failing tests" as an actionable tests-target failure, with deterministic behavior, telemetry, and regression protection.

## Context

A real TradeWing run reported ~48.96% coverage against a 90% requirement. `/fix` iterated without adding tests because the tests path was keyed mainly to failing tests, not coverage-only deficits.

## Scope

**in_scope**

- Add orchestrator-level decision logic that routes coverage-only failures into mandatory coverage-improvement attempts.
- Add regression evals for the exact failure mode (tests pass, coverage below threshold).
- Add result-contract checks in final report/handoff so coverage-attempt evidence is required.
- Add bounded fallback behavior for cases where coverage cannot be increased in-session (clear blocker classification).
- Add lightweight telemetry fields to detect and audit repeated coverage-only exits.

**out_of_scope**

- Reworking unrelated `/fix` targets (docs-only or quality-only flows not tied to coverage).
- Changing repository-wide coverage thresholds or language-specific quality policies.
- Broad redesign of all Synapse prompts.

## Approach

Extend the `/cortex/fix` orchestrator's `fix-tests` decision branch to distinguish "zero failing tests but coverage below threshold" from a clean pass. Introduce a dedicated coverage-only state in the handoff schema that requires an explicit uplift attempt or a blocker declaration before the target can be marked done. Add evals that reproduce the TradeWing failure mode and validate the new branch deterministically.

## Implementation Steps

1. Map current `/fix` control flow — read `fix.md`, `fix-tests.md`, `shared-handoff-schema.md` and all decision points where coverage-only failures can be misclassified as success.
2. Implement explicit `coverage_only_failure` branch in the orchestrator/handoff state so the tests-target remains active until a coverage uplift attempt is made or an explicit blocker is declared.
3. Extend `fix-tests` agent contract to require: module-selection strategy, test-generation attempt count, and coverage delta capture in the final handoff payload.
4. Add evals and integration scenarios that fail if `/fix` exits without `coverage_attempt_evidence` under coverage-only failure conditions.
5. Add minimal telemetry fields (`coverage_attempt_count`, `coverage_delta`, `blocker_reason`) and document diagnostics for future triage.
6. Update prompt guidance and templates to align with the new contract and avoid policy-only exits.

## Verification Checklist

- **Coverage-only decision branch**: search `.cortex/synapse/prompts/fix.md`, `.cortex/synapse/cursor-agents/fix-tests.md` for `coverage_only` state variable or equivalent gating logic.
- **Required coverage-attempt fields**: grep eval task definitions and report schema for `coverage_attempt_evidence`, `coverage_delta`, `blocker_reason`.
- **Blocker classification path**: confirm `fix-tests.md` has an explicit `BLOCKED` classification when coverage cannot be raised in-session.
- **Files to re-read after changes**: `fix.md`, `fix-tests.md`, `shared-handoff-schema.md`, eval task definitions, any updated report schema/template docs.

## Dependencies

- Existing `/fix` orchestrator and handoff contract (`shared-handoff-schema.md`).
- Eval harness for workflow regression tests.

## Success Criteria

- `/fix` no longer reports success for tests-target when coverage is below threshold and no attempt was made.
- Regression eval reproducing the TradeWing-like scenario passes only when `coverage_attempt_evidence` is present in the handoff payload.
- Final diagnostic output includes explicit coverage-attempt result or explicit blocker rationale.
- Behavior remains bounded by existing max-iteration rules.

## Testing Strategy

Target: 95% coverage on newly introduced orchestration logic.

- **Unit tests**: coverage-only branching logic and blocker classification path.
- **Integration/eval tests**: end-to-end `/fix target=all` scenario with passing tests but coverage below threshold.
- **Negative tests**: policy-only recommendation without an attempt fails validation gate.
- **AAA pattern**: Arrange (set up coverage-below-threshold state) → Act (run `/fix`) → Assert (handoff contains `coverage_attempt_evidence` or `BLOCKED` status).
- No blanket skips; every new conditional branch must have a corresponding test.

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| Handoff schema change breaks existing evals | Add backward-compatible optional fields; mark old fields deprecated, not removed |
| Coverage uplift attempt loops indefinitely | Bound attempts to existing max-iteration cap; declare `BLOCKED` on cap hit |
| Eval harness not available in all environments | Gate new evals behind the same harness feature flag used by existing eval tests |

## Partial Progress Log

- 2026-04-16: Implemented coverage-only tests-target evidence contract in `fix.md` and `fix-tests.md`; added regression checks in `tests/integration/test_commit_workflow_integrity_guards.py` — files: .cortex/synapse/prompts/fix.md, .cortex/synapse/cursor-agents/fix-tests.md, tests/integration/test_commit_workflow_integrity_guards.py
