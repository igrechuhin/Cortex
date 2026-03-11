---
title: "Resolve Type-Checker Strategy Ambiguity"
component: "project-config"
work_type: "fix"
status: "COMPLETE"
priority: "High"
created: "2026-03-07"
execution_order: 11
depends_on: []
---

# Resolve Type-Checker Strategy Ambiguity

**Status**: COMPLETE
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
- Type-checker configuration now includes `pyrightconfig.json` (Pyright primary) alongside the `[tool.mypy]` block in `pyproject.toml` for optional/local cross-checks.
- `Makefile` uses `make typecheck` to invoke Pyright.
- Pyright is the primary type checker (CI + local), with mypy retained as an optional/local-only cross-check.

## Implementation Steps

### Step 1: Clarify and document current strategy (DONE)

- Clarify whether pyright or mypy is the primary type checker.
- Update `pyproject.toml` dev dependency comments so they state the primary checker explicitly.
- Add a clear "Type checking strategy" section to contributor docs, describing Pyright as the primary type checker and mypy as optional/secondary (if retained).

### Step 2: Decide on mypy config retention vs removal (DONE)

- Decide whether to keep the `[tool.mypy]` block as an optional local check or remove it entirely.
- Decision: **retain** the `[tool.mypy]` block as an **optional/local-only** cross-check; Pyright remains the sole CI type checker and the primary local checker.
- Confirm `pyproject.toml` comments clearly mark Pyright as primary (CI + local) and mypy as optional/local only; no CI or tooling paths depend on mypy.
- If removed, delete the `[tool.mypy]` block and any associated mypy-specific config.

### Step 3: Sweep and align other docs and prompts (DONE)

- Search docs, prompts, and memory bank for references to both mypy and pyright.
- Ensure they match the chosen strategy (Pyright primary, mypy optional/local-only).
- Update or add any missing guidance so there is a single, consistent story.
- **Status (latest slice, 2026-03-11)**: Non-.cortex public docs, the extension development guide, and `.cortex` memory-bank entries (including `techContext.md` and roadmap) are aligned to say "Pyright primary, optional/local mypy"; this plan text has been updated to reflect the final strategy. Steps 1–3 are DONE.

### Step 4: Finalize HI-6 via quality-gate validation (DONE)

- Ran the full Phase A quality gate/CI type-check slice with Pyright as primary via the job-based pre-commit pipeline (phase "A") to confirm the finalized strategy behaves correctly end-to-end.
- Quality gate and CI slice passed with Pyright as the enforced primary type checker and mypy as optional/local-only, so HI-6 is now fully COMPLETE and this plan can be treated as closed.

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

