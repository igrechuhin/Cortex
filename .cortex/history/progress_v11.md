# Progress Log

## 2026-07-22

- **Session Runtime Token-Spend Guard** - COMPLETE. Added runtime tool-output token-spend tracking to session() (SessionSpendStatus/SessionSpendSummary, determine_spend_status(), SessionLog.cumulative_spend_tokens/record_spend_tokens(), instrumented at manage_file and session-start call sites, add_spend_suggestions() warning surfacing) — warn-only, additive telemetry distinct from the existing static token_budget_status. 19 new tests, quality gate green (91.09% coverage).

## 2026-07-21

- **Fix silent progress.md append failure in plan complete op** - COMPLETE. Propagated execute_append_progress failures into CompletePlanResult (status/error/message) and narrowed validate_progress_entry_text's parenthesis check to unclosed-paren counting so balanced title parens no longer false-positive; 2 new regression tests, full quality gate green (0 errors, 7219 tests passing, 91.08% coverage).
- **Fix validate CONCISE response hardcoding error_count/warning_count to 0** - COMPLETE. format_validate_response now computes real per-check-type error/warning counts instead of always returning 0; roadmap_sync summary gained unlinked_plans_count and build_roadmap_sync_summary now surfaces it.
- <!-- memory_type: milestone -->
- **Investigate pipeline_handoff phase data loss between phase writes in a single session** - COMPLETE. Fixed via locked+atomic pipeline.json writes, UTC-aware clock, and on-disk session-id persistence across MCP process restarts; 46 regression tests added, quality gate green.
**Investigate pipeline_handoff phase data loss between phase writes in a single session** - PARTIAL. Root-caused and fixed one concrete non-idempotency bug: `op_init` (src/cortex/tools/session/pipeline_handoff_io.py) unconditionally rebuilt `phases={}` and `started_at` on every init call, even against a live non-stale manifest, silently discarding already-written phases. Fixed to merge into existing state via `load_or_create_state` when not stale; stale/missing state still resets. Added 3 regression tests (tests/tools/test_pipeline_handoff_extended.py) proving pre-fix failure and post-fix pass; full quality gate green (7234 tests, 91.09% coverage). Plan reopened (not completed) because the broader symptom reproduced live in this same session via a different, not-yet-root-caused path: ~15 minutes after a correct read showing both `select`+`code` phases, a subsequent write (from the implement-code subagent's own direct pipeline_handoff call) showed only `code`, with `started_at` jumped forward — well under the 4h stale-TTL window, so a second defect remains. Leads recorded in the plan's Review Follow-Up Gaps: non-atomic `pipeline.json` writes (no file locking, unlike the atomic per-phase result files) and naive local-time timestamps colliding with the 2026-07-20 pipeline-resume frontier feature's TTL-based abandon sweep.

## 2026-07-20

- **Fix roadmap_sync reference regex for .json paths** - COMPLETE. Extension alternation includes json (longest-first with negative lookahead); .json roadmap references parse correctly; 6 regression tests added; quality gate green.
- **Pipeline Resume as a Frontier Query** - COMPLETE. Frontier-query resume for interrupted pipelines: experience-store queries (frontier, incomplete_runs, mark_abandoned_runs), enforced node lifecycle, pipeline_handoff resume operation with ResumePlan, TTL staleness policy, session() incomplete_pipelines wiring, crash-simulation tests at every phase boundary.
- **Vector-Seeded Experience Recall in Session Start** - COMPLETE. Task-description embeddings (deterministic local HashingEncoder) alongside BM25; SQLite task_embeddings index with cosine top-k; recall_similar_tasks hybrid-reranks and walks node graph for best-fitness/dead-end outcomes; session() surfaces a budget-capped recall block, byte-identical when disabled. 56 tests, 100% new-module coverage, gate green.
- **Investigate pipeline_handoff phase-state loss during long-running subagent calls** - COMPLETE. Root cause: get_session_id() cached the session id only in os.environ, which does not survive an MCP server process restart. Fixed by adding a durable on-disk session-id marker (new module pipeline_handoff_session.py); 3 regression tests added and verified against pre-fix code.
- <!-- memory_type: status -->
- **Rewire /cortex/analyze from Transcript Scraping to Experience Queries** - COMPLETE. Closed the 3 remaining Review Follow-Up Gaps: pipeline_handoff analytics operations (preference_pairs/repeated_failures/fitness_by_task_type/write_failure_evals) with coverage-check/transcript-fallback wiring into analyze-session; evidence-linked failure_based_evals.json writer from preference_pairs(); Evidence: node-pair citations in analyze-session/analyze-compact recommendations and rule writing. Quality gate green; 23 new tests; touched-module coverage 94-100%.
- <!-- memory_type: milestone -->
- **Rewire /cortex/analyze from Transcript Scraping to Experience Queries** - COMPLETE. Closed all 3 Review Follow-Up Gaps on plan `analyze-experience-graph-queries`: evidence-linked `failure_based_evals.json` writes (`failure_evals.py::preference_pairs_to_eval_tasks`/`upsert_eval_tasks`, idempotent id-keyed upsert), coverage-checked `pipeline_handoff` MCP operations (`preference_pairs`/`repeated_failures`/`fitness_by_task_type`/`write_failure_evals` in `pipeline_handoff_analytics.py`), and `Evidence: node <id> (parent <parent_id>)` citations wired into analyze-session/analyze-compact prompts. 46 targeted tests pass, 98-100% coverage on new modules, `run_quality_gate()` green (0 errors/0 warnings). Plan file frontmatter set to `status: DONE`; note: this plan was found already physically archived at `.cortex/plans/archive/Other/` from a prior session but with no matching roadmap.md bullet, so `plan(operation="complete")` could not run its normal roadmap-removal path — activeContext/progress recorded manually instead.
- **Rewire /cortex/analyze from Transcript Scraping to Experience Queries** - PARTIAL. Implemented the experience-graph analytics query foundation: pure `preference_pairs`/`repeated_failures`/`fitness_by_task_type` functions and Pydantic result models (`src/cortex/experience/analytics.py`, `analytics_models.py`), wired into `ExperienceStoreCore`/`ExperienceStore`, and extended `EvalTask` with a backward-compatible `EvidenceLink`/`evidence` field. 21 new tests, 100% coverage on new modules, quality gate green. Remaining: MCP tool exposure + analyze-session coverage-check wiring (step 3), evidence-linked `failure_based_evals.json` writer (step 4), Synapse rule citation (step 5) — tracked as Review Follow-Up Gaps in the plan.
- <!-- memory_type: status -->
- **Synapse Rule Provenance from Experience Pairs** - COMPLETE. Added rule_provenance table + read/write API linking Synapse rule ids to evidence node pairs; wired evidence citation and staleness/pruning reporting into analyze-session.md/analyze-compact.md (Claude + Cursor mirrors). 46 new tests, 100% coverage on new modules, quality gate green.
- <!-- memory_type: milestone -->
**Fix plan graph archive-blindness masking satisfied dependencies** - COMPLETE. plan(operation="graph") and roadmap_plan_graph_annotate.py now call the artifact graph with include_archive=True unconditionally, so archived-but-DONE dependency plans are correctly visible and satisfy dependent plans instead of permanently reporting them BLOCKED. Archived-but-not-DONE dependencies still correctly block. Added 4 regression tests. Quality gate green: 7217 tests passing, 91.08% coverage.
Synapse Rule Provenance from Experience Pairs - COMPLETE. Implemented all 8 plan steps: `rule_provenance` table (schema v2, PRIMARY KEY (rule_id, pair_id) for idempotent re-citation) in `experience.db`; pure aggregation/staleness logic (`rule_provenance.py`: `group_provenance`, `pruning_candidates` with strict-boundary window semantics, `failure_classes_from_pairs`); SQL layer (`rule_provenance_queries.py`); `ExperienceStoreCore`/`ExperienceStore` methods (`record_rule_provenance`, `refresh_rule_matches`, `list_rule_provenance`, `rule_evidence`, `pruning_candidates`); 4 new `pipeline_handoff` MCP operations dispatched via `pipeline_handoff_rule_provenance.py`; `analyze-session.md`/`analyze-compact.md` (both .claude and Synapse submodule mirrors) wired to refresh matches, cite failure_class, record provenance on accepted rules, and report pruning candidates. 64 new/updated tests, 100% coverage on all 4 new modules, `run_quality_gate()` green (0 errors/0 warnings).

## 2026-07-19

- **Unified Experience Store in SQLite** - COMPLETE. New src/cortex/experience/ package (models, schema, store_core, store, artifacts, recorder, gate_hook); pipeline_handoff op_mark_running/op_write_result record experience nodes; _finalize_quality_gate_result attaches gate fitness. 40 tests, 100% new-module coverage, gate green.

## 2026-06-30

- <!-- memory_type: status -->
- **Add setup_codegraph prompt and CodeGraph MCP integration** - COMPLETE. Added `codegraph_configured` field to `ProjectConfigStatus` (checks `.cursor/mcp.json` and `.mcp.json`); added `SETUP_CODEGRAPH_PROMPT` to `prompts.py`; registered `setup_codegraph` setup prompt with visibility gated on `memory_bank_initialized and not codegraph_configured`; refactored `apply_setup_prompt_visibility` to `_build_prompt_visibility` helper; updated `INITIALIZE_PROMPT` with codegraph binary resolution and init steps; added `.codegraph/` to `.gitignore`. Phase A: scope=markdown_only, coverage=90.85%.

## 2026-06-25

- **Convert do.md orchestration to Claude Code dynamic Workflow script** - COMPLETE. Authored do.wf.js with hard JS while-loop (max 5), pipeline() parallelism, deterministic review gate, structured schemas. 69 tests pass. prompts-manifest.json updated with superseded_by.
- **Convert fix.md orchestration to Claude Code dynamic Workflow script** - COMPLETE. Authored fix.wf.js with deterministic JS switch/while replacing LLM-orchestrated prose routing; 84 tests all pass; quality gate green.
- <!-- memory_type: milestone -->
- **Phase B docs sync** - COMPLETE. Updated memory bank, archived completed plans, ran autofix and docs gate for skill pack workflow promotions and fix/do/commit workflow script conversion session.
- **Trim Workflow Agent Specs for Claude Code CLI** - COMPLETE. Rewrote 10 cursor-agent files, 55.9% token reduction (13,557→5,977 tokens), all tests pass, .claude/agents/ synced.
- **Pass Failure Context Inline to Workflow Subagents** - COMPLETE. Added priorErrors injection from coverage pre-flight into fix.wf.js quality/tests agents; added preflight context and Phase A summary into commit.wf.js Phase A/B prompts. Quality gate 0 errors.
- <!-- memory_type: milestone -->
- **Phase B docs sync (commit session)** - COMPLETE. Updated memory bank, archived completed plans, ran autofix and docs gate for trim workflow agent specs and pass failure context inline session.
- <!-- memory_type: milestone -->
- **Phase B docs sync (commit session — workflow-conversion skill)** - COMPLETE. Updated memory bank, archived completed plans, ran autofix and docs gate for workflow-conversion skill JSON addition (src/cortex/resources/skills/workflow-conversion.json). Phase A: scope=source, coverage=90.86%.

## 2026-06-24

- **Promote quality skill to dynamic workflow with retry loop** - COMPLETE. Added execute_sequential_workflow with retry loop to skill_pack; 10 unit tests; quality gate clean.
- **Promote planning skill to dynamic workflow with data passing** - COMPLETE. Added workflow block to planning.json; wired inter-phase data passing (plan_file_name, plan_title) via resolve_workflow_inputs; added phase_inputs to skill_pack execute; 10 new tests all passing.
- **Promote refactoring skill to dynamic workflow with analysis data passing** - COMPLETE. Added workflow block to refactoring.json; four phases (analyse→plan→apply→verify) with target_files threaded from analyse into apply; conditions use ctx-key syntax; think and manage_file added to registry; 8 tests pass, quality gate green.
- **Promote evaluation skill to dynamic workflow with structured pipeline output** - COMPLETE. Added workflow block (run→analyse→store) to evaluation.json, EvaluationReport model to models.py, 6 unit tests. Store phase correctly gated on analyse.passed.
- **Convert commit.md orchestration to Claude Code dynamic Workflow script** - COMPLETE. Created .cortex/workflows/commit.wf.js with deterministic JS control flow: Phase A while-loop (cap=3), Step 12 if/else scope routing, structured subagent schemas, non-blocking push/hook paths. prompts-manifest.json updated with superseded_by. 44 passing structural tests.

## 2026-06-23

- <!-- memory_type: milestone -->
- **Synapse scripts: resolve 99 pyright type errors** - COMPLETE. Fixed untyped dict/CompletedProcess generics, unused call results, implicit string concatenations, private symbol imports, and missing async fixture type annotations across 8 scripts in `.cortex/synapse/scripts/python/` and `.cortex/synapse/scripts/swift/`.
- **Docs gate test: replace Any with concrete types** - COMPLETE. Replaced `from typing import Any` with `ValidateCheckTypeName`, `MCPContext | None`, and `ModelDict` in docs gate test.
- **tests/test_phase3.py: fix stale date and long functions** - COMPLETE. Updated stale date "2025-12-19" to "2026-06-20" for freshness score test; refactored 3 overlong test functions (49, 37, 34 lines) into helpers <=30 lines with concrete return types `ValidationResult` and `QualityScoreResult`.
- **tests/test_phase4.py: fix stale date range** - COMPLETE. Updated stale dates (2025-10-01..2025-12-19 -> 2026-04-01..2026-06-20) that caused floating-point equality failures; CI quality gate green.

## 2026-05-08

- <!-- memory_type: status -->
- **Docs-gate roadmap lookup fix** - COMPLETE. Added roadmap_sync fallback to fs_manager memory-bank path, expanded diagnostics for missing-roadmap errors, and added regression coverage; quality gate green.
- <!-- memory_type: status -->
- **Commit pipeline for roadmap sync fix** - COMPLETE. Ran /commit preflight, Phase A quality+parity checks, and advanced docs/validate/final gate workflow for roadmap sync resolver fallback and regression tests.

## 2026-05-04

- <!-- memory_type: status -->
- **SwiftAdapter coverage guard (teardown signal)** - COMPLETE. Skip reporting line coverage when JSON is absent after a post-run signal so partial profraw does not produce a misleading low fraction; memory-bank log updated.

## 2026-05-03

- <!-- memory_type: status -->
- **Commit pipeline: Cortex metadata + Synapse submodule** — Session index and memory-bank log updated; debug-external-integration prompt tweaked; Synapse gitlink advanced for Swift public-docs script formatting.
- <!-- memory_type: status -->
- fix(core): bind MCP stability semaphores to the active event loop and reset long-running map on loop change; reset root cache lock in clear_cached_root for correct per-loop recreation
- chore: refresh session index snapshot and operations log

## 2026-04-29

- <!-- memory_type: milestone -->
Completed /fix + /commit pipeline prep: fixed do-loop markdown structure in synapse, re-established submodule hygiene, and passed Phase A parity + docs gate.

## 2026-04-27

- <!-- memory_type: status -->
- **Commit pipeline execution for swift adapter and synapse prompt wording** - IN PROGRESS. Ran preflight with rollback snapshot, committed `.cortex/synapse` fix-coverage prompt contract update, and passed Phase A quality gate plus parity scripts.

## 2026-04-26

- <!-- memory_type: status -->
- <!-- memory_type: status -->
/cortex/commit Phase B executed for session `90f2789d546e`: checked handoff status, marked docs running, refreshed activeContext/progress state, archived completed plans, ran `autofix()`, and ran `run_docs_gate()` with roadmap_sync handled per timestamp validity policy.
Promoted SwiftAdapter.extract_test_counts to public API and updated swift adapter tests to satisfy type-check private-usage rules; Phase A quality gate and parity scripts passed during /cortex/commit.

## 2026-04-25

- <!-- memory_type: milestone -->
- **/cortex/commit Phase B — documentation/state update** - COMPLETE. Ran pipeline handoff checks/status/mark_running, refreshed memory-bank records, archived completed plans, executed markdown autofix, and validated docs gate semantics.

## 2026-04-24

- <!-- memory_type: status -->
- **Swift adapter diagnostics + logging commit slice** - COMPLETE. Executed /cortex/commit preflight snapshot, green quality gate with CI parity scripts, wiki staged ingest bridge, and docs/validation/final-gate progression for swift diagnostics updates.

## 2026-04-23

- <!-- memory_type: status -->
- <!-- memory_type: status -->
- **Commit pipeline run for swift adapter diagnostics slice** - COMPLETE. Executed preflight snapshot and synapse pre-stage commit, then ran `run_quality_gate()` plus parity scripts and advanced docs/validation steps for the adapter diagnostics and tests update.
**Commit pipeline prep** - Synapse submodule pre-staged and committed (`dcbb940`), quality gate re-run to green after fixing implicit string concatenation in integration tests, CI parity scripts passed.

## 2026-04-22

- **/cortex/commit — execution environment abstraction commit slice** - COMPLETE. Ran preflight snapshot + Synapse pre-stage, passed `run_quality_gate()` with parity scripts, and advanced commit pipeline documentation/validation phases for this branch state.
- **Stop Synapse usage cache collection by default** - COMPLETE. Made usage persistence opt-in by default, enforced write gating, expanded tests for disabled/enabled modes, and aligned docs.

## 2026-04-20

- <!-- memory_type: preference -->
**/cortex/commit Phase B — memory bank/docs synchronization** - COMPLETE. Added commit-session context for comments-only updates in `tests/unit/test_swift_adapter.py` alongside existing `.cortex` index/history/log edits, then executed plan archival, markdown autofix, and docs-gate validation with roadmap-sync policy handling.
- **Add Append-Only Event Log to Pipeline Handoff for Crash Recovery** - PARTIAL. Implemented append-only `pipeline.log` event writes, `read_log` support, incomplete-pipeline detection surfaced via `SessionBrief.incomplete_pipelines`, and dedicated unit coverage; /do remains open until global quality gate coverage target is satisfied.
- **Add Append-Only Event Log to Pipeline Handoff for Crash Recovery** - COMPLETE. Event logging, read_log, and incomplete pipeline detection are implemented and validated in tests.
- <!-- memory_type: milestone -->
- <!-- memory_type: problem -->
**Add Phase Status Tracking and Resume Capability to Pipeline Agents** - PARTIAL. Implemented mark_running/status lifecycle, prompt resume checks across commit/fix phase agents, and dedicated resume simulation tests; completion blocked because review gate subagent was unavailable in region.
**/cortex/commit Phase B — docs gate run for pipeline event-log/resume commit slice** - COMPLETE. Re-read activeContext/progress/roadmap via manage_file, archived completed plans, ran markdown autofix, and validated docs gate with roadmap_sync warning semantics before publishing commit/docs handoff state.

## 2026-04-21

- **Add Phase Status Tracking and Resume Capability to Pipeline Agents** - COMPLETE. Closed the remaining /do review-gate loop for the status/resume rollout, confirmed quality/docs gate cleanliness, and finalized roadmap completion for the pipeline phase resume capability.
- <!-- memory_type: milestone -->
**/cortex/commit Phase B — docs/memory-bank synchronization** - COMPLETE. Re-read activeContext/progress/roadmap, applied docs-phase bookkeeping updates, archived completed plans, and prepared docs gate validation + pipeline handoff for commit/docs.
- **Introduce Tool Dispatch Layer for Environment-Agnostic Quality Gate Execution** - PARTIAL. Added `ExecutionEnvironment` abstractions and threaded environment dispatch through quality/docs/autofix execution paths with targeted tests; implement step remains open because the branch still has unrelated quality-gate markdown issues.
- **Phase: Investigate autofix MCP Tool Failure** - COMPLETE. Validated the `autofix` env-injection regression path, confirmed updated lock/autofix tests pass, and verified `run_quality_gate()` is green with no additional code changes required in this run.
- **Introduce Tool Dispatch Layer for Environment-Agnostic Quality Gate Execution** - COMPLETE. Completed execution environment abstraction rollout and validated quality/docs/autofix execution paths with green quality gate.
- <!-- memory_type: milestone -->
**Introduce Tool Dispatch Layer for Environment-Agnostic Quality Gate Execution** - COMPLETE. Completed execution environment abstraction rollout and validated quality/docs/autofix execution paths with green quality gate.

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
