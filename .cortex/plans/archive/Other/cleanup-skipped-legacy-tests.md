---
title: "Remove permanently skipped legacy tests and establish skip expiration policy"
component: tests
work_type: refactor
status: DONE
priority: Medium
created: 2026-03-22
depends_on:
  - fix-exception-handling-and-subprocess-comment
sources:
  - "Codex audit: Test Suite Hygiene Signals (Medium)"
---

## Goal

Remove or convert all permanently skipped legacy tests that add noise and reduce suite trust, and introduce a governance policy that prevents permanent skip markers without an expiration condition or linked task reference.

## Context

The Codex audit identified entire test modules that are permanently skipped because the features they covered were replaced (`test_init.py`, `test_ultra_simple.py`). Skipped tests with no expiration date or linked ticket accumulate silently, inflate the apparent suite size, reduce trust in coverage signals, and block future contributors from understanding what was tested.

This plan depends on `fix-exception-handling-and-subprocess-comment` because some skipped tests may cover the exception-handling paths being fixed in that plan — resolving those first ensures we do not delete tests that would become valid again after the fix.

## Progress notes (2026-03-22)

- **Step 2 done:** Removed `tests/test_init.py` and `tests/test_ultra_simple.py` (skipped-only legacy modules). Updated `tests/README.md`.
- **Steps 3–4 (partial):** `tests/skip_reference_policy.py` + `pytest_collection_modifyitems` in `tests/conftest.py` enforce tracked references on unconditional `@pytest.mark.skip`. Unit tests in `tests/unit/test_skip_reference_policy.py`. Every `pytest.skip(...)` in `tests/` now includes `(ref: cleanup-skipped-legacy-tests)` in the reason string. Runtime `pytest.skip()` without a reason is not yet statically enforced.
- **Step 1 (inventory):** `docs/development/test-skip-inventory.md` lists skip/skipif/xfail sites and categories.
- **Step 5 (partial):** `TestResult.skipped_tests` populated from pytest summary; `merge_skip_trend_warnings` persists `.cortex/.cache/last_pytest_skipped_count.json` and appends a non-failing warning when skipped count increases vs last run; `process_tests_check` adds test warnings to `stats.total_warnings`.
- **AST/runtime skip (done):** `collect_runtime_pytest_skip_violations_under` + `enforce_runtime_pytest_skip_in_tests_tree` scan all `tests/**/*.py` at collection; require literal/f-string segments to satisfy `skip_reason_has_tracked_reference`. Hooked from `pytest_collection_modifyitems` before marker enforcement. Unit tests cover literals, f-strings, bare skip, missing ref, and non-literal reasons.
- **Closed (2026-03-22):** Quality gate green; plan archived; skip policy, inventory doc, and pipeline skip trend landed.

## Implementation Steps

### Step 1 — Inventory all skip markers in the test suite

1. Grep `tests/` for `pytest.mark.skip`, `@pytest.mark.skip`, `pytest.skip(`, `@pytest.mark.xfail`.
2. For each hit, record: file, line, reason string (if any), whether a ticket/task ref is present.
3. Classify each:
   - **Permanently skipped, no reason** — highest priority to remove or fix
   - **Permanently skipped with reason but no ticket** — add ticket ref or remove
   - **Temporarily skipped with valid ticket** — leave, verify ticket is still open
   - **xfail with condition** — verify condition is still accurate

#### Verification Checklist — Step 1

| What to check | Search scope | Files to re-read |
|---|---|---|
| Complete skip inventory produced | `tests/**/*.py` | — |
| Each skip classified into one of 4 categories | Inventory doc | — |

### Step 2 — Handle `test_init.py` and `test_ultra_simple.py`

1. Read both files in full.
2. For each skipped test, determine:
   - Does the feature it tests still exist (under a new name/module)?
   - If yes: update the test to target the current implementation and remove the skip.
   - If no: the test covers a deleted feature — remove the test entirely.
3. If the entire file is skipped with no recoverable tests, delete the file.
4. Do not leave empty test files.

#### Verification Checklist — Step 2

| What to check | Search scope | Files to re-read |
|---|---|---|
| Both files resolved (updated or deleted) | `tests/` | — |
| No empty test files remain | `tests/` | — |
| Coverage does not drop below 91% | `run_quality_gate()` | — |

### Step 3 — Resolve remaining permanently-skipped tests from inventory

1. For each "permanently skipped, no reason" test from Step 1:
   - Attempt to re-enable by providing the missing fixture or mock.
   - If the underlying feature no longer exists, remove the test.
2. For each "permanently skipped with reason but no ticket":
   - Add a ticket/plan reference in the skip reason string: `pytest.mark.skip(reason="<reason> — see plan: <slug>")`.
   - Or remove if no longer relevant.

#### Verification Checklist — Step 3

| What to check | Search scope | Files to re-read |
|---|---|---|
| No permanent skips without ticket/plan ref remain | `tests/**/*.py` | All modified test files |
| All re-enabled tests pass | `run_quality_gate()` | — |

### Step 4 — Establish skip expiration policy

1. Add a new linting rule or test that enforces:
   - Every `@pytest.mark.skip` reason string must contain a plan slug or GitHub issue reference matching pattern `[A-Za-z0-9_-]+` after `see` or `ref:` or `issue:`.
   - Bare `pytest.skip()` without a reason is blocked.
2. Implement as a pytest plugin hook or a Ruff/flake8 rule, whichever integrates cleanly with the existing quality gate.
3. Alternatively, implement as a `conftest.py` `pytest_collection_modifyitems` hook that inspects `skip` markers and fails the collection step if any are missing a ref pattern.

#### Verification Checklist — Step 4

| What to check | Search scope | Files to re-read |
|---|---|---|
| Skip policy enforcement implemented | `conftest.py` or lint config | — |
| Policy test: bare skip without ref fails collection | New test | — |
| Policy test: skip with valid ref passes collection | New test | — |
| Existing valid skips still pass | `run_quality_gate()` | — |

### Step 5 — Update CI quality summary with skip count trend

1. Identify where CI quality summary is generated (grep for `quality_summary`, `test_summary`, or similar in `src/cortex/` and CI workflow files).
2. Add skip count to the summary output: `skipped_tests: N`.
3. If the count increases between runs, emit a warning (not a failure) in the summary.

#### Verification Checklist — Step 5

| What to check | Search scope | Files to re-read |
|---|---|---|
| `skipped_tests` field present in quality summary | CI output or `run_quality_gate()` result | — |
| Warning emitted when skip count increases | Test with mock | — |

### Step 6 — Run quality gate and update memory bank

1. Call `run_quality_gate()` — must pass: zero errors, coverage ≥ 91%, no new warnings.
2. Update `activeContext.md` with a completed entry for this plan.
3. Update `progress.md`.

## Dependencies

- `fix-exception-handling-and-subprocess-comment` must be completed first (some skipped tests may cover the exception paths being fixed; resolving those first avoids deleting potentially-valid tests).

## Success Criteria

- Zero permanently skipped tests without a valid plan/issue reference.
- `test_init.py` and `test_ultra_simple.py` either updated with active tests or deleted.
- A policy check blocks bare `@pytest.mark.skip` without a ref pattern.
- CI quality summary reports `skipped_tests: N` and warns on increases.
- `run_quality_gate()` passes: zero errors, coverage ≥ 91%.

## Testing Strategy (95% coverage target)

- Tests for the skip policy enforcement mechanism: bare skip → collection fails; skip with ref → passes; xfail without condition → warned.
- Tests for the skip count trend logic: count increase → warning; count stable → no warning.
- All re-enabled tests from Step 2/3 must pass (inherently tested by `run_quality_gate()`).
- Coverage must not decrease after removing skipped tests — if it does, that is a signal the removed tests were the only coverage for that code path (investigate before deleting).
