---
title: "Synapse prompt filenames: do.md and plan.md"
component: synapse
work_type: cleanup
status: PENDING
priority: normal
created: 2026-04-01
depends_on: []
---

## Goal

Align Synapse prompt **filenames** and **manifest display names** with short, consistent tokens: roadmap implementation prompt becomes `do.md` with name **Do**; plan-creation prompt becomes `plan.md` (display name remains **Plan**). Update the Cortex repo and tests that reference the old filenames.

## Context

- `prompts-manifest.json` (under `.cortex/synapse/prompts/`, also visible via `.cursor/synapse/` symlink) lists `implement-next-roadmap-step.md` / `create-plan.md`.
- `.cursor/synapse` → `.cortex/synapse` (single source tree); renames happen once in the submodule.
- Many tests and docs hardcode the old basenames; `docs/architecture/naming-*.md` documents slug/filename mapping.
- User-facing slash commands (e.g. `/cortex/implement`) are defined in prompt bodies and may remain stable unless product chooses to rename commands in a follow-up.

## Implementation Steps

### Step 1: Submodule renames (Synapse)

- In `.cortex/synapse/`: `git mv prompts/implement-next-roadmap-step.md prompts/do.md` and `git mv prompts/create-plan.md prompts/plan.md`.
- Edit `prompts/prompts-manifest.json`: set `"file": "do.md"`, `"name": "Do"` for the implement entry; set `"file": "plan.md"` for the plan entry (keep `"name": "Plan"`).
- Search within `prompts/` for self-references to old filenames or titles; update prose (e.g. "create-plan" hard gate text) only where it names the file.
- Update `agents/agents-manifest.json` (or similar) if description string references `implement-next-roadmap-step` literally.

### Step 2: Cortex repo references

- Grep repo for `implement-next-roadmap-step`, `create-plan.md` (path references); update:
  - `tests/integration/` (e.g. `test_synapse_final_report_prompt_alignment.py`, `test_feedback_loop_structural.py`, `test_commit_workflow_*`, `test_plan_creation_workflow_compliance.py`, `test_implement_prompt_quality_gates.py`, `test_implement_select_explicit_plan_prompt.py`)
  - `tests/tools/` as needed
  - `docs/architecture/naming-conventions.md`, `docs/architecture/naming-inventory-2026-02.md`
  - `docs/guides/REFACTORING_GUIDE.md`, `test-maintenance.md`, `.cortex/synapse/README.md`, `prompts/REFACTORING_*.md` if still maintained
  - `.cortex/memory-bank/systemPatterns.md` if it lists filenames
- Do **not** rewrite archived plan files under `.cortex/plans/archive/` unless required by CI (prefer leaving historical references).

### Step 3: Verification

- `uv run pytest` for affected tests; `run_quality_gate()` after submodule pointer bump.
- Confirm manifest loads and prompt discovery tests pass.

## Verification Checklist (per step)

| Step | What to search for | Search scope | Files to re-read |
|------|-------------------|--------------|------------------|
| 1 | `implement-next-roadmap-step`, `create-plan.md` | `.cortex/synapse/prompts/`, `agents/` | `prompts-manifest.json`, `do.md`, `plan.md` |
| 2 | same strings | `tests/`, `docs/`, `src/` if any | failing test files |
| 3 | test failures | pytest output | — |

## Dependencies

- Synapse submodule commit + superproject gitlink update for Cortex.

## Success Criteria

- `do.md` and `plan.md` exist; manifest matches; no broken test references in non-archive tree; docs inventory reflects new filenames (or notes intentional slug vs filename).

## Testing Strategy

- Target **≥95%** coverage on touched modules where applicable; run full integration tests for prompt path fixtures.
