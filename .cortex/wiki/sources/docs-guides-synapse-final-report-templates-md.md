# Synapse Final Report Templates

Agent-to-user **final reports** at the end of Synapse prompts. Three report types based on workflow characteristics.

## Report Types

| Type | Workflows | Sections |
|------|-----------|----------|
| **Pipeline** | commit, do | Result, Phases, Artifacts, Next |
| **Diagnostic** | fix | Result, Diagnosis, Iterations, Changes, Next |
| **Artifact** | analyze, plan, review | Result, Output/Scores, Next |

## Section Semantics

### Result (required, all types)

First line: emoji + one-line outcome including command context.

```markdown
## Result

✅ Committed abc1234 to main (3 files)
```

Emoji meanings:

- ✅ Success
- ⚠️ Partial / warning (proceed with caution)
- ❌ Failed / blocked

### Phases (Pipeline type)

Table of pipeline phases with status and notes.

```markdown
## Phases

| Phase | Status | Notes |
|-------|--------|-------|
| Preflight | ✅ | snapshot: HEAD |
| Quality (A) | ✅ | 94% coverage |
| Docs (B) | ✅ | roadmap updated |
| Validate (C) | ✅ | — |
| Final gate | ✅ | 0 fix iterations |
```

**Memory bank rule**: Include memory bank updates in Notes column only when something changed. Do not show "Not updated".

### Diagnosis (Diagnostic type)

Root cause analysis for fix workflows.

For `/fix` coverage uplift runs, the 📈 coverage target (run first in `target=all`) owns the work and returns bounded telemetry in its handoff: `status`, `iterations`, `prior_coverage`, `final_coverage`, `coverage_delta`, `tests_added`, and `blocker_reason` when uplift is no longer feasible. The diagnostic report must surface the coverage row with a concrete `final_coverage` and `tests_added` list, or an explicit `BLOCKED` rationale with a specific `blocker_reason` — never a policy-only reminder.

```markdown
## Diagnosis

**Symptom**: Type error in src/cortex/tools/quality.py:142
**Cause**: Missing return type annotation
```

### Iterations (Diagnostic type)

Table of fix targets with iteration counts.

```markdown
## Iterations

| Target | Status | Count |
|--------|--------|-------|
| Quality | ✅ | 2 |
| Tests | ✅ | 0 |
| Docs | ⏭️ | skipped |
```

### Changes (Diagnostic type)

List of files modified with line references.

```markdown
## Changes

- src/cortex/tools/quality.py:142 — added return type
- tests/unit/test_quality.py — fixed assertion
```

### Artifacts (Pipeline type)

Concrete outputs: commit SHA, files, coverage, push status.

```markdown
## Artifacts

- Commit: `abc1234` on `main`
- Files: activeContext.md, roadmap.md, src/foo.py
- Coverage: 94%
- Pushed: ✅ origin/main
```

### Output (Artifact type)

Table of artifact metadata for analyze/plan.

```markdown
## Output

| Field | Value |
|-------|-------|
| Path | `.cortex/plans/phase-123-feature-x.md` |
| Roadmap | Added to "Active Work" |
| Status | PENDING |
```

### Scores (Review type)

Metrics table with deltas. Flag negative deltas.

```markdown
## Scores

| Metric | Score | Delta |
|--------|-------|-------|
| Architecture | 8 | +0 |
| Test Coverage | 7 | +1 |
| Error Handling | 6 | -1 ⚠️ |
| **Overall** | **7.5** | **+0.1** |
```

### Issues (Review type)

Issue tracker table.

```markdown
## Issues

| ID | Severity | Location |
|----|----------|----------|
| REV-2026-03-28-1 | High | src/foo.py:42 — Missing validation |
```

### Next (required, all types)

Explicit next actions or "None".

```markdown
## Next

Fix High severity issues before commit
```

Or:

```markdown
## Next

None
```

## Complete Examples

### Pipeline: commit

```markdown
## Result

✅ Committed abc1234 to main (3 files)

## Phases

| Phase | Status | Notes |
|-------|--------|-------|
| Preflight | ✅ | snapshot: HEAD |
| Quality (A) | ✅ | 94% coverage |
| Docs (B) | ✅ | roadmap updated |
| Validate (C) | ✅ | — |
| Final gate | ✅ | 0 fix iterations |

## Artifacts

- Commit: `abc1234` on `main`
- Files: activeContext.md, roadmap.md, src/foo.py
- Coverage: 94%
- Pushed: ✅ origin/main

## Next

None
```

### Pipeline: do

```markdown
## Result

✅ Implemented "Add quality config" (full)

## Phases

| Phase | Status | Notes |
|-------|--------|-------|
| Selection | ✅ | from roadmap priority |
| Implementation | ✅ | 5 files, 3 tests, 92% |
| Finalize | ✅ | plan archived |
| Verify | ✅ | roadmap entry removed |
| Fix | ✅ | 1 iteration |

## Artifacts

- Files: src/config.py, src/quality.py, tests/test_config.py
- Tests added: 3
- Coverage: 92%
- Plan: archived to `.cortex/plans/archive/`

## Next

None
```

### Diagnostic: fix

```markdown
## Result

✅ Fixed quality + tests (2 iterations)

## Diagnosis

**Symptom**: Type error in src/cortex/tools/quality.py:142
**Cause**: Missing return type annotation

## Iterations

| Target | Status | Count |
|--------|--------|-------|
| Quality | ✅ | 2 |
| Tests | ✅ | 0 |
| Docs | ⏭️ | skipped |

## Changes

- src/cortex/tools/quality.py:142 — added return type
- tests/unit/test_quality.py — fixed assertion

## Next

None
```

Coverage-only `/fix` runs may end with `Coverage | BLOCKED | <n>` when the 📈 coverage target stayed below threshold after bounded uplift attempts by `@fix-coverage`. In that case, the diagnostic report must include the `tests_added` list (non-empty when at least one attempt was made) or a concrete `blocker_reason`, and must mention `prior_coverage`, `final_coverage`, and `coverage_delta` in the diagnosis or next-step text so triage can distinguish "no attempt" from "attempted but blocked". The Tests row stays focused on assertion failures and subprocess crashes only — it never reports a `Tests | BLOCKED` for coverage reasons.

### Artifact: plan

```markdown
## Result

✅ Plan created: phase-123-feature-x.md

## Output

| Field | Value |
|-------|-------|
| Path | `.cortex/plans/phase-123-feature-x.md` |
| Roadmap | Added to "Active Work" |
| Status | PENDING |

## Next

`/cortex/do @.cortex/plans/phase-123-feature-x.md`
```

### Artifact: analyze

```markdown
## Result

✅ Analysis complete

## Output

| Field | Value |
|-------|-------|
| Report | `.cortex/reviews/session-optimization-2026-03-28T14-30.md` |
| Compaction | 2400 → 1800 tokens (25% reduction) |

## Next

None
```

### Artifact: review

```markdown
## Result

⚠️ Review complete — 3 issues found

## Scores

| Metric | Score | Delta |
|--------|-------|-------|
| Architecture | 8 | +0 |
| Test Coverage | 7 | +1 |
| Code Style | 9 | +0 |
| Error Handling | 6 | -1 ⚠️ |
| **Overall** | **7.5** | **+0.1** |

## Issues

| ID | Severity | Location |
|----|----------|----------|
| REV-2026-03-28-1 | High | src/foo.py:42 — Missing validation |
| REV-2026-03-28-2 | Medium | src/bar.py:18 — Broad exception |

## Next

Fix High severity issues before commit
```

## Anti-patterns

- **Process summaries**: "I ran the pipeline" without phase status or artifacts
- **Buried failures**: Leading with success while ❌ appears at the bottom
- **Memory bank noise**: "Memory bank: Not updated" — omit if nothing changed
- **Missing Next**: Always include `## Next` with explicit "None" or action items
- **Prose instead of tables**: Use tables for phases/iterations/scores
