# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- **Phase 79: Fix Python Version Pinning and Bootstrap Script** — PENDING. Relax patch-level pin, add one-step bootstrap. Plan: `.cortex/plans/phase-79-python-version-pinning-and-bootstrap.md`
- **Phase 80: Add Synapse Submodule Presence Guard** — PENDING. Fast-fail guard for missing submodule with fallback commands. Plan: `.cortex/plans/phase-80-synapse-submodule-guard.md`
- **Phase 86: MCP Connection Resilience and Auto-Recovery** — PENDING. Auto-reconnect on transient MCP disconnections. Plan: `.cortex/plans/phase-86-mcp-connection-resilience.md`

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

- **Phase 83: Remaining Silent Exception Handlers** — PENDING. Fix 7 remaining `except Exception: pass/continue` blocks. Plan: `.cortex/plans/phase-83-remaining-silent-exceptions.md`
- **Phase 84: Remaining Type-Checker Suppression Cleanup** — PENDING. Reduce 27 suppressions to ≤10. Plan: `.cortex/plans/phase-84-type-checker-suppression-cleanup.md`
- **Phase 90: Agent Session Verbosity and "ok, proceed" Pattern** — PENDING. Eliminate unnecessary agent pauses requiring user confirmation. Plan: `.cortex/plans/phase-90-agent-session-verbosity.md`

### Documentation Cleanup (DRY)

- **Phase 85: Unify Developer Command Surface** — PENDING. Consolidate README/Makefile/CI/AGENTS commands. Plan: `.cortex/plans/phase-85-unify-developer-command-surface.md`

### Refactoring

- **Phase 81: Oversized Module Reduction — Wave 1 (Top 10)** — PENDING. Split top 10 files exceeding 400-line limit. Plan: `.cortex/plans/phase-81-oversized-module-reduction-wave1.md`
- **Phase 82: Coverage Exclusion Audit and Reduction** — PENDING. Reduce coverage omit list blind spots. Plan: `.cortex/plans/phase-82-coverage-exclusion-audit.md`
- **Phase 89: Commit Pipeline Efficiency** — PENDING. Reduce redundant check runs in commit pipeline. Plan: `.cortex/plans/phase-89-commit-pipeline-efficiency.md`
- **Phase 91: HealthCheckReport Type Unification** — PENDING. Replace loose dict alias with Pydantic BaseModel. Plan: `.cortex/plans/phase-91-healthcheck-type-unification.md`

### Cleanup

- **Phase 87: Stale exec() Comment and Dead Reference Cleanup** — PENDING. Remove dead comments referencing removed patterns. Plan: `.cortex/plans/phase-87-dead-reference-cleanup.md`
- **Phase 88: Node Tooling Dependency Isolation** — PENDING. Move Node tools to project-local deps. Plan: `.cortex/plans/phase-88-node-tooling-isolation.md`

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements
