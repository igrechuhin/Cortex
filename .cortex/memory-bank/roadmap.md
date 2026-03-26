# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

### No active blockers (all resolved as of 2026-03-14)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

- **Session improvements from 2026-03-26T18-37** - PENDING (`.cortex/plans/session-improvements-2026-03-26t18-37.md`) — Follow-up from analysis: improve session telemetry capture and analysis target routing.

### Fixes

### Quality & Reliability Improvements

### Security

### Documentation Cleanup (DRY)

### Refactoring

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Improvements

- **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern** - PENDING (`.cortex/plans/post-edit-test-hook.md`) — Emit language-appropriate PostToolUse hooks into each project's `.claude/` settings during migrate/initialize (pytest for Python, swift build for Swift, cargo test for Rust, etc.). Depends on language detection from migrate-language-rules-scripts-scaffolding. Component: ci. Priority: high.
- **Pipeline Code Integrity Guard — Prevent Fix-Loop Corruption** - PENDING (`.cortex/plans/pipeline-code-integrity-guard.md`) — Add NO-GO list and post-fix import validation to the fix prompt to prevent duplicate definitions, TYPE_CHECKING violations, and circular imports. Component: pipelines. Priority: high.
- **Session Scope Lock — Single-Goal Session Pattern** - PENDING (`.cortex/plans/session-scope-lock-pattern.md`) — Surface single-goal session discipline at session start to reduce budget exhaustion and partial completions. Component: prompts. Priority: medium.
- **MCP Server Regression Test Suite — Concurrent Subagent and Serialization Tests** - PENDING (`.cortex/plans/mcp-regression-test-suite.md`) — Create regression tests covering concurrent saturation, serialization roundtrip, CWD resolution, graceful degradation, and sequential execution. Component: mcp-server. Priority: high.

### Features & Enhancements

- **Migration: Language-Agnostic Rules and Scripts Scaffolding** - PENDING (`.cortex/plans/migrate-language-rules-scripts-scaffolding.md`) — Extend the migrate prompt to auto-detect project language and scaffold Synapse rules + scripts stubs for Swift, TypeScript, Java, Rust, Go etc. Wire `run_quality_gate` to route by language via `LanguageQualityRouter`. Eliminates manual post-migration setup (8 rule files for TradeWing Swift required manual creation). Component: migration. Priority: high.
