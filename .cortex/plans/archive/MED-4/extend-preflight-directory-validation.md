---
title: "Extend Pre-Flight Directory Validation"
component: "synapse/agents/common-checklist"
work_type: "fix"
status: "COMPLETED"
priority: "Medium"
created: "2026-03-07"
execution_order: 16
depends_on: []
---

## Extend Pre-Flight Directory Validation

**Status**: COMPLETED
**Priority**: Medium
**Complexity**: Low
**Category**: Fix
**Component**: synapse/agents/common-checklist
**Work Type**: fix
**Execution Order**: 16

## Goal

Extend the common-checklist agent to verify all operational directories (plans/, reviews/, .session/) exist on disk, not just core memory bank files.

## Context

- `common-checklist.md` Phase 2.1 validates 3 critical memory bank files (activeContext, roadmap, progress) are non-empty.
- It does NOT validate that operational directories (plans/, reviews/, .session/) exist.
- Missing directories cause silent write failures when creating plans or reviews.
- `get_structure_info()` returns paths for all these directories but common-checklist only checks files.

## Implementation Steps

### Step 1: Add directory existence check to common-checklist

**File**: `.cortex/synapse/agents/common-checklist.md` (after Phase 2.1)

Add Phase 2.2:

```markdown
### Phase 2.2: Operational Directory Validation

Verify these paths from `get_structure_info()` exist as directories:

- `structure_info.paths.plans`
- `structure_info.paths.reviews` (if present)
- `.cortex/.session/`

For each missing directory:

1. Report: "Missing directory: {path}"
2. Create it: `mkdir -p {path}`
3. Log: "Created missing directory: {path}"

**CHECK** (not GATE): Missing directories are auto-created, not pipeline-blocking.
```

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `Phase 2.2` or `Directory Validation` | `common-checklist.md` | Present |
| `mkdir` or `create.*directory` | `common-checklist.md` | Auto-creation logic |

## Dependencies

- None.

## Success Criteria

- Pre-flight validates operational directories exist.
- Missing directories are auto-created with a log message.
- Pipeline is not blocked (CHECK, not GATE).

## Testing Strategy

- **Coverage Target**: N/A (Synapse agent changes)
- **Manual verification**: Delete .cortex/.session/ and run common-checklist; verify it recreates it.
