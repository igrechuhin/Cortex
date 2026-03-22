# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-03-22)

- ✅ **Session context usage statistics and memory bank index** - COMPLETE (2026-03-22) - Refreshed `.cortex/.session/context-usage-statistics.json` rollup and `.cortex/index.json` metadata; Synapse usage cache events for 2026-03-22 committed in submodule.

- ✅ **Clean up legacy Node package manifest and clarify Node dependency** - COMPLETE (2026-03-22) - Removed root `package.json`; contributor docs and AGENTS describe a Python-first workflow and CI/global `cspell` as the remaining Node surface; plan archived to `.cortex/plans/archive/`.

- ✅ **Decompose oversized tool modules (PARTIAL)** - COMPLETE (2026-03-22) - Contributor docs now include Architecture guardrails under Code Constraints (size limits, how to request exemptions, quarterly review). Roadmap item kept pending until audit and any remaining splits land.

- ✅ **Decompose oversized tool modules by responsibility boundaries** - COMPLETE (2026-03-22) - Tool-module decomposition batches 1–4 finished: split models re-exports, pre-commit tools, similarity engine; contributing guardrails; file/function size checks clean. Guard test verifies stable facades and line caps.

- ✅ **Gate MCP list_roots to advertised roots capability** - COMPLETE (2026-03-22) - `project_root_resolver` checks client roots capability before `list_roots()` so bridges without roots do not close the transport; unit tests in `test_project_root_resolver.py`.

- ✅ **Decomposed tool module boundary governance test** - COMPLETE (2026-03-22) - `tests/unit/test_decomposed_tool_module_boundaries.py` asserts stable facades, import paths, and logical line caps aligned with decomposition policy.

- ✅ **Fix broad exception handling and subprocess log fd comment** - COMPLETE (2026-03-22) - Documented intentional broad except in project_root_resolver (_fetch_roots_path) and mcp_stability (usage metrics + tool wrapper), plus diagnostic catches in pre_commit_connection and health_check; added Unix fd inheritance comment in _spawn_detached_process; added RuntimeError fallback unit test; marked REV-2026-03-22-1/2 RESOLVED in code review report. Inventory: the `cortex.tools` package initializer uses intentional side-effect imports to register tool modules at import time—lazy/deferred registration remains a future refactor. Fixed MD036/heading style in sibling .cortex/plans drafts so markdown gate passes.

- ✅ **Reconstruct roadmap backlog and enforce docs-gate consistency invariant** - COMPLETE (2026-03-22) - Docs-gate invariant check_roadmap_progress_consistency integrated into Phase B; tests added; progress reconciled (superseded PARTIALs); roadmap Refactoring backlog for remaining decomposition; Steps 1–5 satisfied.

- ✅ **Add offline mode and preflight network/test failure differentiation for bootstrap** - COMPLETE (2026-03-22) - Preflight CLI and `make preflight` (exit 2 on unreachable registry); `make bootstrap-offline` with `WHEELHOUSE`; contributing.md **Offline / Restricted-Network Setup**; path-gated `.github/workflows/bootstrap-offline.yml` (Docker `--network none`, assert `make preflight` exits 2); regression tests; plan archived to `.cortex/plans/archive/Other/fix-bootstrap-offline-preflight-reliability.md`.

- ✅ **Resolve contributor documentation drift and conflicting quality workflow instructions** - COMPLETE (2026-03-22) - Updated docs/development/contributing.md with .cortex-centric project layout and a human vs MCP quality matrix aligned with AGENTS.md; removed the forbidden legacy Memory Bank path substring from all Markdown; adjusted prompts, ADRs, and tools docs; added unit tests for contributing content and repo-wide Markdown scan.

- ✅ **Decompose oversized tool modules (remainder)** - COMPLETE (2026-03-22) - Verified governance: all src files ≤400 logical lines and functions ≤30 lines; quality gate clean with no file/function length violations. Archived decomposition plan batches 1–4 complete; remainder closed.

- ✅ **Skip cleanup (PARTIAL)** - COMPLETE (2026-03-22) - Deleted `tests/test_init.py` and `tests/test_ultra_simple.py` (only skipped no-ops). README updated. Next: inventory remaining skips, add enforcement + CI trend per plan.

- ✅ **Skip reference enforcement (PARTIAL)** - COMPLETE (2026-03-22) - Collection-time policy for @pytest.mark.skip; all runtime pytest.skip strings cite ref: cleanup-skipped-legacy-tests. Next: CI skip count + inventory doc.

- ✅ **Skip inventory + skipped_tests summary (PARTIAL)** - COMPLETE (2026-03-22) - TestResult.skipped_tests + trend file; docs/development/test-skip-inventory.md. Re-run quality gate after MCP refresh if needed.

- ✅ **Skip policy — runtime pytest.skip AST enforcement (PARTIAL)** - COMPLETE (2026-03-22) - Collection now scans all test modules for pytest.skip calls and requires the same tracked-reference patterns as @pytest.mark.skip, with tests for literals and f-strings.

- ✅ **Remove permanently skipped legacy tests and establish skip expiration policy** - COMPLETE (2026-03-22) - Removed legacy skip-only modules; conftest enforces ref/issue/see on @pytest.mark.skip and AST-scans runtime pytest.skip; skip inventory doc; quality pipeline reports skipped_tests with trend warning; pyright-clean skip_reference_policy strings.

- ✅ **Python framework adapter parsing hardening** - COMPLETE (2026-03-22) - Refined python_adapter_parsing and base adapter wiring; pre_commit processor touch for skipped_tests reporting; tests updated. Lands with skip-reference policy work in the same commit batch.

- ✅ **Narrow broad exception handling in PythonAdapter test execution** - COMPLETE (2026-03-22) - Narrowed test execution catches to (OSError, subprocess.SubprocessError) with descriptive fallback for other exceptions; debug log on skip-count cache write failure; six unit tests; helper _complete_streaming_test_run for function-length compliance.

- ✅ **Test and harden parse_type_errors in python_adapter_parsing** - COMPLETE (2026-03-22) - Added _PYRIGHT_ERROR_RE for pyright path:line:col - error: lines; replaced substring heuristic in parse_type_errors; added TestParseTypeErrors with eight unit tests including summary, warning, and snippet edge cases.

- ✅ **Add URL scheme validation to preflight registry probe** - COMPLETE (2026-03-22) - resolve_registry_url now requires UV_INDEX_URL to start with https:// or <http://>; invalid schemes raise ValueError; main prints [FAIL] and exits 2. Added five tests (file/ftp reject, http/https accept, main invalid scheme).

- ✅ **Document offline bootstrap and preflight CLI architecture** - COMPLETE (2026-03-22) - Replaced stub with architecture doc: overview, UV_INDEX_URL and scheme guard, HEAD to GET fallback, exit codes, offline triage, CI bootstrap-offline vs quality workflow, ASCII flow, security notes, related files. Linked from docs/security/best-practices.md and README developer commands.

- ✅ **Python adapter checks (pyright timeout parity)** - COMPLETE (2026-03-22) - `_run_pyright` uses `timeout=300`; `type_check_pyright_only` catches `TimeoutExpired` with labeled errors. New timeout unit tests. Review-report markdown blank-line fixes for rumdl preflight.

- ✅ **Narrow exceptions in python_adapter_checks** - COMPLETE (2026-03-22) - Pyright path uses 300s timeout and TimeoutExpired handling aligned with check_types script; unit tests for script/pyright timeouts; layered exceptions already present for black/ruff/type/ruff_fix.

- ✅ **Pipeline handoff and usage analytics decomposition** - COMPLETE (2026-03-22) - Split pipeline_handoff into pipeline_handoff_io and pipeline_handoff_validation; usage analytics into analytics_collection and usage_analytics_resources with thin facades; added test_analytics_collection, test_python_adapter_checks, and test_phase_a_lock; updated test_decomposed_tool_module_boundaries and pre_commit_zero_arg_tools; python_adapter_checks and session index aligned with quality gate.

- ✅ **Decompose oversized tool modules — remainder** - COMPLETE (2026-03-22) - All src/cortex/tools/**/*.py files are at or under 400 logical lines; function_length_violations empty. Final trim: moved build_statistics_dict into effectiveness_operations_insights.py. Earlier batches split pipeline_handoff, usage_analytics, synapse prompts, markdown_lint cache/core, and pre_commit_detached/process. Quality gate passed (5412 tests, coverage ~91.6%).

- ✅ **Add narrative doc for preflight HEAD→GET fallback and http:// allowance** - COMPLETE (2026-03-22) - Added narrative subsections: Why http:// is allowed under scheme validation; Probe strategy with HEAD→GET fallback prose and step-by-step list. Linked ALLOWED_SCHEMES to preflight.py. Docs and quality gates pass.

- ✅ **Context/preflight performance tests** - COMPLETE (2026-03-22) - Timing regression tests for load_context_impl (<100ms median) and TokenCounter warm cache (<5ms median); tests in tests/unit/test_context_load_perf.py and test_tiktoken_cache_perf.py; baselines in docs/architecture/performance-baselines.md.

- ✅ **Profile and verify performance of context loading and preflight hot paths** - COMPLETE (2026-03-22) - Added docs/architecture/performance-baselines.md with targets, test enforcement, sample medians (~5.5ms context load, sub-microsecond warm tiktoken on maintainer laptop), and preflight note. Linked from productContext success metrics and tool-usage-tracking Performance section. Timing regression tests already in tree.

- ✅ **Perf regression tests — pyright unused call results** - COMPLETE (2026-03-22) - Assigned `_ =` to warmup `load_context_impl` and `count_tokens_with_cache` in tests/unit/test_context_load_perf.py and test_tiktoken_cache_perf.py so reportUnusedCallResult passes; use run_quality_gate_fresh when Phase A pyright output looks stale versus local fixes (per AGENTS.md).

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
