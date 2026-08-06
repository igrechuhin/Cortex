---
title: "Agentic Tool-Selection Evaluation Harness"
component: "evaluation"
work_type: "feature"
status: PENDING
priority: "High"
created: "2026-08-06"
depends_on: []
---

## Goal

Add an agent-in-the-loop evaluation mode to the existing `run_tool_evaluation` subsystem that measures whether a model can select the correct Cortex MCP tool from its description alone, producing a per-task pass/fail score plus captured model feedback on tool naming and parameter documentation.

## Context

Cortex already has an evaluation subsystem (`src/cortex/tools/evaluation/`) with an `EvalTask` model, task fixtures in `.cortex/evals/tasks/*.json`, and a harness that runs each task through `_invoke_tool` in `evaluation_execution.py`. That harness invokes a named tool directly with fixed arguments and compares output against an `expect` spec. It answers "does this tool work when called correctly."

It does not answer the different and more valuable question: "can an agent, given only the registered tool descriptions, figure out which tool to call and complete the task." Nothing in the current pipeline exercises tool *discoverability*. The `expected_tools` field already present on every fixture in `.cortex/evals/tasks/core_workflows.json` encodes the ground truth for exactly this check but is currently unused by the execution path.

This gap has a concrete cost. The tool budget is capped (`categories.py` enforces a hard limit) and the `/cortex/analyze` pipeline routinely proposes tool consolidation and merges. Those proposals are currently accepted or rejected on judgment, with no measurement of whether a merge made the surviving tool harder for an agent to select. An agentic harness turns that judgment call into a regression test.

The reference implementation is `skills/mcp-builder/scripts/evaluation.py` in the local `~/Repo/skills` checkout (Anthropic's skills repository, Apache 2.0 for this skill). Its `agent_loop` drives a model against a live MCP connection, and its evaluation prompt requires the model to emit `<summary>`, `<feedback>`, and `<response>` blocks — the `<feedback>` block is a direct critique of tool names, parameter docs, and error messages. That feedback is the artifact most useful to Cortex and has no equivalent today.

Constraint: `anthropic` is not currently in `requirements.txt` (only `mcp>=1.26.0`). This harness requires a live model call, so the dependency and its API-key requirement must be optional and must never be imported on the default server path.

A second reference, `docs/DISCOVERY_ELICITATION_SPEC.md` in the local `~/Repo/jcode` checkout, supplies the measurement discipline this plan would otherwise lack. It defines a paired eval for the same question in a different harness — does the agent reach for the right tool given only prompt and schema — and its central argument applies here without modification: raising selection accuracy by writing a more insistent tool description is trivial and actively harmful, so a positives-only score is not a result. Its case taxonomy (`gap` / `control` / `near-miss`) and its invariance rule are adopted below.

## Measurement Contract

The harness measures exactly one term: whether the registered **name, description, and parameter schema** of a Cortex tool are sufficient for a model to select it. Everything else — whether the tool works when called, whether its output is correct — is already covered by the deterministic execution mode and is out of this metric.

Two consequences drive the fixture design.

**Every task declares one `kind`.**

| kind | meaning | correct behavior | scored as |
|------|---------|------------------|-----------|
| `positive` | The task cannot be completed without the tool named in `expected_tools`. | Call that tool. | Hit if `expected_tools` ⊆ called tools. |
| `control` | The task is fully served by ordinary reasoning or file editing; no Cortex MCP tool is required at any point. | Call no Cortex tool. | Any Cortex tool call is a false positive. |
| `near-miss` | The task genuinely touches the subject area of `expected_tools`' tool, but another tool already covers it. | Call the covering tool, not the tempting one. | Calling the tempting tool is a false positive, reported separately. |

`near-miss` is the adversarial half and the reason to do this at all. Cortex's surface has real overlaps — `plan` versus `manage_file` for writing a plan file, `run_quality_gate` versus `autofix` for a formatting complaint, `session` versus `cortex://context` for orientation, `think` versus no tool at all for a one-line judgment. These are precisely where an over-eager description does damage, because the task smells like the tool while a different tool already handles it. A `near-miss` task **must** name the covering tool in a `covered_by` field; if no tool covers it, the task is a `positive`, not a `near-miss`.

**A run that reports selection accuracy without its paired false-positive rate is not a valid result** and the harness must refuse to emit one. `control` and `near-miss` false positives are reported as separate figures, never pooled, because a near-miss failure is the more expensive one.

**Invariance.** The score must stay flat when a tool's implementation, output, or fixture expectations change, and move only when a tool's name, description, or parameter schema changes. If a refactor that touched no description moves the number, the harness is measuring the wrong thing.

**Stable ids.** Each task carries a permanent kebab-case `id`. Scores are tracked per id across description revisions, so renaming an id destroys its history. Retire a task by deleting it, never by repurposing its id.

## Scope

**in_scope**

- A new `EvalRunMode` variant (e.g. `agentic`) alongside the existing modes, selecting the agent-in-the-loop path.
- An agent loop module that connects to the running Cortex MCP server, exposes the registered tool schemas to a model, and runs a task prompt to completion or a bounded turn limit.
- Scoring a task by comparing the tools the model actually called against the fixture's existing `expected_tools` field, plus response matching against `expected_outcome`.
- A `kind` field (`positive` / `control` / `near-miss`) on `EvalTask`, a `covered_by` field required on and only on `near-miss` tasks, and a permanent `id` on every task.
- Negative fixtures: at least five `control` tasks and at least five `near-miss` tasks drawn from Cortex's real tool overlaps.
- Paired reporting — selection accuracy alongside separately reported `control` and `near-miss` false-positive rates — with the suite refusing to emit an accuracy figure when the negative set is absent or empty.
- Capturing the model's structured `<feedback>` on tool names, parameter descriptions, and errors into the persisted `EvalSuiteResult`.
- Optional `anthropic` dependency declared as an extra, imported lazily inside the agentic path only.
- Graceful, explicit skip with a clear reason when the dependency or API key is absent.
- Unit tests with a mocked model client; no network calls in the default test suite.

**out_of_scope**

- Changing the existing deterministic execution mode, its fixtures, or its scoring.
- Adding or rewriting eval task fixtures beyond what is needed to exercise the new mode.
- Acting on any tool-description weaknesses the harness reports — findings only; fixes are separate work.
- Wiring the agentic mode into `run_quality_gate` or any commit-blocking gate.
- Multi-model comparison, cost dashboards, or CI scheduling.

## Approach

Extend rather than fork. Keep `EvalTask`, `EvalSuiteResult`, and the persistence and dashboard helpers in `_run_impl.py` exactly as they are; add the agentic path as a sibling of `run_execution_suite` so both modes write the same result shape and reuse `_persist_latest_suite`.

The agent loop is a thin, self-contained module. It takes an already-established MCP session, converts registered tool schemas into model tool definitions, and runs the standard request → tool-call → result → repeat cycle until the model stops calling tools or a turn cap is hit. Adapt the control flow and the structured-output prompt from `mcp-builder/scripts/evaluation.py`, but use Cortex's own Pydantic models for every result structure rather than that script's `dict[str, Any]` returns, per the project's no-`Any` and Pydantic-mandatory rules. Preserve the `<summary>`/`<feedback>`/`<response>` prompt contract — the feedback block is the reason to do this at all.

Scoring is deliberately simple in this first slice, but it is paired from the start rather than retrofitted. A `positive` task passes when the set of tools called contains the fixture's `expected_tools` and the extracted `<response>` satisfies the existing expectation check. A `control` task passes when no Cortex MCP tool was called. A `near-miss` task passes when the tool named in `expected_tools` was **not** called; calling the tool named in `covered_by` instead is recorded but not required to pass, since the point of the case is the false positive, not the alternative. Richer scoring (ordering, efficiency, token cost per task) is deferred until the harness has produced real runs.

Pairing is enforced structurally, not by convention. The suite assembler computes accuracy only when the run contains at least one `control` and one `near-miss` task, and otherwise returns a typed result carrying the reason instead of a number. This is the single design decision that keeps the harness from degenerating into a description-inflation ratchet, so it belongs in the code rather than in a reviewer's discipline.

Existing fixtures in `.cortex/evals/tasks/core_workflows.json` are all implicitly positive. Default `kind` to `positive` when the field is absent so no fixture needs rewriting, and add the negative set as new tasks.

Isolate the optional dependency behind a lazy import inside the agentic entry point, so a checkout without `anthropic` installed keeps every existing code path and test working unchanged.

## Implementation Steps

1. Read `src/cortex/tools/evaluation/_models.py` and record the current `EvalRunMode`, `EvalTask`, `ExecutionResult`, and `EvalSuiteResult` definitions.
2. Add an `agentic` variant to `EvalRunMode`, and add Pydantic models for the new artifacts: a per-task agentic result (tools called, turn count, extracted response, pass/fail, skip reason) and a tool-feedback record (tool name, feedback text).
2a. Add to `EvalTask`: a permanent `id`, a `kind` enum (`positive` / `control` / `near-miss`, defaulting to `positive`), and an optional `covered_by`. Add a Pydantic model validator enforcing that `covered_by` is present for `near-miss` and absent otherwise, and that `expected_tools` is non-empty for `positive` and `near-miss`.
2b. Author the negative fixture set: at least five `control` tasks needing no Cortex tool, and at least five `near-miss` tasks over the real overlaps (`plan` vs `manage_file`, `run_quality_gate` vs `autofix`, `session` vs `cortex://context`, `think` vs no tool, `update_memory_bank` vs `manage_file`), each naming its `covered_by`.
3. Declare `anthropic` as an optional dependency in `pyproject.toml` (an extra, not a base requirement) and leave `requirements.txt` base install unchanged.
4. Create `src/cortex/tools/evaluation/_agent_loop.py` holding the evaluation prompt constant, the tool-schema conversion, the bounded request/tool-call loop, and the `<summary>`/`<feedback>`/`<response>` extraction. Keep the file under 400 lines and every function under 30 lines.
5. Implement the lazy `anthropic` import and API-key detection inside this module; return a typed skip result rather than raising when either is missing.
6. Create `src/cortex/tools/evaluation/_agentic_suite.py` with a `run_agentic_suite` that mirrors `run_execution_suite`: filter tasks by mode, run each through the agent loop, and assemble an `EvalSuiteResult`.
7. Implement per-kind scoring: `positive` — called tools ⊇ `expected_tools` and the response check passes; `control` — no Cortex tool called; `near-miss` — the tool in `expected_tools` was not called, recording whether `covered_by` was used instead. Record per-task pass/fail with a reason string on failure.
7a. Implement paired aggregation: report selection accuracy over `positive` tasks together with separately reported `control` and `near-miss` false-positive rates. When the run contains no `control` or no `near-miss` task, return a typed unpaired result carrying the reason and omit the accuracy figure entirely.
8. Route the new mode in `run_tool_evaluation_impl` in `_run_impl.py` so `agentic` dispatches to `run_agentic_suite`, reusing `_persist_latest_suite` and the dashboard writer unchanged.
9. Ensure captured tool feedback is included in the persisted payload and surfaced in the dashboard output.
10. Write unit tests under `tests/tools/` with a mocked model client covering: correct tool selection passes; wrong tool selection fails with a reason; missing dependency yields a skip, not an error; missing API key yields a skip; turn cap is enforced; feedback is captured and persisted.
11. Add a short usage note to `docs/` describing how to run the agentic mode and what its output means, and record the `~/Repo/skills` `mcp-builder` provenance and its Apache 2.0 license.
12. Run `run_quality_gate()` and resolve every finding.

## Verification Checklist

- Step 2: search `_models.py` for `EvalRunMode`; confirm the new variant does not break existing exhaustive matches — grep `EvalRunMode.` across `src/` and `tests/` and re-read each hit.
- Step 3: confirm `pip install -r requirements.txt` in a clean environment still succeeds without `anthropic`; re-read `pyproject.toml`.
- Steps 4–6: after creation, re-read both new files and confirm no `Any`, no `dict[str, Any]` returns, no `TYPE_CHECKING`-guarded imports, and file length under 400 lines.
- Step 5: grep for top-level `import anthropic` across `src/` — there must be zero hits outside the lazy call site.
- Step 2a: confirm every existing fixture in `.cortex/evals/tasks/*.json` still loads without modification and defaults to `kind: positive`; confirm a hand-written `near-miss` fixture without `covered_by` fails validation.
- Step 2b: confirm every task `id` is unique across all fixture files; assert this in a test rather than by inspection.
- Step 7a: construct a run containing only `positive` tasks and confirm no accuracy number is emitted anywhere in the result or dashboard payload.
- Step 8: re-read `_run_impl.py` and confirm both modes reach `_persist_latest_suite` with the same result type.
- Step 10: run the suite and confirm no test performs a network call; grep the new tests for `anthropic.Anthropic(` without a mock.
- Step 12: re-read every file the gate modified.

## Dependencies

- None on other Cortex plans.
- External: `anthropic` Python SDK (optional extra) and an `ANTHROPIC_API_KEY` at runtime for live runs only.
- Reference source: `~/Repo/skills/skills/mcp-builder/scripts/evaluation.py` and `connections.py` (Apache 2.0; see `LICENSE.txt` in that skill directory).
- Reference for method only: `~/Repo/jcode/docs/DISCOVERY_ELICITATION_SPEC.md` (MIT) — paired eval design, `gap`/`control`/`near-miss` taxonomy, `covered_by` requirement, stable-id and invariance rules. No code is taken from that repository.

## Success Criteria

- `run_tool_evaluation` accepts the `agentic` mode and returns an `EvalSuiteResult` of the same type as the existing mode.
- A run against the existing `.cortex/evals/tasks/core_workflows.json` fixtures produces a per-task pass/fail using each fixture's `expected_tools` as ground truth, with those fixtures unmodified.
- The fixture set contains at least five `control` and at least five `near-miss` tasks, every `near-miss` names its `covered_by`, and every task id is unique and permanent.
- Every reported accuracy figure is accompanied by separately reported `control` and `near-miss` false-positive rates; a run lacking either negative kind emits no accuracy figure at all, only a typed reason.
- Captured model feedback on tool names and parameter descriptions is present in the persisted result and the dashboard.
- With `anthropic` uninstalled, the full existing test suite passes unchanged and the agentic mode reports a typed skip with a reason.
- Test coverage for the new modules is at least 95%.
- `run_quality_gate()` reports zero errors.

## Testing Strategy

Target 95% coverage on new modules, AAA pattern throughout, fully deterministic with no network access.

- Unit — agent loop: mocked client returning a scripted tool-call sequence; assert called-tool capture, turn-cap enforcement, and correct parsing of `<summary>`/`<feedback>`/`<response>`, including malformed and missing blocks.
- Unit — scoring: expected-tools subset match, superset match, disjoint match, and empty-call case; assert failure reasons are populated.
- Unit — kinds: a `control` task passes on zero tool calls and fails on any Cortex tool call; a `near-miss` task fails when the tempting tool is called and passes when the `covered_by` tool is called instead; an unrecognised kind is a validation error, not a silent default.
- Unit — fixture validation: `near-miss` without `covered_by` rejected; `control` with `covered_by` rejected; `control` with `expected_tools` rejected; duplicate ids across fixture files rejected.
- Unit — pairing enforcement: a positives-only run returns the typed unpaired result with a reason and no accuracy figure; a run with one `control` and one `near-miss` returns accuracy plus both false-positive rates as distinct fields, never pooled.
- Unit — dependency gating: simulate absent `anthropic` and absent API key; assert a typed skip result and that no exception escapes.
- Integration — suite: fake session with two tasks, one passing and one failing; assert the assembled `EvalSuiteResult` and that persistence is invoked with the same shape as the deterministic mode.
- Negative — model returns no tool calls, returns `NOT_FOUND`, or exceeds the turn cap; each yields a recorded failure rather than a crash.
- Regression — the existing deterministic mode's tests pass byte-identically after the mode enum change.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Optional `anthropic` import leaks onto the default server path | Import error for every user without the extra | Lazy import inside the agentic entry point only; verification step greps for top-level imports |
| Live model calls make results non-deterministic | Flaky, untrustworthy scores | Default test suite is fully mocked; live runs are opt-in and reported as advisory, never gate-blocking |
| Model-call cost on a large fixture set | Unbounded spend | Bounded turn cap per task, explicit mode opt-in, and task filtering by mode |
| Scoring on `expected_tools` alone is too coarse | False failures when a valid alternative tool is used | Treat expected tools as a subset check, record the full called-tool list, and record a failure reason for manual review before tightening |
| New modules push `evaluation/` past size limits | Quality gate failure | Two focused new files, each under 400 lines, rather than extending `evaluation_execution.py` |
| Reference code carries a license obligation | Compliance issue | Adapt rather than copy verbatim; record provenance and Apache 2.0 attribution in docs |
| Accuracy is raised by writing more insistent tool descriptions | Metric improves while real tool selection degrades | Paired reporting enforced in code: no accuracy figure is emitted without both negative kinds present, and `near-miss` false positives are reported separately as the expensive failure |
| The score moves when unrelated code changes | Metric is measuring implementation, not description | Invariance check — run the suite before and after a refactor touching no name, description, or schema, and assert the score is unchanged |
| Negative fixtures are too easy and never fail | False confidence in the pairing | `near-miss` cases are drawn from Cortex's real overlapping surfaces; a `near-miss` set with a zero false-positive rate at baseline is treated as evidence the cases are too weak, not as a pass |
| Fixture ids are renamed during tuning | Per-id score history destroyed | Ids are permanent and retired only by deletion; uniqueness asserted by test |
