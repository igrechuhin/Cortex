# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

### No active blockers (all resolved as of 2026-03-14)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

### Documentation Cleanup (DRY)

- **Resolve contributor documentation drift and conflicting quality workflow instructions** - PENDING - Replace stale `.cursor/memory-bank` path references with `.cortex/memory-bank`. Create single canonical human/agent workflow matrix in the contributing guide. Add regression tests for stale paths and matrix presence. Plan: `.cortex/plans/cleanup-contributor-docs-drift.md`

### Refactoring

- **Decompose oversized tool modules (remainder)** - PENDING - Continue module splits and function-length work per `docs/development/contributing.md` policy. Archived reference: `.cortex/plans/archive/Other/decompose-oversized-tool-modules.md`

### Cleanup

- **Remove permanently skipped legacy tests and establish skip expiration policy** - PENDING - Remove or convert legacy permanently-skipped test modules (historical init and ultra-simple suites). Enforce skip expiration policy (every skip must have a plan/issue ref). Add skip count trend to CI quality summary. Plan: `.cortex/plans/cleanup-skipped-legacy-tests.md`

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
