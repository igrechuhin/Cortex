# Progress Log

## 2026-03-26

- **Root-Cause-First Debugging Guardrails** - COMPLETE. Added a HARD GATE + mandatory PHASE 0 (Diagnose First) to the fix prompt requiring evidence-backed hypotheses and selection before any edits.
- **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern** - PARTIAL. Added reusable hook templates (`HookTemplates.get_post_edit_hook`) plus `.claude/settings.json` merge/write utilities and unit tests; then applied the Python post-edit hook to this repo’s `.claude/settings.json` and documented the language-agnostic PostToolUse(Edit) pattern in `docs/prompts/migrate.md`. Wiring into migrate/initialize execution remains deferred because setup/migration are prompt-based rather than filesystem-writing tools.
- **Per-Project Post-Edit Quality Hook** - PARTIAL. Wired hook emission instructions into MIGRATE_PROMPT and INITIALIZE_PROMPT in prompts.py (Step 2b / Step 5b with full language→command table). Updated docs/prompts/migrate.md Step 2a to document auto-emitted hook with language table and merge behavior. Added 14 integration tests covering Python, Swift, all other languages, idempotency, and key preservation. Cortex repo .claude/settings.json already had the Python hook. Remaining: integrate with language detection from migrate-language-rules-scripts-scaffolding for fully automated detection.
- **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern** - PARTIAL. Added programmatic hook-language detection helper (`detect_post_edit_hook_language`) backed by `detect_language_at_path()`, and extended `LanguageDetector` to detect Java (Maven/Gradle) after Kotlin. Added unit tests for Java detection + hook-language detection.
- **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern** - PARTIAL. Wired runtime post-edit hook application into initialize/migrate execution paths with shared helper and tests; quality gate fresh run passed (5548/5548 tests, 91.83% coverage). Remaining work is full integration with migrate-language-rules-scripts-scaffolding language routing.
- **Session improvements from 2026-03-26T18-37** - PARTIAL. Hardened analyze target routing: usage-pattern aliases now normalize reliably, and tools/prompts/rules targets route through health-check analysis paths with regression tests; quality gate fresh pass at 91.82% coverage. Remaining: ensure early-session context-loading analysis telemetry is consistently recorded and no_data is prevented when session activity exists.
- **Session improvements from 2026-03-26T18-37** - PARTIAL. Seeded idempotent early-session context telemetry in session_start and added regression tests to prevent false analyze no_data when session activity exists; remaining work is lifecycle integration validation for end-of-session analyze path.
- **Session improvements from 2026-03-26T18-37** - COMPLETE. Added lifecycle regression coverage for end-of-session context analysis across mixed MCP and direct entrypoints; validates calls_analyzed is present when session activity exists.
- **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern** - PARTIAL. Integrated runtime post-edit hook language detection with shared `LanguageDetector`, added TypeScript detection and unsupported-language fallback tests, and validated via quality gate; remaining work is programmatic routing through `LanguageQualityRouter`.
- **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern** - PARTIAL. Added shared `LanguageQualityRouter` and routed post-edit hook command selection through it; added router unit tests and preserved existing pre-commit adapter patch points. Remaining: consume the same router for runtime quality adapter selection to fully unify routing.
- **Per-Project Post-Edit Quality Hook — Language-Agnostic Pattern** - COMPLETE. Unified runtime hook and quality adapter routing through `LanguageQualityRouter`, removed adapter-registry execution indirection, updated boundary/unit tests, and validated with passing quality gate.

## 2026-03-25

- **MCP stability + quality pipeline hardening** - COMPLETE. Strengthened MCP reconnect/timeout flows and tool validation, refined token counting and project-root resolution behavior, improved markdown lint and pre-commit execution internals (inline + detached worker), and updated multiple language framework adapters with expanded unit tests.
- **Detached fix-quality worker and envelope parser tests** - COMPLETE. Added new detached fix worker module and unit coverage in `test_fix_quality_detached.py`, promoted envelope parsing via public `parse_fix_envelope`, and resolved stale legacy cursor path wording in `debug-external-integration.md` so docs path guard tests pass.
- **Lazy setup prompt pyright suppressions, context rollup, Synapse usage cache** - COMPLETE. Placed `# pyright: ignore[reportPrivateUsage]` on the same lines as private `_INITIALIZE_PROMPT`, `_MIGRATE_PROMPT`, and `_POPULATE_TIKTOKEN_CACHE_PROMPT` imports in `lazy_prompt_registration.py`; refreshed `.cortex/.session/context-usage-statistics.json`, memory bank index, and history snapshot; updated Synapse `.cache/usage/events` for 2026-03-24 and 2026-03-25.
- **Startup repair lifecycle recovery** - COMPLETE. Added `cortex.structure.lifecycle.startup_repair.repair_project_setup` for idempotent startup validation/repair of `.cortex/` structure, Cursor symlinks, and Cortex transient markers in `.gitignore` (git repos only); added `tests/unit/test_startup_repair.py`.
- **pytest-randomly, project root cache validation, sorted memory-bank validation globs** - COMPLETE. Added pytest-randomly to dev extras; project root MCP resource revalidates cached JSON; sorted glob iteration in validation helpers, schema, and quality collection.

## 2026-03-24

- **Lazy Synapse prompt registration and roots cache** - COMPLETE. Deferred Synapse prompt and cursor-agent sync until first `list_prompts` with correct MCP roots resolution; per-process `list_roots` cache to prevent stdio corruption under concurrent tools; `notifications/prompts/list_changed` after deferred registration; Synapse prompts modules and `config/status` refactors; unit tests for lazy registration, resolver, cursor-agent sync, and prompts.

## 2026-03-23

- **Pipeline state + quality gate reliability updates** - COMPLETE. Added `pipeline_state` core model and updated zero-arg commit pipeline execution flows (`pipeline_handoff_io`, `pre_commit_zero_arg_tools`, `completion_validation`, `markdown_lint_core`, usage tracking) with corresponding test updates.

## 2026-03-22

- **Session context usage statistics and memory bank index** - COMPLETE. Rolled up context usage statistics; refreshed memory bank index; Synapse usage analytics for 2026-03-22.
- **Clean up legacy Node package manifest** - COMPLETE. Removed unused root `package.json`; documented CI/global `cspell` and Node usage in contributor docs and AGENTS; archived plan `clean-up-legacy-package-json` to `.cortex/plans/archive/`.
- **Decompose oversized tool modules by responsibility boundaries** - COMPLETE. Batches 1–4 done; quality gate and size checks verified; boundary tests cover facades. (Earlier PARTIAL note on architecture guardrails folded into contributing.md policy; remaining splits tracked under roadmap Refactoring.)
- **Project root resolver — roots capability gate** - COMPLETE. Skip `list_roots()` unless the client advertises MCP roots (`ClientCapabilities` / `RootsCapability`); prevents Cursor MCP bridge transport failures; `test_project_root_resolver.py` extended.
- **Decomposed tool module boundary governance** - COMPLETE. Added `tests/unit/test_decomposed_tool_module_boundaries.py` for stable imports and logical-line caps on split tool modules.
- **Fix broad exception handling and subprocess log fd comment** - COMPLETE. Documented exception surfaces, subprocess log fd, central MCP wrappers; REV items resolved; `cortex.tools` package initializer side effects inventoried for follow-up.
- **Reconstruct roadmap backlog and enforce docs-gate consistency invariant** - COMPLETE. Docs-gate PARTIAL/PENDING invariant, progress/roadmap reconciliation, refactoring backlog entry for remaining module splits.
- **Add offline mode and preflight network/test failure differentiation for bootstrap** - COMPLETE. Preflight CLI/`make preflight`; `make bootstrap-offline` with `WHEELHOUSE`; contributing.md offline/restricted-network section; path-gated `bootstrap-offline.yml` (Docker `--network none`, preflight exit 2); regression tests; quality gate passed; plan archived.
- **Resolve contributor documentation drift and conflicting quality workflow instructions** - COMPLETE. Contributing guide, repo Markdown, and regression tests aligned with .cortex/memory-bank and MCP-first quality workflow.
- **Decompose oversized tool modules (remainder)** - COMPLETE. Verified file/function size checks and quality gate; no remaining violations; archived plan work done.
- **Remove permanently skipped legacy tests and establish skip expiration policy** - COMPLETE. Legacy skip-only modules removed; `skip_reference_policy` enforces ref/issue/see on `@pytest.mark.skip` and AST-scans runtime `pytest.skip`; inventory `docs/development/test-skip-inventory.md`; `skipped_tests` and skip-count trend in quality pipeline; plan archived.
- **Python framework adapter parsing** - COMPLETE. Hardened `python_adapter_parsing.py` and base adapter integration; `pre_commit_pipeline_processors` aligned with skip summary reporting; unit tests refreshed in `test_python_adapter.py` and `test_python_adapter_parsing.py`.
- **Narrow broad exception handling in PythonAdapter test execution** - COMPLETE. Narrowed catches in streaming and non-streaming test paths; debug log for cache OSError; six tests added.
- **Test and harden parse_type_errors in python_adapter_parsing** - COMPLETE. Regex-based parse_type_errors; TestParseTypeErrors in test_python_adapter_parsing.py.
- **Add URL scheme validation to preflight registry probe** - COMPLETE. UV_INDEX_URL must use https or http scheme; ValueError and preflight main exit 2; tests in test_preflight.py.
- **Document offline bootstrap and preflight CLI architecture** - COMPLETE. docs/offline-bootstrap-preflight.md plus cross-links in security best practices and README.
- **Narrow exceptions in python_adapter_checks** - COMPLETE. Pyright timeout parity, TimeoutExpired branch, ruff command timeouts with `test_timeout_returns_lint_error`, tests in `test_python_adapter_checks.py`; review-report markdown preflight fixes.
- **Pipeline handoff + usage analytics decomposition** - COMPLETE. Split `pipeline_handoff` into `pipeline_handoff_io` and `pipeline_handoff_validation`; split usage analytics into `analytics_collection` and `usage_analytics_resources` with thin facades; `test_analytics_collection`, `test_python_adapter_checks`, `test_phase_a_lock`; boundary governance and pre-commit zero-arg wiring updated; Phase A ~0.916 coverage.
- **Decompose oversized tool modules (prompts, markdown cache, pre-commit process, effectiveness)** - COMPLETE. Split Synapse prompts into `prompts_content`, `prompts_paths`, `prompts_registration`, and `prompts_agents` with a thin `prompts.py` facade; moved markdown lint cache updates and `after_one_file` to `markdown_lint_cache_updates.py`; moved detached spawn/poll/result I/O to `pre_commit_process.py`; moved `build_statistics_dict` into `effectiveness_operations_insights.py`; updated prompt, markdown lint, cursor-agent sync, and boundary tests. Remainder plan archived under `.cortex/plans/archive/Other/`.
- **Add narrative doc for preflight HEAD→GET fallback and http:// allowance** - COMPLETE. Documented HEAD→GET 405 fallback and intentional http:// for internal mirrors in docs/offline-bootstrap-preflight.md.
- **Profile and verify performance of context loading and preflight hot paths** - COMPLETE. Documented performance baselines with measured samples and links from productContext and tool-usage-tracking; context/tiktoken paths remain guarded by unit perf tests.
- **Perf regression tests — pyright reportUnusedCallResult** - COMPLETE. Warmup `load_context_impl` and `count_tokens_with_cache` calls assign `_ =` for intentional discard; Phase A used `run_quality_gate_fresh` when cached typecheck lagged the working tree.
- **Synapse prompts path and usage analytics hardening** - COMPLETE. Synapse prompts path resolution, narrowed I/O exceptions, usage date-range docstring, session/index rollup and Synapse usage events for 2026-03-22.

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
- **Phase A markdown coercion and run_quality_gate integration test** - COMPLETE. Hardened markdown error detection for non-numeric files_with_errors strings; added async integration test with mocked poll_for_result; Synapse commit prompt updates; Phase A worker coverage about 91 percent.
- **Quality gate CI parity** - COMPLETE. Verified parity matrix and preflight/Phase A alignment; typing cleanup in markdown-merge tests; dispatch comment for markdown_lint; run_quality_gate passed. (Intermediate PARTIAL checkpoints on markdown merge, spelling in Phase A, and docs matrix were superseded by this completion.)
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
- **Narrow broad exception handlers in markdown lint core** - COMPLETE. Narrowed subprocess/I/O and cache exceptions; added tests for OSError handling, TypeError/RuntimeError propagation, and FileLockTimeoutError logging.
- **Handle subprocess.TimeoutExpired in pre_commit_submodule_guard** - COMPLETE. Wrapped submodule status and porcelain git calls with TimeoutExpired handling; warn and fail-soft; tests cover both paths.
- **Remove redundant asserts in plan tool** - COMPLETE. Removed redundant asserts after guard returns in plan dispatch helpers.
- **Automate dependency parity between pyproject.toml and requirements.txt** - COMPLETE. Validation script, tests, CI, Makefile target, and docs.
- **Deduplicate _session_dir helper across pre-commit modules** - COMPLETE. Shared session_dir in session_paths.py; both pre-commit modules consume it; unit test for path creation.
- **Decompose oversized tool modules** - Note (2026-03-21). Split `models_reexports` into `models_reexports_workflows.py` and `models_reexports_system.py` with thin aggregator + static `__all__`; added `pyproject.toml` per-file Ruff F405 ignore for the aggregator. Later 2026-03-22 batches completed related decomposition work; treat this line as historical context only.
- **MCP TaskGroup -32000 connection classification** - COMPLETE. `main._handle_broken_resource_in_group` treats nested MCP connection RuntimeErrors consistently; circuit-breaker test resets; `test_mcp_crash_fixes.py` coverage.
- **Decompose oversized tool modules** - Note (2026-03-21). Split pre_commit_tools into inline_execution + execute_checks modules; tests updated for patch targets; full pytest -n0 green. Superseded by subsequent decomposition COMPLETE entries on 2026-03-22.
- **Decompose oversized tool modules by responsibility boundaries** - Note (2026-03-21). Split `similarity_engine.py` into `similarity_core.py` (content/section metrics), `similarity_stop_words.py`, and a slimmer `SimilarityEngine` (semantic/functional); public API unchanged; quality gate green. Follow-up completion recorded under 2026-03-22 COMPLETE entries.

## 2026-03-16

- **Week containing 2026-03-16** - 1 entries summarized.

## 2026-03-15

- **Week containing 2026-03-15** - 1 entries summarized.

## 2026-03-14

- **Week containing 2026-03-14** - 1 entries summarized.

## 2026-03-13

- **Week containing 2026-03-13** - 1 entries summarized.

## 2026-03-12

- **Week containing 2026-03-12** - 1 entries summarized.

## What Works

Pre-commit pipeline (fix_errors, format, type_check, quality, tests); 3702 tests, 90.36% coverage; integration tests for projectBrief schema; Option C HTTP/SSE transport (Phase 1 and 2). Create-plan and memory-bank-updater mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption.

## What's Left

See roadmap.md.
