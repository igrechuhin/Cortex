# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Phase 76: Replace TypedDict with BaseModel and remove type-checker suppressions** - PENDING - Eliminate 8 TypedDict classes, 2 TYPE_CHECKING imports, ~17 suppression comments. Plan: `.cortex/plans/phase-76-typeddict-suppressions-cleanup.md`
- **Phase 77: Fix coverage gaps, silent error handling, and stub implementation** - PENDING - Add tests for 0%-coverage module, fix 11 silent `except Exception: pass` blocks, resolve migration stub. Plan: `.cortex/plans/phase-77-coverage-gaps-error-handling.md`
- **Phase 78: Agent implementation verification protocol** - PENDING - Add mandatory post-edit re-read, full-codebase search, plan-scope verification, date validation, commit message quality enforcement, selective staging (no `git add -A`), and analyze target specification to prevent agents from declaring incomplete work as done and improve commit pipeline discipline. Plan: `.cortex/plans/phase-78-agent-implementation-verification.md`

### Fixes

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
