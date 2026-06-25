---
title: "Promote planning skill to dynamic workflow with data passing"
component: "skill_pack"
work_type: "feature"
status: BLOCKED
priority: "Medium"
created: "2026-06-24"
depends_on: ["skill-dw-quality"]
---

## Goal

Add a `workflow` execution blueprint to the `planning` skill manifest so that
`skill_pack(operation="execute", pack_name="planning")` runs the
create → register → complete cycle as a sequential workflow that automatically
threads `plan_file_name` and `plan_title` between phases, removing the need
for callers to extract and re-inject these values manually.

## Context

The `planning` skill's three-step sequence (create → register → complete) works
correctly when agents follow the `workflow_sequences` string hints. The friction
is data threading: `plan(operation="create")` returns a `plan_file_name` that
must be passed to `plan(operation="register")` and `plan(operation="complete")`.
Agents either hard-code this or re-query the result — a minor but repeated
friction that accumulates across planning-heavy sessions.

Promoting `planning` to a DW is the canonical demonstration of **inter-phase data
passing** via `inputs`/`outputs` maps — the pattern all other skills will reuse.
This plan depends on `skill-dw-quality` because the `SkillWorkflow` model and
`_execute_sequential_workflow` engine are introduced there; this plan only adds
the `planning.json` manifest workflow block and the data-passing wiring to the
existing engine.

## Scope

**in_scope**

- Add `workflow` block to `src/cortex/resources/skills/planning.json` with three phases: create, register, complete
- Wire `inputs`/`outputs` maps so `plan_file_name` and `plan_title` flow from `create` → `register` and `create` → `complete`
- Unit tests for planning workflow execute: happy path, data passing assertions, `complete` skipped when `create` failed

**out_of_scope**

- `SkillWorkflow` / `SkillWorkflowPhase` model changes (introduced in skill-dw-quality)
- `execute` operation implementation (introduced in skill-dw-quality)
- Modifying `plan()` tool internals
- Handling the `plan(operation="enrich")` or `plan(operation="graph")` operations as DW phases (separate concern)

## Approach

Once the engine from `skill-dw-quality` is in place, adding the planning workflow
is a manifest-only change plus tests. The `planning.json` `workflow` block
declares three `SkillWorkflowPhase` entries:

1. **create** — calls `plan(operation="create")`, captures `plan_file_name` and `plan_title` as outputs.
2. **register** — calls `plan(operation="register")`, maps `create.plan_file_name` and `create.plan_title` from prior phase outputs.
3. **complete** — calls `plan(operation="complete")`, maps `create.plan_title`, gated by `condition: "phases.create.status == 'success'"`.

The `_execute_sequential_workflow` engine resolves `inputs` maps by reading
captured `outputs` from the `pipeline_handoff` state for the named prior phase.

## Implementation Steps

1. After `skill-dw-quality` is merged, update
   `src/cortex/resources/skills/planning.json` — add `workflow` block:

   ```json
   {
     "mode": "sequential",
     "description": "Create plan, register in roadmap, and mark complete",
     "phases": [
       { "name": "create",   "tool": "plan", "operation": "create",
         "inputs": {},
         "outputs": ["plan_file_name", "plan_title"] },
       { "name": "register", "tool": "plan", "operation": "register",
         "inputs": {"create.plan_file_name": "plan_file_name",
                    "create.plan_title": "plan_title"},
         "outputs": ["status"] },
       { "name": "complete", "tool": "plan", "operation": "complete",
         "condition": "phases.create.status == 'success'",
         "inputs": {"create.plan_title": "plan_title"},
         "outputs": ["archived_path"] }
     ]
   }
   ```

2. Write unit tests in `tests/tools/test_skill_pack_planning_workflow.py`:
   - Happy path: all three phases run, `plan_file_name` is passed correctly from create to register
   - `complete` skipped when create status is not `success`
   - Missing required input raises `SkillWorkflowInputError` before tool call

3. Smoke-test: call `skill_pack(operation="execute", pack_name="planning", phase_inputs={"create": {"plan_title": "Test", "content": "..."}})` in the test environment with plan tools mocked.

## Verification Checklist

- `skill_pack(operation="load", pack_name="planning")` returns manifest with `workflow` field
- `skill_pack(operation="execute", pack_name="planning", ...)` calls `plan(operation="create")` then `plan(operation="register")` in order, passing `plan_file_name`
- `pipeline_handoff(operation="read", pipeline="skill:planning")` shows create and register phase results
- `pytest tests/tools/test_skill_pack_planning_workflow.py -v` all pass
- Existing `test_skill_pack.py` tests still pass

## Dependencies

- `skill-dw-quality` (introduces `SkillWorkflow` model, `execute` operation, sequential engine)

## Success Criteria

- `skill_pack(operation="execute", pack_name="planning")` resolves and passes `plan_file_name` between phases without caller intervention.
- `complete` phase is correctly skipped when `create` failed.
- ≥95% branch coverage on planning workflow path through `_execute_sequential_workflow`.

## Testing Strategy

Unit tests (AAA pattern):

- **Arrange**: mock `plan` tool to return fixture JSONs for each operation
- **Act**: call `skill_pack(operation="execute", pack_name="planning", phase_inputs={...})`
- **Assert**: mock called with correct `plan_file_name` value injected from prior phase

Negative cases:

- `create` returns error status → `register` and `complete` skipped
- `phase_inputs` missing required `plan_title` for create → structured error before any tool call

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `inputs` key format (`prior_phase.field`) is ambiguous if field name contains `.` | Restrict field names to `[a-z_]+`; validate at manifest load time |
| `plan(operation="complete")` is destructive (archives file) | Gate strictly on `condition`; tests use mocked plan tool, never real filesystem |
| Depends on skill-dw-quality being merged first | Enforce via `depends_on` in YAML frontmatter; roadmap ordering ensures sequencing |
