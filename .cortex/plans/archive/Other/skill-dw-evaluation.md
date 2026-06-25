---
title: "Promote evaluation skill to dynamic workflow with structured pipeline output"
component: "skill_pack"
work_type: "feature"
status: BLOCKED
priority: "Low"
created: "2026-06-24"
depends_on: ["skill-dw-quality", "skill-dw-planning"]
---

## Goal

Add a `workflow` execution blueprint to the `evaluation` skill manifest so that
`skill_pack(operation="execute", pack_name="evaluation")` runs the
run-evaluation → analyse-results → store-report cycle as a sequential workflow
that produces a typed `EvaluationReport` result, rather than requiring callers
to parse free-text evaluation output and manually trigger analysis.

## Context

The `evaluation` skill covers "evaluation execution and analysis" — running
correctness/quality evaluations and interpreting their outputs. Currently this
is advisory guidance: agents run the evaluation tool, read the output, decide
whether to store the results, and format a report themselves.

The profit of promoting `evaluation` to a DW is specifically the **structured
output contract**: downstream consumers (session analysis, roadmap updates)
need a typed result (`score`, `passed`, `gaps: list[str]`) rather than
free-text. The DW formalises this and ensures every evaluation session produces
a consistent, storable artefact.

This plan has lower priority than `quality`, `planning`, and `refactoring`
because:

- Evaluation is run less frequently than the others.
- The current free-text approach is workable, just inconsistent.
- The structured output benefit depends on `skill-dw-quality` establishing the
  `SkillWorkflowResult` model (which `EvaluationReport` will extend or reuse).

## Scope

**in_scope**

- Read `src/cortex/resources/skills/evaluation.json` and add a `workflow` block
- Define three phases: run, analyse, store
- `store` phase writes a structured `EvaluationReport` to the memory bank via `manage_file`
- Wire `outputs` so `run` phase captures `score` and `raw_results`, `analyse` captures `gaps` and `passed`
- Unit tests: happy path, `store` skipped when `analyse.passed == True` (no gaps to record), structured result shape

**out_of_scope**

- Implementing new evaluation MCP tools
- Changing the evaluation tool's scoring logic
- Fan-out across multiple evaluation targets in parallel
- Changes to the `_execute_sequential_workflow` engine beyond what prior plans deliver

## Approach

The evaluation workflow follows a run → analyse → store pattern:

1. **run** — executes the evaluation tool (from `evaluation.json` tool inventory), captures `score: float` and `raw_results: dict`.
2. **analyse** — interprets raw results to produce `passed: bool` and `gaps: list[str]`.
3. **store** — calls `manage_file(operation="write")` to persist an `EvaluationReport` to memory bank, gated on `condition: "not phases.analyse.passed"` (only store when gaps are found).

The tool mapping for `run` and `analyse` must be confirmed against `evaluation.json`
in Step 1 (same audit-first discipline as `skill-dw-refactoring`).

## Implementation Steps

1. Read `src/cortex/resources/skills/evaluation.json` and map phases to tools.
   Document the tool-to-phase mapping as a comment before coding.

2. Define `EvaluationReport` as a Pydantic model in
   `src/cortex/tools/skill_pack/models.py` (or a new
   `src/cortex/tools/skill_pack/evaluation_models.py` if it grows large):
   `score: float`, `passed: bool`, `gaps: list[str]`, `stored_path: str | None`.

3. Write the `workflow` block into `evaluation.json` with three phases,
   `inputs`/`outputs` maps, and the `store` phase condition.

4. Write unit tests in `tests/tools/test_skill_pack_evaluation_workflow.py`:
   - Happy path (gaps found): all three phases run, `store` called with `EvaluationReport`
   - No gaps: `store` phase skipped, result has `stored_path: None`
   - `run` phase fails: `analyse` and `store` skipped

5. Smoke-test with mocked tools; confirm `EvaluationReport` shape matches expected fields.

## Verification Checklist

- `skill_pack(operation="load", pack_name="evaluation")` returns manifest with `workflow` field
- `skill_pack(operation="execute", pack_name="evaluation")` runs all three phases when gaps are found
- `store` phase correctly skipped when `analyse.passed == True`
- `pytest tests/tools/test_skill_pack_evaluation_workflow.py -v` all pass
- `run_quality_gate()` passes (no regressions)

## Dependencies

- `skill-dw-quality` (engine, `SkillWorkflowResult` base model)
- `skill-dw-planning` (validates data-passing pattern; evaluation reuses same mechanism)

## Success Criteria

- `skill_pack(operation="execute", pack_name="evaluation")` returns a typed `EvaluationReport` with `score`, `passed`, `gaps`, `stored_path`.
- `store` phase gating on `analyse.passed` works correctly in both directions.
- ≥95% branch coverage on evaluation workflow path.

## Testing Strategy

Unit tests (AAA pattern):

- **Arrange**: mock `run` to return `{"score": 0.72, "raw_results": {...}}`, mock `analyse` to return `{"passed": false, "gaps": ["X", "Y"]}`
- **Act**: `skill_pack(operation="execute", pack_name="evaluation")`
- **Assert**: `store` called; result `EvaluationReport.gaps == ["X", "Y"]`

Negative cases:

- `analyse.passed == True` → `store` not called, `stored_path` is `None`
- `run` returns error → `analyse` and `store` skipped, `EvaluationReport.passed == False`

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Evaluation tool inventory in `evaluation.json` may not map to 3 clean phases | Audit in Step 1; reduce to 2 phases (run + store) if analyse is implicit in the tool |
| `EvaluationReport` model added to `models.py` may push file over 400-line limit | Add to a separate `evaluation_models.py` if the file grows; import into `models.py` |
| `store` writing to memory bank in tests creates real files | Mock `manage_file` in unit tests; never write real memory bank files in test suite |
