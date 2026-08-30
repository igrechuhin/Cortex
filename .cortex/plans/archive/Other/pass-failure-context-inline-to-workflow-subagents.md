---
title: "Pass Failure Context Inline to Workflow Subagents"
component: synapse
work_type: optimize
status: PENDING
priority: Medium
created: 2026-06-25
depends_on: []
status: PENDING
---

## Goal

Reduce wasted subagent tool calls and iteration count by pre-running diagnostics in the workflow JS orchestrator and injecting the specific failures into each agent's prompt — so agents start with the answer rather than re-discovering it.

## Context

Currently each `fix-tests`, `fix-quality`, and `commit-phase-a` subagent starts by calling `run_quality_gate()` as its first action, spending ~20K tokens and 2–3 minutes just to learn what's failing. The workflow JS already has this information from the coverage pre-flight gate (`preflight_passed`, `tests_failed`, `errors`). Passing it in the prompt eliminates the first gate call in most subagents, saving one full quality gate run per target per iteration. For a typical fix run (quality + tests), that's 2 gate calls avoided = ~5 minutes and ~40K tokens saved per run.

## Scope

**in_scope**

- Update `fix.wf.js`: before spawning `@fix-quality` and `@fix-tests`, run `run_quality_gate()` inline (or reuse coverage pre-flight result) and inject `errors`, `tests_failed`, `failing_tests` into the agent prompt
- Update `commit.wf.js`: pass preflight `staged_count`, `snapshot_ref`, and Phase A gate results into subsequent phase prompts
- Keep agent specs unchanged (they remain valid for standalone invocation)
- Run quality gate to confirm no regressions

**out_of_scope**

- Changing cursor-agent `.md` files (covered by the trim plan)
- Changing MCP tool implementations
- Passing context to `fix-docs` (docs gate is fast; no benefit)
- `do.wf.js` (implement-code agent needs full context discovery; pre-injecting would over-constrain it)

## Approach

In `fix.wf.js`, the coverage pre-flight already calls `run_quality_gate()` once. Extract `results.type_check.output`, `results.quality.output`, and `results.tests.errors` from that result and pass them as a `prior_gate_output` block in the quality and tests agent prompts. The agents can then skip their first gate call and go straight to fixing. Add a `prior_failures` field to `QUALITY_SCHEMA` and `TESTS_SCHEMA` so agents can acknowledge what they received.

In `commit.wf.js`, pass `preflight.snapshot_ref` and `preflight.staged_count` into the Phase A prompt, and pass Phase A's `gate_output` summary into the Phase B prompt so Phase B knows which files were changed.

## Implementation Steps

1. In `fix.wf.js`: after the coverage pre-flight `run_quality_gate()` call, extract error summary into a `priorErrors` variable (type errors, lint errors, failing test names from `results.*.errors`).
2. Append `priorErrors` to the quality agent prompt: `"Prior gate output (skip re-running gate if these are the only failures): <errors>"`.
3. Append `priorErrors` to the tests agent prompt similarly.
4. In `commit.wf.js`: pass `preflight.snapshot_ref` and staged file list into Phase A prompt.
5. Pass Phase A `gate_summary` (pass/fail counts) into Phase B prompt as context.
6. Run `run_quality_gate()` to confirm no regressions.
7. Smoke-test: invoke `/cortex/fix` on a tree with known type errors; confirm quality agent skips initial gate call in `/workflows` tool count.

## Verification Checklist

- [ ] `fix.wf.js` passes `priorErrors` to quality and tests agent prompts
- [ ] `commit.wf.js` passes preflight context to Phase A and Phase B
- [ ] Workflow JS still parses correctly (no syntax errors — run node parse check)
- [ ] `run_quality_gate()` passes with no new failures
- [ ] `/workflows` panel shows fewer tool calls per subagent on a test run

## Dependencies

- Trim plan (`trim-workflow-agent-specs-for-claude-code-cli.md`) is independent; either can run first

## Success Criteria

- Quality and tests subagents make ≥1 fewer `run_quality_gate()` call per iteration on average
- No new test failures introduced
- `/workflows` tool call count per fix run reduced by ≥10 calls

## Testing Strategy

- Existing `tests/workflows/` structural tests continue to pass unchanged
- Manual verification: run `/cortex/fix` before and after, compare tool call counts from `/workflows` output
- No new unit tests needed — JS control flow changes are covered by existing structural tests

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| Agent receives stale prior_errors (from coverage pre-flight) that don't match current state after autofix | Add a note in the prompt: "re-run gate if autofix may have changed the error set" — agent can still call gate if needed |
| `results.*.errors` truncated in large outputs → agent gets incomplete context | Extract only the first 20 error lines; agent falls back to gate if errors seem incomplete |
| JS extraction logic adds complexity and its own bugs | Keep extraction simple: `(results.type_check?.errors ?? []).slice(0,20).join('\n')` — one line per check |

## Change History

_No revisions recorded yet — enrich or edit implementation steps to append history._
