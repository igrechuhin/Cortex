---
title: "Persist Pipeline State Decisions via Checkpoints"
component: "synapse/prompts, synapse/agents"
work_type: "fix"
status: "COMPLETED"
priority: "High"
created: "2026-03-07"
execution_order: 8
depends_on:
  - "add-mcp-circuit-breaker-pattern"
---

# Persist Pipeline State Decisions via Checkpoints

**Status**: COMPLETED
**Priority**: High
**Complexity**: Low
**Category**: Fix
**Component**: synapse/prompts, synapse/agents
**Work Type**: fix
**Execution Order**: 8
**Depends On**: add-mcp-circuit-breaker-pattern

## Goal

Ensure critical LLM-generated decisions (`similarity_decision`, `target_plan_path`, `primary_language`) are persisted via pipeline-state-tracker checkpoints instead of relying solely on LLM context window, preventing data loss during context compression.

## Context

- In `create-plan.md`, `similarity_decision` (enrich vs. create new), `target_plan_path`, and `decision_rationale` live only in context between Steps 1 and 3. Context compression could lose or distort them.
- In `commit.md`, `primary_language` is detected by `common-checklist` and passed through 8 sequential agents. Context compression could cause wrong-language analysis.
- `pipeline-state-tracker.md` already supports `checkpoint_write` with arbitrary step data. The infrastructure exists; it's just not used for these decisions.

## Implementation Steps

### Step 1: Add checkpoint_write after create-plan.md Step 1

**File**: `.cortex/synapse/prompts/create-plan.md` (end of Step 1)

Add instruction: "After recording the similarity decision, persist it: `checkpoint_write(pipeline_name='create-plan', step='similarity_check', result={similarity_decision, target_plan_path, decision_rationale})`"

### Step 2: Add checkpoint_read before create-plan.md Step 3

**File**: `.cortex/synapse/prompts/create-plan.md` (start of Step 3)

Add instruction: "Before creating/enriching, read back the similarity decision: `checkpoint_read(pipeline_name='create-plan', step='similarity_check')` to ensure decision was not lost during context compression."

### Step 3: Add primary_language to commit pipeline initial checkpoint

**File**: `.cortex/synapse/prompts/commit.md` (after common-checklist completes in Step 0)

Add instruction: "Include `primary_language` in the Phase A checkpoint: `checkpoint_write(pipeline_name='commit', step='phase_a_init', result={primary_language, ...})`"

### Step 4: Document which decisions require checkpointing

**File**: `.cortex/synapse/agents/pipeline-state-tracker.md`

Add a "Critical Decisions" section listing decisions that MUST be checkpointed:

- `similarity_decision` (create-plan pipeline)
- `primary_language` (commit, review pipelines)
- `coverage_threshold_override` (commit pipeline, if overridden)

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `checkpoint_write.*similarity` | `create-plan.md` | Present after Step 1 |
| `checkpoint_read.*similarity` | `create-plan.md` | Present before Step 3 |
| `primary_language.*checkpoint` | `commit.md` | Present after common-checklist |

## Dependencies

- `add-mcp-circuit-breaker-pattern` (for checkpoint infrastructure)

## Success Criteria

- All critical decisions are checkpointed immediately after generation.
- All critical decisions are read back before consumption.
- Pipeline-state-tracker documents which decisions require checkpointing.

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt changes)
- **Manual verification**: Run create-plan with a long context and verify similarity decision survives.
