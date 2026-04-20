# Progress Log

## 2026-04-19

- <!-- memory_type: status -->
- <!-- memory_type: status -->
- <!-- memory_type: status -->
**SwiftAdapter MLX-disable-metal default for captured swift test** - COMPLETE. Child env merge in SwiftAdapter._run_swift, _swift_test_env helper, Makefile/README/AGENTS/testing.md alignment, swift_adapter unit tests, Cortex session index/history/log refresh.
**/cortex/commit — fix prompt integrity + fix-coverage agent contracts** - COMPLETE. Strengthened tests/integration/test_commit_workflow_integrity_guards.py for fix.md coverage short-circuit and fix-coverage three-iteration discipline; Synapse submodule carries aligned prompts/fix.md.
**Fix pipeline validation + Synapse /fix MCP availability** - COMPLETE. Hardened pipeline/phase token allowlists for the fix workflow, aligned Synapse fix.md with session()-first MCP probing, and ran /cortex/commit compound updates with green quality and docs gates.

## 2026-04-18

- <!-- memory_type: milestone -->
- <!-- memory_type: status -->
- MCP stability timeout tests: extracted helpers to tests/unit/mcp_stability_timeouts_helpers.py; refactored test_mcp_stability_timeouts for function-length and file-size gates; aligned semaphore wait test with 600s default.
- <!-- memory_type: status -->
**/cortex/commit — Synapse fix-coverage + commit integrity slice** - COMPLETE. Green Phase A quality gate and parity scripts; wiki staged ingest for docs/guides; memory bank compound updates; submodule f90ea86 with fix-coverage agent; integration test and workflow/report template doc edits staged with temporal.db.
**Commit pipeline: quality gate poll timeout + Synapse typecheck** - COMPLETE. Raised default Phase A test_timeout to 600s in pre_commit_zero_arg_tools.py, fixed Synapse swift_test_runner.py implicit string concatenation for pyright, committed Synapse prompt/agent alignment (fix.md, fix-tests.md), and obtained green run_quality_gate with parity scripts.

## 2026-04-17

- <!-- memory_type: status -->
- **Fix prompt integrity and commit pipeline validation** - COMPLETE. Restored exact coverage-only BLOCKED wording and markdown list spacing in Synapse fix prompts, then ran commit pipeline gates to green with synced submodule pointer.
- **Add Local Environment Context Memory Artifact** - COMPLETE. Delivered canonical local-environment context artifact lifecycle with startup validation, rebind guidance, and dedicated tests; review gate confirmed no remaining gaps.
- <!-- memory_type: status -->
- **Commit pipeline run for Synapse fix prompt updates** - COMPLETE. Executed full /cortex/commit flow with green quality parity checks, docs/validation gates, and staged Synapse gitlink update for the superproject commit.
- <!-- memory_type: status -->
**Swift framework adapter coverage + Synapse fix path** - COMPLETE. Extended Swift coverage parsing and adapter wiring in `swift_adapter.py`/`swift_coverage.py` with shared base helpers, refreshed Cortex session telemetry (`index.json`, history slices, `log.md`), and bumped Synapse submodule for aligned `fix.md` / `fix-tests.md` guidance.
**Add Local Environment Context Memory Artifact** - PARTIAL. Implemented canonical local environment artifact plus startup housekeeping/validation and prompt integration; review reopened plan for follow-up test-depth and remediation/API consistency gaps.

## 2026-04-16

- <!-- memory_type: status -->
- **Commit pipeline guard and handoff hardening** - COMPLETE. Tightened pre-commit submodule/staged-file guardrails, expanded pipeline handoff config/path validation, hardened memory-bank update validation, and added regression coverage for commit integrity and staged gitignored protection.
- <!-- memory_type: status -->
- **Commit pipeline run for plan workflow updates** - COMPLETE. Ran /cortex/commit preflight, Phase A quality gate + mandatory parity scripts, wiki staged ingest bridge, and progressed docs/validation/final-gate execution for current staged changes.
- <!-- memory_type: status -->
- **Harden /fix Workflow for Coverage-Only Failures** - COMPLETE. Aligned shared workflow/report guidance with the coverage-only evidence-or-BLOCKED contract and added regression tests that keep the docs synchronized with prompt behavior.
- <!-- memory_type: milestone -->
- **Commit pipeline parity fix for wiki-source markdown** - COMPLETE. Fixed the local `check-ci-parity` markdown mismatch in `Makefile` so `.cortex/wiki/sources/` no longer produce false MD057 failures; Phase A quality gate and parity shell checks now pass.
- **Enforce Post-Implementation Review Loop in /do Pipeline** - COMPLETE. Added a mandatory internal Review Gate to /cortex/do, wired reopened-plan behavior, and covered the prompt/runtime contract with regression tests.
- **BELIEF Annotation Enforcement — Emit Guidance and Mid-Function Heuristics** - COMPLETE. Added concrete BELIEF triggers to the shared annotation rule, taught the implement-code agent to emit BELIEF annotations before external-state-shape assumptions, and extended Python reflection heuristics plus tests to suggest BELIEF annotations for risky dict-key and chained-attribute access.
- <!-- memory_type: status -->
- **Commit pipeline run for BELIEF annotation enforcement** - COMPLETE. Ran /cortex/commit for the BELIEF annotation guidance and reflection-heuristic slice with preflight, green quality/parity checks, wiki staged ingest, and docs/validation follow-through.
- **Fix-Loop Exhaustion — Root-Cause Reframe Output** - COMPLETE. Added the post-exhaustion analysis block to `fix.md`, `fix-tests.md`, and `fix-quality.md`, requiring a root-cause hypothesis, a reformulated brief, and the explicit `Do NOT retry in this session.` directive.
- Swift coverage exclusions: optional swift_coverage.json drives SwiftAdapter and swift_coverage helpers.
**Harden /fix Workflow for Coverage-Only Failures** - PARTIAL. Added explicit coverage-only failure evidence contract to /fix and fix-tests prompts (`coverage_only_failure`, `coverage_attempt_evidence`, `coverage_attempt_count`, `coverage_delta`, `blocker_reason`) and added regression integration tests to enforce contract presence.

## 2026-04-15

- **Commit pipeline — Swift coverage threshold parity + Synapse cursor-agents** - COMPLETE. Committed `swift_adapter.py` enhancements, new `swift_coverage.py` numeric-coverage extraction module, `test_swift_adapter.py` and `test_swift_coverage.py` test updates, archived plan, and Synapse cursor-agents/commit prompt files; Phase A quality+parity checks passed.
- **Improvement: Memory Write-Ahead Log for Audit Trail and Rollback** - COMPLETE. Added WAL logging/snapshot tooling, integrated WAL hooks into memory mutations, added update_memory_bank WAL integration tests, and refactored touched modules to satisfy structural limits.
- **Improvement: Typed Memory Classification for Memory Bank Entries** - COMPLETE. Fixed memory_types circular import; classification stack verified with unit tests.
- <!-- memory_type: status -->
- **Improvement: Hybrid BM25 + Keyword Retrieval for Memory Bank Search** - COMPLETE. Implemented BM25 retrieval modules, manage_file search integration, and full retrieval/tool test coverage; L3 deep-search wire-in explicitly deferred because target module is absent.
- <!-- memory_type: status -->
- <!-- memory_type: milestone -->
- **WAL and quality-gate fallback repair** - COMPLETE. Resolved submodule hygiene blocker by syncing/staging `.cortex/synapse`, fixed fallback behavior in synapse `check_file_sizes` scripts, reduced overlong WAL tests, and re-ran quality/docs gates successfully.
- **Enforce Swift Coverage Threshold Parity** - COMPLETE. Implemented Swift numeric coverage extraction and enforced existing threshold behavior with regression tests and prompt/docs alignment.
- <!-- memory_type: status -->
- **Commit pipeline run for Swift coverage parity updates** - COMPLETE. Executed /cortex/commit preflight, quality+parity checks, wiki staged ingest, docs/validation, and staged Synapse gitlink changes for final commit.
✅ Commit pipeline validation complete — Phase A quality+parity checks passed for retrieval and file-tool changes; docs/validation gates aligned before commit creation.
**Quality follow-up** - COMPLETE. Split `_generate_orphaned_files_insight` in `insight_dep_quality.py` to satisfy the 30-line function cap (structural gate); behavior unchanged.

## 2026-04-14

- **Remove offline setup/bootstrap support** - COMPLETE. Removed `preflight-offline` and `bootstrap-offline` targets plus related onboarding/docs guidance; offline setup flows are now intentionally out of scope unless explicitly requested again.
- **FastMCP v3 — Phase 2: Replace Internal Handler Patches with Official APIs** - PARTIAL. Removed direct `mcp._mcp_server.*` access from `server.py`, moved roots change-notification wiring into startup path in `main.py`, and added startup regression tests while keeping the remaining disconnect shim decision for follow-up.
- **FastMCP v3 — Phase 2: Replace Internal Handler Patches with Official APIs** - PARTIAL. Evaluated `_patch_mcp_server_handle_request` disconnect handling and intentionally deferred removal to Phase 3; added regression tests covering unpatched vs patched `ClosedResourceError` behavior and validated no residual patch-related `type: ignore` in `server.py`.
- **FastMCP v3 — Phase 2: Replace Internal Handler Patches with Official APIs** - COMPLETE. Removed server-level private patching for prompt/roots flows and documented intentional defer of disconnect wrapper removal to Phase 3 middleware replacement.
- **FastMCP v3 — Phase 3: Middleware for Disconnect Handling and Request Logging** - COMPLETE. Replaced private `_handle_request` monkey patch with registered middleware for disconnect handling, debug logging, and response limiting; added optimization config key and middleware test coverage.
- **FastMCP v3 — Phase 4: Transport Configuration Cleanup** - COMPLETE. Transport run kwargs now pass explicit host/port, legacy FASTMCP host/port forwarding is removed, and streamable-http is the default for port-based mode with tests/docs aligned.
- **FastMCP v3 — Phase 5: New Features (Lifespan, Visibility, Auth, Transforms)** - COMPLETE. Added FastMCP v3 lifespan startup injection, dynamic setup-prompt visibility toggling, per-component auth enforcement for write tools, tool-compat resource/prompt transforms behind config flags, and dev hot-reload workflow with tests/docs updates.
- **Fix: Stale Test-Count Metric in progress.md What Works Section** - PARTIAL. Updated What Works metrics, added StaleNumericClaimCheck with tests/docs integration, but global quality/docs gates remain red due unrelated pre-existing issues.
- **Refactor: Split Oversized `src/cortex/tools/session/brief.py` and `src/cortex/tools/optimization/handlers.py`** - PARTIAL. Extracted `brief_cap`, `brief_loaders`, `context_appenders`, and `context_loaders` with compatibility shims preserved; quality gate remains blocked by structural debt (`memory_bank_lint_checks.py` > 400 lines) and one remaining oversized helper in `brief.py`.
- **Fix: Stale Test-Count Metric in progress.md What Works Section** - COMPLETE. Updated stale What Works metrics and added StaleNumericClaimCheck protection.
- **Refactor: Split Oversized `src/cortex/tools/session/brief.py` and `src/cortex/tools/optimization/handlers.py`** - COMPLETE. Verified split module sizes/imports and passed full quality gate.
- **Improvement: Layered Context Budget L0-L3 Tiering** - COMPLETE. Implemented L0/L1/L2/L3 context layering builders, wired layered context responses, and added targeted layer/resource tests.
- **Layered context budget (L0-L3)** - COMPLETE. Added layered context modules and integration wiring in optimization/session config paths; plan moved to archive path and tests/resources context layer coverage added.
- **Temporal store slice for Improvement: Temporal Memory with Validity Windows** - COMPLETE. Implemented the temporal SQLite store (`TemporalFact`, deterministic IDs, add/invalidate/query/current methods) and added focused unit tests for initialization, validity-window queries, invalidation, and idempotent inserts.
- **Improvement: Temporal Memory with Validity Windows** - PARTIAL. Added temporal indexing (`TemporalIndexer`), contradiction detection warnings, timeline query models/handler, `manage_file` timeline/invalidation operations, and session-start background indexing with dedicated indexer/timeline tests.
- **Improvement: Temporal Memory with Validity Windows** - COMPLETE. Implemented temporal fact storage, indexing, timeline retrieval, and session integration with tests.
- <!-- memory_type: status -->
- **Improvement: Typed Memory Classification for Memory Bank Entries** - COMPLETE. Implemented typed memory classification/reader paths and associated tests; stabilized quality-gate flow with scoped Phase-A locking and helper extraction updates.

## 2026-04-13

- **Commit + fix pipeline run** - COMPLETE. Executed `/cortex/fix` (quality/tests/docs all green), then `/cortex/commit` pipeline preflight and Phase A parity checks; committed `.cortex/synapse` prompt updates and prepared superproject commit artifacts.
- **migrate-check-function-lengths-callers** - COMPLETE. Migrated direct callers to router path, replaced legacy function with compatibility shim, and validated parity behavior.
- **BLOCKER: Fix mcp>=1.26.0 Structured-Output Crash on Startup** - COMPLETE. Prevented structured-output startup crash by setting structured_output=False in typed tool registration and added startup import regression coverage.
- **FastMCP v3 — Phase 1: Dependency Swap and Import Migration** - COMPLETE. Added `fastmcp>=3.0,<4`; migrated all FastMCP/Context imports to `fastmcp`; fixed mount_path→path for SSE transport; fixed _log_with_compat bound-method signature check; fixed registered_prompt_names to use _local_provider._components directly; 6505 tests pass, pyright clean, all three transports smoke-tested.
- **requirements.txt fastmcp parity (CI)** - COMPLETE. Added `fastmcp>=3.0,<4` to root `requirements.txt` to match `pyproject.toml` runtime deps; fixes `scripts/check_dep_parity.py` / quality workflow failure on fork CI.
- **FastMCP v3 — Phase 1: Dependency Swap and Import Migration** - COMPLETE. fastmcp 3.x pinned; FastMCP/Context imports from fastmcp; tests and gates green.

## 2026-04-12

- **Project Wiki for Attached Projects (.cortex/wiki/)** - PARTIAL. Step 4: MCP `ingest` routes raw snapshots to `.cortex/wiki/sources/` when the wiki exists, writes an auto summary page (category from tags, default concepts), updates `index.md`, and `read_recent_ingested_sources_markdown` prefers wiki sources for cortex://context.
- **Project Wiki for Attached Projects (.cortex/wiki/)** - PARTIAL. Step 5: added Synapse `/cortex/query` prompt (`query.md`), manifest entry, query icon in `prompts_content.py`, and unit test for prompt registration.
- **Project Wiki for Attached Projects (.cortex/wiki/)** - PARTIAL. Step 6: `manage_file(file_artifact)` for `review_report` and `session_analysis` now mirrors into `.cortex/wiki/analyses/` with schema frontmatter and `index.md` catalog rows when the wiki tree exists.
- **Project Wiki for Attached Projects (.cortex/wiki/)** - PARTIAL. Step 8: seeded Cortex self-hosted wiki with 12 ingest-derived pages (README, AGENTS, CLAUDE, core docs/ADRs); `index.md` catalog updated. Step 6 commit prompt wiring landed in Synapse `commit.md`; ingest idempotency remains in `wiki-auto-ingest-git-hooks.md`.
- **Auto-Ingest from Git Hooks (Wiki Auto-Update)** - PARTIAL. Implemented default auto-ingest glob patterns, optional schema frontmatter override, `wiki_ingest_staged_docs` calling synchronous ingest for matched staged paths, unit tests, and Synapse commit prompt wiring for Phase A→B ingest + `git add`. Step 4 partial: stable-path idempotent ingest (skip unchanged, versioned raw, summary upsert + `## Revision`). Remaining: deeper diff/revision semantics and broader verification.
- **Project Wiki for Attached Projects (.cortex/wiki/)** - PARTIAL. Step 6 commit slice: Synapse commit prompt now runs wiki staged ingest (`wiki_ingest_staged_docs` + `git add` wiki paths) after Phase A and before Phase B; plans partial logs updated.
- **Project Wiki for Attached Projects (.cortex/wiki/)** - PARTIAL. Idempotent wiki staged ingest: stable path slug, skip unchanged content, versioned raw snapshots, summary upsert with revision history.
- **Project Wiki for Attached Projects (.cortex/wiki/)** - PARTIAL. Completed Step 3 conditional `/cortex/init-wiki` MCP prompt registration: `wiki_has_content` / `wiki_scaffold_present`, skip `init-wiki.md` in manifest bulk load, register `init_wiki` lazily after startup repair when wiki scaffold exists and summary categories have no `.md` pages.
- **Project Wiki for Attached Projects (.cortex/wiki/)** - COMPLETE. Wiki KB end-to-end: ingest, ask, lint, commit-time staged ingest, review/analyze filing to wiki/analyses; prompts aligned for dual-path artifact reporting.
- **Auto-Ingest from Git Hooks (Wiki Auto-Update)** - COMPLETE. Commit pipeline runs wiki_ingest_staged_docs after Phase A; patterns from schema; idempotent ingest with archived raw snapshots and revision notes; tests cover staged_ingest edge and error paths.
- **Fast-Forward vs. Step-by-Step Planning Modes** - PARTIAL. Step 1 complete: `PlanningMode`, `PlanSectionStatus`, and `PlanSection` models in `cortex.core.models` with unit tests.
- **Fast-Forward vs. Step-by-Step Planning Modes** - PARTIAL. Implemented step draft file format, plan(create) planning_mode=step, continue_step/approve_step/finalize_step operations, and tests; prompt/draft-list/session polish (plan steps 6–7) still open.
- **Fast-Forward vs. Step-by-Step Planning Modes** - PARTIAL. Step 6: `/cortex/plan` prompt documents `planning_mode` ff/step and resume flow. Step 7: `manage_file` `list_drafts` / `discard_draft` and stale-draft hints in `session()` suggestions. Step 8: unit tests for drafts + session suggestion + parse.
- **Fast-Forward vs. Step-by-Step Planning Modes** - COMPLETE. Planning modes shipped with tests, manage_file draft ops, session hints, and log heading uniqueness for MD024.
- **Type Policy Hardening: Remove Any from Production Code** - COMPLETE. Typed PreCommitRunSummary, ModelDict returns, Ruff ANN401 guard.
- **Deprecation Completion: Legacy Quality Entrypoints Migration** - COMPLETE. Preflight uses the detached Phase A runner aligned with `run_quality_gate`; E2E flows use `run_quality_gate`; offline-bootstrap workflow and dedicated deprecation plan files removed; Synapse agent prompts prefer zero-arg `autofix()` over deprecated pre-commit tool names.
- **README Tool Inventory Parity Fix** - COMPLETE. README Key Tools table + AGENTS 12-tool parity; tests/docs/test_tool_inventory_parity.py; uv-build in dev deps; test refactors for governance.
- **Network-Resilience Onboarding** - COMPLETE. Offline preflight, Makefile, README, CI workflow, tests.
- **Quality tooling** - Committed legacy quality MCP compat, offline preflight/bootstrap, deprecation plans, split pre-commit phase tests, roadmap sync wording, and wiki sources for README/tools docs.
- **Phase: Investigate run_composite_workflow MCP Tool Failure** - COMPLETE. Detached worker result JSON must be an object; non-object payloads return error envelope instead of AttributeError during poll. Added tests; removed unused composite helper.
- **Chore: legacy quality + offline-bootstrap cleanup** - COMPLETE. Preflight and docs point agents at autofix/run_quality_gate; offline bootstrap workflow removed; plans and tests updated; Synapse agent prompt sync.

## 2026-04-11

- **Week containing 2026-04-11** - 26 entries summarized.

## 2026-04-10

- **Week containing 2026-04-10** - 1 entries summarized.

## 2026-04-09

- **Week containing 2026-04-09** - 14 entries summarized.

## 2026-04-08

- **Week containing 2026-04-08** - 26 entries summarized.

## 2026-04-07

- **Week containing 2026-04-07** - 26 entries summarized.

## 2026-04-06

- **Week containing 2026-04-06** - 7 entries summarized.

## 2026-04-04

- **Week containing 2026-04-04** - 1 entries summarized.

## 2026-04-03

- **Week containing 2026-04-03** - 9 entries summarized.

## 2026-04-02

- **Week containing 2026-04-02** - 12 entries summarized.

## 2026-04-01

- **Week containing 2026-04-01** - 8 entries summarized.

## 2026-03-31

- **Week containing 2026-03-31** - 3 entries summarized.

## 2026-03-30

- **Week containing 2026-03-30** - 9 entries summarized.

## 2026-03-29

- **Week containing 2026-03-29** - 27 entries summarized.

## 2026-03-28

- **Week containing 2026-03-28** - 4 entries summarized.

## What Works

Pre-commit pipeline (fix_errors, format, type_check, quality, tests); 6495 tests, 91.14% coverage (as of 2026-04-14); integration tests for projectBrief schema; Option C HTTP/SSE transport (Phase 1 and 2). Plan prompt and memory-bank-updater mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption.

## What's Left

See roadmap.md.
