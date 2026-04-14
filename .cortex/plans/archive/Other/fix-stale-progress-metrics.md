---
title: "Fix: Stale Test-Count Metric in progress.md What Works Section"
component: "memory-bank"
work_type: "fix"
status: PENDING
priority: medium
created: 2026-04-13
depends_on: []
---

## Fix: Stale Test-Count Metric in progress.md What Works Section

## Goal

`progress.md` has a "What Works" section (line 257) that contains a static,
hardcoded test-count snapshot: `"3702 tests, 90.36% coverage"`. Entries
earlier in the same file (2026-03-31 region) cite a 5805/5805 run, and the
current MEMORY.md index notes 5182 tests. The stale number erodes trust in
the memory bank and can mislead planning and quality decisions.

The fix is twofold:

1. Update the hardcoded number to reflect the current state.
2. Add a lint check or guidance so this section does not silently rot again.

## Context

- `progress.md` line 257 (approximate): `"Pre-commit pipeline (fix_errors,
  format, type_check, quality, tests); 3702 tests, 90.36% coverage; ..."`
- More recent entries in the same file cite 5805/5805 and current MEMORY.md
  cites 5182, indicating the "What Works" figure is at least 6 weeks stale.
- The `lint_memory_bank` tool (`LintCheck` family) already exists and could
  host a `CodeClaimCheck`-style rule for numeric status in "What Works".
- No CI/CD currently validates the "What Works" counter against actual test
  output.

## Implementation Steps

### Step 1 — Confirm current test count

Run the quality gate or read the latest test run from CI:

```bash
uv run pytest --co -q 2>/dev/null | tail -n 3
```

Or read the most recent `run_quality_gate` output from `.cortex/memory-bank/`.

### Verification checklist 1

- [ ] Exact current test count and coverage % are known
- [ ] Source is authoritative (fresh test run or CI artefact, not another stale
  snapshot)

### Step 2 — Update "What Works" in progress.md

Edit the `## What Works` section of `.cortex/memory-bank/progress.md`:

1. Replace the stale `3702 tests, 90.36% coverage` with the current figure.
2. Add a date stamp in parentheses: `(as of 2026-04-13)` so readers can judge
   freshness.
3. Optionally add a note: `# AI: updated by fix-stale-progress-metrics plan —
   this counter must be refreshed after each significant test suite change`.

Do **not** use `manage_file(write)` directly on `roadmap.md`; use
`manage_file(write)` on `progress.md` which is a legitimate arbitrary
memory-bank file (not the roadmap).

### Verification checklist 2

- [ ] "What Works" no longer contains `3702`
- [ ] New count matches actual test suite (verified in Step 1)
- [ ] Date stamp present so staleness is visible

### Step 3 — Add a `StaleNumericClaimCheck` to `lint_memory_bank`

In `src/cortex/tools/lint/` (wherever `LintCheck` subclasses live):

1. Create `StaleNumericClaimCheck` that:
   - Scans `progress.md` "What Works" section for patterns like `\d{3,5} tests`
     and `\d{2}\.\d{1,2}% coverage`.
   - Compares the captured number against the last `run_quality_gate` result
     stored in `.cortex/memory-bank/` (or session config).
   - Emits a `LintFinding(severity="warning", ...)` when the delta exceeds a
     configurable threshold (default: 10% drift or 200 tests).
2. Register the check in the `lint_memory_bank` aggregator.
3. Add unit tests: stale number triggers warning; fresh number is clean; missing
   "What Works" section is a no-op.

### Verification checklist 3

- [ ] `lint_memory_bank()` returns a warning when "What Works" is stale
- [ ] No warning when number is current
- [ ] Unit tests cover warning/clean/no-section paths
- [ ] `LintCheck` subclass follows existing patterns in the module

### Step 4 — Document lint-config knob

Add a `stale_test_count_threshold` key to `docs/guides/lint-config.md` and
the `.cortex/config/lint-config.json` schema docs, consistent with existing
`stale_threshold_days` documentation.

### Verification checklist 4

- [ ] `docs/guides/lint-config.md` documents `stale_test_count_threshold`
- [ ] Schema key is optional with a sensible default

### Step 5 — Quality gate and docs gate

Run `run_quality_gate()` and `run_docs_gate()`. Fix any regressions.

## Dependencies

- `lint_memory_bank` tool and `LintCheck` base class must exist (confirmed).
- `docs/guides/lint-config.md` must exist (confirmed — referenced in progress
  log 2026-04-07).

## Success Criteria

1. `progress.md` "What Works" test count matches the current test suite.
2. `lint_memory_bank()` emits a warning when the figure drifts by more than
   the configured threshold.
3. Unit tests for `StaleNumericClaimCheck` pass at 95%+ coverage for the new
   code.
4. Quality and docs gates both green.

## Testing Strategy

- **Unit tests** (Step 3): parametrized tests for stale/fresh/missing-section.
- **Integration**: call `lint_memory_bank()` against a fixture `progress.md`
  with a known-stale number; assert finding is emitted.
- **Regression**: existing `LintCheck` tests must still pass.

Coverage target: 95% for `StaleNumericClaimCheck` and its helpers.

## Partial Progress Log

- 2026-04-14: Updated stale What Works metrics and implemented StaleNumericClaimCheck with tests/docs integration — files: .cortex/memory-bank/progress.md, src/cortex/tools/lint/memory_bank_lint_checks.py, src/cortex/tools/lint/lint_memory_bank.py, src/cortex/tools/lint/**init**.py, tests/unit/tools/lint/test_memory_bank_lint_checks.py, docs/guides/lint-config.md
