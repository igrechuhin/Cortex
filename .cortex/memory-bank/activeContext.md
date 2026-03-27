# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-27)

- ✅ **Pipeline Code Integrity Guard — Prevent Fix-Loop Corruption** - COMPLETE (2026-03-27) - Added fix-loop NO-GO section, post-fix py_compile/import validation, and rollback guidance to fix.md; added TestFixPromptIntegrityGuard alignment tests.

- ✅ **Session Scope Lock (PARTIAL)** - COMPLETE (2026-03-27) - Session start JSON now includes `session_scope` prompting single-goal discipline and confirming one primary goal before expanding scope.

## Completed Work (2026-03-26)

- ✅ **Root-Cause-First Debugging Guardrails** - COMPLETE (2026-03-26) - Updated the Synapse fix prompt to enforce a mandatory diagnose-first Phase 0 with a hard gate that blocks edits until a hypothesis-driven Diagnosis Note is written.

- ✅ **Per-Project Post-Edit Quality Hook (PARTIAL)** - COMPLETE (2026-03-26) - Hook emission instructions added to MIGRATE_PROMPT and INITIALIZE_PROMPT with full language→command table. migrate.md Step 2a updated. 14 integration tests added. Remaining: wire to language detection from migrate-language-rules-scripts-scaffolding.

- ✅ **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern (PARTIAL)** - COMPLETE (2026-03-26) - Runtime now applies/merges project-specific PostToolUse(Edit) hooks during initialize/migrate via a shared setup helper and both direct/lazy prompt handlers, reducing manual setup drift; remaining work is tighter integration with the language-routing scaffolding pipeline.

- ✅ **Session improvements from 2026-03-26T18-37 (PARTIAL)** - COMPLETE (2026-03-26) - Implemented robust analysis target normalization and dispatch routing for usage-pattern aliases and tools/prompts/rules targets, with regression tests and passing quality gate. This materially improves end-of-session analysis target reliability in current MCP/CLI flows; telemetry-presence checks remain.

- ✅ **Session improvements from 2026-03-26T18-37** - COMPLETE (2026-03-26) - Added lifecycle regression coverage for end-of-session context analysis across mixed MCP and direct entrypoints, ensuring sessions with activity no longer produce false no_data results.

- ✅ **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern** - COMPLETE (2026-03-26) - Completed router unification by making LanguageQualityRouter the runtime single source of truth for both post-edit hook command selection and quality adapter selection across inline and detached pre-commit execution, with updated tests and passing quality gate.

- ✅ **Pipeline Code Integrity Guard — Prevent Fix-Loop Corruption (PARTIAL)** - COMPLETE (2026-03-26) - Added integrity guardrails (NO-GO list, post-fix module validation, rollback guidance) to repo-owned quality workflow and fix-quality tool documentation, and added integration tests to prevent regression; still need direct `fix.md` prompt updates to fully complete roadmap step.

## Completed Work (2026-03-25)

- **Summary (2026-03-25)** - 1 entries archived.

## Completed Work (2026-03-24)

- **Summary (2026-03-24)** - 1 entries archived.

## Completed Work (2026-03-23)

- **Summary (2026-03-23)** - 1 entries archived.

## Completed Work (2026-03-22)

- **Summary (2026-03-22)** - 1 entries archived.

## Completed Work (2026-03-21)

- **Summary (2026-03-21)** - 1 entries archived.

## Completed Work (2026-03-20)

- **Summary (2026-03-20)** - 1 entries archived.

## Completed Work (2026-03-16)

- **Summary (2026-03-16)** - 1 entries archived.

## Completed Work (2026-03-14)

- **Summary (2026-03-14)** - 1 entries archived.

## Completed Work (2026-03-13)

- **Summary (2026-03-13)** - 1 entries archived.

## Completed Work (2026-03-12)

- **Summary (2026-03-12)** - 1 entries archived.

## Completed Work (2026-03-11)

- **Summary (2026-03-11)** - 1 entries archived.

## Completed Work (2026-03-10)

- **Summary (2026-03-10)** - 1 entries archived.

## Completed Work (2026-03-09)

- **Summary (2026-03-09)** - 1 entries archived.

## Completed Work (2026-03-08)

- **Summary (2026-03-08)** - 1 entries archived.

## Completed Work (2026-03-07)

- **Summary (2026-03-07)** - 1 entries archived.

## Completed Work (2026-03-06)

- **Summary (2026-03-06)** - 1 entries archived.

## Completed Work (2026-03-05)

- **Summary (2026-03-05)** - 1 entries archived.

## Completed Work (2026-03-04)

- **Summary (2026-03-04)** - 1 entries archived.

## Completed Work (2026-03-03)

- **Summary (2026-03-03)** - 1 entries archived.

## Completed Work (2026-03-02)

- **Summary (2026-03-02)** - 1 entries archived.

## Completed Work (2026-03-01)

- **Summary (2026-03-01)** - 1 entries archived.

## Completed Work (2026-02-28)

- **Summary (2026-02-28)** - 1 entries archived.

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

No queued pending plans under `.cortex/plans` in [roadmap.md](roadmap.md); next slice is chosen from Future Enhancements or the implement command.

## Recent Changes

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
