---
title: "Convert commit.md orchestration to Claude Code dynamic Workflow script"
component: "skill_pack"
work_type: "feature"
status: PENDING
priority: "High"
created: "2026-06-24"
depends_on: []
---

## Goal

Replace the `commit.md` Synapse prompt — which relies on LLM reasoning to follow
16-phase commit pipeline instructions — with a deterministic Claude Code `Workflow`
JS script that encodes retry loops, conditional gates, and subagent sequencing in
code, eliminating the class of bugs where agents pause between phases, skip retry
iterations, or misroute based on scope analysis.

## Context

`commit.md` is the most complex Synapse prompt: 16 phases, 5 subagents
(@commit-preflight, @commit-phase-a, @commit-phase-b, @commit-phase-c,
@commit-final-gate), a Phase A retry loop (max 3 autofix iterations), and
conditional Step 12 scope routing (source-changed vs markdown-only vs nothing).

Two documented failure modes motivate this conversion:

1. **Premature stopping**: CLAUDE.md explicitly instructs "do not pause after
   Phase A" — because LLM agents sometimes do, treating Phase A completion as
   a natural stopping point. A Workflow script makes pausing physically impossible:
   `agent()` calls are sequential JS, not instructions an agent can choose to halt.

2. **Retry loop drift**: The Phase A `autofix → gate` retry loop (max 3) is
   implemented as LLM instructions. Agents sometimes cap at 2, sometimes continue
   past failures. A `while (iterations < 3 && !passed)` JS loop is exact.

Additional gains:

- `resumeFromRunId`: a crashed commit mid-Phase B can resume from the failed
  phase rather than restarting from Preflight.
- `budget` tracking: enforce token ceiling across all subagent calls.
- Structured subagent results via `schema`: Phase A returns `{passed, iterations,
  coverage}` as a typed object rather than free text parsed by the next phase.

## Scope

**in_scope**

- Author a `commit.wf.js` Workflow script in `.cortex/workflows/` encoding all
  16 phases as sequential `agent()` calls with JS control flow
- Implement Phase A retry loop as `while` with `max_iterations=3`
- Implement Step 12 scope routing as `if/else` branches (source vs markdown-only)
- Wire structured schemas for subagent returns (`{passed, snapshot_ref, coverage}`,
  `{docs_phase_passed}`, `{submodule_committed}`)
- Preserve all existing subagent types (@commit-preflight, @commit-phase-a, etc.)
  via `opts.agentType`
- Register the script so `/cortex/commit` invokes it via `Workflow({scriptPath})`
  instead of loading the markdown prompt
- Update `prompts-manifest.json` to mark `commit.md` as superseded
- Tests: a lightweight integration harness that runs the script with mocked
  subagents and asserts phase ordering, retry cap, and scope routing

**out_of_scope**

- Changing the logic of individual subagent phases (preflight, phase-a, etc.)
- Converting other prompts (each has its own plan)
- Parallel phase execution within commit (phases are inherently sequential)
- Altering git operations — the subagents still run shell commands

## Approach

The Workflow script structure mirrors the existing phase sequence but replaces
prose instructions with JS:

```js
export const meta = {
  name: 'cortex-commit',
  description: 'Cortex commit pipeline: preflight → A → B → C → gate → push',
  phases: [
    { title: 'Preflight' },
    { title: 'Phase A', detail: 'quality gate + autofix retry loop (max 3)' },
    { title: 'Phase B', detail: 'docs sync' },
    { title: 'Phase C', detail: 'validate + submodule commit' },
    { title: 'Final Gate' },
    { title: 'Commit & Push' },
  ],
}

phase('Preflight')
const preflight = await agent('Run commit preflight checks', {
  agentType: 'commit-preflight',
  schema: PREFLIGHT_SCHEMA,  // { passed, snapshot_ref, staged_count }
})
if (!preflight.passed) { log(`Preflight failed: ${preflight.error}`); return preflight }

phase('Phase A')
let phaseA = null
let iterations = 0
while (iterations < 3) {
  phaseA = await agent('Run Phase A quality gate', {
    agentType: 'commit-phase-a',
    schema: PHASE_A_SCHEMA,  // { passed, coverage, autofix_ran }
  })
  iterations++
  if (phaseA.passed) break
  if (iterations < 3) log(`Phase A failed (attempt ${iterations}/3), autofixing...`)
}
if (!phaseA.passed) { log('Phase A failed after 3 attempts'); return { ...phaseA, iterations } }

// ... phases B, C, final gate ...

phase('Commit & Push')
const scope = phaseA.scope  // 'source' | 'markdown_only' | 'none'
if (scope === 'none') { log('Nothing to commit'); return { committed: false } }
const gate = await agent(
  scope === 'markdown_only'
    ? 'Run markdown-only final gate'
    : 'Run full source final gate',
  { agentType: 'commit-final-gate', schema: GATE_SCHEMA }
)
// ... git commit + push via subagent ...
```

The script is stored at `.cortex/workflows/commit.wf.js`. The `/cortex/commit`
slash command is updated to call `Workflow({ scriptPath: '.cortex/workflows/commit.wf.js' })`
instead of loading `commit.md`.

## Model and Effort per Agent Call

Specify `model` and `effort` opts on every `agent()` call in `commit.wf.js`:

| Phase / agentType | `model` | `effort` | Rationale |
|---|---|---|---|
| Preflight (`commit-preflight`) | `haiku` | `low` | MCP health + snapshot — purely mechanical tool calls |
| Phase A (`commit-phase-a`) | `haiku` | `low` | `run_quality_gate` + `autofix` retry loop — no reasoning |
| Phase B (`commit-phase-b`) | `sonnet` | `medium` | Docs sync needs judgment (what changed, how to summarize) |
| Phase C (`commit-phase-c`) | `haiku` | `low` | Timestamp validation + submodule git ops — mechanical |
| Final Gate (`commit-final-gate`) | `haiku` | `medium` | Scope classification (source vs markdown-only) needs light reasoning |

In the script this means, e.g.:
```js
const preflight = await agent('Run commit preflight checks', {
  agentType: 'commit-preflight',
  model: 'haiku',
  effort: 'low',
  schema: PREFLIGHT_SCHEMA,
})
```

## Implementation Steps

1. Read `commit.md` in full. Extract the exact phase sequence, all conditional
   branches, retry caps, and data dependencies between phases. Produce an
   annotated phase map (can be inline in the script as a comment block).

2. Define Pydantic-style JS schema objects for each subagent's return value:
   `PREFLIGHT_SCHEMA`, `PHASE_A_SCHEMA`, `PHASE_B_SCHEMA`, `PHASE_C_SCHEMA`,
   `GATE_SCHEMA`. These are JSON Schema objects passed to `agent()` `schema` opt.

3. Write `.cortex/workflows/commit.wf.js` implementing all phases. Validate:
   - Phase A `while` loop caps at 3 iterations
   - Step 12 scope routing covers all three branches
   - Early-exit returns are structured (not thrown)
   - `phase()` calls match `meta.phases` titles exactly

4. Update the `/cortex/commit` invocation point (wherever the prompt is loaded
   — likely in `src/cortex/setup/prompts.py` or the lazy prompt registry) to
   call `Workflow({ scriptPath })` when the script file exists, falling back to
   the markdown prompt if it does not (safe rollout).

5. Update `prompts-manifest.json`: add `"superseded_by": "commit.wf.js"` to
   the commit entry.

6. Write tests in `tests/workflows/test_commit_wf.py`:
   - Mock all 5 subagent `agentType` calls; assert call order
   - Phase A: mock first 2 calls as `passed=false`, third as `passed=true`; assert `iterations=3`
   - Phase A: mock all 3 as `passed=false`; assert early exit with `iterations=3, passed=false`
   - Step 12 routing: `scope='markdown_only'` → final gate receives correct prompt variant
   - Preflight failure → pipeline stops before Phase A

## Verification Checklist

- Running `/cortex/commit` on a clean repo invokes the Workflow script (not the markdown prompt)
- Phase A retry loop fires exactly 3 times when gate keeps failing; stops as soon as it passes
- `resumeFromRunId` resumes from Phase B when Phase A has already completed
- Structured subagent results are typed — no string parsing in JS control flow
- All 5 subagent types are invoked with correct `agentType` opts
- Markdown prompt fallback works when `.cortex/workflows/commit.wf.js` does not exist
- `pytest tests/workflows/test_commit_wf.py -v` all pass
- Existing commit pipeline manual smoke-test: `git commit` on a real change completes all phases

## Dependencies

None. Existing subagents (@commit-preflight etc.) are unchanged; this plan
only changes the orchestration layer above them.

## Success Criteria

- Zero LLM instructions needed to advance between commit phases — all sequencing
  is in JS.
- Phase A retry cap is a hard `while (iterations < 3)` constraint, not prose.
- Crashed commit mid-Phase B is resumable via `resumeFromRunId` without
  re-running Preflight or Phase A.
- All existing commit pipeline tests pass; new Workflow tests achieve ≥90%
  branch coverage of the JS script's control flow paths.

## Testing Strategy

Unit/integration tests in `tests/workflows/test_commit_wf.py` (Python, using
the Workflow test harness if available, else mocking the `agent()` primitive):

- **Arrange**: stub each `agentType` call to return a fixture schema object
- **Act**: run the Workflow script via the test harness
- **Assert**: phase call order, retry counts, early-exit conditions, scope routing

Negative cases:

- Preflight `passed=false` → pipeline returns immediately, Phase A never called
- Phase A fails all 3 attempts → `passed=false` result, Phases B/C never called
- Phase C submodule failure (non-blocking) → pipeline continues to final gate

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Workflow script JS syntax error silently breaks `/cortex/commit` | Fallback to markdown prompt if script file missing or parse error; CI lints the JS |
| Subagent `schema` validation rejects current free-text phase outputs | Start with loose schemas (`additionalProperties: true`); tighten after smoke-testing |
| `resumeFromRunId` caches Phase A result but code changes mid-commit invalidate it | Document: resume is only safe within the same working tree state; warn in script `log()` |
| Converting 16-phase prompt faithfully is high-effort | Phase 1 (annotated phase map in Step 1) must be reviewed before writing JS |
| Regression: edge cases in `commit.md` built up over many sessions | Keep `commit.md` as fallback; run both in parallel for 2 weeks before removing prompt |
