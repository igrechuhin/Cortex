---
title: "Delta Specs for Plans"
component: planning
work_type: feature
status: PENDING
priority: Medium
created: 2026-04-06
depends_on: []
---

## Goal

Track what changed between plan revisions using explicit delta sections (`ADDED / MODIFIED / REMOVED / RENAMED`). Plans currently are point-in-time snapshots that are silently rewritten when scope changes. Delta specs make scope shifts explicit, auditable, and visible across sessions.

## Context

Inspired by OpenSpec's semantic delta specs with merge operations. In Cortex, when a plan is enriched, the diff between versions is lost — the roadmap just shows the latest state. For long-running multi-session work, "what changed since last session" is opaque. Delta tracking solves this by appending change records to the plan file instead of silently overwriting sections.

## Implementation Steps

### Step 1: Define delta record schema

- Add `PlanDelta` Pydantic model in `src/cortex/core/models.py`:
  - `timestamp: datetime`
  - `author: str` (agent or human)
  - `added: list[str]` — new steps/requirements
  - `modified: list[str]` — changed steps/requirements (with old → new)
  - `removed: list[str]` — deleted steps/requirements
  - `renamed: list[str]` — renamed items
  - `reason: str` — why the change was made
- Apply operations in strict order: `RENAMED → REMOVED → MODIFIED → ADDED` (same as OpenSpec).

**Verification**: Model importable, fully typed, validates correctly.

### Step 2: Add `## Change History` section to plan template

- Update the plan creation template in `src/cortex/tools/plan.py` to include a `## Change History` section at the end, initially empty.
- Each delta entry renders as:

```markdown
### 2026-04-06T14:00Z — agent

**ADDED**

- Step 4: Add constitutional compliance check

**MODIFIED**

- Step 2: Expanded verification criteria (was: "file exists"; now: "file exists and renders correctly")

**Reason**: Scope expanded after constitutional layer feature merged.
```

**Verification**: New plans include an empty `## Change History` section.

### Step 3: Implement delta computation in `plan(operation="enrich")`

- Before writing updated content, diff the old and new plan:
  1. Parse existing `## Implementation Steps` into a dict keyed by step header.
  2. Parse incoming new content similarly.
  3. Compute sets: added, removed, modified (text changed), renamed (header changed, body same).
  4. Construct a `PlanDelta` record.
  5. Append the record to `## Change History` (never overwrite history).
- Use `think()` for complex diffing logic.

**Verification**: Enriching a plan with new steps appends a correctly populated delta entry; original history is preserved.

### Step 4: Expose delta summary in `plan(operation="get")`

- When returning plan details, include a `change_count` field and the latest delta summary.
- This allows `session()` and `implement-code` to quickly see "this plan was modified 3 times; last change added 2 steps" without reading the full file.

**Verification**: `plan(operation="get")` response includes `change_count` and `latest_delta`.

### Step 5: Surface delta in `cortex://context` resource

- When the context resource loads plans, include the last delta entry (if any) for active plans.
- Prefix with `[LAST CHANGE: <date>]` so agents immediately see what shifted.

**Verification**: Context output for an active plan includes last delta; no noise for unchanged plans.

### Step 6: Tests

- Unit: `PlanDelta` model validation.
- Unit: Delta computation — added steps detected correctly; removed steps detected; modified steps detected; renamed steps detected; empty diff produces no history entry.
- Unit: History append is idempotent (no duplicate entries on repeated enrich with same content).
- Integration: Full enrich cycle with real temp plan file.

**Verification**: All tests pass, ≥ 95% coverage on new code.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `PlanDelta` class | `src/cortex/core/` | `models.py` |
| 2 | `Change History` section | `src/cortex/tools/plan.py` | plan template |
| 3 | Delta computation logic | `src/cortex/tools/plan.py` | `enrich` branch |
| 4 | `change_count`, `latest_delta` | `src/cortex/tools/plan.py` | `get` branch |
| 5 | Delta in context | `src/cortex/resources/context.py` | full file |
| 6 | Test files | `tests/` | new test files |

## Dependencies

- Existing `plan` tool
- Existing `cortex://context` resource
- `PlanDelta` model (new, Step 1)

## Success Criteria

- Every plan enrichment appends a delta entry; existing history is never overwritten.
- `plan(operation="get")` returns delta metadata.
- Context resource surfaces the last change for active plans.
- No `Any` types; functions ≤ 30 lines; ≥ 95% coverage.

## Testing Strategy

Target: 95% coverage on all new code paths.

- **Unit**: Model validation; diff computation (parametrized across all four delta types); history append.
- **Integration**: Enrich cycle with temp file; verify history grows monotonically.
- **Edge cases**: Plan with no prior history; identical content (no delta written); plan with all four delta types in one enrich.
