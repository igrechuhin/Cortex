# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-21)

- ✅ **Pre-commit submodule hygiene guard** - COMPLETE (2026-03-21) - Added `pre_commit_submodule_guard.py` (submodule status scan, dirty/out-of-sync violations, remediation text), wired into `pre_commit_tools.py` and `pre_commit_worker.py`, with `test_pre_commit_submodule_guard.py` and updates to `test_pre_commit_tools.py`. Plan `block-dirty-submodule-references-in-commit-workflow` archived under `.cortex/plans/archive/Other/`.

- ✅ **Session telemetry hardening against synthetic pollution** - COMPLETE (2026-03-21) - `ContextTelemetryRecordQuality` classification; production-only rollups; exclusion logging; in-process counters with optional env-gated debounced POST export (`CORTEX_CONTEXT_TELEMETRY_EXCLUSION_METRICS_*`); internal-consistency rules and `reconcile_context_usage_statistics_entries` with load-time backfill when `usage_writable`. Docs: `docs/architecture/tool-usage-tracking.md`, `docs/guides/troubleshooting.md`. Tests: `test_effectiveness_telemetry_quality.py`.

- ✅ **MCP docs, README, and CI — single source of truth for published tool surface** - COMPLETE (2026-03-21) - Added cortex.discovery.published_inventory, docs/_generated/tool-inventory.json, README drift markers, tests for JSON/README parity, split docs/api/tools.md into canonical vs historical catalog, clarified tool_registry scope, docs/prompts guidance for zero-arg quality tools.

- ✅ **Convert tests/test_phase5_3_4.py to pytest and guard script-only test files** - COMPLETE (2026-03-21) - Converted Phase 5.3–5.4 script tests to pytest (tmp_path memory-bank layout, async tests). Added AST guard test_script_only_pytest_files_guard for tests/**/test_*.py. Migrated test_phase6_imports, test_quick, and test_simple from script-only to collected tests so the guard passes.

- ✅ **Offline / network-restricted verification bootstrap and triage docs** - COMPLETE (2026-03-21) - Added troubleshooting section for offline/air-gap uv bootstrap (wheelhouse, UV_OFFLINE, frozen sync, mirrors), verification preflight, CI parity pointers, and symptom triage matrix; linked from README Developer commands and AGENTS Cursor Cloud prerequisites.

- ✅ **Telemetry — Synapse usage cache policy and context-usage-statistics semantics** - COMPLETE (2026-03-21) - Documented superproject vs Synapse .cache/usage commit policy; expanded context-usage-statistics.json field semantics and reconcile behavior; added schema_version (default 1) to ContextUsageStatistics with loader tests; PR checklist in contributing.md.

- ✅ **Phase A markdown lint scope and preflight markdown merge** - COMPLETE (2026-03-21) - `collect_pre_commit_markdown_paths` in `pre_commit_worker.py` excludes `.cortex/history/` and `.cortex/.cache/` from the detached worker rumdl file list (snapshots keep sibling-only links); merged `markdown_result` into `_poll_phase_a_result` in `pre_commit_zero_arg_tools.py` so `preflight_passed` reflects rumdl. Tests: `test_pre_commit_worker_md_collect.py`, `test_poll_phase_a_markdown_merge.py`.

- ✅ **Narrow broad exception handlers — plans completion I/O and migration** - COMPLETE (2026-03-21) - Replaced broad except Exception in completion_io and migration with specific exception tuples; added tests for I/O, JSON, validation, and rollback paths.

- ✅ **Pytest isolation for MCP circuit breaker (xdist)** - COMPLETE (2026-03-21) - Added `reset_connection_state_for_testing` / `ensure_clean_connection_state_for_testing` in `mcp_stability_retry.py`, autouse `isolate_mcp_connection_state` in `tests/conftest.py`, and aligned reconnect tests so `test_reconnect_opens_circuit_after_max_failures` cannot leave the global circuit open for unrelated tests on the same pytest-xdist worker.

- ✅ **Phase A markdown error coercion and run_quality_gate markdown merge test** - COMPLETE (2026-03-21) - `_markdown_result_has_errors` now treats non-numeric `files_with_errors` strings as failures (try/except around int coercion). Added `TestRunQualityGateMarkdownMerge` with mocked detached worker envelope so `run_quality_gate()` returns `preflight_passed: false` when markdown reports errors. Synapse `prompts/commit.md` Phase A markdown remediation text updated; submodule commits record usage analytics.

- ✅ **Quality gate CI parity (PARTIAL)** - COMPLETE (2026-03-21) - Local Phase A now runs synapse `check_spelling.py` by default. `docs/api/tools.md` adds CI parity table; full parity plan still open.

- ✅ **Quality gate CI parity: close remaining gaps between local and CI checks** - COMPLETE (2026-03-21) - Verified CI/local parity deliverables; removed Any from markdown-merge tests; clarified PHASE_A vs preflight markdown_lint in dispatch; quality gate green (5259 tests, ~91.4% coverage).

- ✅ **Sanitize pipeline/phase path parameters in pipeline_handoff** - COMPLETE (2026-03-21) - Added allowlisted pipeline and phase names on top of safe-token regex validation; unknown alphanumeric tokens return JSON errors without touching the filesystem. Adjusted integration tests to use allowlisted pipeline names for empty-state cases; added unit tests for allowlist rejection and happy path.

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
