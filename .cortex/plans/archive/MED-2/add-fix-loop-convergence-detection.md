---
title: "Add Fix Loop Non-Convergence Detection"
component: "synapse/prompts/commit"
work_type: "fix"
status: "COMPLETED"
priority: "Medium"
created: "2026-03-07"
execution_order: 14
depends_on: []
---

## Add Fix Loop Non-Convergence Detection

**Status**: COMPLETED
**Priority**: Medium
**Complexity**: Low
**Category**: Fix
**Component**: synapse/prompts/commit
**Work Type**: fix
**Execution Order**: 14

## Goal

Detect oscillating fix loops (fix A introduces B, fix B reintroduces A) and abort early instead of consuming all 3 iterations without converging.

## Context

- Commit.md Step 12 allows up to 3 fix iterations. Each iteration runs fixes and re-checks.
- Fix loops can oscillate: formatting fix breaks type-check, type-check fix breaks formatting.
- The 3-iteration limit prevents infinite loops but wastes 2 iterations on non-converging fixes.
- Current behavior: "3 iterations exhausted, commit blocked."
- Desired: "Violation count not decreasing after iteration 2, aborting early."

## Implementation Steps

### Step 1: Add violation tracking to commit.md fix loop

**File**: `.cortex/synapse/prompts/commit.md` (Step 12 fix loop section)

Add instruction:

```markdown
**Fix Loop Convergence Check**:
After each fix iteration, record the total violation count.

- Iteration 1: N1 violations
- Iteration 2: N2 violations
- If N2 >= N1: **ABORT** — "Fix loop not converging (N1→N2 violations). Likely oscillation. Commit blocked. Manual intervention required."
- If N2 < N1: continue to iteration 3 if needed.
- Iteration 3: N3 violations
- If N3 > 0: commit blocked (max iterations).
```

### Step 2: Add convergence tracking to pipeline-state-tracker

**File**: `.cortex/synapse/agents/pipeline-state-tracker.md`

Add to fix loop state:

```json
{
  "fix_iterations": [
    {"iteration": 1, "violation_count": 5, "violations": ["..."]},
    {"iteration": 2, "violation_count": 3, "violations": ["..."]}
  ]
}
```

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `convergence` or `N2 >= N1` or `not converging` | `commit.md` | Early abort logic present |

## Dependencies

- None (but coordinates with `simplify-commit-pipeline-structure` for step naming).

## Success Criteria

- Fix loops abort after iteration 2 if violation count is not decreasing.
- Abort message clearly indicates oscillation.
- Non-oscillating fix loops still get 3 full iterations.

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt changes)
- **Manual verification**: Introduce two mutually-conflicting fixes and verify early abort.
