# Code Review Report

**Date:** 2026-10-09T14-14
**Scope:** Uncommitted `/cortex/do` implementation — "Per-connection pipeline run ids for concurrent cortex pipelines" (plan archived at `.cortex/plans/archive/Other/`).

Changed vs HEAD: `src/cortex/tools/session/pipeline_handoff_session.py` (rewritten core), `pipeline_handoff_lock.py` (+36), `pipeline_handoff_io.py` (+29), `pipeline_handoff_resume.py` (+51), `src/cortex/experience/resume.py` (+30), `src/cortex/tools/session/start_tools.py` (+14); new `tests/tools/test_pipeline_handoff_concurrent_runs.py` (903 ln), `tests/tools/test_pipeline_handoff_identity_units.py` (440 ln); updated `tests/experience/test_pipeline_resume_integration.py` (+30), `tests/tools/test_pipeline_handoff_session_persistence.py` (docstring).

**Prior report:** `code-review-report-2026-03-13T12-44.md` — legacy format with **no Issue Tracker section, no IDs, no statuses**; its three Low prose findings (duplicate `_session_dir`, log-fd comment, redundant asserts in `plan.py`) target files outside this scope. No carried-forward OPEN rows exist to carry; nothing was silently dropped. No regressions adjudicable.

## Gate (Step 3)

`run_quality_gate` zero-arg: `success`, `total_errors: 0`, `total_warnings: 0`, `preflight_passed`, markdown `files_with_errors: 0` across 8 stages (fix_errors, quality, format, synapse_format, synapse_lint, spelling, type_check, tests). Authoritative envelope `.cortex/.session/pre_commit_result_5738f00f2f71.json`: `status: completed`, `result.status: success`, tests 7988/7988 (4 skipped), `completed_at` 2026-10-09T07:24:44Z — postdates the last source edit (06:59:58Z), so the served verdict is current for the reviewed scope; no force-fresh retry warranted. Coverage 91.80% global / 100% modified files per the implementing pass's focused run (provenance: pass Fix-phase report).

## Invariant Verdicts (contract adjudication)

| # | Invariant | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Concurrent init → distinct run state, no shared window | VERIFIED | `session.py:302-330` claim under strict lock; loser sees live foreign owner → mints fresh; real-subprocess test `test_concurrent_init_processes_get_distinct_run_ids` + `test_contended_adoption_single_winner` |
| 2 | Restart resumes ITS run, never a live sibling's | VERIFIED | `session.py:194-233` adoption guards (no live foreign owner, TTL-fresh, incomplete store run); `_owner_alive` treats foreign host/EPERM as alive (`session.py:98-112`); `resume.py:_find_run` excludes `excluded_owners`; `test_restart_after_owner_death_adopts_incomplete_run`, `test_live_sibling_run_is_never_adopted`, `test_resume_never_attaches_live_sibling_run` |
| 3 | Ownership claims fail closed | VERIFIED | `pipeline_claim_lock` raises `PipelineClaimLockTimeout` (`lock.py:91-123`); `_claim_run_id` returns None on timeout → `_adopt_run_id` mints (`session.py:302-330`); `_register_owned_id` bounded 2 attempts then False → env-id switch (`session.py:236-289`); `test_claim_lock_timeout_refuses_adoption` |
| 4 | Unregistrable inherited id switches to fresh mint | VERIFIED | `_use_registered_env_id` (`session.py:269-289`): keep only when durably registered, recorded owner, or self-minted (pid-keyed set filters forked children); `test_unregistrable_inherited_env_id_switches_fresh`, `test_unregistrable_inherited_id_switches_when_claims_time_out` |
| 5 | TOCTOU snapshot/re-query cannot report a foreign run post-latch | VERIFIED | `op_resume` (`pipeline_handoff_resume.py`): refused bind → exactly non-resumable (no re-query); successful bind → rebuild post-validated — plan pointing at any other id becomes non-resumable, never falls back; injected-interleaving tests `test_refused_bind_never_requeries_store`, `test_successful_bind_losing_its_run_never_falls_back` |
| 6 | Documented residual (freshest-dead-owned ambiguity; `resume_run_id` override) | HONORED | `get_session_id` docstring (`session.py:369-377`); `test_two_dead_owned_runs_resolve_without_sharing`, `test_explicit_resume_run_id_pins_older_run` |

## Scores

| Metric | Score | Delta | Evidence |
|--------|-------|-------|----------|
| Architecture | 9 | +2 | Identity/ownership (`session.py`) split from locking policy (`lock.py:95-123`), resume binding (`pipeline_handoff_resume.py`), and IO threading (`io.py:39-53` pipeline-scoped `prefer_run_id`); two-level lock ordering documented (`session.py:64-69`); Pydantic registry models (`session.py:75-86`) |
| Test Coverage | 9 | +2 | 42 new tests incl. real-subprocess concurrent-init acceptance tests; discriminating controls on every guard (live vs dead pid, excluded vs not, pin vs fallback); TOCTOU via call-count wrappers; 7988/7988 green; 100% modified-file coverage. No mutation testing → not 10 |
| Documentation | 7 | +1 | Rationale-rich docstrings on every new function; archived plan + progress entry; no standalone design note for two-level locking/registry semantics; mixed `# AI:` placement (see REV-3) |
| Code Style | 8 | +0 | format/synapse_format/spelling stages green; consistent naming; in-docstring comment nit |
| Error Handling | 9 | +1 | Typed timeout exception, fail-closed claims; specific catches (`(OSError, json.JSONDecodeError)`, `ValidationError`, `ProcessLookupError`); degradation tested (`test_registration_oserror_degrades_to_warning`); sole broad catch is pre-existing documented `# noqa: BLE001` best-effort fallback with logging (`resume.py:186`) |
| Performance | 8 | +1 | O(entries) registry ops; atomic single-file writes; bounded poll loops (5s × 2); per-entry store re-scan hoistable (Improvement 1) |
| Security | 9 | +1 | `resume_run_id` used only as registry dict key/comparison target — never a path component; registry under `.cortex/.session`; atomic replace prevents torn reads; no secrets |
| Maintainability | 8 | +1 | Small focused functions, clear ownership; `session.py` at exactly 400 lines (zero headroom); `io.py` 794 / `start_tools.py` 588 pre-existing large files touched lightly |
| Rules Compliance | 9 | +1 | Gate 0 violations incl. file/function length checks; no `Any` (grep clean); no mutable defaults; Pydantic v2; AAA-labeled tests |
| **Overall** | **8.4** | **+1.1** | 76/9 = 8.4 (arithmetic checked) |

No metric unchanged for ≥3 consecutive reports (only 2 reports exist).

## Issue Tracker

| ID | First Found | Status | Location | Description |
|----|-------------|--------|----------|-------------|
| REV-2026-10-09-1 | 2026-10-09 | OPEN | `pipeline_handoff_session.py:151-168` | Foreign-host (or EPERM) owners are conservatively alive, so expired entries with only such owners are never pruned — registry grows without bound in shared-disk multi-host setups and those runs stay unadoptable forever. Suggestion: hard age cap (e.g. 7× TTL) applied regardless of undecidable liveness. |
| REV-2026-10-09-2 | 2026-10-09 | OPEN | `pipeline_handoff_session.py:120-128, 141-148` | A transient registry read failure (`OSError`/`JSONDecodeError` → `{}`) followed by a claim-time save overwrites the registry — ownership reset. Availability-only (connections fall back to fresh mints; no shared-window risk). Suggestion: distinguish missing vs unreadable; refuse claims when unreadable. |
| REV-2026-10-09-3 | 2026-10-09 | OPEN | `pipeline_handoff_session.py:101-102, 156-157`; `pipeline_handoff_lock.py` claim-lock docstring | `# AI:` rationale blocks inconsistently placed inside docstrings (render as doc text) vs as real comments elsewhere. Move below the closing quotes for consistency. |

## Improvement Suggestions

1. **Hoist the store scan out of the adoption loop** — `src/cortex/tools/session/pipeline_handoff_session.py:215-219`. Before: `if _entry_adoptable(project_root, run_id, entry, pipeline)` per entry, each call re-running `_store_incomplete_owner_ids` (full store scan). After: `incomplete = _store_incomplete_owner_ids(project_root, pipeline)` once before the loop, passed into `_entry_adoptable` (add keyword arg, default `None` → lazy compute for single callers). Effort Low, Impact Low (registry is pruned-small; correctness unaffected).
2. **Fix `# AI:` comment placement** — move the two in-docstring blocks (`session.py:101-102`, `156-157`) and the claim-lock docstring block below their closing quotes as real comments. Effort Low, Impact Low.

## Filing

Not filed into the memory bank per operator decision (2026-10-09): review reports are delivered in chat; `manage_file(file_artifact)` skipped regardless of score (8.4 ≥ default threshold 7 would otherwise file).
