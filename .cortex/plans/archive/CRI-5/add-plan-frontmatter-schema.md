---
title: "Add YAML Frontmatter Schema for Plan Files"
component: "synapse/prompts/create-plan, synapse/agents/plan-creator"
work_type: "fix"
status: "COMPLETED"
priority: "Critical"
created: "2026-03-07"
execution_order: 5
depends_on: []
---

## Add YAML Frontmatter Schema for Plan Files

**Status**: COMPLETED
**Priority**: Critical
**Complexity**: Medium
**Category**: Fix / Infrastructure
**Component**: synapse/prompts/create-plan, synapse/agents/plan-creator
**Work Type**: fix
**Execution Order**: 5

## Goal

Replace subjective prose-based plan similarity judgment with deterministic scoring based on enforced YAML frontmatter fields (`component`, `work_type`, `status`).

## Context

- `create-plan.md` Step 1.3 asks the LLM "Does it target the same component? Does it address the same type of work?" — this is subjective and non-deterministic.
- Plan files currently have ad-hoc markdown headers (e.g., `**Status**: PENDING`, `**Component**: ...`) but no enforced schema.
- The `similarity_decision` state lives only in LLM context and can be lost during context compression.
- External review classified this as **Critical** (most frequently identified weakness across all analysis files).

## Implementation Steps

### Step 1: Define the frontmatter schema

All plan files must start with YAML frontmatter:

```yaml
---
title: "Fix TODO Scanner Exclusion Patterns"
component: "validation/roadmap_sync"
work_type: "fix"          # fix | refactor | feature | optimize | docs | infrastructure
status: "PENDING"         # PENDING | IN_PROGRESS | COMPLETED | ARCHIVED
priority: "Critical"      # Critical | High | Medium | Low
created: "2026-03-07"
depends_on: []            # list of plan file names (without .md)
---
```

### Step 2: Update plan-creator agent to emit frontmatter

**File**: `.cortex/synapse/agents/plan-creator.md`

Add instruction: "All plan files MUST begin with YAML frontmatter containing: title, component, work_type, status, priority, created, depends_on. The `**Status**:` markdown headers are kept for backward compatibility but frontmatter is the source of truth."

### Step 3: Update create-plan.md similarity check with deterministic scoring

**File**: `.cortex/synapse/prompts/create-plan.md` (Step 1.3)

Replace the subjective questions with:

```markdown
For each existing plan with YAML frontmatter, compute similarity score:

- Same `component` value: +2
- Same `work_type` value: +1
- Title keyword overlap (>50% shared words): +1

**Decision**:

- Score >= 3: **enrich** the existing plan
- Score 1-2: **ask user** whether to enrich or create new
- Score 0: **create new** plan

For plans without frontmatter, fall back to the current prose comparison.
```

### Step 4: Add frontmatter to all existing active plans

Run through any active plans in `.cortex/plans/` and add frontmatter. (Currently no active plans, so this is a no-op but documents the migration path.)

### Step 5: Update create-plan.md to persist similarity_decision

**File**: `.cortex/synapse/prompts/create-plan.md` (Step 1.4)

Add: "Persist `similarity_decision`, `target_plan_path`, and `decision_rationale` via `checkpoint_write` immediately after Step 1 completes. Recall at Step 3."

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `frontmatter` or `---` schema | `plan-creator.md` | Frontmatter requirement documented |
| `similarity score` or `+2` | `create-plan.md` | Deterministic scoring replaces prose |
| `checkpoint_write` | `create-plan.md` | similarity_decision persisted |

## Dependencies

- None (but benefits from circuit-breaker checkpoint infrastructure).

## Success Criteria

- `plan-creator.md` requires YAML frontmatter on all new plans.
- `create-plan.md` uses numeric scoring for similarity.
- `similarity_decision` is checkpointed, not just held in context.
- Zero duplicate plans created in 10 consecutive operations.

## Testing Strategy

- **Coverage Target**: N/A (Synapse prompt changes)
- **Manual verification**: Create 3 plans targeting the same component and verify enrichment triggers correctly.

## Risks & Mitigation

- **Risk**: Archived plans without frontmatter cause errors during comparison. **Mitigation**: Skip plans without frontmatter during scoring; fall back to prose comparison.
