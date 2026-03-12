---
title: "Reduce Redundant Pipeline Checks in Commit Pipeline"
component: "synapse/prompts/commit"
work_type: "optimize"
status: "PENDING"
priority: "High"
created: "2026-03-07"
execution_order: 12
depends_on:
  - "add-mcp-circuit-breaker-pattern"
  - "simplify-commit-pipeline-structure"
---

## Reduce Redundant Pipeline Checks in Commit Pipeline

**Status**: PENDING
**Priority**: High
**Complexity**: Medium
**Category**: Optimization
**Component**: synapse/prompts/commit
**Work Type**: optimize
**Execution Order**: 12
**Depends On**: add-mcp-circuit-breaker-pattern, simplify-commit-pipeline-structure

## Goal

Eliminate ~40% redundant check execution in the commit pipeline by having Phase A results carry forward and Step 12 only re-running checks when state has changed.

## Context

- Type-check runs in Phase A and again in Step 12.2. Quality check runs in Phase A, Step 3, Step 12.3, and Step 12.6.
- Phase 89 added `skip_if_clean` optimization but sessions still show extensive redundant execution.
- Each redundant check costs MCP tool calls and LLM tokens.

## Implementation Steps

### Step 1: Define dirty-state tracking in pipeline-state-tracker

**File**: `.cortex/synapse/agents/pipeline-state-tracker.md`

Add to state schema:

```json
{
  "dirty_checks": {
    "type_check": false,
    "quality": false,
    "tests": false,
    "markdown_lint": false,
    "formatting": false
  },
  "last_clean_results": {
    "type_check": {"passed": true, "step": "A.4", "timestamp": "..."},
    ...
  }
}
```

### Step 2: Update commit.md to set dirty flags

After any fix loop iteration that modifies files, set the relevant dirty flags:

- Formatting fix → `formatting: true`, `type_check: true`, `quality: true`
- Quality fix → `quality: true`, `type_check: true`
- Memory bank update → no dirty flags (not code)

### Step 3: Update Step 12 (final validation) to skip clean checks

In the final validation gate, before running each check:

1. Read `dirty_checks` from pipeline state.
2. If `dirty_checks[check] == false` AND `last_clean_results[check].passed == true`: skip with "Skipped (clean since Phase A)".
3. If dirty or no previous result: run the check.

### Step 4: Log skip decisions

When skipping a check, log: "Skipping {check} in final validation — passed in {step} and no files changed since."

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `dirty_checks` | `pipeline-state-tracker.md` | Schema defined |
| `skip.*clean` or `Skipped.*clean` | `commit.md` | Skip logic present |

## Dependencies

- `add-mcp-circuit-breaker-pattern` (checkpoint infrastructure)
- `simplify-commit-pipeline-structure` (step naming)

## Success Criteria

- Checks that passed in Phase A and had no subsequent file changes are skipped in final validation.
- Skip decisions are logged.
- No quality regressions (all checks still run when files change).

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt changes)
- **Manual verification**: Run commit pipeline on a clean change and count MCP tool calls vs. before.
