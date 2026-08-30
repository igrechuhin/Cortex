---
title: "Convert fix.md orchestration to Claude Code dynamic Workflow script"
component: "skill_pack"
work_type: feature
status: PENDING
priority: High
created: 2026-06-24
depends_on: []
---

## Goal

Replace the `fix.md` Synapse prompt with a deterministic Claude Code `Workflow`
JS script that encodes the four-target routing (coverage → quality → tests → docs),
per-target retry loops (max 3), and coverage-result-driven branching as JS
`switch`/`while` — eliminating LLM mis-routing between targets and over/under-run
of retry iterations.

## Context

`fix.md` orchestrates a diagnostic-first fix pipeline across four targets:
coverage, quality, tests, and docs. Its routing logic is the most decision-dense
of all Synapse prompts:

1. **PHASE 0 diagnosis** gates all subsequent work — skipping it is a documented
   violation, but LLMs sometimes proceed directly to fixing.
2. **Coverage preflight** determines whether the coverage target runs at all
   (threshold already met → skip), and its result determines which target runs
   next (`passed→quality`, `tests_failing→tests target`, `failed→STOP`).
3. **Per-target retry loops** run up to 3 `autofix → gate` iterations, each
   with different tools (quality uses `autofix()`, tests uses test-runner output,
   docs uses `run_docs_gate()`).
4. **Scope routing** inside the quality target branches on markdown-only vs
   source-changed — different tool chains for each.

All of this is currently LLM-reasoned from prose. A JS `switch` on coverage
result, a JS `while (iterations < 3)` per target, and a JS `if (scope ===
'markdown_only')` branch make these decisions exact and auditable.

Additional gains:

- `resumeFromRunId`: a fix run interrupted mid-quality-target resumes from
  quality, not from PHASE 0 diagnosis.
- Structured subagent results via `schema`: each subagent (@fix-coverage,
  @fix-quality, @fix-tests, @fix-docs) returns a typed object; the orchestrator
  branches on fields, not parsed text.
- `log()` narration: each target's start, iteration count, and outcome are
  emitted as Workflow progress messages visible in `/workflows`.

## Scope

**in_scope**

- Author a `fix.wf.js` Workflow script in `.cortex/workflows/` encoding PHASE 0
  and all four targets with JS control flow
- Implement coverage routing as a `switch` on `coverage_result.status`
  (`passed|skipped` → quality, `tests_failing` → tests, `failed|BLOCKED` → stop)
- Implement per-target retry loops as `while (iterations < 3 && !target_passed)`
- Implement quality scope routing as `if (scope === 'markdown_only')`
- Wire structured schemas for all four subagent returns
- Register the script so `/cortex/fix` invokes it via `Workflow({scriptPath})`
  with fallback to the markdown prompt
- Update `prompts-manifest.json` to mark `fix.md` as superseded
- Tests: assert coverage routing (all 3 branches), per-target retry cap,
  quality scope branching, PHASE 0 gate

**out_of_scope**

- Changing @fix-coverage, @fix-quality, @fix-tests, @fix-docs subagent logic
- Converting other prompts (separate plans)
- Adding new fix targets
- Altering the quality gate or autofix tool internals

## Approach

The script structure maps directly to `fix.md`'s decision tree:

```js
export const meta = {
  name: 'cortex-fix',
  description: 'Cortex fix pipeline: diagnose → coverage → quality → tests → docs',
  phases: [
    { title: 'Diagnosis' },
    { title: 'Coverage', detail: 'preflight + conditional execution' },
    { title: 'Quality', detail: 'autofix retry loop (max 3)' },
    { title: 'Tests', detail: 'test-runner retry loop (max 3)' },
    { title: 'Docs', detail: 'docs gate retry loop (max 3)' },
  ],
}

phase('Diagnosis')
const diagnosis = await agent('Diagnose fix scope and targets', {
  schema: DIAGNOSIS_SCHEMA,  // { scope, targets, change_scope: 'source'|'markdown_only' }
})
if (!diagnosis.targets.length) { log('Nothing to fix'); return { fixed: false } }

// Coverage target
let runQuality = true
let runTests = false
if (diagnosis.targets.includes('coverage')) {
  phase('Coverage')
  const cov = await agent('Fix coverage gaps', {
    agentType: 'fix-coverage',
    schema: COVERAGE_SCHEMA,  // { status: 'passed'|'skipped'|'tests_failing'|'failed'|'BLOCKED' }
  })
  switch (cov.status) {
    case 'passed': case 'skipped': break  // → quality
    case 'tests_failing': runTests = true; runQuality = false; break
    case 'failed': case 'BLOCKED':
      log(`Coverage hard stop: ${cov.status}`); return { ...cov, stopped_at: 'coverage' }
  }
}

// Quality target (with scope routing and retry loop)
if (runQuality && diagnosis.targets.includes('quality')) {
  phase('Quality')
  let qualityPassed = false
  let iterations = 0
  while (iterations < 3 && !qualityPassed) {
    const quality = await agent(
      diagnosis.change_scope === 'markdown_only'
        ? 'Fix markdown quality issues only'
        : 'Fix source code quality issues (lint, types, format)',
      { agentType: 'fix-quality', schema: QUALITY_SCHEMA }
    )
    qualityPassed = quality.passed
    iterations++
    if (!qualityPassed) log(`Quality iteration ${iterations}/3 failed, retrying...`)
  }
  if (!qualityPassed) log('Quality not resolved after 3 iterations — continuing to tests')
}

// Tests target
if (runTests || diagnosis.targets.includes('tests')) {
  phase('Tests')
  // ... same while (iterations < 3) pattern ...
}

// Docs target
if (diagnosis.targets.includes('docs')) {
  phase('Docs')
  // ... same while (iterations < 3) pattern ...
}
```

The script is stored at `.cortex/workflows/fix.wf.js`.

## Model and Effort per Agent Call

Specify `model` and `effort` opts on every `agent()` call in `fix.wf.js`:

| Phase / agentType | `model` | `effort` | Rationale |
|---|---|---|---|
| Diagnosis (inline) | `sonnet` | `medium` | Scope detection + target routing — needs judgment |
| Coverage (`fix-coverage`) | `sonnet` | `medium` | Writing new test files — requires understanding code patterns |
| Quality (`fix-quality`) | `haiku` | `low` | `autofix` + `run_quality_gate` loop — purely mechanical |
| Tests (`fix-tests`) | `sonnet` | `medium` | Root-cause diagnosis + targeted code edits |
| Docs (`fix-docs`) | `haiku` | `medium` | Memory bank sync + timestamp fixes — light judgment |

In the script this means, e.g.:
```js
const quality = await agent('Fix source code quality issues', {
  agentType: 'fix-quality',
  model: 'haiku',
  effort: 'low',
  schema: QUALITY_SCHEMA,
})
```

## Implementation Steps

1. Read `fix.md` in full. Extract: exact PHASE 0 gate conditions, coverage routing
   branches (all 5 status values), quality scope routing, per-target retry semantics
   (what constitutes `passed` for each target), and how targets are activated
   (`target=all` vs individual target). Produce annotated routing map.

2. Determine whether `target` parameter (coverage/quality/tests/docs/all) is
   passed as a Workflow `args` value or inferred from diagnosis. Map to JS
   conditional logic.

3. Define JSON Schema objects:
   `DIAGNOSIS_SCHEMA`, `COVERAGE_SCHEMA`, `QUALITY_SCHEMA`,
   `TESTS_SCHEMA`, `DOCS_SCHEMA`. Map from `pipeline_handoff` keys currently
   used in `fix.md`.

4. Write `.cortex/workflows/fix.wf.js` with all phases. Validate:
   - PHASE 0 diagnosis always runs first; no target runs without it
   - Coverage `switch` covers all 5 status values including `BLOCKED`
   - Quality `while` caps at 3; `change_scope` routing selects correct agent prompt
   - Tests and docs loops are structurally identical to quality loop
   - `phase()` titles match `meta.phases` exactly

5. Update the `/cortex/fix` invocation point to call `Workflow({ scriptPath })`
   with fallback to markdown prompt.

6. Update `prompts-manifest.json`: add `"superseded_by": "fix.wf.js"` to the
   fix entry.

7. Write tests in `tests/workflows/test_fix_wf.py`:
   - Coverage routing: mock `status='passed'` → quality runs; `status='tests_failing'`
     → quality skipped, tests runs; `status='BLOCKED'` → pipeline stops
   - Quality retry: mock 2 failures then pass → 3 iterations, `qualityPassed=true`
   - Quality retry cap: mock all failures → 3 iterations, pipeline continues to tests
   - Quality scope: `change_scope='markdown_only'` → agent prompt variant confirmed
   - PHASE 0 gate: assert diagnosis agent called first, before any target agent

## Verification Checklist

- `/cortex/fix` invokes the JS Workflow script (not the markdown prompt)
- PHASE 0 diagnosis always precedes any target agent call
- Coverage `BLOCKED` status terminates the pipeline immediately
- Coverage `tests_failing` skips quality and routes directly to tests
- Quality retry loop fires at most 3 times; passes correct scope variant
- `resumeFromRunId` resumes from the quality target when coverage is cached
- `pytest tests/workflows/test_fix_wf.py -v` all pass
- Markdown prompt fallback works when `.cortex/workflows/fix.wf.js` does not exist

## Dependencies

None. Existing subagents (@fix-coverage etc.) are unchanged.

## Success Criteria

- Coverage routing is a deterministic JS `switch` — no LLM routing decisions
  for the `tests_failing` vs `failed` distinction.
- Each target's retry loop is a hard `while (iterations < 3)` — no over-run
  or under-run.
- PHASE 0 diagnosis gates the pipeline by construction — it is the first `await
  agent()` call; no subsequent call can execute without it returning.
- ≥90% branch coverage of JS routing paths in test harness.

## Testing Strategy

Tests in `tests/workflows/test_fix_wf.py` using mocked `agent()` primitive:

- **Arrange**: stub diagnosis, coverage, quality, tests, docs agents with fixture schemas
- **Act**: run fix.wf.js via test harness with `args = { target: 'all' }` or specific target
- **Assert**: correct agents called in correct order; routing decisions match coverage status

Negative cases:

- `target='quality'` → only diagnosis + quality run; coverage and tests agents not called
- Quality always fails after 3 iterations → pipeline continues to tests (not a hard stop)
- Docs `run_docs_gate` fails all 3 → result has `docs_passed: false`; no crash

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `fix.md` has 5 coverage status values — missing one in the `switch` causes silent wrong routing | Exhaustive `switch` with explicit `default` that logs and stops; test covers all 5 values |
| Quality scope routing depends on `change_scope` field that must come from diagnosis | `DIAGNOSIS_SCHEMA` must include `change_scope`; validate at schema level before quality phase |
| Per-target `passed` semantics differ (quality: types+lint+format; tests: zero failures; docs: roadmap_sync+timestamps) | Each target's `schema.passed` is defined independently; agent prompts specify the criteria |
| fix.md edge cases (bridge mismatch non-blocking warning, roadmap.md corruption guard) | Keep fix.md as fallback; document known edge cases as // comments in the JS script |
| Large number of routing branches makes the script hard to maintain | Extract target execution into a `runTarget(name, agentType, schema, iterations)` helper function |
