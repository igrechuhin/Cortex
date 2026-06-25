---
title: "Convert do.md orchestration to Claude Code dynamic Workflow script"
component: "skill_pack"
work_type: "feature"
status: PENDING
priority: "High"
created: "2026-06-24"
depends_on: []
---

## Goal

Replace the `do.md` Synapse prompt with a deterministic Claude Code `Workflow`
JS script that encodes the implementation loop (`while !step_fully_complete`),
the review gate decision, and optional parallel step execution (`[P]` markers)
in code — eliminating LLM-reasoned loop termination and enabling true `pipeline()`
parallelism for plans that declare parallel steps.

## Context

`do.md` implements a six-phase orchestration: Selection → Implementation loop →
Review Gate → Finalize → Verify → Fix. The implementation loop is the core:
it spawns @implement-code repeatedly until `step_fully_complete=true`, capped
at 5 iterations. Plans can declare `[P]`-marked parallel steps; when
`can_parallelize=true`, up to 3 concurrent @implement-code agents are allowed.

Two structural problems motivate conversion:

1. **Loop termination via LLM reasoning**: The `while !step_fully_complete`
   loop is expressed as prose instructions. The LLM must read `pipeline_handoff`
   output, extract `step_fully_complete`, decide whether to loop, and count
   iterations — all via natural language reasoning. A JS `while` loop with a
   parsed boolean is exact and cannot over-run or under-run.

2. **Pseudo-parallel execution**: The `[P]` parallelism hint is advisory —
   agents approximate it by invoking subagents sequentially with coordination
   notes. A Workflow script can use `pipeline()` to run @implement-code agents
   truly concurrently over the parallel step list, with wall-clock time equal
   to the slowest single step rather than the sum.

Additional gains:

- `resumeFromRunId`: an interrupted implementation (e.g. after 3 of 5 subtasks)
  resumes from the failed iteration rather than restarting Selection.
- Structured return from @implement-code via `schema`: `{step_fully_complete,
  files_changed, subtasks_done, needs_review}` — no `pipeline_handoff` parsing
  in the orchestrator JS.
- Review Gate becomes a deterministic branch: `if (implResult.needs_review)`
  rather than "agent reads pipeline_handoff and decides".

## Scope

**in_scope**

- Author a `do.wf.js` Workflow script in `.cortex/workflows/` encoding all
  six phases with JS control flow
- Implement the implementation loop as `while (!result.step_fully_complete && iterations < 5)`
- Implement parallel step execution as `pipeline(parallelSteps, step => agent(..., {agentType: 'implement-code'}))`
  when `can_parallelize=true`
- Wire structured schemas for @implement-code return and review gate result
- Register the script so `/cortex/do` invokes it via `Workflow({scriptPath})`
  with fallback to the markdown prompt
- Update `prompts-manifest.json` to mark `do.md` as superseded
- Tests: assert loop termination, parallelism fan-out, review gate branching

**out_of_scope**

- Changing @implement-code subagent logic
- Converting fix/review/commit prompts (separate plans)
- Altering roadmap or plan file structures
- Implementing new parallelism beyond what `pipeline()` already provides

## Approach

The core of the script is the implementation loop and the parallel/sequential
routing:

```js
export const meta = {
  name: 'cortex-do',
  description: 'Cortex implement pipeline: select → implement loop → review → finalize',
  phases: [
    { title: 'Selection' },
    { title: 'Implementation', detail: 'loop until complete, max 5 iterations' },
    { title: 'Review Gate' },
    { title: 'Finalize' },
  ],
}

phase('Selection')
const selection = await agent('Select next roadmap step', {
  agentType: 'implement-code',  // Selection is inline; or dedicated selector
  schema: SELECTION_SCHEMA,     // { step, plan_file, scope, parallel_steps, can_parallelize }
})

phase('Implementation')
let implResult = null
let iterations = 0

if (selection.can_parallelize && selection.parallel_steps.length > 1) {
  // True parallel execution via pipeline()
  const results = await pipeline(
    selection.parallel_steps,
    step => agent(`Implement step: ${step}`, {
      agentType: 'implement-code',
      schema: IMPL_SCHEMA,
      phase: 'Implementation',
    })
  )
  implResult = mergeParallelResults(results)  // combine files_changed, subtasks_done
} else {
  // Sequential loop
  while (iterations < 5) {
    implResult = await agent('Implement next subtask', {
      agentType: 'implement-code',
      schema: IMPL_SCHEMA,  // { step_fully_complete, files_changed, subtasks_done, needs_review }
      phase: 'Implementation',
    })
    iterations++
    if (implResult.step_fully_complete) break
    log(`Subtask incomplete (${iterations}/5), continuing...`)
  }
}

phase('Review Gate')
if (implResult.needs_review) {
  const review = await agent('Review implementation for gaps', {
    schema: REVIEW_SCHEMA,  // { outcome: 'no_gaps' | 'gaps_found', gaps }
  })
  if (review.outcome === 'gaps_found') {
    log(`Gaps found: ${review.gaps.join(', ')} — reopening`)
    // re-enter implementation loop (handled by outer resumeFromRunId or next /do invocation)
  }
}

phase('Finalize')
// plan(complete) or roadmap update based on implResult + review outcome
```

The script is stored at `.cortex/workflows/do.wf.js`.

## Model and Effort per Agent Call

Specify `model` and `effort` opts on every `agent()` call in `do.wf.js`:

| Phase / call | `model` | `effort` | Rationale |
|---|---|---|---|
| Selection | `sonnet` | `medium` | Roadmap reasoning + scope judgment, not trivial |
| Implementation loop (sequential) | `sonnet` | `high` | Code writing — correctness-critical, full reasoning needed |
| Implementation (parallel steps) | `sonnet` | `high` | Same as sequential; each step writes real code |
| Review Gate | `sonnet` | `medium` | Gap detection needs judgment but not exhaustive search |
| Finalize | `haiku` | `low` | Mechanical: `plan(complete)` + roadmap write, no reasoning |

In the script this means, e.g.:
```js
const implResult = await agent('Implement next subtask', {
  agentType: 'implement-code',
  model: 'sonnet',
  effort: 'high',
  schema: IMPL_SCHEMA,
  phase: 'Implementation',
})
```

## Implementation Steps

1. Read `do.md` in full. Extract the exact phase sequence, gate conditions, loop
   cap, parallel step routing logic, and `pipeline_handoff` key names used for
   data passing. Produce an annotated phase map before writing JS.

2. Define JSON Schema objects: `SELECTION_SCHEMA`, `IMPL_SCHEMA`, `REVIEW_SCHEMA`,
   `FINALIZE_SCHEMA`. Determine which fields @implement-code currently writes to
   `pipeline_handoff` and map them to schema fields.

3. Implement `mergeParallelResults(results)` helper — a pure JS function that
   combines `files_changed` arrays and `subtasks_done` counts from parallel
   @implement-code results.

4. Write `.cortex/workflows/do.wf.js` with all phases. Validate:
   - Sequential loop caps at 5 iterations
   - Parallel branch uses `pipeline()` not `parallel()` (no barrier needed)
   - Review gate is a deterministic `if (implResult.needs_review)` branch
   - Finalize receives merged results from either code path

5. Update the `/cortex/do` invocation point to call `Workflow({ scriptPath })`
   with fallback to markdown prompt.

6. Update `prompts-manifest.json`: add `"superseded_by": "do.wf.js"` to the
   do entry.

7. Write tests in `tests/workflows/test_do_wf.py`:
   - Sequential loop: mock @implement-code returning `step_fully_complete=false`
     for 3 calls then `true`; assert 4 total calls, loop exits
   - Loop cap: mock always returning `false`; assert exactly 5 calls
   - Parallel path: `can_parallelize=true`, 3 parallel steps → assert `pipeline()`
     called with 3 items, not sequential loop
   - Review gate: `needs_review=false` → finalize called without review agent
   - Review gate: `needs_review=true, outcome='gaps_found'` → gaps logged

## Verification Checklist

- `/cortex/do` on a plan with sequential steps invokes the JS Workflow script
- Implementation loop fires exactly N times until `step_fully_complete=true`,
  never exceeding 5
- A plan with `[P]` parallel steps runs them concurrently via `pipeline()`;
  wall-clock is faster than sequential
- `resumeFromRunId` resumes from the Implementation phase when Selection is cached
- Review gate correctly branches on `needs_review` without LLM reasoning
- `pytest tests/workflows/test_do_wf.py -v` all pass
- Markdown prompt fallback works when `.cortex/workflows/do.wf.js` does not exist

## Dependencies

None. @implement-code subagent is unchanged; this plan changes only the
orchestration layer.

## Success Criteria

- Implementation loop termination is a hard JS `while` constraint — not prose.
- Parallel `[P]` steps execute concurrently via `pipeline()` with measurable
  wall-clock improvement over sequential baseline.
- Crashed mid-implementation resumes from the failed iteration via `resumeFromRunId`.
- ≥90% branch coverage of JS control flow paths in test harness.

## Testing Strategy

Tests in `tests/workflows/test_do_wf.py` using mocked `agent()` primitive:

- **Arrange**: stub @implement-code to return fixture schemas; set `can_parallelize`
  flag in Selection result
- **Act**: run do.wf.js via test harness
- **Assert**: call counts, parallelism, gate branching, finalize inputs

Negative cases:

- Selection returns empty step → pipeline returns immediately with structured message
- All 5 loop iterations return `step_fully_complete=false` → finalize receives
  `partial=true`; no crash
- Parallel step fails mid-pipeline → remaining steps complete; failed step
  surfaces in merged result as `null`-filtered

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `pipeline()` parallelism requires worktree isolation for file-writing agents | Evaluate whether @implement-code needs `isolation: 'worktree'`; if yes, add to pipeline opts |
| Merging parallel @implement-code results is non-trivial (conflicting edits) | Restrict parallelism to independent steps (no shared files); document constraint in script |
| Selection logic is complex (roadmap priority, gate_feedback reading) — hard to reproduce in schema | Keep Selection as a full agent call with prose prompt; schema only captures the output |
| `resumeFromRunId` caches @implement-code results but files may have changed | Document: resume only safe if working tree unchanged since prior run |
| do.md has accumulated edge cases (gate_feedback loop, partial_progress) | Keep do.md as fallback; run side-by-side for 2 weeks before removing |
