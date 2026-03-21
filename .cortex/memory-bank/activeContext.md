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

- ✅ **Fix review prompt to track issues across reviews** - COMPLETE (2026-03-21) - Updated Synapse review.md: mandatory Issue Tracker with REV- IDs; telemetry-only diff scope expansion; Step 4 regression check; score deltas and stale-metric flag; improvement suggestions require file:line, before/after, max 3 files; success criteria aligned.

- ✅ **Targeted exception narrowing in validation and config paths** - COMPLETE (2026-03-21) - Narrowed validation_config reads/parses/save and container post-init catches; completion_io already used specific exceptions; added tests ensuring TypeError propagates from validate/save paths.

- ✅ **Replace sync file I/O with async in pipeline_handoff** - COMPLETE (2026-03-21) - All pipeline_handoff filesystem work runs inside asyncio.to_thread via _dispatch_sync offload; tests assert to_thread is invoked (TestAsyncToThreadOffload). Quality gate green.

- ✅ **Align docs/index.md with canonical 10-tool inventory** - COMPLETE (2026-03-21) - Removed stale 70+ tool claims; docs/index.md now matches README inventory marker and describes the live 10-tool/6-resource surface; Key Features Phase 5 updated for quality gates and pipelines; architecture.md and getting-started.md aligned. rumdl + quality gate green.

- ✅ **Clarify file/function size governance: document logical-line counting** - COMPLETE (2026-03-21) - Documented logical-line file/function limits in contributing.md with CI script commands and exclusion lists; quality.yml step names and errors say logical lines; MAX_* comments in constants.py point to check scripts. Step 4 optional dashboard not added (check_file_sizes already warns near limit).

- ✅ **Add CI markdown link validation for non-archive docs** - COMPLETE (2026-03-21) - Added markdown_link_validation module, Synapse check_markdown_links.py CLI, quality.yml step, merged link results into run_markdown_lint_all_files_check for Phase A parity.

- ✅ **Markdown link validation — Pyright and test typing** - COMPLETE (2026-03-21) - Renamed link-check helpers to public names for lawful test imports; consumed `Path.relative_to` and `write_text` results; typed `Path.read_text` monkeypatch in `test_check_markdown_links.py` so pyright passes under strict unused-result and private-usage rules.

- ✅ **Tighten tool-count guardrail from MAX=16 to MAX=12** - COMPLETE (2026-03-21) - Reduced MAX_REGISTERED_TOOLS to 12; documented escalation in docs/api/tools.md; added test_max_registered_tools_cap. Plan `tool-budget-tightening` archived under `.cortex/plans/archive/Other/`.

- ✅ **Improve submodule preflight resilience and error messaging** - COMPLETE (2026-03-21) - Interactive submodule init prompt in check_synapse.sh (TTY only); bootstrap.sh runs git submodule update before uv sync when scripts dir missing; precommit_block_response adds remediation git submodule update --init --recursive.

- ✅ **Rumdl scope parity and submodule MCP remediation** - COMPLETE (2026-03-21) - CI `quality.yml` and `make check-ci-parity` exclude `.cortex/.cache/` from rumdl discovery; `markdown_lint_core.get_all_markdown_files_for_lint` mirrors `.cortex/history/` and `.cortex/.cache/` excludes with POSIX-normalized relative paths; `precommit_block_response` adds explicit `remediation` (`git submodule update --init --recursive`). Plan `submodule-resilience.md` moved to `.cortex/plans/archive/Other/`. Tests updated for lint paths and guard behavior.

- ✅ **Align bootstrap.sh Synapse readiness check with check_synapse.sh** - COMPLETE (2026-03-21) - Added scripts/_synapse_lib.sh with _synapse_scripts_ready(); bootstrap.sh and check_synapse.sh source it. Bootstrap prints remediation text then runs git submodule update when scripts dir missing or empty. Added tests/unit/test_synapse_scripts_readiness.py for empty/missing/non-empty cases and bootstrap wiring.

- ✅ **Narrow broad exception handlers in markdown lint core** - COMPLETE (2026-03-21) - Replaced broad except Exception in run_command, _calculate_file_hash, and update_markdown_lint_cache_safe with specific types; added FileLockTimeoutError for cache path; exported calculate_file_hash for tests; added unit tests for propagation and logging.

- ✅ **Handle subprocess.TimeoutExpired in pre_commit_submodule_guard** - COMPLETE (2026-03-21) - Wrapped both git subprocess calls in try/except for TimeoutExpired; log warnings and return safe empty/skip behavior; added unit tests for status and porcelain timeouts.

- ✅ **Remove redundant asserts in plan tool** - COMPLETE (2026-03-21) - Removed dead assert lines after guard returns in _plan_dispatch_complete and _plan_dispatch_register; existing falsy checks suffice for pyright narrowing.

- ✅ **Automate dependency parity between pyproject.toml and requirements.txt** - COMPLETE (2026-03-21) - Added scripts/check_dep_parity.py validating [project.dependencies] against requirements.txt (PEP 503 names); unit tests; quality.yml step; make check-dep-parity; contributing.md note.

- ✅ **Deduplicate _session_dir helper across pre-commit modules** - COMPLETE (2026-03-21) - Added cortex.tools.execution.session_paths.session_dir (single get_cortex_path+mkdir); pre_commit_detached and pre_commit_status import it; removed duplicate _session_dir; added tests/unit/test_session_paths.py.

- ✅ **MCP TaskGroup connection error classification (-32000)** - COMPLETE (2026-03-21) - `_handle_broken_resource_in_group` no longer skips `RuntimeError("MCP error -32000: Connection closed")`; nested TaskGroup failures use `is_connection_error` for graceful shutdown classification. Hardened `mcp_stability_retry` test isolation; added `tests/unit/test_mcp_crash_fixes.py`; aligned `test_main_error_handling`.

- ✅ **pre_commit_tools decomposition (PARTIAL)** - COMPLETE (2026-03-21) - pre_commit_tools.py split into pre_commit_tools_inline_execution.py and pre_commit_tools_execute_checks.py; MCP surface unchanged; re-exports for worker/tests; unit test mocks target inline/execute modules.

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
