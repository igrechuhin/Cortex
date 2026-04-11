# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step** as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work (in progress), (3) Future Enhancements, (4) Pending plans (from .cortex/plans). Order within each section is top-to-bottom. New plans are added by the Plan prompt in the correct place so this order defines execution.

## Blockers (ASAP Priority)

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

#### Knowledge Base & Wiki (High Priority)

#### Token Efficiency (High Priority)

### Features & Enhancements

#### Token Efficiency (Medium Priority)

#### Claude Code Harness Improvements (High Priority)

#### Planning & Brainstorming (High Priority)

#### Planning & Brainstorming (Medium Priority)

#### Wiki for Attached Projects (High Priority)

- Plan: [Project Wiki for Attached Projects (.cortex/wiki/)](../plans/project-wiki-attached-projects.md) — Full `.cortex/wiki/` knowledge base for attached projects: `init-wiki`, `query`, per-category pages, wiki index page, wired into review/analyze/commit pipelines; works when Cortex is attached to itself. Depends on memory-bank-ingest-tool, file-review-reports, memory-bank-lint. PENDING.
- Plan: [Auto-Ingest from Git Hooks (Wiki Auto-Update)](../plans/wiki-auto-ingest-git-hooks.md) — Post-commit hook auto-ingests changed doc files matching configurable glob patterns; idempotent (update vs create); registers via `/cortex/init-wiki`. Depends on project-wiki-attached-projects, hook-conditional-dsl. PENDING.

#### Planning & Brainstorming (Low Priority)

- Plan: [Fast-Forward vs. Step-by-Step Planning Modes](../plans/fast-forward-vs-step-by-step-modes.md) — Add `--ff` (one-shot) and `--step` (one section at a time, human-reviewed) modes to `/cortex/plan`. PENDING.
