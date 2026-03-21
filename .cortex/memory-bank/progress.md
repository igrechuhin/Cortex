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
- **Harden session telemetry against synthetic data pollution** - PARTIAL. `ContextTelemetryRecordQuality`, synthetic/pytest and invalid zero-budget classification, production-only rollups, exclusion logs, in-process counters, internal-consistency invalid rules (tokens vs files, relevance without files), `reconcile_context_usage_statistics_entries` + load-time backfill when usage_writable, tests including legacy JSON. Remaining: optional external metrics export; operator note when usage_writable is false (reconcile in memory only).

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
