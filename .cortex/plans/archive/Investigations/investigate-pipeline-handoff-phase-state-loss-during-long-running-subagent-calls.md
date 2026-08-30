---
title: "Investigate pipeline_handoff phase-state loss during long-running subagent calls"
component: "session-tools"
work_type: investigation
status: DONE
priority: High
created: 2026-07-21
completed: "2026-07-21"
depends_on: []
---

## Goal

Root-cause and fix the pipeline_handoff phase-state loss observed when a long-running subagent (implement-code) runs between two orchestrator-side phase writes on the same pipeline session.

## Context

See description. Evidence trail: orchestrator's own pipeline_handoff read after writing `code` phase (session fb7d5600d0e0, `started_at: 2026-07-20T12:38:00`) showed both `select` and `code` phases present. After the implement-code subagent returned and the orchestrator wrote the `review` phase, the read response showed only `review`, with a new `started_at: 2026-07-20T13:26:08`. Filesystem inspection of `.cortex/.session/fb7d5600d0e0/implement/` confirmed `select-result.json` and `code-result.json` were absent; `pipeline.json`'s `phases` key contained only `review`.

## Scope

**in_scope**

- Reproduce the phase-state loss with a minimal test harness (two writes to the same pipeline/session separated by a simulated subagent init or long-running call).
- Identify the code path in the MCP server's `pipeline_handoff` implementation that can clear/reset phases for an existing session_id.
- Fix so phases accumulate (merge) rather than reset unless an explicit `operation="init"` or `operation="clear"` is called by the *same* logical pipeline owner.
- Regression test covering: orchestrator writes phase A, subagent-simulated call writes phase B, orchestrator reads full state and sees both A and B.

**out_of_scope**

- Redesigning the pipeline_handoff data model.
- Any change to how implement-code subagents are invoked (Agent tool usage stays as-is).

## Implementation Steps

1. Reproduce: write a test that writes phase "select", then simulates a second MCP client/session performing a write against the same pipeline (or an init call), then asserts the first phase's write survives.
2. Locate the pipeline_handoff read/write implementation (`src/cortex/tools/session/pipeline_handoff*.py`) and trace how `phases` is loaded/merged/persisted, and whether `session_id` resolution can diverge between the orchestrator's MCP connection and a subagent's separate MCP connection while sharing the same on-disk directory.
3. Fix root cause (likely a read-modify-write race or accidental init on session start inside the subagent path) so phase writes always merge into the existing `phases` dict for a given `(session_id, pipeline)` pair.
4. Add regression tests for the reproduced scenario; verify `do.md`'s Finalize/Verify phases can still read `select`/`code` after a subagent gap.

## Verification Checklist

- Step 1: reproduction test fails against current code, demonstrating the bug.
- Step 3: reproduction test passes after fix; `rg "operation.*init" src/cortex/tools/session/pipeline_handoff*.py` reviewed for accidental auto-init triggers.
- Step 4: `run_quality_gate()` green.

## Dependencies

None.

## Success Criteria

- Reproduction test demonstrates the bug before the fix and passes after.
- A full /cortex/do run spanning a long implement-code subagent call retains `select` and `code` phase data through Review Gate and Finalize (verified by an integration-style test or manual session trace).
- Quality gate green; coverage maintained.

## Testing Strategy

- Unit test simulating concurrent/sequential writes to the same pipeline session from two "clients" (direct calls into the handler, not real subagents).
- Regression test for the exact do.md read sequence: write select, write code, read (expect both), simulate gap, write review, read (expect select+code+review all present).

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Root cause is outside pipeline_handoff (e.g. subagent's own session() call resets shared state) | Trace both pipeline_handoff and session() start-up code paths for any file truncation/init side effects |
| Fix changes semantics of explicit `operation="init"`/`clear"` | Keep those explicit operations as full resets; only change implicit/accidental resets |

## Change History

*No revisions recorded yet.*

## Review Follow-Up Gaps

- [x] Fix is incomplete: the reported symptom (phase loss + `started_at` jump) reproduced live in this same session AFTER the op_init idempotency fix was already committed to disk, failing this plan's own Success Criterion "A full /cortex/do run spanning a long implement-code subagent call retains select and code phase data through Review Gate and Finalize." Evidence: orchestrator wrote the code-phase (in_progress) at 07:39:25 with `pipeline_state` showing both `select`+`code` present; the implement-code subagent's own step-5 write to the same live pipeline (per `.claude/agents/implement-code.md` protocol: one direct `pipeline_handoff` write at the end of its run) landed at 07:54:40 per `.cortex/.session/47a97c2820ac/implement/pipeline.log`, and `started_at` in `pipeline.json` reset to `2026-07-21T07:54:40` with the `select` phase gone — only ~15 minutes elapsed, far under the 4h `PIPELINE_TTL_SECONDS`, so the existing stale-TTL branch cannot explain it. RESOLVED: root-caused to `get_session_id()` caching the session id only in `os.environ` (per-process memory) — an MCP server process restart between calls (the realistic long-subagent-call gap) left the next process with no `CORTEX_SESSION_ID`, so it minted a fresh random id and silently resolved to an empty pipeline directory, orphaning all prior phases. Fixed via `pipeline_handoff_session.py`'s on-disk TTL-bounded marker; regression coverage in `tests/tools/test_pipeline_handoff_session_persistence.py`.
- [x] Root cause of this second reproduction is not yet identified. Two concrete unaddressed leads: (1) `pipeline.json` is still written via plain non-atomic `Path.write_text` (in both `op_init` and `_update_pipeline_state_file` in `src/cortex/tools/session/pipeline_handoff_io.py`) with no file locking, unlike the per-phase result files which already use the atomic temp-file+replace helper `_atomic_write_json` — a concurrent orchestrator+subagent read-modify-write on the same file could race, hit a truncated read, and silently fall back to `phases={}`; (2) `now_iso()` emits naive local-time timestamps with no `tzinfo`, and the 2026-07-20 pipeline-resume frontier feature added a TTL-based `mark_abandoned_runs` sweep (`CORTEX_RESUME_TTL_SECONDS`, default 4h) — if that sweep's "now" reference and the naive `started_at` are compared under a UTC/local mismatch, a 15-minute-old pipeline could appear hours old and get abandoned/cleared. RESOLVED: (1) fixed via `pipeline_handoff_lock.py`'s synchronous file lock wrapping every `pipeline.json` read-modify-write, plus the pre-existing `_atomic_write_json` helper now used consistently for the manifest too; regression coverage in `tests/tools/test_pipeline_handoff_race.py`. (2) fixed via `pipeline_handoff_clock.py`'s UTC-aware `now_iso()`/`age_seconds()`, matching `cortex.experience.frontier.age_seconds`'s convention and safely interpreting legacy naive timestamps; regression coverage in `tests/tools/test_pipeline_handoff_clock.py`.

## Partial Progress Log

- 2026-07-21: Root-caused and fixed one concrete non-idempotency bug in `op_init` (unconditionally rebuilt `phases={}`/`started_at` on every init call, even against a live non-stale manifest); added 3 regression tests proving pre-fix failure and post-fix pass. Plan reopened because the broader symptom reproduced live during this same session via a different, not-yet-root-caused path (see Review Follow-Up Gaps). — files: src/cortex/tools/session/pipeline_handoff_io.py, tests/tools/test_pipeline_handoff_extended.py

## Completion Summary

- Root cause 1 (session identity divergence, matches the originally reported symptom): `get_session_id()` cached the session id only in `os.environ`; a recycled MCP server process during a long subagent gap minted a new id and orphaned every phase written under the old one. Fixed with an on-disk, TTL-bounded session-id marker (`src/cortex/tools/session/pipeline_handoff_session.py`), explicit `CORTEX_SESSION_ID` still taking precedence.
- Root cause 2 (concurrent-writer race): `pipeline.json` read-modify-write was neither locked nor atomic. Fixed with a synchronous file lock (`src/cortex/tools/session/pipeline_handoff_lock.py`) around every read-modify-write cycle, plus consistent use of the existing atomic-replace helper for the manifest file.
- Root cause 3 (naive/aware timestamp mismatch): `now_iso()` emitted naive local time, risking a mismatch against the UTC-based experience-store TTL sweep. Fixed with a UTC-aware clock module (`src/cortex/tools/session/pipeline_handoff_clock.py`) that also safely interprets legacy naive timestamps.
- Root cause 4 (found live during this same `/cortex/do` run, after root causes 1-3 were fixed and verified): `op_clear` (`src/cortex/tools/session/pipeline_handoff_io.py`) accepted no `phase` argument and unconditionally `shutil.rmtree`'d the *entire* pipeline directory. `gate_feedback.py`'s `persist_gate_feedback()` calls `pipeline_handoff(operation="clear", pipeline="implement", phase="gate_feedback")` whenever `run_quality_gate()`/`run_docs_gate()` passes, intending to clear only its own scratch phase — but the dispatcher silently dropped the `phase` argument before reaching `op_clear`, so every passing quality/docs gate mid-run wiped `select`/`code`/`review`/`finalize`/`verify` along with it. Reproduced live: after a correct `verify`-phase write (5 phases present), a passing `run_quality_gate()` call left the next `fix`-phase write showing only `fix` with a brand-new `started_at`. Fixed by threading `phase` through `_dispatch_simple_operation`/`_dispatch_query_operation` to `op_clear`, which now removes only that phase's entry/files (via a new `_clear_single_phase` helper) when `phase` is given, leaving the rest of the pipeline state untouched; a phase-less `clear` call (the do.md Cleanup-phase contract) still does the full directory removal. Regression coverage: `tests/tools/test_pipeline_handoff.py::TestClear::test_phase_scoped_clear_does_not_wipe_other_phases`; `tests/integration/test_gate_feedback_loop.py::test_gate_success_clears_only_gate_feedback_phase` (previously asserted the buggy whole-directory-wipe behavior as intended — corrected to assert only the `gate_feedback` phase is removed).
- `op_init` was also made idempotent against a live, non-stale manifest (merges instead of resetting `phases`/`started_at`).
- Regression tests: `tests/tools/test_pipeline_handoff_session_persistence.py`, `tests/tools/test_pipeline_handoff_race.py`, `tests/tools/test_pipeline_handoff_lock.py`, `tests/tools/test_pipeline_handoff_clock.py`, `tests/tools/test_pipeline_handoff.py`, `tests/integration/test_gate_feedback_loop.py`, plus 3 added cases in `tests/tools/test_pipeline_handoff_extended.py`. `rg "operation.*init"` across `pipeline_handoff*.py` confirmed no accidental auto-init call sites. `run_quality_gate()` green (0 errors/warnings); all targeted tests pass (85/85 in the affected suites).
