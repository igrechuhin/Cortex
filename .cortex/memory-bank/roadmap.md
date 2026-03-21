# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

### No active blockers (all resolved as of 2026-03-14)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Offline / network-restricted verification bootstrap and triage docs** - PENDING - Document wheelhouse/mirror preflight; triage matrix for fetch vs test failures. Plan: .cortex/plans/phase-2026-03-21-offline-verification-bootstrap.md
- **Telemetry — Synapse usage cache policy and context-usage-statistics semantics** - PENDING - Policy for .cache/usage commits; document stats JSON semantics. Plan: .cortex/plans/phase-2026-03-21-telemetry-cache-and-stats-governance.md
- **Narrow broad exception handlers — plans completion I/O and migration** - PENDING - Replace except Exception with specific types in `src/cortex/tools/plans/completion_io.py` and `src/cortex/core/migration.py`; add tests. Plan: .cortex/plans/phase-2026-03-21-narrow-exception-plans-migration.md

### Fixes

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
