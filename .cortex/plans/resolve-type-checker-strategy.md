---
title: "Resolve Type-Checker Strategy Ambiguity"
component: "project-config"
work_type: "fix"
status: "PENDING"
priority: "High"
created: "2026-03-07"
execution_order: 11
depends_on: []
---

# Resolve Type-Checker Strategy Ambiguity

**Status**: PENDING
**Priority**: High
**Complexity**: Low
**Category**: Fix / Documentation
**Component**: project-config
**Work Type**: fix
**Execution Order**: 11

## Goal

Document the official type-checker strategy and remove any stale configuration, resolving the ambiguity between mypy and pyright.

## Context

- `pyproject.toml` has full mypy configuration (lines 74-95) with strict settings.
- `pyright>=1.1.400` is listed as a dev dependency (line 46).
- No `pyrightconfig.json` or `[tool.pyright]` section exists in `pyproject.toml`.
- `Makefile` uses `make typecheck` — need to verify which tool it invokes.
- Unclear whether pyright is intentionally kept for cross-validation or is leftover.

## Implementation Steps

### Step 1: Check what `make typecheck` runs

Read `Makefile` and determine if it runs mypy, pyright, or both.

### Step 2: Decide and document strategy

If mypy is the primary (as `pyproject.toml` config suggests):

- Add a comment in `pyproject.toml` dev dependencies: `"pyright>=1.1.400",  # secondary checker, mypy is primary`
- OR remove pyright from dev dependencies if unused.

### Step 3: Document in techContext.md or CONTRIBUTING

Add a one-liner: "Type checking: mypy is the primary type checker (configured in pyproject.toml). Pyright is [kept for cross-validation / removed]."

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| `pyright` | `pyproject.toml` | Documented with comment or removed |
| `type.check` or `typecheck` | `docs/` or memory bank | Strategy documented |

## Dependencies

- None.

## Success Criteria

- Clear, documented type-checker strategy.
- No ambiguity between mypy and pyright.

## Testing Strategy

- **Coverage Target**: N/A (documentation/config)
