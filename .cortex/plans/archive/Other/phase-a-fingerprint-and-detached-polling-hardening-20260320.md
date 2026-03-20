# Plan: Phase A Fingerprint & Detached Polling Hardening

## Status: PENDING

## Priority: P2 (Medium)

## Created: 2026-03-20

## Effort: Low-Medium

## Motivation

A recent review report identified three non-blocking opportunities to improve correctness robustness and responsiveness:

1. **Narrow broad exception handling** in Phase A bookkeeping so unexpected failures don’t silently degrade later commit decisions.
2. **Reduce micro-blocking** in detached polling by avoiding synchronous file reads on the async event loop.
3. **Improve stub error messages** for mixin-required methods to make integration failures more self-explanatory.

These changes are intended to preserve the current passing quality gate while improving resilience and developer/operator experience.

---

## Step 1: Narrow exception handling for Phase A fingerprint bookkeeping

**Target:** `src/cortex/tools/execution/pre_commit_phase_dispatch.py` (`_run_phase_a`, `except Exception:` around `_record_phase_a_fingerprint`).

**Goal:** Replace the broad exception catch with a narrower set of expected exceptions (or validate inputs) while still ensuring fingerprint failures never prevent the actual pre-commit checks from completing.

**Implementation steps:**

1. Inspect `_run_phase_a()` and confirm which calls can realistically fail (`get_or_resolve_project_root`, `PipelineDirtyTracker` operations).
2. Replace `except Exception:` with narrow exception types plus an explicit validation guard for the expected `result` shape.
3. Ensure the failure mode remains “best-effort bookkeeping” (log structured warning, but do not change the checks result semantics).

**Verification checklist:**

- What to search for: `except Exception` within `pre_commit_phase_dispatch.py` after modifications
- Search scope: `_run_phase_a` only
- Files to re-read: `src/cortex/tools/execution/pre_commit_phase_dispatch.py`

**Acceptance criteria:**

- No broad `except Exception` remains in `_run_phase_a`.
- Phase A bookkeeping failures log at `warning` (with enough context) but never change `run_quality_gate()` success/failure behavior.

---

## Step 2: Reduce micro-blocking in detached polling loop

**Target:** `src/cortex/tools/execution/pre_commit_detached.py` (`_read_result_file` and the polling loop).

**Goal:** Avoid synchronous `Path.read_text()` during async polling by moving the file read to a worker thread (or equivalent async-safe approach).

**Implementation steps:**

1. Identify the single polling hotspot (`result_path.read_text()`).
2. Implement an async-safe read (e.g., `asyncio.to_thread(result_path.read_text)`), preserving existing error handling for JSON decode and filesystem exceptions.
3. Keep heartbeat behavior unchanged.

**Verification checklist:**

- What to search for: `read_text()` usage inside the polling loop call path
- Search scope: `_read_result_file()` only
- Files to re-read: `src/cortex/tools/execution/pre_commit_detached.py`

**Acceptance criteria:**

- No synchronous filesystem reads remain on the async event loop polling path.
- Unit tests (existing) and quality gates still pass.

---

## Step 3: Make mixin-required NotImplementedError stubs self-explanatory

**Target:** `src/cortex/optimization/rules_hybrid.py` (mixin-required stubs: `_get_local_rules_models`, `_select_within_budget_models`).

**Goal:** Keep the stubs raising `NotImplementedError`, but provide a descriptive message indicating which mixin/owner must implement them.

**Implementation steps:**

1. Update `raise NotImplementedError` to include a consistent message for each stub.
2. Ensure messages are stable (do not depend on runtime values).

**Verification checklist:**

- What to search for: `raise NotImplementedError` in `rules_hybrid.py`
- Search scope: the two stub methods
- Files to re-read: `src/cortex/optimization/rules_hybrid.py`

**Acceptance criteria:**

- Stub exceptions remain unreachable in normal runtime paths.
- If triggered, the error message clearly indicates required mixin integration.

---

## Overall Verification

1. Quality gate still passes (Phase A checks).
2. Test coverage remains high (target >= 90% coverage remains). 
3. No security regressions in path/filename handling or MCP protocol enforcement.

## Testing Strategy (target 95% coverage where practical)

- Run full test suite: `pytest` (repo quality gate)
- Add/adjust unit tests only if existing tests don’t cover new branches introduced by exception narrowing or async-safe polling read.
