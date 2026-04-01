# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- [Phase: Investigate validate_impl MCP Tool Failure](../plans/phase-investigate-validate_impl-failure-20260331-195026.md) - ASAP (PLANNING) - Investigate and fix MCP tool failure that occurred during commit procedure - Tool: `validate_impl`, Error: TypeError - Impact: Commit procedure blocked - Target completion: 2026-03-31

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Migration: Language-Agnostic Rules and Scripts Scaffolding (follow-up)** - PENDING - Optional TradeWing template reconciliation and further language packs; tracks remaining work reflected in progress PARTIAL entries.

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

### Features & Enhancements

- **Analyze Feedback Loop: Post-Prompt Self-Improvement** - PENDING - Auto-invoke analyze after every prompt; route findings to Skills, Plans, or Rules. Plan: `.cortex/plans/analyze-feedback-loop.md`
