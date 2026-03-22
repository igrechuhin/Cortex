# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

### No active blockers (all resolved as of 2026-03-14)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

- **Add narrative doc for preflight HEAD→GET fallback and http:// allowance** - PENDING - Write a narrative section in docs/offline-bootstrap-preflight.md explaining the HEAD→GET probe fallback design and the deliberate http:// allowance for internal mirrors. Closes the Documentation plateau at 7/10. Plan: `.cortex/plans/preflight-narrative-doc.md`.
- **Profile and verify performance of context loading and preflight hot paths** - PENDING - Profile cortex://context resource load time and tiktoken cache hot/cold paths. Add timing regression tests asserting <100ms context load. Move Performance score from assumed-7 to evidence-based-8. Plan: `.cortex/plans/preflight-performance-profiling.md`.

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
