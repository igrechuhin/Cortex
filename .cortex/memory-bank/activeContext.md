# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-28)

- ✅ **Migration: language rule templates and scaffolded_languages reporting** - COMPLETE (2026-03-28) - Synapse submodule adds minimal rules/_templates for Go, Java, JavaScript, Rust, and TypeScript. Structure migration now derives scaffolded_languages from scaffolded rule/script paths (_collect_scaffolded_languages, _to_json_list) with expanded unit tests; plan doc and AGENTS touched. Submodule pointer updated to the new Synapse commit.

- ✅ **Migration: Language-Agnostic Rules and Scripts Scaffolding** - COMPLETE (2026-03-28) - Documented migrate Step 2b (language detection, rules/scripts scaffolding, quality gate routing) and extended expected migration JSON. Clarified zero-arg run_quality_gate and LanguageQualityRouter docs; added unit tests proving resolve_adapter_worker selects SwiftAdapter vs PythonAdapter. Optional TradeWing template reconciliation remains a manual follow-up outside this repo.

## Completed Work (2026-03-27)

- ✅ **Pipeline Code Integrity Guard — Prevent Fix-Loop Corruption** - COMPLETE (2026-03-27) - Added fix-loop NO-GO section, post-fix py_compile/import validation, and rollback guidance to fix.md; added TestFixPromptIntegrityGuard alignment tests.

- ✅ **Session Scope Lock (PARTIAL)** - COMPLETE (2026-03-27) - Session start JSON now includes `session_scope` prompting single-goal discipline and confirming one primary goal before expanding scope.

- ✅ **Session Scope Lock — Single-Goal Session Pattern (PARTIAL)** - COMPLETE (2026-03-27) - Documented single-goal session discipline in `CLAUDE.md` under a new `Session Discipline` section to reduce mixed-scope sessions and partial completions.

- ✅ **Session Scope Lock — context parity (PARTIAL)** - COMPLETE (2026-03-27) - `cortex://context` now includes `session_scope` in success payloads, aligning start-session guidance with context resources. Added test coverage in optimization resource tests; remaining roadmap work is prompt-level split-commit and analyze scope-risk guidance.

- ✅ **Submodule Hygiene Unblock for Fix Pipeline** - COMPLETE (2026-03-27) - Adjusted submodule hygiene behavior for FIX semantics so dirty_worktree findings no longer block `/cortex/fix` quality/test progression, while out_of_sync and merge_conflict still block. Added regression tests for both non-blocking and blocking FIX-mode cases; quality gate verified green.

- ✅ **Session Scope Lock — Single-Goal Session Pattern** - COMPLETE (2026-03-27) - Enforced single-goal session discipline in commit/analyze prompts by adding mandatory split-commit guidance and multi-goal scope-risk reporting, with integration tests updated accordingly.

- ✅ **MCP Server Regression Test Suite — Concurrent Subagent and Serialization Tests** - COMPLETE (2026-03-27) - Added deterministic regression tests covering concurrent tool saturation, `pipeline_handoff` serialization (string/object payloads), and CWD/root-resolution edge cases, plus sequencing safeguards; quality gates now pass.

- ✅ **Commit pipeline run + docs lint repair** - COMPLETE (2026-03-27) - Executed commit pipeline phases inline, pre-staged Synapse submodule hygiene commit, and repaired roadmap link path to unblock markdown lint in Phase A.

- ✅ **Investigate fix_quality_issues MCP Tool Failure** - COMPLETE (2026-03-27) - Restored backwards-compatible `phase_a_lock` symbol as an alias to `get_phase_a_lock`, unblocking `fix_quality_issues()` runtime execution; verified via full quality gate and docs gate.

- ✅ **Migration: Language-Agnostic Rules and Scripts Scaffolding (PARTIAL)** - COMPLETE (2026-03-27) - Migration now scaffolds Swift rule templates into project-local Synapse rules and reports `rules_scaffolded`; tests added and quality gate passes. Remaining work: multi-language templates, quality-gate language routing, and migrate prompt updates.

## Completed Work (2026-03-26)

- **Summary (2026-03-26)** - 1 entries archived.

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
