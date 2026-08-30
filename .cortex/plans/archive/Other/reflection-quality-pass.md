---
title: "Reflection Quality Pass — Self-Evaluation Step in Cortex Pipelines"
component: tools/evaluation
work_type: feature
status: PENDING
priority: Medium
created: 2026-04-02
depends_on: []
---

## Goal

Add an optional reflection/self-evaluation pass to Cortex's quality pipeline, inspired by `reflection-pattern.md` from the ai-coding-kb. After the primary quality gate passes, a lightweight "critic" analysis identifies issues the gate missed (logic errors, missed edge cases, security gaps) and surfaces them before commit — without a full second gate run.

## Context

The KB documents the Producer-Critic model: a separate evaluator reviews output against constraints and the primary producer iterates. Currently `run_quality_gate` runs checks (type, lint, test) but does not reason about *semantic* quality: missing edge cases, skipped error paths, security omissions. A reflection pass would consume the diff + gate output and emit a structured critique that the agent can act on before finalizing. This is particularly valuable before `run_docs_gate` and Step 12 final gate.

## Implementation Steps

### Step 1 — Define ReflectionResult model

- Create `src/cortex/tools/evaluation/reflection.py`:
  - `CritiqueItem(BaseModel)`: `category: Literal["logic","security","edge_case","test_coverage","docs"]`, `severity: Literal["warning","error"]`, `location: str`, `description: str`, `suggestion: str`
  - `ReflectionResult(BaseModel)`: `items: list[CritiqueItem]`, `score: int` (0-100), `summary: str`, `approved: bool`
- Verification: pyright passes; `from cortex.tools.evaluation.reflection import ReflectionResult` works.

### Step 2 — Reflection analyzer function

- `analyze_diff(diff_text: str, gate_output: str, rules_content: str) -> ReflectionResult`
- Uses structured prompting pattern from KB (Role + Context + Goal + Constraints + Output Format)
- Calls internal `think()` equivalent or returns heuristic-only result if LLM not available
- Heuristic checks: missing `except` clauses, untested public functions, TODO markers, hardcoded values
- Verification: Unit tests with sample diffs confirm CritiqueItem output shape.

### Step 3 — Integrate into `run_quality_gate` as optional phase

- Add `reflection: bool = False` to quality gate config (read from session config or `pipeline_handoff` state)
- When enabled: after all checks pass, run `analyze_diff()` and append `ReflectionResult` to gate response
- If `reflection_result.approved == False` and any `error`-severity items: gate returns failed status
- Verification: Integration test enables reflection, injects known diff with missing try/except, checks gate fails.

### Step 4 — Synapse prompt update: `/cortex/do` reflection guidance

- Update `do.md` to document that `force_reflection: true` can be passed via `pipeline_handoff` before Step 12
- Add a note: reflection is recommended for security-critical or data-mutation code paths
- Verification: `do.md` contains `force_reflection` reference.

### Step 5 — `cortex://rules` resource: reflection criteria

- Add `## Reflection Checklist` section to the rules resource output
- Lists the 5 critique categories and what triggers each
- Verification: `cortex://rules` response contains "Reflection Checklist".

### Step 6 — Documentation

- Add `docs/guides/reflection-pass.md` explaining the pattern, how to enable, and how to interpret results
- Verification: File exists with example ReflectionResult JSON.

## Verification Checklist

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|-----------------|
| 1 | `class ReflectionResult` | `src/cortex/tools/evaluation/` | reflection.py |
| 2 | `def analyze_diff` | `src/cortex/tools/evaluation/reflection.py` | reflection.py |
| 3 | `reflection: bool` in gate config | quality gate handler | gate config model |
| 4 | `force_reflection` in do.md | `.cortex/synapse/prompts/do.md` | do.md |
| 5 | `Reflection Checklist` in rules resource | `src/cortex/resources.py` or rules handler | rules resource |
| 6 | `reflection-pass.md` exists | `docs/guides/` | reflection-pass.md |

## Dependencies

- `src/cortex/tools/execution/` — quality gate runner
- `src/cortex/core/session_config.py` — read reflection flag
- `src/cortex/tools/session/pipeline_handoff.py` — `force_reflection` state key

## Success Criteria

- `ReflectionResult` model is fully typed and validated
- Reflection pass runs after gate checks when enabled
- Heuristic analysis catches at least: missing exception handlers, TODO markers, untested public functions
- `/cortex/do` prompt documents the feature
- 95%+ coverage on `tools/evaluation/` module
- Zero regressions in existing gate tests

## Testing Strategy

- Unit tests (AAA): `tests/unit/tools/evaluation/test_reflection.py` — test heuristics with fixture diffs
- Integration tests: `tests/integration/test_reflection_gate.py` — enable reflection, verify ReflectionResult in response
- Parametric tests: multiple diff scenarios (clean diff → approved, TODO diff → warning, missing except → error)
- 95%+ coverage target on new module
