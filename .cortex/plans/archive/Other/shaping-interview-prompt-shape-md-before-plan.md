---
title: "Shaping Interview Prompt (shape.md) Before Plan"
component: "synapse-prompts"
work_type: feature
status: PENDING
priority: High
created: 2026-08-02
depends_on: []
---

## Goal

Add a `shape.md` Synapse prompt plus a `shape-interviewer` subagent that interrogates the user one question at a time until the decision tree for a request is resolved, then emits a shaping decision record consumed by `/cortex/plan` as pre-resolved constraints.

## Context

Cortex's pipeline starts at `/cortex/plan`, which assumes the user already knows what they want. `explore.md` covers a different need: the agent generates 2-5 candidate approaches and asks the user to pick one. Neither prompt resolves *unknown requirements* — the constraints, edge cases, and success conditions that live only in the user's head.

Analysis of the aihero.dev skills pack (Matt Pocock, `mattpocock/skills`) identified `/grill-me` as the transferable missing piece. Its mechanics are specific and directly portable:

- one question at a time, never a wall of questions
- the agent proposes its own recommended answer so the user can just confirm
- if an answer is discoverable in the codebase, the agent reads the code instead of asking
- loop until the decision tree is resolved, then hand off

The third bullet is the one Cortex most lacks: `plan-creator` today has no license to stop and ask, so it silently guesses. This plan closes the gap at the front of the spine without disturbing anything downstream.

## Scope

**in_scope**

- New `.cortex/synapse/prompts/shape.md` prompt file
- New `.claude/agents/shape-interviewer.md` subagent definition
- Registration of `shape.md` in `.cortex/synapse/prompts/prompts-manifest.json`
- Shaping decision-record template and write path under `.cortex/plans/shape/`
- A `shape_log_path` passthrough into `plan(operation="create")`, mirroring the existing `explore_log_path` parameter
- Step 4 of `plan.md` extended so the gate chooses between explore, shape, both, or neither
- Tests for the new tool parameter and log-path validation

**out_of_scope**

- Changes to `explore.md` behavior or its log format
- Any change to `do.md`, `review.md`, `fix.md`, or `commit.md`
- Installing or vendoring the `mattpocock/skills` package itself
- Glossary/terminology enforcement (separate plan)
- Prompt-layer DRY refactor (separate plan)

## Approach

Model `shape.md` closely on `explore.md`'s structure — same orientation preamble (`session()`, `cortex://context`, `cortex://rules`), same ephemeral-log guardrails, same "do not create formal plans or roadmap entries" boundary. The difference is the body: instead of a generate-options loop, an interview loop with an explicit termination condition.

The interview loop is the core artifact and must be specified precisely enough that the subagent cannot degrade into a questionnaire dump. Each iteration: identify the single highest-leverage unresolved decision; attempt to resolve it from the codebase first; if it remains unresolved, ask exactly one question with a recommended default; record the answer. Terminate when no unresolved decision materially changes the resulting plan.

The output is a shaping record with resolved decisions, explicit assumptions, and out-of-scope declarations. `plan()` receives it via a new `shape_log_path` parameter and treats its decisions as fixed constraints rather than re-derivable choices. Reusing the `explore_log_path` plumbing keeps the tool surface additive and avoids a new tool.

## Implementation Steps

1. Read `.cortex/synapse/prompts/explore.md` and `plan.md` in full to fix the shared prompt conventions (heading order, guardrail phrasing, orientation preamble) that `shape.md` must match.
2. Write `.cortex/synapse/prompts/shape.md` with sections: When to invoke, Goal, Workflow, Interview Loop, Termination Condition, Guardrails, Shaping Record Template, Handoff.
3. Specify the interview loop with the four mechanics verbatim: one question per turn; proposed recommended answer; codebase-first resolution; loop until decision tree resolved.
4. Specify the termination condition as binary and checkable: no remaining unresolved decision would change the plan's scope, approach, or success criteria.
5. Define the shaping record template (`.cortex/plans/shape/shape-<slug>.md`) with sections: Topic, Created, Resolved Decisions (decision / answer / source: user or codebase), Assumptions, Explicitly Out of Scope, Open Risks.
6. Add the `shape.md` entry to `prompts-manifest.json` under `general` with `internal: true` and keywords covering shaping, requirements, interview, decisions.
7. Add `.claude/agents/shape-interviewer.md` granting `mcp__cortex__*`, `Read`, `Grep`, `Glob` — read-only by construction, no `Edit` or `Write` beyond the shaping record.
8. Add a `shape_log_path` parameter to the `plan` tool alongside `explore_log_path`, with the same validation and path-containment checks.
9. Thread `shape_log_path` through plan creation so resolved decisions are injected into the plan body's Context and Scope sections as fixed constraints.
10. Extend Step 4 of `plan.md` (Explore Gate) into a combined gate that routes to shape, explore, both, or neither, with explicit selection criteria for each.
11. Write tests: `shape_log_path` accepted and validated; path traversal rejected; missing file handled; both log paths supplied together; neither supplied.
12. Run `run_quality_gate()` and `run_docs_gate()` until clean.

## Verification Checklist

- Step 2-5: re-read `shape.md` after writing; confirm all eight sections present and the four interview mechanics appear explicitly.
- Step 6: grep `prompts-manifest.json` for `shape.md`; confirm valid JSON via the docs gate.
- Step 7: confirm `.claude/agents/shape-interviewer.md` grants no write tool beyond what the shaping record needs.
- Step 8-9: grep `src/cortex/tools/plans/` for `explore_log_path` and confirm every site handling it also handles `shape_log_path`.
- Step 10: re-read `plan.md` Step 4; confirm the gate names all four routes and that skip criteria remain reachable.
- Step 11: confirm new tests follow AAA and cover the negative cases listed.
- After all steps: re-read `prompts-manifest.json`, `shape.md`, and `plan.md` to confirm no section drift.

## Dependencies

None. This plan is independent of `content-preserving-wal-as-of.md` and of the two sibling absorption plans (prompt reference layer, glossary gate).

## Success Criteria

- `.cortex/synapse/prompts/shape.md` exists and is registered in `prompts-manifest.json`
- `shape-interviewer` subagent is defined and invocable
- `plan(operation="create", shape_log_path=...)` accepts a shaping record and reflects its decisions in the generated plan's Context and Scope
- Invalid or traversing `shape_log_path` values are rejected with a typed error
- `plan.md` Step 4 documents all four gate routes
- `run_quality_gate()` and `run_docs_gate()` both pass
- New code paths reach the 95% coverage target

## Testing Strategy

Target 95% coverage on changed lines, AAA pattern throughout, `tests/tools/test_plan_shape_log.py`.

- Unit — positive: valid `shape_log_path` accepted; decisions surfaced in generated plan body.
- Unit — negative: path traversal (`../`), absolute path outside project, nonexistent file, empty file, malformed record without a Resolved Decisions section.
- Unit — interaction: `shape_log_path` and `explore_log_path` supplied together; neither supplied (existing behavior unchanged).
- Integration: end-to-end `plan(operation="create")` with a fixture shaping record; assert all ten required plan sections still present.
- Docs: markdown lint over `shape.md` and the record template; JSON schema validity of `prompts-manifest.json`.

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Interview loop degrades into a wall of questions | User friction; prompt gets abandoned | Termination condition is binary and checkable; "one question per turn" stated as a hard gate, not a preference |
| Overlap with `explore.md` confuses the agent about which to run | Wrong prompt selected; wasted turns | Step 4 gate states explicit, non-overlapping selection criteria: shape resolves unknown requirements, explore compares known approaches |
| Agent asks what it could have read from the codebase | Wastes user time; erodes trust in the prompt | Codebase-first resolution stated as a mandatory pre-check before every question, with the answer's source recorded in the record |
| `shape_log_path` duplicates `explore_log_path` plumbing | Divergence and drift between the two paths | Share one validation helper rather than copying; verification checklist greps every `explore_log_path` site |
| Shaping records accumulate as clutter under `.cortex/plans/shape/` | Directory rot | Mirror the existing explore-log lifecycle, including the `clear_explore_logs` equivalent |

## Change History

*No revisions recorded yet — enrich or edit implementation steps to append history.*
