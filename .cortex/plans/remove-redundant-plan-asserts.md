---
title: "Remove redundant asserts in plan.py"
component: tools/plans
work_type: fix
status: PENDING
priority: low
created: 2026-03-21
depends_on: []
---

## Goal

Remove the redundant `assert` statements at lines 129 and 144 in `plan.py` that follow guard-return clauses, or convert them to type-narrowing comments for pyright.

## Context

- **Cortex review REV-2026-03-13-3** (Low severity, carried): `assert plan_title is not None and summary is not None` immediately after `if not plan_title or not summary: return ...` — the assert is unreachable and adds no value.

## Implementation Steps

### Step 1: Remove or convert redundant asserts

Read `plan.py` lines 120-150. Remove the `assert` statements. If pyright needs type narrowing, replace with `# pyright: narrowing handled by guard above` or restructure the guard to satisfy the type checker without assert.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| `assert plan_title` | `src/cortex/tools/plans/plan.py` | Lines 125-150 |
| pyright errors after removal | Type check output | N/A |

### Step 2: Run type check and quality gate

Verify pyright passes without the asserts. If type narrowing fails, add explicit `if` guards that pyright recognizes.

**Verification Checklist:**

| What to search for | Search scope | Files to re-read |
|---|---|---|
| pyright errors in plan.py | Type check output | `plan.py` |

## Dependencies

- None.

## Success Criteria

- No redundant `assert` after guard returns.
- pyright strict mode passes.
- Quality gate passes.

## Testing Strategy

- Existing plan tests should cover the paths.
- No new tests needed (removing dead code).
- Target: 95% coverage maintained.
