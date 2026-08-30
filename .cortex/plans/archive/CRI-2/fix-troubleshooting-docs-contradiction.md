---
title: "Fix Contradictory Coverage Documentation in Troubleshooting Guide"
component: "docs/guides"
work_type: fix
status: DONE
priority: Critical
created: 2026-03-07
execution_order: 2
depends_on: []
---

## Fix Contradictory Coverage Documentation in Troubleshooting Guide

**Status**: PENDING
**Priority**: Critical
**Complexity**: Low
**Category**: Fix / Documentation
**Component**: docs/guides
**Work Type**: fix
**Execution Order**: 2

## Goal

Resolve contradictory statements about pytest coverage configuration in `docs/guides/troubleshooting.md`.

## Context

- Line 261 states: "Coverage is **not** in the default `pytest.ini` addopts. CI and `execute_pre_commit_checks` pass `--cov=src/cortex`, `--cov-report=...`, and `--cov-fail-under=90` explicitly"
- Line 274 states: "`pytest.ini` sets `--cov-fail-under=90` in `addopts`"
- These directly contradict each other.
- Actual `pytest.ini` addopts do NOT include coverage options — CI passes them explicitly.
- External review (2026-03-07) classified this as **Critical** severity.

## Implementation Steps

### Step 1: Read current pytest.ini to confirm ground truth

**File**: `pytest.ini`

Verify that `addopts` does NOT contain `--cov-fail-under=90` or any `--cov` flags.

### Step 2: Fix the contradictory section

**File**: `docs/guides/troubleshooting.md` (around lines 261-293)

- Remove or correct line 274 to align with the ground truth (line 261 is correct).
- Ensure the full section consistently says: coverage flags are passed by CI and MCP tools, not by `pytest.ini` addopts.
- Keep the explanation of why IDE runs may or may not show coverage enforcement.

### Step 3: Add a cross-reference note

Add a note near the coverage section: "See `pytest.ini` for current addopts. Coverage is configured in CI workflows and `execute_pre_commit_checks`, not in pytest.ini."

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `cov-fail-under` | `docs/guides/troubleshooting.md` | Consistent: only in CI/MCP context, not pytest.ini |
| `pytest.ini sets` | `docs/guides/troubleshooting.md` | No claim that pytest.ini sets coverage |

## Dependencies

- None.

## Success Criteria

- No contradictory statements about coverage configuration remain.
- Documentation matches actual `pytest.ini` contents.

## Testing Strategy

- **Coverage Target**: N/A (documentation only)
- **Manual verification**: Read through the section for consistency.
