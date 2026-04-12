---
title: "Deprecation Completion: Legacy Quality Entrypoints Migration"
component: quality
work_type: refactor
status: IN_PROGRESS
priority: medium
created: 2026-04-12
depends_on: []
---

## Deprecation Completion: Legacy Quality Entrypoints Migration

## Goal

Define an explicit migration matrix and sunset schedule for `execute_pre_commit_checks`, `start_quality_job`, and `get_quality_job_status`. Convert internal callers and tests to the zero-arg gate tools (`run_quality_gate()`, `autofix()`). Reduce legacy entrypoint references by ≥50% in one release, with a hard removal date.

## Context

### Finding (Review 2026-04-12, Issue #4 — Medium)

- `docs/api/tools.md` marks `execute_pre_commit_checks`, `start_quality_job`, and `get_quality_job_status` as deprecated for agent-facing workflows.
- Internal callers remain in `src/cortex/core/mcp_stability_usage.py`, `tests/e2e/test_commit_pipeline.py`, and multiple unit tests.
- No explicit removal date or migration matrix exists.
- Legacy pathways increase maintenance burden and blur contributor guidance.

**Replacement tools** (zero-arg, canonical):

- `run_quality_gate()` — replaces `execute_pre_commit_checks` + `get_quality_job_status`
- `autofix()` — replaces `start_quality_job` in autofix scenarios

## Implementation Steps

### Step 1: Build migration matrix

1. Search for all references: `rg -rn "execute_pre_commit_checks|start_quality_job|get_quality_job_status" src/ tests/`.
2. For each reference, classify:
   - **Type**: internal caller in `src/`, test caller in `tests/unit/`, test caller in `tests/e2e/`, doc reference in `docs/`.
   - **Replacement**: which zero-arg tool or pattern to substitute.
   - **Complexity**: `low` (direct swap) / `medium` (requires adapter) / `high` (requires architectural change).
3. Output the matrix as a table comment at the top of this plan or as a sibling `migration-matrix.md` file.
4. Identify any callers that **cannot** be migrated yet (external API contracts, backwards-compat) — these become the allowlist for the narrow compatibility layer.

**Verification checklist:**

- `rg -c "execute_pre_commit_checks" src/ tests/` — record baseline count before changes.
- Re-read `src/cortex/core/mcp_stability_usage.py` fully.
- Re-read `tests/e2e/test_commit_pipeline.py` fully.

### Step 2: Migrate `src/` internal callers

1. For each `src/` caller classified `low`/`medium` complexity:
   - Replace `execute_pre_commit_checks(...)` calls with `run_quality_gate()`.
   - Replace `start_quality_job(...)` calls with `autofix()`.
   - Replace `get_quality_job_status(...)` calls with result inspection from `run_quality_gate()`.
2. Keep functions ≤30 lines and files ≤400 lines; extract helpers if needed.
3. After each file, run `run_quality_gate()` to confirm no regressions.

**Verification checklist:**

- `rg "execute_pre_commit_checks" src/` — zero results after migration.
- `run_quality_gate()` — all green.

### Step 3: Migrate unit tests

1. For each `tests/unit/` reference to legacy entrypoints:
   - Update test to call/mock `run_quality_gate()` or `autofix()` instead.
   - Adjust assertions to match new return types (typed models from the quality gate).
2. Do not change test intent — update only the call surface.

**Verification checklist:**

- `rg "execute_pre_commit_checks" tests/unit/` — zero results.
- `run_quality_gate()` — all unit tests green.

### Step 4: Migrate or quarantine e2e tests

1. Read `tests/e2e/test_commit_pipeline.py` fully.
2. For tests that directly drive legacy entrypoints:
   - If the e2e test is still exercising a valid path → update to zero-arg gate tools.
   - If the e2e test is testing the legacy *interface itself* (backwards-compat) → move to a `tests/e2e/legacy/` subdir with a `@pytest.mark.legacy_compat` marker and a sunset date comment.
3. Document the sunset criteria in the test file header.

**Verification checklist:**

- Re-read migrated e2e test file; confirm intent preserved.
- `run_quality_gate()` — all e2e tests green.

### Step 5: Establish compatibility layer with sunset criteria

1. Identify remaining callers that require the legacy interface (from Step 1 allowlist).
2. Add a thin shim in `src/cortex/core/mcp_stability_usage.py` (or a dedicated `_legacy_compat.py`) that wraps the old signatures and delegates to zero-arg tools.
3. Mark shim with:

   ```python
   # DEPRECATED: remove by 2026-07-01. Migrate callers to run_quality_gate().
   ```

4. Add a test that asserts the shim file still has `DEPRECATED: remove by` annotation — this will fail if the date passes and the shim is forgotten.

**Verification checklist:**

- Re-read shim file; confirm deprecation annotation present.
- `rg "remove by 2026-07-01" src/` — returns the shim location.

### Step 6: Update documentation

1. Update `docs/api/tools.md`: add sunset date (`2026-07-01`) next to deprecated tool entries.
2. Add migration guide section: before/after code samples showing deprecated → zero-arg replacement.
3. Update `README.md` if it references legacy entrypoints.

**Verification checklist:**

- `run_docs_gate()` — green.
- `rg "execute_pre_commit_checks" docs/` — only in the migration guide section.

### Step 7: Measure and record reduction

1. Run `rg -c "execute_pre_commit_checks|start_quality_job|get_quality_job_status" src/ tests/`.
2. Compare against baseline from Step 1; confirm ≥50% reduction.
3. Record metric in `activeContext.md` via `manage_file`.

**Verification checklist:**

- Reduction count ≥50% baseline.
- `manage_file(operation="read", file_name="activeContext.md")` — entry present.

## Dependencies

- `src/cortex/core/mcp_stability_usage.py` — primary internal caller
- `tests/e2e/test_commit_pipeline.py` — e2e test caller
- `docs/api/tools.md` — documentation update target
- Zero-arg gate tools: `run_quality_gate()`, `autofix()` must be fully functional

## Partial Progress Log

- 2026-04-12: Phase A preflight migrated to `run_detached_phase_a_checks` (shared with `run_quality_gate`); e2e commit pipeline uses `run_quality_gate`; added `legacy_quality_mcp_compat.py` sunset marker + unit test; docs sunset + migration table in `docs/api/tools.md`; migration matrix at `.cortex/plans/deprecation-legacy-quality-entrypoints-migration-matrix.md` — files: `src/cortex/tools/execution/pre_commit_zero_arg_tools.py`, `src/cortex/tools/execution/pre_commit_preflight_helpers.py`, `tests/unit/test_pre_commit_phase_tools.py`, `tests/e2e/test_commit_pipeline.py`, `tests/unit/test_legacy_quality_mcp_compat.py`, `src/cortex/tools/execution/legacy_quality_mcp_compat.py`, `docs/api/tools.md`, `src/cortex/core/constants.py`, `src/cortex/tools/execution/pre_commit_phase_dispatch.py`

## Success Criteria

- `rg "execute_pre_commit_checks|start_quality_job|get_quality_job_status" src/` (excluding shim) returns zero results.
- Legacy reference count in `tests/` reduced by ≥50% vs baseline.
- Compatibility shim present with removal date annotation `2026-07-01`.
- `docs/api/tools.md` lists sunset date.
- `run_quality_gate()` and `run_docs_gate()` both green.

## Testing Strategy

- **Unit tests**: updated to use zero-arg gate tool mocks. Target 95%+ coverage on changed files.
- **E2e tests**: migrated to call zero-arg tools; legacy-only tests quarantined under `@pytest.mark.legacy_compat`.
- **Sunset test**: asserts shim file still contains `DEPRECATED: remove by 2026-07-01` — CI reminder for hard removal.
- **Regression**: no behavioral change expected; all existing assertions must pass after call-site updates.
