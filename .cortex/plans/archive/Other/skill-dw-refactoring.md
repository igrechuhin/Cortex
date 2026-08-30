---
title: "Promote refactoring skill to dynamic workflow with analysis data passing"
component: "skill_pack"
work_type: feature
status: BLOCKED
priority: Medium
created: 2026-06-24
depends_on: ["skill-dw-quality"]
---

## Goal

Add a `workflow` execution blueprint to the `refactoring` skill manifest so that
`skill_pack(operation="execute", pack_name="refactoring")` runs the
analyse → plan-refactor → apply → verify cycle as a sequential workflow where
the analysis output (target files, identified patterns) is automatically threaded
into the planning and apply phases.

## Context

The `refactoring` skill currently lists tools for pattern analysis and code
refactoring with guidance strings. In practice, a refactoring session involves:

1. Analysing a file or module for refactoring candidates (oversized functions,
   god objects, DRY violations)
2. Planning the specific transformations
3. Applying the changes
4. Verifying quality gates pass after the change

Each step produces data that the next step consumes — the analysis phase
identifies which functions to extract; the plan phase produces a diff target;
the apply phase needs both. This data flow is currently manual, making
refactoring sessions error-prone and hard to resume.

Promoting `refactoring` to a DW is the first skill that tests **multi-phase
structured data passing** where intermediate results (analysis JSON with found
patterns) drive subsequent phase parameters. This builds on the engine and
data-passing mechanism from `skill-dw-quality` and `skill-dw-planning`.

## Scope

**in_scope**

- Read `src/cortex/resources/skills/refactoring.json` and add a `workflow` block
- Define four phases: analyse, plan, apply, verify
- Wire `inputs`/`outputs` so analysis results (target_files, patterns) flow into plan and apply
- Unit tests: happy path, analysis results threaded correctly, verify skipped if apply failed
- Extend `SkillWorkflowPhase.outputs` to support nested field extraction (`result.targets[*].file`) if needed

**out_of_scope**

- Implementing new analysis or refactoring MCP tools (use existing tools listed in refactoring skill)
- Fan-out across multiple files in parallel (deferred — requires parallel execution mode)
- Changes to `_execute_sequential_workflow` engine beyond what `skill-dw-quality` delivered, except nested output extraction if the engine does not yet support it

## Approach

The `refactoring` workflow phases map to existing tool calls in the skill:

1. **analyse** — calls the analysis tool (e.g. `manage_file` with a refactoring-focused prompt, or a dedicated analysis operation if available), captures `target_files: list[str]` and `patterns: list[str]` as outputs.
2. **plan** — uses analysis outputs to build a structured refactoring plan via `plan(operation="create")`, captures `plan_file_name`.
3. **apply** — executes the refactoring steps (tool TBD from refactoring skill inventory), consumes `target_files` and `plan_file_name`.
4. **verify** — calls `run_quality_gate()`, gated on `condition: "phases.apply.status == 'success'"`.

The exact tool mapping for `analyse` and `apply` phases must be confirmed against
the current `refactoring.json` tool list before implementation — this is the key
research task in Step 1.

## Implementation Steps

1. Read `src/cortex/resources/skills/refactoring.json` and inventory the tools
   listed. Map each workflow phase to the most appropriate tool and operation.
   Document the mapping as a comment in the plan before proceeding.

2. If `SkillWorkflowPhase.outputs` does not support list fields, add list-type
   output extraction to `_execute_sequential_workflow` (small engine change).
   Add a test for this case in `test_skill_pack_execute.py`.

3. Write the `workflow` block into `refactoring.json`:
   - `mode: "sequential"`
   - Phases: analyse, plan, apply, verify with correct `tool`, `operation`,
     `inputs`, `outputs`, and `condition` fields.

4. Write unit tests in `tests/tools/test_skill_pack_refactoring_workflow.py`:
   - Happy path: all four phases run, `target_files` threaded from analyse to apply
   - `verify` skipped if `apply` failed
   - Analysis returning empty `target_files` → plan and apply skipped with structured message

5. Smoke-test against mocked tools confirming the full four-phase sequence.

## Verification Checklist

- `skill_pack(operation="load", pack_name="refactoring")` returns manifest with `workflow` field
- `skill_pack(operation="execute", pack_name="refactoring")` runs all four phases in order
- `pipeline_handoff(operation="read", pipeline="skill:refactoring")` shows per-phase outputs
- `pytest tests/tools/test_skill_pack_refactoring_workflow.py -v` all pass
- Engine change (if any) covered by updated `test_skill_pack_execute.py`
- `run_quality_gate()` passes (no regressions)

## Dependencies

- `skill-dw-quality` (engine and models)
- `skill-dw-planning` (data-passing pattern validated there first; refactoring reuses same mechanism)

## Success Criteria

- `skill_pack(operation="execute", pack_name="refactoring")` threads `target_files` from analyse to apply without caller intervention.
- `verify` phase correctly skipped when `apply` failed.
- ≥95% branch coverage on refactoring workflow path.
- No new `Any` types, no functions >30 lines added.

## Testing Strategy

Unit tests (AAA pattern):

- **Arrange**: mock all four tool calls to return fixture JSONs; set up `target_files` in analyse fixture
- **Act**: `skill_pack(operation="execute", pack_name="refactoring")`
- **Assert**: apply mock called with `target_files` equal to analyse fixture output

Negative cases:

- Analyse returns empty targets → plan/apply skipped, result has `skipped_phases: ["plan", "apply"]`
- Apply fails → verify skipped

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `refactoring.json` tool list may not map cleanly to four phases | Step 1 explicitly audits the mapping before coding; adjust phase count if needed |
| List-type output extraction added to engine may break existing phase tests | Add the extraction as an opt-in feature; existing tests use scalar outputs only |
| Refactoring tools may have side effects (file writes) | All unit tests mock the tool functions; no real file writes in test suite |
| Phase count may grow beyond 4 (e.g. separate lint-fix step) | Cap at 6 phases; beyond that, evaluate whether fan-out mode is needed instead |
