# Agentic Tool-Selection Eval

The agentic mode of `run_tool_evaluation` measures one thing only: whether the
registered **name, description, and parameter schema** of a Cortex MCP tool are
enough for a model to select it. Whether the tool then works is already covered
by the deterministic execution mode and is out of this metric.

## Running it

```text
run_tool_evaluation(mode="agentic")
```

Requirements:

- The optional `anthropic` extra: `pip install -e '.[agentic-evals]'`.
  The base `requirements.txt` install is unchanged and never imports `anthropic`.
- An `ANTHROPIC_API_KEY` in the environment.

If either is missing the mode does not fail. It returns an `agentic_summary`
with `skipped: true` and a typed `skip_reason` of `dependency_missing` or
`api_key_missing`, and the dashboard prints the same reason.

## Reading the output

`agentic_summary.scorecard` is a **paired** scorecard:

| Field | Meaning |
|-------|---------|
| `selection_accuracy` | Share of `positive` tasks where the model called the expected tool. Present **only** in a paired run. |
| `control_false_positive_rate` | Share of `control` tasks where any Cortex tool was called at all. |
| `near_miss_false_positive_rate` | Share of `near-miss` tasks where the tempting tool was called instead of the covering one. |
| `unpaired_reason` | Why no accuracy figure was emitted. |

A run that contains no `control` task or no `near-miss` task emits **no**
accuracy figure — `selection_accuracy` is `null`, `paired` is `false`, and
`unpaired_reason` explains which negative kind was missing. This is enforced by
a Pydantic validator on `AgenticScorecard`, not by reviewer discipline, because
a positives-only score can be raised for free by writing a more insistent tool
description while real tool selection gets worse.

The two false-positive rates are never pooled. A near-miss false positive is the
more expensive failure: the model reached for a tool whose subject area matched
when another tool already covered the task.

`agentic_summary.feedback` carries the model's verbatim `<feedback>` block per
tool — its critique of tool names, parameter descriptions, and error messages.
This is the artifact the harness exists to collect. It is advisory: acting on it
is separate work, and the agentic mode is never wired into a commit-blocking gate.

## Fixtures

Tasks live in `.cortex/evals/tasks/*.json`. Each declares a `kind`:

- `positive` (default) — the task cannot be done without the tool in `expected_tools`.
- `control` — no Cortex tool is needed; `expected_tools` must be empty.
- `near-miss` — the task touches the subject area of `expected_tools` but another
  tool already covers it. `covered_by` is required and names that covering tool.

Every `expected_tools` and `covered_by` value on a negative task must name a
tool Cortex actually publishes; this is asserted by
`test_negative_fixture_tool_references_are_registered_tools`. A negative case
naming a tool that is never shown to the model can never fire, and would give
false confidence in the negative set.

### Tool visibility

The harness exposes exactly the surface a client sees, read from
`cortex.server.mcp.list_tools()`. That call applies the server's visibility
filtering, so tools gated behind an authenticated context are absent when the
eval runs without one. `missing_published_tools()` names the gap rather than
hiding it, and `select_agentic_tasks()` drops any task whose tools are not
exposed instead of scoring it — otherwise an unexposed tool would book a
guaranteed `positive` failure and a guaranteed `near-miss` pass. If dropping
leaves the run without both negative kinds, the run reports as unpaired and
emits no accuracy figure, which is the intended loud failure.

Legacy `positive` fixtures predate the current tool surface and name tools that
are no longer registered. They load fine and are excluded from selection scoring
by the same exposure filter.

Task `id`s are permanent. Scores are tracked per id across description
revisions, so renaming an id destroys its history. Retire a task by deleting it,
never by repurposing its id.

## Invariance

The score must stay flat when a tool's implementation, output, or fixture
expectations change, and move only when a tool's name, description, or parameter
schema changes. If a refactor that touched no description moves the number, the
harness is measuring the wrong thing.

## Provenance

The agent-loop control flow and the `<summary>`/`<feedback>`/`<response>` prompt
contract are **adapted** from `skills/mcp-builder/scripts/evaluation.py` in
Anthropic's [`skills`](https://github.com/anthropics/skills) repository, licensed
under the **Apache License 2.0** (see `LICENSE.txt` in that skill directory).
No code is copied verbatim; all result structures use Cortex Pydantic models.

The paired-eval method — the `gap`/`control`/`near-miss` taxonomy, the
`covered_by` requirement, and the stable-id and invariance rules — follows
`docs/DISCOVERY_ELICITATION_SPEC.md` from the `jcode` project (MIT). No code is
taken from that repository.
