# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

- Phase 58 tools consolidation: merge check_task_available_lock, claim_task_lock, release_task_lock, list_active_tasks into single dispatcher (low priority)

## Pending plans (from .cortex/plans)

- **PENDING** Fix gitignore gaps and remove tracked build artifacts (see plan). Plan: `.cortex/plans/plan-gitignore-coverage-cleanup.md`
- **PENDING** Compact CLAUDE.md at project root — remove ~80 lines duplicated from Synapse rules. Plan: `.cortex/plans/plan-claude-md-compaction.md`
- **PENDING** Move docs/phase-9-completion-summary.md to docs/design/. Plan: `.cortex/plans/plan-docs-move-phase-summary.md`
- **PENDING** Rename docs/design/roadmap-fix-temp.md to permanent name. Plan: `.cortex/plans/plan-docs-rename-roadmap-fix-temp.md`

### Fixes

- **PENDING** Fix stale tool/test/module counts in documentation (docs say "100+ tools", actual 71). Plan: `.cortex/plans/plan-docs-fix-stale-counts.md`
- **PENDING** Fix session function naming inconsistency in AGENTS.md (mixes session() and session_start()). Plan: `.cortex/plans/plan-docs-fix-session-naming.md`

### Documentation Cleanup (DRY)

- **PENDING** Archive 7 legacy prompt docs superseded by 3 unified prompts. Plan: `.cortex/plans/plan-docs-archive-legacy-prompts.md`
- **PENDING** Consolidate duplicate protocol documentation (2 files, same content). Plan: `.cortex/plans/plan-docs-consolidate-protocols.md`
- **PENDING** Deduplicate token budget table (identical in CLAUDE.md and AGENTS.md). Plan: `.cortex/plans/plan-deduplicate-budget-table.md`

### Refactoring

- **PENDING** Fix 26 tool files exceeding 400-line limit (project rule violation). Plan: `.cortex/plans/plan-tools-file-size-violations.md`
- **PENDING** Rename 47 phase-prefixed tool files to functional names (depends on file-size plan). Plan: `.cortex/plans/plan-rename-phase-prefixed-files.md`
- **PENDING** Reorganize tools/ into domain sub-packages (depends on rename + file-size plans). Plan: `.cortex/plans/plan-tools-subpackage-reorganization.md`

### Cleanup

- **PENDING** Remove 3 empty archive files and stale history (0-byte placeholders). Plan: `.cortex/plans/plan-empty-file-cleanup.md`

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
