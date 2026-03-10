---
title: "Simplify Commit Pipeline Structure"
component: "synapse/prompts/commit"
work_type: "refactor"
status: "PENDING"
priority: "High"
created: "2026-03-07"
execution_order: 6
depends_on:
  - "add-mcp-circuit-breaker-pattern"
  - "add-commit-pipeline-rollback"
  - "reduce-prompt-alignment-test-fragility"
---

# Simplify Commit Pipeline Structure

**Status**: PENDING
**Priority**: High
**Complexity**: High
**Category**: Refactoring
**Component**: synapse/prompts/commit
**Work Type**: refactor
**Execution Order**: 6
**Depends On**: add-mcp-circuit-breaker-pattern, add-commit-pipeline-rollback, reduce-prompt-alignment-test-fragility

## Goal

Restructure the commit pipeline from 15+ steps with half-step numbering to 3 clear macro-phases with tabular sub-steps, reducing cognitive load by ~60%.

## Context

- `commit.md` currently has Steps 0, 0.5, 1, 1.5, 2, 3, 3.5, 3.6, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 — ~25 decision points, 12 agent delegations, 2 fix loops.
- Half-step numbering (0.5, 1.5, 3.5, 3.6) indicates organic growth without restructuring.
- Sessions show agents skipping intermediate validation steps (3.5-3.6) and intermediate state checks (Step 10).
- External review rated this as "HIGHEST COGNITIVE LOAD" and primary improvement target.
- **CRITICAL**: This plan MUST execute AFTER `reduce-prompt-alignment-test-fragility` (plan 3.8) because changing commit.md will break substring-assertion tests. Refactor tests first, then restructure pipeline.

## Implementation Steps

### Step 1: Map current steps to new phases

Current → New mapping:

| Current Steps | New Phase | New Sub-step |
|---|---|---|
| Step -1 (resume check) | Pre-flight | P.1 Resume check |
| Step -0.5 (snapshot) | Pre-flight | P.2 Snapshot |
| Step 0 (common-checklist) | Pre-flight | P.3 Common checklist |
| Step 0.5 (quality preflight) | Phase A: Quality | A.1 Quality gate |
| Step 1 (formatting) | Phase A: Quality | A.2 Formatting |
| Step 1.5 (markdown lint) | Phase A: Quality | A.3 Markdown lint |
| Step 2 (type-check) | Phase A: Quality | A.4 Type check |
| Step 3 (quality check) | Phase A: Quality | A.5 Quality check |
| Step 3.5-3.6 (intermediate validation) | Phase A: Quality | A.6 Intermediate validation |
| Step 4 (tests) | Phase A: Quality | A.7 Tests |
| Step 5-8 (docs/memory bank) | Phase B: Documentation | B.1-B.4 |
| Step 9-11 (staging/commit/message) | Phase C: Commit | C.1-C.3 |
| Step 12 (final validation) | Phase C: Commit | C.4 Final gate |
| Step 13-15 (post-commit) | Phase C: Commit | C.5 Post-commit |

### Step 2: Rewrite commit.md with new structure

**File**: `.cortex/synapse/prompts/commit.md`

Replace the step-by-step list with:

1. **Pre-flight** section (resume, snapshot, common-checklist) — 3 sub-steps in a table
2. **Phase A: Quality Gate** — 7 sub-steps in a table with columns: Sub-step | Agent | GATE/CHECK | Description
3. **Phase B: Documentation** — 4 sub-steps in a table
4. **Phase C: Commit & Validate** — 5 sub-steps in a table

Each table row is one line. Total cognitive load drops from ~150 lines of step descriptions to ~40 lines of tables.

### Step 3: Update pipeline-state-tracker references

Update step IDs in pipeline-state-tracker documentation to use the new naming (A.1, A.2, ... instead of step_0, step_0.5, ...).

### Step 4: Update prompt-alignment tests

After the test refactoring (dependency), update any remaining structural tests to match the new phase/sub-step naming.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `Step 0.5` or `Step 1.5` or `Step 3.5` | `commit.md` | Zero matches (half-steps removed) |
| `Phase A` and `Phase B` and `Phase C` | `commit.md` | All three phases present |
| `test_commit_workflow` | `tests/integration/` | All tests pass |

## Dependencies

- `reduce-prompt-alignment-test-fragility` (MUST complete first — otherwise test refactoring is needed twice)
- `add-mcp-circuit-breaker-pattern` (resume check references circuit-breaker state)
- `add-commit-pipeline-rollback` (snapshot step references rollback)

## Success Criteria

- Commit pipeline uses 3 macro-phases with tabular sub-steps.
- No half-step numbering remains.
- All existing tests pass after update.
- Agent step-skipping rate decreases (qualitative, measured in next 5 sessions).

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt restructuring)
- **Integration**: Run full commit pipeline and verify all phases execute.
- **Regression**: Ensure prompt-alignment tests still pass (after refactoring).

## Risks & Mitigation

- **Risk**: Agents trained on old step numbers may be confused. **Mitigation**: Keep a "Migration note" at the top of commit.md for 2 weeks: "Steps have been renumbered. See Phase A/B/C structure below."
