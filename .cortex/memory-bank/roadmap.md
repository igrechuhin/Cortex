# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

- Phase 58 tools consolidation: merge check_task_available_lock, claim_task_lock, release_task_lock, list_active_tasks into single dispatcher (low priority)
- **Evaluate .cortex/history vs git history** - PENDING - Evaluate whether `.cortex/history` provides unique value beyond git, and if not, simplify or phase it out while preserving safety and rollback guarantees.
- **Evaluate .cortex/history vs git history** - PENDING - Evaluate whether `.cortex/history` provides unique value beyond git, and if not, simplify or phase it out while preserving safety and rollback guarantees. Plan: `.cortex/plans/evaluate-cortex-history-vs-git-history.md`

## Pending plans (from .cortex/plans)

### Fixes

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

- **Cleanup Cortex derived-state directories (.cortex/.cache, .cortex/history, .cortex/rules, .cortex/script-capture, benchmark_results)** - PENDING - For each directory, either document the concrete reason to keep (owner, retention policy, consumers) or remove/consolidate it safely. Plan: `.cortex/plans/cleanup-cortex-derived-state.md`
- **Cleanup Cortex derived-state directories** - PENDING - Ensure each of .cortex/.cache/sessions, .cortex/.cache/usage, .cortex/.cache/.cache, .cortex/history, .cortex/rules, .cortex/script-capture, and benchmark_results is either justified (owner, purpose, retention) or removed/consolidated.

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
