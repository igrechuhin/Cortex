# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

### No active blockers (all resolved as of 2026-03-14)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

- **Automate dependency parity between pyproject.toml and requirements.txt** — PENDING (medium) — CI validation step to prevent manual sync drift. Plan: `.cortex/plans/dependency-declaration-parity.md`

### Documentation Cleanup (DRY)

### Refactoring

- **Deduplicate _session_dir helper across pre-commit modules** — PENDING (low) — Extract shared `session_dir` from `pre_commit_detached` and `pre_commit_status`. Plan: `.cortex/plans/deduplicate-session-dir-helper.md`
- **Decompose oversized tool modules by responsibility boundaries** — PENDING (medium) — Split largest files/functions to comply with 400-line/30-line limits. Plan: `.cortex/plans/decompose-oversized-tool-modules.md`

### Cleanup

- **Clean up legacy Node package manifest and clarify Node dependency** — PENDING (low) — Remove or formalize legacy Node metadata; document exact CI Node usage. Plan: `.cortex/plans/clean-up-legacy-package-json.md`

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
