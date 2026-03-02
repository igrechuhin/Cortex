# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

- Phase 58 tools consolidation: merge check_task_available_lock, claim_task_lock, release_task_lock, list_active_tasks into single dispatcher (low priority)

## Pending plans (from .cortex/plans)

- **Consolidate roadmap + append_entry** - PENDING - Merge roadmap and append_entry into update_memory_bank tool with operations for roadmap add/remove and progress/activeContext append. Reduces tool count by 1. ([plan](.cortex/plans/consolidate-roadmap-append-entry.md))
- **Consolidate validate + check_structure_health** - PENDING - Evaluate merging validate and check_structure_health into single project health tool. Go/no-go in Step 1 due to different domains and side-effect semantics. ([plan](.cortex/plans/consolidate-validate-check-structure-health.md))
- **Consolidate suggest_refactoring + apply_refactoring** - PENDING - Evaluate merging suggest_refactoring and apply_refactoring into single refactoring tool. Go/no-go in Step 1 due to different intents (read vs write). ([plan](.cortex/plans/consolidate-suggest-apply-refactoring.md))

### Fixes

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
