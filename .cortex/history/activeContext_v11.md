# Active Context: Cortex

## Current Focus (2026-01-30)

See [roadmap.md](roadmap.md) for current status and milestones.

### Active Work

- ✅ **Phase 66: Plan Creation Workflow Compliance** - COMPLETE (2026-01-30)
  - Create-plan prompt path resolution and roadmap-update rules strengthened; memory-bank-updater note added; 8 integration tests.

- ✅ **Phase 65: Commit Workflow — Cortex Tools Only** - COMPLETE (2026-01-30)
  - Commit prompt now uses only Cortex MCP tools; no direct script invocations. Next: Phase 64.

- **Commit in progress** (2026-01-30)
  - Changes: .github/workflows/quality.yml, src/cortex/services/framework_adapters/python_adapter.py, .cortex/synapse (submodule); markdown lint fix on .cortex/synapse/prompts/commit.md.
  - Steps 0–4 passed: fix_errors (0), format, markdown lint (179 files, 1 fixed), type_check (0 errors, 0 warnings), quality (0 violations), tests (2932 passed, 90.01% coverage).

- ✅ **Commit: Coverage above 90%** - COMPLETE (2026-01-30)
- ✅ **Multi-Language Validation Support** - COMPLETE (2026-01-29)
- ✅ **Phase 55: Improve Implementation Prompt Quality Gates** - COMPLETE (2026-01-29)
- ✅ **Phase 56: Commit Workflow Parallelization (Steps 9–11)** - COMPLETE (2026-01-29)
- ✅ **Plan: Enhance Tool Descriptions with USE WHEN and EXAMPLES** - COMPLETE (2026-01-29)
- ✅ **Phase 62: Synapse Session Optimization** - COMPLETE (2026-01-29)
- ✅ **TypeScript Pre-Commit Adapter** - COMPLETE (2026-01-29)

### Recently Completed

- ✅ **Commit: Coverage above 90%** - COMPLETE (2026-01-30)
- ✅ **TypeScript Pre-Commit Adapter** - COMPLETE (2026-01-29)
- ✅ **Multi-Language Validation Support** - COMPLETE (2026-01-29)

## Project Health

- **Tests**: 2932 passing, 0 failed, coverage 90.01%.
- **Linting/Types**: No Ruff or pyright issues.
- **Pre-commit adapters**: SUPPORTED_LANGUAGES = (python, typescript, javascript, rust, go, java); Python and TypeScript full implementations.

## Next Focus

- **Phase 64: Promote fixed string sets to enums** - PLANNED (.cortex/plans/phase-64-promote-fixed-strings-to-enums.md).
- **Phase 66: Plan Creation Workflow Compliance** - COMPLETE (2026-01-30) — create-plan prompt and memory-bank-updater updated; integration tests added.
- Phase 65 plan updated to Completed; no archive move (plan remains in .cortex/plans/).
