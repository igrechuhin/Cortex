# Progress Log

## 2026-03-20

- **Pytest lightweight MCP usage init expansion** - COMPLETE. Expanded `_PYTEST_LIGHTWEIGHT_TOOLS` in `mcp_stability_usage.py`, refreshed tool governance tests under `tests/tools/`, tuned `pytest.ini`, and kept Makefile env-check quoting plus integration smoke guard stable; Phase A ~0.91 coverage.
- **Makefile env-check smoke guard and commit/docs gate hardening** - COMPLETE. Fixed env-check quoting in `Makefile`, added smoke integration coverage, and aligned commit/docs flow with zero-arg `run_quality_gate*`/`run_docs_gate` entrypoints plus dirty-submodule guard handling.
- **Phase A Fingerprint & Detached Polling Hardening** - COMPLETE. Narrowed Phase A fingerprint bookkeeping exception handling, moved detached polling file reads off the event loop, and improved hybrid-rule NotImplementedError stub messages. Phase A quality gate passed.
- **Harden pipeline_handoff path safety & async IO** - COMPLETE. Secured `pipeline_handoff` against path traversal and moved blocking FS operations off the event loop via `asyncio.to_thread`; tightened exception handling and improved container init logging; added negative and async-offload tests; Phase A green.
- **Align docs to zero-arg quality pipeline and deprecate stale entrypoints (2026-03-20)** - COMPLETE. Canonical tools.md section + cross-links; README/AGENTS/troubleshooting and broad docs/** aligned; tests/unit/test_docs_zero_arg_quality_consistency.py (4 tests) guards deprecated quality entrypoint strings.
- **Makefile env-check Python -c quoting for GitHub Actions (2026-03-20)** - COMPLETE. Replaced broken f-string escapes in `make env-check` with percent-format `print` so Ubuntu CI passes; refreshed `test_makefile_env_check_smoke_guard.py`.
- **Split make quality flows into non-mutating check and fix modes** - COMPLETE. make check uses Black --check + ruff + pyright + fast tests; make fix applies Black/ruff fixes; check-ci-parity adds synapse scripts, sizes, rumdl, pytest with coverage; README, AGENTS, troubleshooting, tests.
- **Document MCP-unavailable fallback for read-only audits** - COMPLETE. Added AGENTS policy, troubleshooting runbook, README link, and test_mcp_unavailable_read_only_fallback_docs_wired.
- **Block dirty submodule references in commit workflow** - COMPLETE. Phase A and detached worker now fail fast with remediation when submodules are dirty or gitlink is out of sync.

## 2026-03-21

- **Pre-commit submodule hygiene guard** - COMPLETE. Landed `pre_commit_submodule_guard` (dirty/out-of-sync submodule detection with remediation), integrated Phase A inline and detached worker paths, added unit tests, and archived plan `block-dirty-submodule-references-in-commit-workflow` to `.cortex/plans/archive/Other/`.
- **Harden session telemetry against synthetic data pollution** - COMPLETE. `ContextTelemetryRecordQuality`, synthetic/pytest and invalid zero-budget classification, production-only rollups, exclusion logs, in-process counters, internal-consistency rules, `reconcile_context_usage_statistics_entries` + load-time backfill when `usage_writable`, env-gated debounced POST export of `ContextTelemetryExclusionCountersSnapshot` (optional Authorization header); `docs/architecture/tool-usage-tracking.md`, `docs/guides/troubleshooting.md`; `test_effectiveness_telemetry_quality.py`.
- **MCP docs, README, and CI — single source of truth for published tool surface** - COMPLETE. Canonical inventory module, generated JSON, CI drift tests, README markers, tools.md current vs legacy sections, prompts README cross-link.
- **Convert tests/test_phase5_3_4.py to pytest and guard script-only test files** - COMPLETE. Pytest module for Phase 5.3–5.4; guard for script-only test_*.py; legacy tests converted.
- **Offline / network-restricted verification bootstrap and triage docs** - COMPLETE. Added offline/bootstrap and preflight docs, triage matrix, README and AGENTS cross-links; optional devcontainer deferred per plan.
- **Telemetry — Synapse usage cache policy and context-usage-statistics semantics** - COMPLETE. Documented VC policy, stats JSON semantics, schema_version + tests, contributor checklist.
- **Phase A markdown lint scope and preflight markdown merge** - COMPLETE. `collect_pre_commit_markdown_paths` excludes history and session cache trees from worker rumdl; zero-arg Phase A polling merges markdown lint into `preflight_passed`; unit tests for collection and merge helpers.
- **Narrow broad exception handlers — plans completion I/O and migration** - COMPLETE. Replaced broad except Exception in completion_io and migration with specific exception tuples; added tests for I/O, JSON, validation, and rollback paths.
- **Pytest isolation for MCP circuit breaker (xdist)** - COMPLETE. Reset/prime helpers in `mcp_stability_retry.py`, autouse fixture in `tests/conftest.py`, reconnect test cleanup; fixes `Connection not healthy before tool execution` flakes after circuit-open reconnect tests under parallel pytest.
- **Quality gate CI parity** - PARTIAL. Added `TestRunQualityGateMarkdownMerge` so `run_quality_gate()` under mocked detached worker returns `preflight_passed: false` when `markdown_result` reports errors (Step 4). Remaining: CI/local matrix audit, cSpell parity, file/function script parity verification, docs in tools.md.
- **Phase A markdown coercion and run_quality_gate integration test** - COMPLETE. Hardened markdown error detection for non-numeric files_with_errors strings; added async integration test with mocked poll_for_result; Synapse commit prompt updates; Phase A worker coverage about 91 percent.
- **Quality gate CI parity** - PARTIAL. Added `spelling` to `_PRE_FLIGHT_DEFAULT_CHECKS` and `PHASE_A_CHECKS` (cSpell parity with CI). Documented CI ↔ local matrix and eval gap in `docs/api/tools.md`. Plan remains IN_PROGRESS (Step 1 audit matrix, file-size script parity verification).
- **Quality gate CI parity** - PARTIAL. Extended docs/api/tools.md CI parity section with full blocking-quality matrix, CI-only rows, local-only fix_errors, and .cortex/.cache rumdl exclusion note; file/function governance cross-checked vs CI.
- **Quality gate CI parity** - COMPLETE. Verified parity matrix and preflight/Phase A alignment; typing cleanup in markdown-merge tests; dispatch comment for markdown_lint; run_quality_gate passed.
- **Sanitize pipeline/phase path parameters in pipeline_handoff** - COMPLETE. Allowlist for pipeline/phase plus unit tests; integration tests updated.
- **Fix review prompt to track issues across reviews** - COMPLETE. Review prompt now carries forward OPEN issues, expands scope on telemetry-only diffs, requires concrete suggestions and score deltas, and adds regression checks.
- **Targeted exception narrowing in validation and config paths** - COMPLETE. Narrowed validation_config and container handlers; verified completion_io; added propagation tests.
- **Replace sync file I/O with async in pipeline_handoff** - COMPLETE. Dispatch runs in asyncio.to_thread; tests verify offload.
- **Align docs/index.md with canonical 10-tool inventory** - COMPLETE. Canonical 10/6/4 surface documented; 70+ removed from top-level docs.
- **Clarify file/function size governance: document logical-line counting** - COMPLETE. Docs, CI labels, and constant comments aligned with check_file_sizes/check_function_lengths.
- **Add CI markdown link validation for non-archive docs** - COMPLETE. Internal link checker for docs + policy files, CI step, local preflight via markdown lint merge, unit tests.
- **Markdown link validation — Pyright and test typing** - COMPLETE. Public helper names in `markdown_link_validation.py`, unused-result cleanup, typed `read_text` test double; Phase A typecheck clean for module and `test_check_markdown_links.py`.
- **Tighten tool-count guardrail from MAX=16 to MAX=12** - COMPLETE. MAX_REGISTERED_TOOLS=12, Adding new tools section in tools.md, governance test for cap; plan `tool-budget-tightening` archived to `.cortex/plans/archive/Other/`.
- **Improve submodule preflight resilience and error messaging** - COMPLETE. TTY prompt in check_synapse.sh, bootstrap auto-init, MCP remediation on submodule hygiene block.
- **Rumdl scope parity and submodule MCP remediation (2026-03-21)** - COMPLETE. Excluded `.cortex/.cache/` in CI/Makefile rumdl find; aligned `markdown_lint_core` excludes (history, cache, POSIX rel paths); submodule guard `precommit_block_response` includes `remediation`; archived `submodule-resilience` plan under `.cortex/plans/archive/Other/`; unit tests refreshed.
- **Align bootstrap.sh Synapse readiness check with check_synapse.sh** - COMPLETE. Shared _synapse_lib.sh; bootstrap aligns with check_synapse empty-dir semantics; pytest regression tests.

## 2026-03-16

- **Commit pipeline Phase B re-validation**
  - Re-ran commit pipeline Phase B (docs/state) for the current rules and composite tools batch using Phase A coverage 0.90 from pipeline handoff as context.
  - Confirmed `activeContext.md`, `progress.md`, and `roadmap.md` already reflected the rules-hybrid categorization fix and migration helper directory-creation changes; no new roadmap items or plan archive moves were required.
- **Code review bug fixes**
  - Fixed `_categorize_non_generic_rule` in `rules_hybrid.py` to use mutually exclusive `if/elif` branching so a non-generic rule cannot be classified into multiple buckets (e.g., `language_rules` and `local_rules`) in the same pass, and updated Synapse coding standards with guidance on avoiding overlapping branches.
  - Updated structure migration helpers (`migrate_memory_bank_files_from_source`, `migrate_single_file`, `migrate_plans`) to create destination directories with `mkdir(parents=True, exist_ok=True)` before calling `shutil.copy2`, preventing `FileNotFoundError` when running migrations on a fresh workspace.
  - Ran commit pipeline Phase B (docs/state) for this batch using Phase A coverage 0.90 from pipeline handoff; verified memory bank (`activeContext.md`, `progress.md`, `roadmap.md`) and plans archive are already consistent with these changes.

## 2026-03-15

- **Commit pipeline Phase B**
  - Memory bank verified (activeContext, progress, roadmap); 0 plans archived; documentation validation run.

## 2026-03-14

- **MCP Connection Stability Fix**
  - COMPLETE. Root-caused `ClosedResourceError` crash when concurrent tool calls from parallel subagents raced on shared stdio write stream. Fix: (1) monkeypatched `_handle_request` in `main.py` to catch `ClosedResourceError` on `message.respond()`; (2) removed `log_client` stream writes from `_run_standard_checks_mode`; (3) used cached `get_current_project_root()` to avoid `list_roots` round-trips; (4) made `_dispatch_phase` use detached mode; (5) changed `fix.md` from parallel to sequential subagent execution. Root cause: Cursor kills connection when 3-4 concurrent tool calls pending >10-15s. Sequential execution eliminated all disconnections. All 5102 tests pass.

## 2026-03-13

- **Week containing 2026-03-13** - 1 entries summarized.

## 2026-03-12

- **Week containing 2026-03-12** - 1 entries summarized.

## What Works

Pre-commit pipeline (fix_errors, format, type_check, quality, tests); 3702 tests, 90.36% coverage; integration tests for projectBrief schema; Option C HTTP/SSE transport (Phase 1 and 2). Create-plan and memory-bank-updater mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption.

## What's Left

See roadmap.md.
