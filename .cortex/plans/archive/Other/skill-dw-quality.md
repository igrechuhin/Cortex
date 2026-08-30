---
title: "Promote quality skill to dynamic workflow with retry loop"
component: "skill_pack"
work_type: feature
status: PENDING
priority: High
created: 2026-06-24
depends_on: []
---

## Goal

Add a `workflow` execution blueprint to the `quality` skill manifest so that
`skill_pack(operation="execute", pack_name="quality")` runs the quality gate →
autofix → re-gate cycle as a bounded sequential workflow with a structured result,
rather than relying on agents to re-implement the loop each time.

## Context

The `quality` skill today lists two tools (`run_quality_gate`, `autofix`) and
hints at the retry loop in `workflow_sequences` strings. In practice every
consuming agent — Synapse prompts, commit pipeline, fix orchestrator — re-derives
the same `gate → autofix if failed → gate (max 3)` pattern independently.
This causes:

- Inconsistent retry caps (some agents cap at 2, others at 3).
- No structured result: callers parse free-text gate output to decide next steps.
- Drift when `autofix` adds new fix categories — each prompt must be updated.

Making `quality` a dynamic workflow centralises the loop, enforces the retry cap,
and returns a typed `SkillWorkflowResult` that callers can branch on without
string parsing.

The `quality` skill is the highest-value pilot for DW promotion because:

1. Its retry/conditional logic is non-trivial (not just sequencing).
2. It is the most frequently invoked skill across all pipelines.
3. It has a clear finite done condition: gate passes or max retries reached.

## Scope

**in_scope**

- Add `SkillWorkflowPhase`, `SkillWorkflow` models to `skill_pack/models.py`
- Add `workflow` field (optional) to `SkillPackManifest`
- Add `execute` operation to `skill_pack()` dispatcher in `operations.py`
- Implement `_execute_sequential_workflow()` with retry-loop support (max N iterations per phase)
- Persist per-phase results via `pipeline_handoff` (pipeline name: `skill:quality`)
- Update `quality.json` manifest with `workflow` block: gate → autofix → gate (max 3)
- Unit tests for execute operation, retry cap, condition evaluation, structured result

**out_of_scope**

- Fan-out / parallel phase execution (deferred)
- Workflow script generation (JS for Claude Code Workflow tool) — separate plan
- Promoting other skills (each has its own plan)
- Changes to `run_quality_gate` or `autofix` tool internals
- Changes to existing Synapse prompts consuming the quality tools directly

## Approach

Extend `SkillPackManifest` with an optional `workflow: SkillWorkflow | None`
field. `SkillWorkflow` holds a `mode` (initially only `"sequential"` is
implemented) and an ordered list of `SkillWorkflowPhase` objects.

Each `SkillWorkflowPhase` maps to one MCP tool call and adds:

- `max_iterations: int` — how many times this phase may repeat (default 1; set to 3 for `autofix`)
- `retry_condition: str | None` — Python expression; if truthy after the phase, loop back up to `max_iterations`
- `inputs: dict[str, str]` — map from `prior_phase.field` to param name (data passing)
- `outputs: list[str]` — field names to capture from the result JSON

The `_execute_sequential_workflow()` helper calls each tool function directly
(not via a new subprocess), persists each phase result via `pipeline_handoff`,
evaluates `retry_condition`, and returns a `SkillWorkflowResult` with:
`passed: bool`, `iterations: int`, `phases: list[PhaseResult]`.

The quality workflow blueprint in `quality.json`:

```text
phase gate_1:   run_quality_gate()          → capture preflight_passed
phase autofix:  autofix() if not passed     → max_iterations=3, retry_condition="not gate_1.preflight_passed"
phase gate_2:   run_quality_gate()          → final verdict
```

## Implementation Steps

1. Add `SkillWorkflowPhase` and `SkillWorkflow` Pydantic models to
   `src/cortex/tools/skill_pack/models.py`. Fields: `name`, `tool`, `operation`,
   `required`, `condition`, `retry_condition`, `max_iterations`, `inputs`, `outputs`.

2. Add `workflow: SkillWorkflow | None = None` field to `SkillPackManifest`.

3. Add `execute` branch to `skill_pack()` dispatcher in
   `src/cortex/tools/skill_pack/operations.py`. Validate `pack_name` and that
   the manifest has a `workflow` block.

4. Implement `_execute_sequential_workflow(manifest, phase_inputs)` helper:
   - Iterate phases in order
   - Evaluate `condition` (skip if False)
   - Call the target tool function directly by name from a tool registry lookup
   - Capture `outputs` fields from the JSON result
   - Evaluate `retry_condition`; loop up to `max_iterations`
   - Persist each phase result via `pipeline_handoff(operation="write", pipeline=f"skill:{pack_name}", phase=phase.name, ...)`
   - Return `SkillWorkflowResult`

5. Add `SkillWorkflowResult` Pydantic model to `models.py`:
   `passed: bool`, `iterations: int`, `phases: list[PhaseResult]`,
   `error: str | None`.

6. Update `src/cortex/resources/skills/quality.json` with the `workflow` block
   describing the three-phase gate → autofix → gate cycle with `max_iterations=3`
   on the autofix phase.

7. Write unit tests in `tests/tools/test_skill_pack_execute.py`:
   - Execute quality workflow happy path (gate passes first time)
   - Execute quality workflow with autofix (gate fails, autofix runs, gate passes)
   - Retry cap enforced (gate never passes → result has `passed=False` after 3 iterations)
   - Condition evaluation skips a phase
   - Missing `workflow` block returns structured error

## Verification Checklist

- `skill_pack(operation="load", pack_name="quality")` returns manifest with `workflow` field populated
- `skill_pack(operation="execute", pack_name="quality")` runs without error on a clean codebase
- `skill_pack(operation="execute", pack_name="quality")` on a dirty codebase triggers autofix and returns `passed=True` after fix
- `pipeline_handoff(operation="read", pipeline="skill:quality")` shows per-phase results after execution
- `pytest tests/tools/test_skill_pack_execute.py -v` all pass
- `run_quality_gate()` passes (no regressions in existing tools)
- `mypy` / `pyright` clean on modified files

## Dependencies

None. `run_quality_gate` and `autofix` are already stable zero-arg tools.

## Success Criteria

- `skill_pack(operation="execute", pack_name="quality")` returns `{"passed": true|false, "iterations": N, "phases": [...]}` with no string parsing required by the caller.
- Retry cap of 3 is enforced and tested.
- All 7 existing skill pack tests continue to pass.
- New tests achieve ≥95% branch coverage of `_execute_sequential_workflow`.

## Testing Strategy

Unit tests (AAA pattern) in `tests/tools/test_skill_pack_execute.py`:

- **Arrange**: mock `run_quality_gate` and `autofix` return values
- **Act**: call `skill_pack(operation="execute", pack_name="quality")`
- **Assert**: `SkillWorkflowResult` fields match expected `passed`, `iterations`, `phases`

Negative cases:

- Pack without `workflow` block → structured error response
- `max_iterations` exceeded → `passed=False`, no infinite loop
- `condition` false → phase skipped, not in `phases` list

Integration smoke: call against real tools in test environment with `run_quality_gate` stubbed to return a known fixture.

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Tool function resolution at runtime (calling `run_quality_gate` by name) | Use an explicit `_TOOL_REGISTRY: dict[str, Callable]` in `operations.py`; fail fast if name not found |
| `pipeline_handoff` unavailable in test environments | Inject handoff function as a dependency; tests pass a no-op stub |
| `autofix` side effects in tests | Mock `autofix` to return a known JSON fixture; never call real autofix in unit tests |
| Retry loop running forever if `retry_condition` always true | `max_iterations` hard cap enforced before evaluating condition; assert in tests |
