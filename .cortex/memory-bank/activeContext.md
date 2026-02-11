# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-02-11)

- ✅ **Session Optimization: Commit Pipeline Orchestration Refactor — Step 6** - COMPLETE (2026-02-11) - Updated session-optimization and quality plans with cross-references to orchestration refactor plan. session-optimization-commit-pipeline-improvements-2026-02-07.md, quality-gate-commit-pipeline-spelling-gap.md, session-optimization-load-context-on-problem-fix-path-2026-02-09.md now reference orchestration refactor for structural vs content focus. AGENTS.md already describes phase-based pipeline (Step 5). Plan status updated to Steps 1-6 complete.

- ✅ **Session Optimization: Commit Pipeline Orchestration Refactor — Steps 7–8** - COMPLETE (2026-02-11) - Step 7: create-plan.md — added explicit phases (1–5), Phases overview, slimmed Path Resolution and ERROR HANDLING by referencing memory-bank-workflow.mdc and AGENTS.md. Step 8: analyze.md — added Phases (1–3), Tooling reference to memory-bank-workflow.mdc/AGENTS.md, phase labels on Pre-Analysis Checklist and steps, Phase D alignment in commit-pipeline-phases.md, full-report/no-truncation for review writes. Plan status set to COMPLETED (Steps 1–8).

- ✅ **Phase 43 Step 6: Naming Unification and get_* Tool Review**- COMPLETE (2026-02-11) - Documented naming conventions (Tools: imperative verbs; Resources: cortex:// URIs; get_* read-only). Added inventory and per-case decisions to phase-43-reconsider-tools-registration.md. Updated docs/api/tools.md and AGENTS.md. Added tests/tools/test_phase43_get_tools_naming.py. No breaking renames; backward compatibility maintained.

- ✅ **Claude-mem improvements: get_usage_events tool** - COMPLETE (2026-02-11) - Implemented MCP tool get_usage_events(ids=[...]) backed by UsageTracker.get_events_by_ids, plus unit tests and quality gate / coverage checks, enabling token-efficient workflow search_usage -> get_usage_events for selected observations.

- ✅ **Usage analytics boundary model and test fixes** - COMPLETE (2026-02-11) - Updated usage analytics models and tools to use a UsageEventPayload boundary model with stable IDs, improved robustness of get_usage_events/search/observation flows, and fixed python_adapter tests/type checking so MCP-based pre-commit checks (fix_errors, format, quality, tests) pass with ~90.19% coverage.

- ✅ **Claude-mem inspired improvements – Steps 9–11 (keyword search, context injection config, usage JSON docs)** - COMPLETE (2026-02-11) - Implemented keyword-based usage search over usage events via UsageTracker.search_usage and search_usage MCP tool (query parameter, tests, helper filters); extended optimization configuration schema and docs with a context_injection policy section (enabled flag, always_include_files, recent_usage_events, max_usage_summary_tokens) and updated optimization config via Cortex MCP; and documented how to query raw usage events JSON under .cortex/.cache/usage/events/ with jq in tool-usage-tracking.md. Tests and quality gate pass; global coverage remains ~90.2% with legacy modules tracked separately via existing coverage-improvement plans.

- ✅ **Claude-mem inspired improvements (usage search, observations, progressive disclosure)** - COMPLETE (2026-02-11) - Completed remaining Claude-mem inspired improvements plan steps: added keyword-based usage search over tool usage events using UsageTracker.search_usage and the search_usage MCP tool (query parameter and tests) for token-efficient discovery, extended optimization configuration with a documented context_injection policy (always-include memory bank files and usage summary limits) via Cortex MCP configuration, and documented how to query raw usage event JSON files under .cortex/.cache/usage/events/ with jq and scripts in the tool-usage-tracking architecture doc. All tests and quality checks pass; global coverage remains ~90.2% with legacy gaps tracked by existing coverage-improvement roadmap items. Plan marked COMPLETE and archived.

- ✅ **Claude-mem usage timeline support** - COMPLETE (2026-02-11) - Implemented UsageTracker.get_usage_timeline and validated the get_usage_timeline MCP tool with new unit tests and full quality gate passes; overall Claude-mem plan remains in progress with later steps still pending.

- ✅ **Conditional prompt registration** - COMPLETE (2026-02-11) - Conditionally register setup and migration MCP prompts based on a synchronous project configuration status check so that setup prompts only appear when needed; implementation, tests, and documentation are all in place and passing the full quality and test gates.

- ✅ **Make fix_markdown_lint report progress like tests tool** - COMPLETE (2026-02-11) - Implemented real file-count-based progress reporting for fix_markdown_lint by wiring ctx through the markdown lint pipeline, reporting (processed, total) after each file, and disabling wrapper-based time progress; added unit tests to verify progress behavior with and without ctx and all checks/tests now pass.

- ✅ **Phase 9: Excellence 9.8+ – Complete TODO implementations (script promotion)** - COMPLETE (2026-02-11) - Eliminated remaining production TODO markers in script promotion templates by updating the script integrator and tool converter to reference the original script path and provide clear, non-TODO guidance for porting logic, with all tests, coverage (90%+), and quality gates passing.

- ✅ **Refactor setup prompts (simplify to 3)** - COMPLETE (2026-02-11) - Simplified setup prompt system from 7 prompts (4 setup + 3 migration) to 3 unified prompts: initialize (complete setup), migrate (legacy migration), and setup_synapse (always available with default URL). Updated all code, tests, and documentation.

## Completed Work (2026)

- ✅ **Implement prompt memory bank and function length** - COMPLETE (2026) - Enforced manage_file-only for memory bank writes in implement Step 5 (requirement, prohibition, full-content fallback); added function-length reminder in Step 4; added rules-disabled fallback in analyze prompt. Fixed token-budget integration test to accept comma-formatted numbers.

- ✅ **Phase 43: Reconsider Tools Registration - Transform Tools to Resources** - COMPLETE (2026) - Completed Phase 43: Transformed read-only operations from Tools to Resources, unified naming conventions, and verified all Resources and Tools work correctly. All 3810 tests pass, quality gate passes, documentation updated.

- ✅ **Quality gate: commit pipeline spelling gap** - COMPLETE (2026) - Added spelling check to execute_pre_commit_checks (PreCommitCheck.SPELLING enum, pipeline step via synapse script check_spelling.py), updated commit prompt Step 12 to explicitly call spelling check, and updated docstring. CI already pins cspell@8.6.1.

## Completed Work (2026-02-10)

- ✅ **Implement load_context at step start, rules fallback, and task-type token budget** - COMPLETE (2026-02-10) - Updated implement-next-roadmap-step prompt: (1) load_context at step start with session-recording note in Pre-Action Checklist and Step 1; (2) rules fallback when status disabled (read from structure_info.paths.rules); (3) task-type token budget mapping (10k update/implement-add, 15k fix-debug/other, 20–30k small feature, 40–50k architecture).

- ✅ **Tool failure investigations archive** - COMPLETE (2026-02-10) - Archived 20 tool-failure investigation plans (Phase 45 MCP annotations) to .cortex/plans/archive/Investigations/2026-02-04; two were already archived. Removed "Tool Failure Investigations (Archive Recommended)" section and 22 list entries from roadmap.

- ✅ **Plan Status MD036 side-effect imports** - COMPLETE (2026-02-10) - Added Synapse rule for plan Status format (avoids MD036), Python testing rule for side-effect imports (_ = module), commit prompt reminders for both, and integration test asserting commit prompt contains the reminders.

- ✅ **Markdown corruption in progress and plans** - COMPLETE (2026-02-10) - Added MD037 and code identifiers in backticks to markdown-formatting rule; extended corruption guard to progress.md via fix_memory_bank_content_if_needed (phrase-only fix); added verify-code-symbols guidance to memory-bank-updater and memory-bank-workflow; plan files documented as out of scope for phrase fix.

- ✅ **Public API, memory bank, rules** - COMPLETE (2026-02-10) - Added Synapse rules (public API no private type names, SDK generic type parameters), implement prompt and memory-bank-updater guidance to update memory bank after user-requested fixes; verified no outdated type names in progress/activeContext.

- ✅ **Sequential thinking in Cortex MCP** - COMPLETE (2026-02-10) - Implemented sequentialthinking MCP tool: Pydantic models (SequentialThinkingInput/Output), SequentialThinkingCore with process_thought, in-memory thought history and branches, handler with USE WHEN/EXAMPLES/RETURNS, optional DISABLE_THOUGHT_LOGGING, registration in tools **init**, unit tests ≥95% coverage, docs (tools.md, README, CLAUDE.md).

- ✅ **Claude-mem ideas for Cortex** - COMPLETE (2026-02-10) - Implemented short-term items from the claude-mem ideas plan: (1) Progressive disclosure—added Context Workflow section to CLAUDE.md, added context workflow note to docs/api/tools.md, and added token-efficient guidance to the implement prompt; (2) Privacy convention—documented `<private>...</private>` and `<!-- private -->` in CLAUDE.md and memory-bank-workflow.mdc. Docs and prompts only; no production code changes.

- ✅ **Session Optimization: Roadmap Section Removal and Roadmap Sync Clarity** - COMPLETE (2026-02-10) - Documented safe roadmap section removal pattern in memory-bank-updater and confirmed roadmap_sync behavior around archived plans/unlinked_plans so future roadmap edits avoid full-content manage_file writes for section removal.

- ✅ **Claude-mem inspired improvements: documentation groundwork** - COMPLETE (2026-02-10) - Confirmed that CLAUDE.md and implement-next-roadmap-step already implement the claude-mem context workflow (progressive disclosure, token-aware context loading, search → select IDs → get_usage_event pattern) and the `<private>` / `<!-- private -->` privacy convention, then updated the `claude-mem-inspired-improvements` plan to mark Steps 1–2 as completed and set the plan status to IN PROGRESS.

- ✅ **Claude-mem inspired improvements – Step 3: Stable IDs for usage events** - COMPLETE (2026-02-10) - Implemented stable `id` field on `ToolUsageEvent`, ensured new usage events persist IDs, added deterministic UUIDv5 backfill for legacy events in `usage_tracker`, and extended tests to cover ID assignment and backfill behavior within the existing usage tracking pipeline.

- ✅ **Claude-mem inspired improvements – Step 4: usage observation resource** - COMPLETE (2026-02-10) - Implemented usage observation-by-ID support via `get_usage_observation` MCP tool and `cortex://usage/observation/{id}` resource on top of `UsageTracker.get_event_by_id`, including tests, coverage, and quality gate compliance.

- ✅ **Usage analytics and commit pipeline maintenance** - COMPLETE (2026-02-10) - Ran full MCP-based pre-commit pipeline for usage tracking and analytics changes, auto-fixed quality and markdown issues, and validated tests/coverage for this session.

- ✅ **fix_markdown_lint connection closed mitigations (2026-02-10)** - COMPLETE. Reduced heartbeat from 15 s to 5 s and added batched markdownlint (25 files per invocation) to cut duration and improve MCP connection stability. ListOfferings correlates with disconnect; shorter heartbeat and faster runs mitigate. Plan archived to .cortex/plans/archive/Investigations/2026-02-10/.

- ✅ **Commit Pipeline Orchestration Refactor - Step 1: Define Canonical Phases** - COMPLETE (2026-02-10) - Created `docs/design/commit-pipeline-phases.md` defining 4 canonical commit phases (A: Preflight Checks covering Steps 0-4, B: Docs & Memory Bank Sync covering Steps 5-10, C: Submodule & Git Operations covering Steps 11-14, D: Session Analysis covering Step 15). All 16 existing commit steps mapped to exactly one phase with documented inputs/outputs and failure semantics. Plan updated to IN PROGRESS (Step 1/6 complete).

- ✅ **Session Optimization: Commit Pipeline Orchestration Refactor – Phase A preflight helper** - COMPLETE (2026-02-10) - Implemented `run_preflight_checks` MCP tool that wraps `execute_pre_commit_checks` Phase A checks and `fix_markdown_lint` into a single structured preflight phase with Pydantic models and tests, ready for `/cortex/commit` orchestration.

- ✅ **Session Optimization – Commit Pipeline Orchestration (Phase B helper)** - COMPLETE (2026-02-10) - Implemented `run_docs_and_memory_bank_sync` MCP tool to aggregate timestamps and roadmap_sync validations into a single Phase B helper with structured summaries, wired it into discovery, and added focused tests ensuring success, validation-failure, and tool-error paths are covered.

- ✅ **Commit pipeline Phase A/B helper refactor** - COMPLETE (2026-02-10) - Extracted Phase A preflight and Phase B docs/memory bank helper logic into dedicated helper modules (`pre_commit_preflight_helpers.py` and `pre_commit_docs_memory_helpers.py`), slimmed `pre_commit_phase_tools.py` to thin MCP wrappers, updated unit tests, and ensured all format, type, tests, and quality gates pass for the new Phase helpers.

- ✅ **Phase 18: Markdown Lint Fix Tool** - COMPLETE (2026-02-10) - Completed archival alignment for the Phase 18 markdown lint fix tool plan by ensuring only the archived copy under Phase18 is referenced from the roadmap and memory bank, and removing any stray unarchived root plan file so roadmap_sync no longer reports an unlinked plan for Phase 18.

- ✅ **Commit Pipeline Orchestration Refactor - Step 2 Complete** - COMPLETE (2026-02-10) - Completed Step 2 (phase-level MCP tools/helpers) with 45 comprehensive tests achieving 95-100% coverage. Phase A (run_preflight_checks) and Phase B (run_docs_and_memory_bank_sync) tools fully tested with success, failure, tool-error, and edge-case scenarios. Steps 3-4 partially done from previous session (commit prompt updated, helper commands created).

- ✅ **Commit Pipeline Orchestration Refactor (Steps 4–5)** - COMPLETE (2026-02-10) - Completed Step 4: markdown list/indentation fixes in fix-quality.md and docs-sync.md. Started Step 5: added AGENTS.md section 'Commit pipeline (phase-based)' with phase helpers and helper commands; added one-line references in commit.md and implement-next-roadmap-step.md to AGENTS. Quality gate passed.

- ✅ **Session Optimization: Commit Pipeline Step 5 — Slim and centralize rules** - COMPLETE (2026-02-10) - Completed Step 5 of session-optimization-commit-pipeline-orchestration-refactor: added Synapse rule general/commit-pipeline.mdc for rules(operation="get_relevant"); slimmed commit.md (Pre-Step Load Rules references checklist and commit-pipeline.mdc/memory-bank-workflow.mdc; Verify code conformance shortened); review.md references AGENTS.md for Phase A type/quality checks. Quality gate passed.

## Completed Work (2026-02-09)

- ✅ **Investigate roadmap corruption on plan registration (blocker)** - COMPLETE (2026-02-09). Mandated `register_plan_in_roadmap` and `add_roadmap_entry` for plan registration: updated create-plan Step 6 and memory-bank-updater to require register_plan_in_roadmap for adding a new plan entry; manage_file(full content) only as fallback. Updated integration tests to assert prompt requires register_plan_in_roadmap. Documented structured JSON roadmap as future work. Blocker removed from roadmap.

- ✅ **Commit (rules and manage_file test fixes)** - COMPLETE (2026-02-09). Fixed test failures: (1) Added `manager.initialize = AsyncMock(return_value=None)` to `mock_rules_manager` in `tests/tools/test_rules_operations.py` so `await rules_manager.initialize()` in rules tool does not raise. (2) Fixed `test_manage_file_metadata_success` in `tests/tools/test_consolidated.py`: prevent usage-context from persisting real managers by patching `set_current_managers` and `set_current_project_root` (no-op); use existing path for `construct_safe_path` return value. All 3702 tests pass; coverage 90.36%.

- ✅ **Commit (type, quality, markdown)** - COMPLETE (2026-02-09) - Fixed reportUnusedCallResult in plan_completion._write_progress; refactored_execute_append_progress, _execute_append_active_context (plan_completion),_execute_roadmap_removal (roadmap_operations) under 30 lines via error helpers; fix_markdown_lint fixed 3 Synapse files.

- ✅ **Commit (markdown lint MD033, plan archive check)** - COMPLETE (2026-02-09) - Fixed MD033 no-inline-html in phase-investigate-execute_pre_commit_checks-failure plan by wrapping error message in backticks. Markdown lint check_all_files: 0 errors. Plan archiving: 0 completed plans in plans root. 3717 tests, 90.16% coverage.

- ✅ **Structured JSON roadmap (future)** - COMPLETE (2026-02-09) - Evaluation complete. Created docs/design/roadmap-json-evaluation.md with pros/cons, recommendation to keep Markdown short-term, and future-work steps (JSON schema, canonical store, APIs, optional roadmap.md generation). Roadmap entry removed.

- ✅ **Analyze prompt and memory bank responsibilities** - COMPLETE (2026-02-09) - Aligned Analyze prompt Pre-Analysis Checklist with memory bank contract: activeContext.md described as completed work only, roadmap.md as current/upcoming work; added explicit instruction to read both so end-of-session analysis reflects both; no content migration (optional step deferred).

- ✅ **Connection closed follow-ups (2026-02-03)** - COMPLETE (2026-02-09) - Verified commit prompt note for fix_markdown_lint (per-file progress, 15s heartbeat, retry then Step 12.5 fallback). Recorded fix_quality_issues: no -32000 in reviews—no heartbeat added unless observed. Plan archived to .cortex/plans/archive/SessionOptimization/.

- ✅ **Roadmap full-content enforcement** - COMPLETE (2026-02-09) - Strengthened create-plan Step 6 with explicit prohibition and pre-write length check; memory-bank-updater no-truncation rule and recovery instruction; integration tests for anti-truncation wording.

- ✅ **Commit (pre-commit pipeline)** - COMPLETE (2026-02-09) - Pre-commit pipeline run: fix_errors, format, markdown lint (check_all_files, 13 files fixed, 0 errors), type_check, quality, tests 3729 passed, 90.12% coverage. Memory bank and roadmap updated; plan archiving validated.

## Completed Work (2026-02-07)

- ✅ **Gradual migration to Option C: HTTP/SSE transport (blocker)** - COMPLETE (2026-02-07). Implemented Phase 1 and Phase 2: (1) Optional HTTP/SSE and Streamable HTTP alongside stdio via `CORTEX_MCP_TRANSPORT`, `CORTEX_MCP_PORT`, `CORTEX_MCP_HOST`; entry point applies env to FastMCP and selects transport; uvicorn/starlette when sse or streamable-http. (2) Option C default: when port set, default transport is sse unless `CORTEX_MCP_TRANSPORT=stdio`. Added `cortex.transport_config`, unit tests (`test_transport_config.py`), main transport selection tests; updated `docs/mcp-tool-timeouts.md` (HTTP/SSE section, Deployment and configuration, Option C). Plan archived: .cortex/plans/archive/Transport/mcp-transport-http-sse-implementation.md.

- ✅ **Commit (integration tests projectBrief schema, markdown lint)** - COMPLETE (2026-02-07). Fixed two failing integration tests: `test_full_workflow` (tests/test_integration.py) and `test_initialize_read_write_workflow` (tests/integration/test_mcp_tools_integration.py) by using projectBrief content with required schema sections (Project Overview, Goals, Core Requirements, Success Criteria). Fixed MD026 in .cortex/history/progress_v11.md. Markdown lint (check_all_files): 0 errors. All pre-commit checks pass; 3635 tests, 90.01% coverage.

- ✅ **MCP transport HTTP/SSE analysis (blocker)** - COMPLETE. Delivered [docs/mcp-transport-http-sse-analysis.md](../../docs/mcp-transport-http-sse-analysis.md): SDK transport survey (stdio, SSE, streamable-http), client compatibility matrix (Cursor supports SSE URL), concurrency/behavior, design options (A/B/C), recommendation **Go**. Follow-up implementation plan added to roadmap ([.cortex/plans/archive/Transport/mcp-transport-http-sse-implementation.md](../plans/archive/Transport/mcp-transport-http-sse-implementation.md)). Analysis plan marked COMPLETED; roadmap blocker removed. Pre-existing function-length violations fixed (file_operation_helpers, file_operations); quality gate passed.

- ✅ **Phase 18: Markdown Lint Fix Tool** - COMPLETE. Markdown lint fix tooling; plan archived. Reference: [.cortex/plans/archive/Phase18/phase-18-markdown-lint-fix-tool.md](../plans/archive/Phase18/phase-18-markdown-lint-fix-tool.md).

- ✅ **Commit (roadmap_sync type fix, tests, markdown lint)** - COMPLETE (2026-02-07). Fixed Pyright reportUnknownVariableType for `completed_entries_in_roadmap` in `SyncValidationResult`: introduced typed default factory `_default_completed_entries_in_roadmap()` in `src/cortex/validation/roadmap_sync.py`. Added unit test `test_completed_entries_in_roadmap_default_is_empty_list` in `tests/unit/test_roadmap_sync.py`. Markdown lint (check_all_files): 16 files fixed, 0 errors. All pre-commit checks pass; 3631 tests, 90%.

- ✅ **Ensure proper logging for FastMCP (Phase 5 complete)** - COMPLETE (2026-02-07). Completed Phase 5 (Documentation and Cleanup) of the FastMCP logging plan: updated `docs/development/logging-guidelines.md` to use MCPContext, log_client, and report_progress_safe; updated `docs/guides/troubleshooting.md` with a "Context logging (client-visible messages)" subsection; verified code review (no unused logging imports; server-side logger use appropriate); ran format, quality gate, and full test suite (3624 tests passed). Plan `.cortex/plans/archive/Infrastructure/ensure-proper-logging-fastmcp.md` marked COMPLETE; roadmap step removed.

- ✅ **Investigation: MCP connection closed during fix_markdown_lint (2026-02-07)** - COMPLETE. Root cause: client (Cursor) closed the MCP stdio connection while the tool was running (~56 s), likely due to client-side tool-call timeout or IDE lifecycle—not a server bug. Server already uses per-file progress and 15 s heartbeat; no server logic change required. Optional follow-up applied: added short note in commit prompt (Connection Closed section). Plan archived to `.cortex/plans/archive/Investigations/2026-02-07/investigate-mcp-connection-closed-2026-02-07.md`.

- ✅ **Phase 4 and Validation (FastMCP logging plan)** - COMPLETE. Completed Phase 4 testing and validation for FastMCP Context logging: mock_ctx fixture, test_context_logging_integration.py, all tests pass, quality gate passes. Plan: `.cortex/plans/archive/Infrastructure/ensure-proper-logging-fastmcp.md`.

- ✅ **Commit (test fixes and markdown lint)** - COMPLETE. Fixed test failures and markdown lint errors in commit pipeline.

- ✅ **Commit (type fixes, integration tests, quality)** - COMPLETE. Type and quality fixes for commit pipeline; all tests pass; coverage/quality/markdown checks pass.

## Current Focus

Commit pipeline; no active feature focus.

## Recent Changes

Blocker (2026-02-09): create-plan and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
