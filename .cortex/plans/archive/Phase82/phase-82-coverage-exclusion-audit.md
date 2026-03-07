# Phase 82: Coverage Exclusion Audit and Reduction

**Status**: IN PROGRESS
**Priority**: Medium
**Complexity**: Medium
**Category**: Fix / Quality

## Goal

Audit and reduce the coverage omit list in `pyproject.toml` to eliminate blind spots in high-impact infrastructure modules.

## Context

- Coverage configuration excludes 30+ patterns including `*/models.py`, `*/container.py`, `*/factory.py`, and many infrastructure modules.
- Some exclusions are reasonable (protocols, benchmarks, `__init__.py`).
- Others hide critical runtime paths: `container.py` (591 LOC of DI logic), `factory.py` (656 LOC of manager creation), structure analysis modules.
- Project review (2026-03-05): "exclusions can inflate overall coverage confidence while high-impact integration paths remain weakly verified."
- Current coverage is ~92% but with significant omitted code.

## Approach

1. Classify each omit entry as "permanent" (truly no runtime logic) or "temporary" (needs tests).
2. Remove "temporary" exclusions and add targeted tests.
3. Track omitted-lines ratio as a metric.

## Implementation Steps

### Step 1: Audit current omit list

- Read `pyproject.toml` coverage omit entries.
- For each entry, check if the file contains runtime logic (not just type defs or constants).
- Classify into: **permanent** (protocols, benchmarks, `__init__.py`, pure type aliases) vs **temporary** (has logic that should be tested).

### Step 2: Remove high-impact exclusions

- Remove `*/container.py` — 591 LOC of DI initialization logic.
- Remove `*/factory.py` — 656 LOC of manager creation.
- Remove `*/initialization_health.py`, `*/groups.py` — manager infrastructure.

### Step 3: Add integration tests for newly-included modules

- Add tests for container initialization paths.
- Add tests for factory creation flows.
- Add tests for initialization health checks.

### Step 4: Evaluate model exclusions

- `*/models.py` excludes ALL models.py files (including `validation/models.py` at 700 LOC).
- Determine if any models.py files contain validation logic or computed properties that should be tested.
- Narrow the exclusion or remove it entirely.

### Step 5: Update coverage threshold

- After removing exclusions and adding tests, re-assess coverage.
- Adjust threshold if needed (may temporarily decrease as more code is measured).

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `container.py` in omit | `pyproject.toml` | Not present |
| `factory.py` in omit | `pyproject.toml` | Not present |

## Dependencies

- Phase 81 (oversized module reduction) may simplify some of these files first.

## Success Criteria

- Omit list reduced by at least 5 entries.
- No decrease in actual test quality (new tests added for newly-measured code).
- Coverage threshold still met after omit reduction.
- Omit list documented with clear rationale for each remaining entry.

## Testing Strategy

- **Coverage Target**: Maintain 90%+ even after reducing exclusions.
- **Unit Tests**: Add tests for DI container, factory, initialization paths.
- **Integration Tests**: Test end-to-end initialization flows.
- **Edge Cases**: Test with missing/corrupt configuration.

## Risks & Mitigation

- **Risk**: Coverage drops below threshold. **Mitigation**: Add tests before removing exclusions.
- **Risk**: Some excluded code is genuinely untestable. **Mitigation**: Keep permanent exclusions documented.

## Current Status (2026-03-06)

- Removed coverage exclusions for `*/container.py`, `*/factory.py`, `*/initialization_health.py`, and `*/groups.py` in `pyproject.toml`.
- Verified existing tests for container, factory, and manager groups still pass; added targeted tests for `initialization_health.handle_file_change`.
- Ran full test suite via `execute_pre_commit_checks(checks=["tests"])`: 4916/4916 tests passing, coverage ≈ 91.18% (≥ 90% threshold).
- Remaining work: evaluate the `*/models.py` exclusion and other model-related entries, document per-entry rationale for the final omit list, and adjust the plan status to COMPLETE when that audit is finished.

## Timeline

- Estimated: 1–2 days.
