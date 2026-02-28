# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-02-28)

- ✅ **Synapse Usage Storage with usage_writable and Static Snapshot Mode** - COMPLETE (2026-02-28) - Implemented usage_writable config, static snapshot gating for UsageTracker and context stats, Synapse storage root for usage when writable, and documentation updates.

- ✅ **Session Improvements 2026-02-27** - COMPLETE (2026-02-28) - Updated rules_folder to .cortex/synapse/rules for indexing; added Phase 58 consolidation to roadmap. Context effectiveness and MCP health already covered by existing prompts.

- ✅ **Markdown lint fix (MD040)** - COMPLETE (2026-02-28) - Added language specifiers to fenced code blocks in plan-gitignore-coverage-cleanup.md and plan-tools-subpackage-reorganization.md.

- ✅ **Fix requirements.txt and Dockerfile dependency gap** - COMPLETE (2026-02-28) - Migrated Dockerfile to pip install . (pyproject.toml as source of truth); updated requirements.txt with all 6 core deps and sync header.

- ✅ **Fix legacy .memory-bank/ path references** - COMPLETE (2026-02-28) - Replaced legacy .memory-bank/ path references across 15+ docs with current .cortex/ layout. Architecture diagram and Storage Layer updated. ADR and migration docs left as-is.

- ✅ **Fix getting-started.md Removed Tool References** - COMPLETE (2026-02-28) - Rewrote Quick Start to use initialize prompt, validate(check_type=...), get_structure_info; replaced removed tools; updated to .cortex/ layout; 70+ tools.

- ✅ **Fix Gitignore Gaps and Remove Tracked Build Artifacts** - COMPLETE (2026-02-28) - Added coverage.json and coverage_consolidated.json to .gitignore; removed coverage_consolidated.json from git tracking (~2.5 MB).

- ✅ **Compact CLAUDE.md at project root — remove ~80 lines duplicated from Synapse rules** - COMPLETE (2026-02-28) - Reduced .claude/CLAUDE.md from 175 to 120 lines by replacing Python Standards and MCP Development with compact summaries referencing Synapse rules.

- ✅ **Move docs/phase-9-completion-summary.md to docs/design/** - COMPLETE (2026-02-28) - Moved docs/phase-9-completion-summary.md to docs/design/phase-9-completion-summary.md and updated README link and internal references.

- ✅ **Rename roadmap-fix-temp.md to Permanent Name** - COMPLETE (2026-02-28) - Renamed docs/design/roadmap-fix-temp.md to docs/design/roadmap.md; updated session review reference to new path.

- ✅ **Fix stale tool/test/module counts in documentation** - COMPLETE (2026-02-28) - Updated docs/architecture.md, docs/api (index), docs/testing-speed-optimization.md, AGENTS.md, README.md, tool-optimization-baseline.md: 100+→70+ tools, 3700+→4800+ tests, 41+→20+ modules, removed hardcoded test count.

- ✅ **Fix session function naming inconsistency in AGENTS.md** - COMPLETE (2026-02-28) - Standardized session naming in AGENTS.md to session(operation="start"); added README equivalence note.

## Completed Work (2026-02-27)

- **Summary (2026-02-27)** - 1 entries archived.

## Completed Work (2026-02-26)

- **Summary (2026-02-26)** - 1 entries archived.

## Completed Work (2026-02-25)

- **Summary (2026-02-25)** - 1 entries archived.

## Completed Work (2026-02-24)

- **Summary (2026-02-24)** - 1 entries archived.

## Completed Work (2026-02-23)

- **Summary (2026-02-23)** - 1 entries archived.

## Completed Work (2026-02-22)

- **Summary (2026-02-22)** - 1 entries archived.

## Completed Work (2026-02-21)

- **Summary (2026-02-21)** - 1 entries archived.

## Completed Work (2026-02-20)

- **Summary (2026-02-20)** - 1 entries archived.

## Completed Work (2026-02-19)

- **Summary (2026-02-19)** - 1 entries archived.

## Completed Work (2026-02-18)

- **Summary (2026-02-18)** - 1 entries archived.

## Completed Work (2026-02-17)

- **Summary (2026-02-17)** - 1 entries archived.

## Completed Work (2026-02-16)

- **Summary (2026-02-16)** - 1 entries archived.

## Completed Work (2026-02-13)

- **Summary (2026-02-13)** - 1 entries archived.

## Completed Work (2026-01-14)

- **Summary (2026-01-14)** - 1 entries archived.

## Completed Work (2026-02-12)

- **Summary (2026-02-12)** - 1 entries archived.

## Completed Work (2026-02-11)

- **Summary (2026-02-11)** - 1 entries archived.

## Completed Work (2026-02-10)

- **Summary (2026-02-10)** - 1 entries archived.

## Completed Work (2026-02-09)

- **Summary (2026-02-09)** - 1 entries archived.

## Completed Work (2026-02-07)

- **Summary (2026-02-07)** - 1 entries archived.

## Current Focus

Commit pipeline; no active feature focus.

## Recent Changes

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
