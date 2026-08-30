---
title: "Reduce Oversized Source Modules (>400 lines)"
component: "src/cortex (multiple)"
work_type: refactor
status: DONE
priority: Medium
created: 2026-03-07
execution_order: 21
depends_on: []
---

## Reduce Oversized Source Modules (>400 lines)

**Status**: PENDING
**Priority**: Medium
**Complexity**: High
**Category**: Refactoring
**Component**: src/cortex (multiple)
**Work Type**: refactor
**Execution Order**: 21

## Goal

Split the top 5 largest source modules (>550 lines each) to comply with the 400-line architectural constraint.

## Context

Phase 81 already started this work (split `rules_manager.py` into `rules_loading` and `rules_matching`). 15 files still exceed 400 lines. Top 5:

| File | Lines |
|---|---|
| `src/cortex/optimization/rules_manager.py` | 617 |
| `src/cortex/core/mcp_failure_handler.py` | 601 |
| `src/cortex/core/container.py` | 591 |
| `src/cortex/structure/structure_migration.py` | 589 |
| `src/cortex/refactoring/split_recommender.py` | 589 |

## Implementation Steps

### Step 1: Analyze each file for split points

For each of the 5 files:

1. Read the file and identify logical groupings (classes, function clusters).
2. Identify natural split boundaries (e.g., public API vs. internal helpers, different concerns).
3. Propose a split that results in files <= 400 lines each.

### Step 2: Split rules_manager.py (617 lines)

Phase 81 already split into `rules_loading` and `rules_matching`. Verify the original is still 617 lines — if so, the split didn't complete. Finish it.

### Step 3: Split mcp_failure_handler.py (601 lines)

Likely split: failure detection/classification vs. recovery/retry logic.

### Step 4: Split container.py (591 lines)

Likely split: container setup/registration vs. provider factories.

### Step 5: Split structure_migration.py (589 lines)

Likely split: migration detection vs. migration execution.

### Step 6: Split split_recommender.py (589 lines)

Likely split: analysis/scoring vs. recommendation generation.

### Step 7: Update imports and run tests

For each split:

1. Update all imports across the codebase.
2. Run full test suite.
3. Verify no circular imports.

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| Files > 400 lines | `src/cortex/` | Top 5 reduced to <= 400 |
| Import errors | `pytest` | Zero |

## Dependencies

- None (can be done incrementally, one file at a time).

## Success Criteria

- Top 5 oversized files are split to <= 400 lines each.
- All tests pass.
- No circular imports.

## Testing Strategy

- **Coverage Target**: 95% for all split modules
- **Unit tests**: Existing tests should pass unchanged
- **Integration**: Import graph validation (no cycles)

## Risks & Mitigation

- **Risk**: Splitting creates circular imports. **Mitigation**: Use dependency injection and interface modules.
