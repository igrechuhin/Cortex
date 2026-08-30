---
id: reduce-quality-gate-latency-tokens
title: "Reduce Quality Gate Latency and Pre-commit Token Bloat"
status: IN_PROGRESS
priority: High
created: 2026-04-03
area: Quality & Reliability Improvements
tags: [quality-gate, pre-commit, latency, tokens, caching, performance]
---

## Goal

Reduce `run_quality_gate` average latency from 56 seconds toward ≤ 30 seconds, reduce
`run_quality_gate` average response from 2,323 tokens to < 800 tokens, and reduce redundant
`execute_pre_commit_checks` runs (17,844 calls × 3.3s avg = ~16.4h cumulative) by improving
skip-logic hit rate and eliminating unnecessary re-runs.

## Context

### Metrics

From 418K events over 50 days:

| Tool | Calls | Avg Latency | Total Tokens | Avg Tokens |
|------|-------|-------------|--------------|------------|
| `run_quality_gate` | 921 | 56s | 2,142K | 2,323 |
| `execute_pre_commit_checks` | 17,844 | 3.3s | 66.7M | 3,739 |

- `run_quality_gate_fresh` (now removed) was 101s average — removal is already done
- 921 quality gate runs × 56s = 14.4 hours of wall-time per 50-day window
- `execute_pre_commit_checks` is the 2nd most-called tool overall; redundant re-runs likely given
  the `skip_if_clean` path already exists but may not be activated in all agent call sequences

### Code Path — `run_quality_gate`

`run_quality_gate()` → `run_quality_gate_inner()`:

1. `clear_all_cached_results(root)` — invalidates all detached worker cache on every call
2. `_read_quality_gate_config(root)` — reads pipeline session file
3. `_spawn_and_poll_phase_a(root, ...)` — acquires `get_phase_a_lock()`, starts detached subprocess
   via `_start_phase_a_job()`, polls with `poll_phase_a_result()` (2s poll interval)
4. `apply_reflection_to_gate_result()` — optional reflection pass
5. `persist_gate_feedback()` — writes gate feedback
6. `append_agent_log_to_quality_result(result)` — appends full agent log to response dict

The `clear_all_cached_results()` call in step 1 is unconditional — it deletes all cached result
files every time `run_quality_gate` runs, even if the source has not changed. The subprocess
spawned in step 3 runs the full Phase A suite: type check, lint, format check, tests, markdown
lint. The 56s average is the subprocess execution time, which is hard to reduce without
parallelism or smarter incremental checking.

The 2,323 avg token response includes the full `checks` array (one entry per check with details)
plus the `agent_log` appended by `append_agent_log_to_quality_result`. For passing runs, most
check details add no actionable value.

### Code Path — `execute_pre_commit_checks`

`execute_pre_commit_checks_dispatch()` → `_dispatch_phase()` → detached or inline runner. The
`try_skip_clean_checks()` path exists and uses `PipelineDirtyTracker` but requires the tracker to
be `is_active`. If the tracker is not activated by the calling agent (e.g. Cursor zero-args
stripping `skip_if_clean=True`), the skip logic never fires and checks re-run redundantly.

## Implementation Steps

### Step 1 — Make `clear_all_cached_results` conditional on force_fresh

Currently `run_quality_gate_inner` calls `clear_all_cached_results(root)` unconditionally before
every run. This forces a fresh subprocess even when called back-to-back with no code changes.
Change to only clear when `force_fresh=True` (already a config key read from pipeline session).

- File: `src/cortex/tools/execution/pre_commit_zero_arg_tools.py`
- In `run_quality_gate_inner`: gate the `clear_all_cached_results` call behind `if force_fresh:`
- Default `force_fresh` remains `True` so existing Step 12 flows are unaffected; agents that call
  `run_quality_gate()` without writing `force_fresh=false` continue clearing as before

### Step 2 — Trim `run_quality_gate` response for passing runs

When `preflight_passed=True`, the detailed per-check entries add no actionable content. Add a
response-trimming step in `run_quality_gate_inner`:

- On pass: keep only `status`, `preflight_passed`, `summary`, `checks_performed`, `markdown_result`
  (omit per-check `details` arrays and `agent_log`)
- On fail: keep full response including `checks` details so agents can act on failures

Estimated reduction: from 2,323 avg tokens to < 600 avg tokens for the ~80% of passing runs.

- File: `src/cortex/tools/execution/pre_commit_zero_arg_tools.py`
- Add `trim_passing_quality_gate_result(result: ModelDict) -> ModelDict` helper
- Call after `append_agent_log_to_quality_result` only when `preflight_passed is True`

### Step 3 — Trim `append_agent_log_to_quality_result` output

`append_agent_log_to_quality_result` appends the full agent log to the result dict. Review what
fields are added and whether they are useful on the pass path.

- File: `src/cortex/tools/logging/instrumentation.py`
- If `append_agent_log_to_quality_result` adds fields only useful on failure, gate them behind
  a `preflight_passed` check

### Step 4 — Activate `PipelineDirtyTracker` from quality gate

`try_skip_clean_checks()` in `execute_pre_commit_checks` requires `PipelineDirtyTracker.is_active`.
The tracker is not reliably activated by all call paths. Activate the tracker automatically when
`run_quality_gate()` completes with `preflight_passed=True`, marking the current git state as
clean. Subsequent `execute_pre_commit_checks` calls within the same session can then skip redundant
re-runs.

- File: `src/cortex/tools/execution/pre_commit_zero_arg_tools.py`
- After a successful quality gate run, call `PipelineDirtyTracker.get_instance().mark_clean()` (or
  equivalent activation) so downstream tools can skip
- File: `src/cortex/tools/execution/pre_commit_dirty_state.py` — add `mark_clean()` method if
  absent

### Step 5 — Reduce poll interval in `poll_phase_a_result`

Current poll interval inside `poll_for_result` is 2 seconds. For fast runs (< 20s), this means
~10 polls. Reduce to 1s for the first 30s, then back off to 3s. This reduces average latency for
fast runs by 0.5–1s and adds minimal overhead for slow runs.

- File: `src/cortex/tools/execution/pre_commit_detached.py` (the `poll_for_result` function)
- Implement adaptive polling: `1s` for first 30s, `3s` thereafter, max total `timeout + 60`

### Step 6 — Instrument skip-logic activation rate

Add a counter to `try_skip_clean_checks` that records when checks are skipped vs executed. Emit a
structured log entry with `"event": "checks.skipped"` or `"event": "checks.executed"` including
`check_names` and `skip_reason`. This makes the skip-logic hit rate visible in future usage
analysis.

- File: `src/cortex/tools/execution/pre_commit_tools_execute_checks.py`

### Step 7 — Run quality gate and verify

After all steps, run `run_quality_gate()` to confirm 0 regressions. Compare token counts in the
next measurement window.

## Verification Checklist

- [x] `force_fresh=False` prevents cache clear; `force_fresh=True` still clears (Step 1)
- [x] Passing run quality gate response is < 800 tokens (heuristic: `test_trimmed_json_under_mcp_token_budget_heuristic`) (Step 2)
- [x] Failing run quality gate response still includes full check details (`TestRunQualityGateInnerTrimPass.test_skips_trim_when_preflight_failed`) (Step 2)
- [x] `agent_log` suppressed on passing runs (`TestTrimPassingResult` drops `agent_log`) (Step 3)
- [x] `PipelineDirtyTracker` activated after successful quality gate (mocked in `TestRunQualityGateInnerCacheClear` / inner path) (Step 4)
- [x] Poll interval adaptive: 1s first 30s, 3s after (`TestPollIntervalAdaptive`) (Step 5)
- [x] Skip events visible in structured log (Step 6 — implementation + tests in pre-commit execute checks)
- [x] `run_quality_gate()` passes after all changes (Step 7 — MCP `run_quality_gate` + full gate in CI)

## Partial Progress Log

- 2026-04-03: Steps 1–6 implemented (conditional `clear_all_cached_results` on `force_fresh`, `trim_passing_quality_gate_result`, omit `agent_log` on pass, `record_phase_a` after successful gate, `poll_interval_for_elapsed` adaptive polling, `checks.skipped` / `checks.executed` structured logs); unit tests added. Files: `pre_commit_zero_arg_tools.py`, `pre_commit_process.py`, `instrumentation.py`, `pre_commit_tools_execute_checks.py`, `roadmap_progress_consistency.py`, `tests/unit/test_quality_gate_latency_helpers.py`, `tests/unit/tools/logging/test_instrumentation.py`. Step 7 (measurement window) pending.
- 2026-04-03: Step 7 verification slice — added `test_trimmed_json_under_mcp_token_budget_heuristic`; `run_quality_gate` green; refactored `brief.py` and `test_session_start_tools.py` for function-length limits and `ManagersDict` typing; fixed `progress.md` MD076. Ongoing: 50-day latency/token metrics per Success Criteria.
- 2026-04-03: Step 1 unit coverage — `TestRunQualityGateInnerCacheClear` (`test_skips_clear_when_force_fresh_false`, `test_clears_when_force_fresh_true`); public `run_quality_gate_inner` rename (tests + pyright) — files: `tests/unit/test_quality_gate_latency_helpers.py`, `pre_commit_zero_arg_tools.py`
- 2026-04-03: `/cortex/do` — `TestRunQualityGateInnerTrimPass.test_skips_trim_when_preflight_failed`; verification checklist marked complete for automated items; progress deduped; files: `tests/unit/test_quality_gate_latency_helpers.py`, `progress.md`, this plan
- 2026-04-03: `/cortex/do` — `_merge_markdown_into_inner` uses `compute_preflight_passed` (clean markdown no longer forces `preflight_passed` when Phase A `status` is error); `test_failed_execute_clean_markdown_not_success`; extracted `_run_quality_gate_with_envelope` / `_enter_trim_fail_mocks` + `_TRIM_FAIL_PHASE_A` for function-length limits — files: `pre_commit_zero_arg_tools.py`, `test_poll_phase_a_markdown_merge.py`, `test_quality_gate_latency_helpers.py`, memory bank
- 2026-04-03: `/cortex/do` — Step 7 session slice: MCP `run_quality_gate()` returned `preflight_passed: true` (full Phase A); module docstring in `test_quality_gate_latency_helpers.py` records verification; operational metrics (Success Criteria 1–3) still tracked in the next 50-day window.

## Dependencies

- `src/cortex/tools/execution/pre_commit_zero_arg_tools.py`
- `src/cortex/tools/execution/pre_commit_detached.py`
- `src/cortex/tools/execution/pre_commit_tools_execute_checks.py`
- `src/cortex/tools/execution/pre_commit_dirty_state.py`
- `src/cortex/tools/logging/instrumentation.py`
- `src/cortex/tools/execution/pre_commit_config.py`

## Success Criteria

1. `run_quality_gate` avg latency reduced by ≥ 10s (≤ 46s) within next 50-day measurement window
2. `run_quality_gate` avg tokens reduced from 2,323 to < 800 (passing runs)
3. Skip-logic hit rate for `execute_pre_commit_checks` measurably > 0% in structured logs
4. All existing tests pass; `run_quality_gate()` returns `preflight_passed: true`

## Testing Strategy

- Unit: test `_trim_passing_result` with passing and failing fixture result dicts
- Unit: test `PipelineDirtyTracker.mark_clean()` and subsequent `try_skip_clean_checks` skip
- Unit: test adaptive poll interval helper returns correct intervals at 0s, 30s, 60s marks
- Integration: call `run_quality_gate()` twice in sequence; assert second call uses cached result
  when `force_fresh=False`
- Regression: full suite via `run_quality_gate()` after all changes
