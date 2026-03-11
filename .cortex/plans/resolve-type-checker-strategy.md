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

**Status**: IN_PROGRESS
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

### Step 1: Clarify and document current strategy (DONE)

- Clarify whether pyright or mypy is the primary type checker.
- Update `pyproject.toml` dev dependency comments so they state the primary checker explicitly.
- Add a clear "Type checking strategy" section to contributor docs, describing Pyright as the primary type checker and mypy as optional/secondary (if retained).

### Step 2: Decide on mypy config retention vs removal (PARTIAL)

- Decide whether to keep the `[tool.mypy]` block as an optional local check or remove it entirely.
- If kept, ensure comments in `pyproject.toml` and docs clearly mark it as optional/local only. (CURRENT: `[tool.mypy]` is retained and explicitly documented as an optional/local cross-check, with Pyright as the primary type checker.)
- If removed, delete the `[tool.mypy]` block and any associated mypy-specific config.

### Step 3: Sweep and align other docs and prompts (PARTIAL)

- Search docs, prompts, and memory bank for references to both mypy and pyright.
- Ensure they match the chosen strategy (Pyright primary, mypy optional/removed).
- Update or add any missing guidance so there is a single, consistent story.

### Step 4: Finalize HI-6 and plan status (TODO)

- Once mypy retention/removal is decided and all docs are aligned, mark this plan as COMPLETE.
- Ensure the roadmap entry for **[HI-6] Resolve Type-Checker Strategy** is updated from PARTIAL to COMPLETE at that time.

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
