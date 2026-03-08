# Add Circuit-Breaker Pattern for MCP Pipeline Failures

**Status**: PENDING
**Priority**: Critical
**Complexity**: Medium
**Category**: Fix / Infrastructure
**Component**: synapse/prompts, synapse/agents
**Work Type**: fix
**Execution Order**: 3

## Goal

Add a standardized circuit-breaker pattern to Synapse prompts so that 3+ consecutive MCP tool failures cause a clean pipeline abort with persisted state, instead of cascading failures or session-killing stalls.

## Context

- Sessions commit-7 and impl-17 both show MCP server drops at Step 12.5-12.7 of the commit pipeline. The agent correctly blocked the commit but could not self-recover. The user had to manually reconnect MCP each time.
- `shared-conventions.md` currently defines max-retry limits (lines 55-61): fix loops max 3 iterations, MCP retries max 2. But there is no **cross-step** circuit-breaker — each step retries independently.
- `pipeline-state-tracker.md` already supports `checkpoint_write` with step status and `errors_encountered` fields. State is stored in `.cortex/.session/{pipeline_name}-pipeline-state.json`.
- External review (2026-03-07) classified this as **Critical** severity.

## Implementation Steps

### Step 1: Define circuit-breaker convention in shared-conventions.md

**File**: `.cortex/synapse/agents/shared-conventions.md` (after line 61)

Add a new section:

```markdown
## Circuit-Breaker Pattern

When **3 consecutive MCP tool calls fail** (across any steps in the current pipeline):

1. **Persist pipeline state** via `checkpoint_write` with `status: "circuit_breaker_tripped"` and `last_successful_step`.
2. **Report to user**: "MCP circuit-breaker tripped after 3 consecutive failures. Pipeline state saved. To resume: re-run the pipeline — it will pick up from step {last_successful_step + 1}."
3. **Do NOT** continue executing remaining steps.
4. **Do NOT** attempt to roll back completed steps (they are already checkpointed).

**Counter reset**: The failure counter resets to 0 after any successful MCP tool call.
```

### Step 2: Add resume-from-checkpoint logic to commit.md

**File**: `.cortex/synapse/prompts/commit.md` (at the start of execution steps)

Add before Step 0:

```markdown
### Step -1: Check for interrupted pipeline state

1. Check `.cortex/.session/commit-pipeline-state.json` exists and has `status: "circuit_breaker_tripped"`.
2. If yes: read `last_successful_step`, report "Resuming from step {N}", skip to that step + 1.
3. If no: proceed normally from Step 0.
```

### Step 3: Update pipeline-state-tracker agent

**File**: `.cortex/synapse/agents/pipeline-state-tracker.md`

Add `circuit_breaker_failures: int` to the state schema. Document the `circuit_breaker_tripped` status value. Add `resume_from_step` field.

### Step 4: Add circuit-breaker reference to create-plan.md and review.md

**Files**: `.cortex/synapse/prompts/create-plan.md`, `.cortex/synapse/prompts/review.md`

Add a one-liner in the error handling section: "Follow circuit-breaker pattern per `shared-conventions.md` for consecutive MCP failures."

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `circuit_breaker` | `.cortex/synapse/` | Present in shared-conventions, pipeline-state-tracker, commit.md |
| `resume_from_step` or `last_successful_step` | `.cortex/synapse/` | Present in commit.md and pipeline-state-tracker |

## Dependencies

- None. This is a prompt/agent-level change only.

## Success Criteria

- `shared-conventions.md` defines circuit-breaker pattern.
- `commit.md` has resume-from-checkpoint step.
- `pipeline-state-tracker.md` documents `circuit_breaker_tripped` status.
- `create-plan.md` and `review.md` reference the pattern.

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt changes only)
- **Manual verification**: Simulate MCP failure during commit pipeline and verify circuit-breaker triggers.

## Risks & Mitigation

- **Risk**: Stale pipeline state from a previous session causes incorrect resume. **Mitigation**: Include `started_at` timestamp; ignore state files older than 1 hour.
