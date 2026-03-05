# Phase 89: Commit Pipeline Efficiency — Reduce Redundant Check Runs

**Status**: PENDING
**Priority**: Medium
**Complexity**: Medium
**Category**: Refactoring / Performance

## Goal

Reduce the number of redundant quality check invocations in the commit pipeline. Currently, the 16-step pipeline runs the same checks multiple times (Phase A preflight, then Step 12 final gate), resulting in long commit times.

## Context

- Chat sessions show commit pipelines running **4880+ tests twice** (once in Phase A, once in Step 12.7).
- Type checking runs at least 3 times: Phase A, Step 12.2, and as a sub-check of quality in Step 12.3.
- Format checking runs 3 times: Phase A, Step 12.1.1, Step 12.1.2 (plus CI parity).
- A typical commit session takes 30+ minutes primarily due to redundant checks.
- The pipeline was designed for safety but the duplication is excessive.

## Approach

1. Analyze which Step 12 re-runs are truly necessary (only re-run if code changed between Phase A and Step 12).
2. Add a "dirty check" — if no files changed between Phase A and Step 12, skip re-runs.
3. Implement incremental checking where possible.

## Implementation Steps

### Step 1: Audit pipeline redundancy

- Map each check invocation across the pipeline (Phase A, Phase B, Step 12.0–12.7).
- Identify which checks are truly repeated vs which verify different things.
- Determine minimum necessary check set for Step 12.

### Step 2: Add dirty-state tracking

- After Phase A passes, record a hash of staged files.
- Before each Step 12 check, compare current staged files hash.
- If unchanged, skip the re-run and report "already verified in Phase A."

### Step 3: Optimize Step 12

- Step 12.7 (tests + coverage): Only re-run if source files changed after Phase A.
- Step 12.2 (type check): Only re-run if Python files changed after Phase A.
- Step 12.1 (format): Only re-run if files were formatted in Phase A.

### Step 4: Update commit prompt

- Update `.cortex/synapse/prompts/commit.md` to document the optimization.
- Make skip behavior visible in output: "Step 12.7: Skipped (no changes since Phase A)."

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| Duplicate test runs | Commit pipeline output | Single test run when no changes between phases |

## Dependencies

- None.

## Success Criteria

- Commit pipeline completes in < 50% of current time when no files change between phases.
- Safety is preserved: if files change between Phase A and Step 12, full re-runs execute.
- Pipeline output clearly indicates skipped checks with rationale.

## Testing Strategy

- **Coverage Target**: 95%+ for dirty-state tracking logic.
- **Unit Tests**: Test hash comparison for staged files.
- **Integration Tests**: Test full pipeline with and without intermediate changes.

## Risks & Mitigation

- **Risk**: Skipping checks misses a regression. **Mitigation**: Hash comparison is conservative — any file change triggers re-run.

## Timeline

- Estimated: 1 day.
