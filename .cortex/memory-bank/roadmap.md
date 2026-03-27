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

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

### Features & Enhancements

- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PENDING (`.cortex/plans/migrate-language-rules-scripts-scaffolding.md`) — Extend the migrate prompt to auto-detect project language and scaffold Synapse rules + scripts stubs for Swift, TypeScript, Java, Rust, Go etc. Wire `run_quality_gate` to route by language via `LanguageQualityRouter`. Eliminates manual post-migration setup (8 rule files for TradeWing Swift required manual creation). Component: migration. Priority: high.
- **Structured Final Reports for Cortex Synapse Prompts** - PENDING (`.cortex/plans/synapse-prompt-final-report-standardization.md`) — Standardize user-facing final report layout across Synapse prompts (commit, implement, fix, analyze, plan, review) and Cursor commands so pipeline outcomes use one predictable markdown skeleton per prompt family.
