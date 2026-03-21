# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](../memory-bank/activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

### No active blockers (all resolved as of 2026-03-14)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Harden pipeline_handoff path safety & async IO** (`.cortex/plans/harden-pipeline-handoff-path-safety-async-io.md`) - PENDING - Fix security path traversal risk in `pipeline_handoff`, move async FS operations off the event loop, narrow pre-commit exception handling, and improve container init diagnosability; add tests and keep Phase A green.

### Fixes

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](../memory-bank/activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
