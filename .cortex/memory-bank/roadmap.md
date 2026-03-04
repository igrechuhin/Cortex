# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- **Phase 70: Replace exec() with safe templating and add path validation** - PENDING - Eliminate `exec()` security vulnerability in prompt file loading; add path traversal protection. Plan: `.cortex/plans/phase-70-replace-exec-safe-templating.md`
- **Phase 71: Fix TOCTOU race conditions in file and task locking** - PENDING - Atomic lock acquisition to prevent data corruption under concurrent access. Plan: `.cortex/plans/phase-71-fix-toctou-locking.md`
- **Phase 72: Fix is_connection_error over-matching and consolidate duplicates** - PENDING - Replace broad "resource" keyword matching with precise connection error patterns; consolidate 3 duplicate implementations into single canonical function. Plan: `.cortex/plans/phase-72-fix-connection-error-matching.md`

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Phase YY: .cortex/history retention and keep_versions behavior** - PENDING - Define and implement a configurable retention policy and `keep_versions` behavior for `.cortex/history/`, including VersionManager changes, cleanup tooling, diagnostics, and tests so history growth is bounded and predictable.
- **Phase 73: Fix blocking event loop and O(n) data structures** - PENDING - Replace `time.sleep()` with async, LRU cache list with OrderedDict, `list.pop(0)` with deque. Plan: `.cortex/plans/phase-73-fix-blocking-and-data-structures.md`
- **Phase 74: Async I/O migration for hot paths** - PENDING - Migrate sync file I/O to async in context loading, cache, and session modules; add parallel file reading. Plan: `.cortex/plans/phase-74-async-io-hot-paths.md`
- **Phase 75: Unify tool response format** - PENDING - Standardize all MCP tool responses to `{"status": "success"|"error", ...}` with shared response builder. Plan: `.cortex/plans/phase-75-unify-response-format.md`
- **Phase 76: Replace TypedDict with BaseModel and remove type-checker suppressions** - PENDING - Eliminate 8 TypedDict classes, 2 TYPE_CHECKING imports, ~17 suppression comments. Plan: `.cortex/plans/phase-76-typeddict-suppressions-cleanup.md`
- **Phase 77: Fix coverage gaps, silent error handling, and stub implementation** - PENDING - Add tests for 0%-coverage module, fix 11 silent `except Exception: pass` blocks, resolve migration stub. Plan: `.cortex/plans/phase-77-coverage-gaps-error-handling.md`
- **Phase 78: Agent implementation verification protocol** - PENDING - Add mandatory post-edit re-read, full-codebase search, plan-scope verification, and date validation to prevent agents from declaring incomplete work as done. Plan: `.cortex/plans/phase-78-agent-implementation-verification.md`

### Fixes

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
