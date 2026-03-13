---
title: "Add Schema Validation for Agent Handoff Outputs"
component: "synapse/agents"
work_type: "fix"
status: "COMPLETED"
priority: "Medium"
created: "2026-03-07"
execution_order: 13
depends_on: []
---

## Add Schema Validation for Agent Handoff Outputs

**Status**: PENDING
**Priority**: Medium
**Complexity**: Medium
**Category**: Fix
**Component**: synapse/agents
**Work Type**: fix
**Execution Order**: 13

## Goal

Add programmatic validation of agent outputs against `shared-handoff-schema.md` before pipeline-state-tracker checkpoints them, preventing malformed results from corrupting downstream steps.

## Context

- `shared-handoff-schema.md` defines required fields for agent results (e.g., `PlanCreatorResult`, `ReviewResult`), but validation is mentioned in prose only — not enforced.
- Malformed agent results can corrupt downstream steps silently.
- Pipeline-state-tracker accepts any JSON via `checkpoint_write` without validation.

## Implementation Steps

### Step 1: Define required fields per result type

**File**: `.cortex/synapse/agents/shared-handoff-schema.md`

Add a machine-readable section listing required fields per schema:

```markdown
## Required Fields (Machine-Readable)

| Schema | Required Fields |
|---|---|
| CommonChecklistResult | status, project_root, primary_language, memory_bank_loaded |
| PlanCreatorResult | status, plan_path, plan_title, similarity_decision |
| ReviewResult | status, metrics, overall_score, summary |
| CommitResult | status, commit_hash, files_changed |
```

### Step 2: Add validation instruction to pipeline-state-tracker

**File**: `.cortex/synapse/agents/pipeline-state-tracker.md`

Add to `checkpoint_write` section:

```markdown
**GATE**: Before writing a checkpoint, validate that the agent result contains ALL required fields for its schema type (see shared-handoff-schema.md Required Fields table). If any required field is missing, set `status: "validation_error"` and report which fields are missing. Do NOT write a checkpoint with missing required fields.
```

### Step 3: Add validation to orchestrator prompts

**Files**: `commit.md`, `create-plan.md`, `review.md`

After each agent delegation, add: "Verify agent result contains required fields per `shared-handoff-schema.md` before passing to pipeline-state-tracker."

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `Required Fields` | `shared-handoff-schema.md` | Machine-readable table |
| `validation_error` | `pipeline-state-tracker.md` | Validation failure handling |

## Dependencies

- None.

## Success Criteria

- Required fields are defined per schema type.
- Pipeline-state-tracker rejects incomplete results.
- Orchestrator prompts validate before checkpointing.

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt/agent changes)
- **Manual verification**: Submit incomplete agent result and verify rejection.
