# Progress Log

## 2026-03-15

- **Commit pipeline Phase B** — Memory bank verified (activeContext, progress, roadmap); 0 plans archived; documentation validation run.

## 2026-03-14

- **MCP Connection Stability Fix** — COMPLETE. Root-caused `ClosedResourceError` crash when concurrent tool calls from parallel subagents raced on shared stdio write stream. Fix: (1) monkeypatched `_handle_request` in `main.py` to catch `ClosedResourceError` on `message.respond()`; (2) removed `log_client` stream writes from `_run_standard_checks_mode`; (3) used cached `get_current_project_root()` to avoid `list_roots` round-trips; (4) made `_dispatch_phase` use detached mode; (5) changed `fix.md` from parallel to sequential subagent execution. Root cause: Cursor kills connection when 3-4 concurrent tool calls pending >10-15s. Sequential execution eliminated all disconnections. All 5102 tests pass.

## 2026-03-13

- **Blocker: Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps** - PARTIAL. Implement finalize (session f3f88e7c190b): Step 7 smoke tests (get/create with full payload) documented in activeContext and roadmap; optional metrics remain. Blocker still IN_PROGRESS.
- **Blocker: Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps** - PARTIAL. Step 7 smoke tests: added smoke tests for plan(operation='get') and plan(operation='create') with full payload in tests/tools/test_plan_tool_dispatch.py. Optional metrics remain. Blocker still IN_PROGRESS.
- **Blocker: Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps** - PARTIAL. Step 7 guardrail tests: added tests for plan payload builders (complete, register, create) in test_plan_payloads.py; fixed pyright reportUnusedCallResult in pytest.raises blocks. Smoke tests and optional metrics remain. Blocker still IN_PROGRESS.
- **Commit pipeline Phase B** - Memory bank verified (activeContext, progress, roadmap); 0 plans archived; documentation validation run.
- **Blocker: Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps** - PARTIAL. Guardrail test test_create_missing_title_and_content added for plan(operation='create') missing title/content; pre-existing type/quality fixes in pre_commit_status.py and test_plan_completion.py. Blocker still IN_PROGRESS.
- **Blocker: Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps** - PARTIAL. Step 1 audit: added docs/development/mcp-tool-call-audit.md with inventory of MCP tool call sites (implement, commit, other agents), argument style, Safe/Unsafe classification; all documented call sites use full payloads (Safe). Step 7 test: added TestPlanToolHappyPath and test_plan_operation_list_returns_success in tests/tools/test_plan_tool_dispatch.py. Type fixes in src/cortex/tools/session/pipeline_handoff.py (unnecessary isinstance, unused write_text return, dict typing for json.loads/update). Blocker remains IN_PROGRESS.
- **Blocker: Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps** - PARTIAL. Step 7: added lightweight logging in plan tool (operation + required_args_present); added test in tests/tools/test_plan_payloads.py for build_plan_create_arguments validation. Blocker remains IN_PROGRESS.

## 2026-03-12

- **Commit pipeline Phase B** - Ran `/cortex/commit` Phase B (docs/memory validation) for current changes; no new implementation work beyond existing roadmap items, memory bank and roadmap remained consistent.
- **Commit pipeline Phase B** - Ran `/cortex/commit` Phase B (docs/memory validation) for the current workspace changes; memory bank and roadmap were already in sync so no additional roadmap mutations were required in this pass.
- **[MED-3] Calibrate Review Metric Scores** - COMPLETE. Verified all 9 review metrics in `review.md` have calibration tables and evidence requirements, and that `review-output-schema.md` defines an evidence field for each metric; Phase A pre-commit job was started via Cortex MCP but its result is still pending/unavailable.
- **[MED-10] Make Prompts Agent-Agnostic** - PARTIAL. Added an agent-agnostic Agent Tool Mapping section to shared-conventions and updated the create-plan prompt to refer to generic file operation tools instead of Cursor-specific names for roadmap writes; additional prompt and tool description updates remain.
- **[MED-8] Reduce Prompt-Alignment Test Fragility** - PARTIAL. Relaxed the `TestImplementPromptRefactoringGuidance` tests in `tests/integration/test_commit_workflow_prompt_alignment.py` to assert semantic concepts for incremental validation and duplicate-detection guidance in the implement pipeline using lowercased content and synonym lists instead of single fragile substrings; pre-commit job remained running and should be re-run in a live environment; remaining fragile substring assertions still need semantic refactors in later subtasks.
- **Blocker: Implement-Select Must Respect Explicit Plan Targets** - PARTIAL. Implemented explicit-plan-first selection behavior at the prompt/orchestration level so `implement-select` prefers an `explicit_plan_path` hint when the referenced plan exists and is eligible, and added prompt-level tests covering (A) no explicit plan → roadmap ordering, (B) valid explicit plan → preferred over roadmap, and (C) invalid or ineligible explicit plan → fallback with a clear explanatory note; deeper runtime wiring and eligibility checks remain for future work.

## 2026-03-11

- No additional implementation work beyond existing memory bank entries; this commit only runs Phase B (docs/memory validation) for the current diff.

## 2026-03-10

- **Phase: Investigate execute_pre_commit_checks MCP Tool Failure** - COMPLETE. Documented detached worker vs semaphore interaction, updated troubleshooting docs, and verified Phase A of execute_pre_commit_checks runs successfully with detached semantics.

## 2026-03-09

- Archived 7 completed investigation plans (execute_pre_commit_checks failures and commit pipeline hang) from .cortex/plans/ to archive/Investigations/2026-03-08/; cleared both roadmap blocker entries.
- **[CRI-3] Add MCP Circuit-Breaker Pattern** — Added circuit-breaker convention (3 consecutive MCP failures) to shared-conventions.md, resume-from-checkpoint (Step -1) to commit.md, circuit_breaker_failures/resume_from_step to pipeline-state-tracker state schema, and circuit-breaker references to create-plan.md and review.md.
- **[CRI-4] Add Commit Pipeline Rollback** — Added pre-pipeline snapshot (Step -0.5, git stash create + store) to commit.md, rollback offer in Failure Handling, snapshot_ref to pipeline-state-tracker schema, and memory bank snapshot recovery docs.
- **[CRI-5] Add Plan YAML Frontmatter Schema** — Added YAML frontmatter requirement (Phase 2.5) to plan-creator.md, deterministic similarity scoring (+2/+1 system) replacing prose comparison in create-plan.md, checkpoint persistence for similarity_decision, and added frontmatter to all 19 active plan files.
- **[HI-3] Persist Pipeline State Decisions** — Added checkpoint_read before create-plan Step 3, primary_language in commit pipeline initial checkpoint, and Critical Decisions table in pipeline-state-tracker documenting which decisions must be checkpointed.
- **[HI-5] Fix Roadmap Logging Leakage** — Verified already resolved: only one logging call in roadmap_sync.py at warning level with metadata only, no content previews anywhere.
- **[MED-2] Fix Loop Convergence Detection** — Added convergence check to commit.md Failure Handling (abort if N2 >= N1) and shared-conventions.md Max-Retry Limits, plus fix_iterations tracking schema in pipeline-state-tracker.
- **[MED-4] Extend Pre-Flight Directory Validation** — Added Phase 2.2 to common-checklist.md: validates plans/, reviews/, .session/ directories exist and auto-creates missing ones (CHECK, not GATE).
- **[MED-5] Atomic Memory Bank Writes** — Replaced direct file write in file_system.py `_write_file_content` with atomic temp file + fsync + rename pattern; 3 new tests (no .tmp residue, preservation on error, same-directory temp file) in test_file_system.py; all 3333 tests pass.
- **[CRI-2] Fix Troubleshooting Docs Contradiction** — Fixed contradictory coverage config in troubleshooting.md: line 275 incorrectly claimed pytest.ini sets --cov-fail-under=90 in addopts; corrected to explain coverage is passed by CI/MCP tools explicitly, not pytest.ini.
- **[MED-6] Schema-Define Roadmap Section Names** — Created RoadmapSection StrEnum and SECTION_TO_KEY/KEY_TO_SECTION in roadmap_models.py; updated register_helpers.py to use constants and auto-create missing sections; updated schema_validator.py; 6 new tests in test_roadmap_constants.py; all 3333 tests pass.
- **[MED-1] Agent Handoff Output Validation** — Added Required Fields Summary table (17 schemas) to shared-handoff-schema.md, validation GATE to pipeline-state-tracker checkpoint_write, and handoff validation instruction to commit.md, review.md, and create-plan.md.
- Investigated execute_pre_commit_checks MCP long-running semaphore failures when a second call was made while the first was still running. Refactored long-running semaphore handling into cortex.core.mcp_stability_semaphores with configurable wait, retry window, and auto-release, and re-exported constants via mcp_stability_config. Added long-running semaphore tests in tests/unit/test_mcp_stability_timeouts.py to cover sequential success, wait-timeout failure, retry success, and cancellation release. Verified execute_pre_commit_checks(checks=["tests"]) passes the full test suite (4954 tests, coverage 90.96%), confirming the commit pipeline can proceed without regressions.
- **Phase: Investigate execute_pre_commit_checks MCP Tool Failure** — Investigation performed; semaphore and timeout configuration reviewed; long-running serialization tests and troubleshooting docs validated. `execute_pre_commit_checks` MCP tool still reports "Another long-running tool is in progress" from this session, so full pre-commit quality gate could not be executed; re-run once other long-running tools have finished or MCP has been restarted.

## 2026-03-08

- **Commit pipeline** - Phase A fixes: reportUnusedCallResult in `pre_commit_pipeline.py` (`_ = _run_non_test_checks`); function-length in `pre_commit_tools_run_helpers.py` (`_callbacks_for_ctx` extraction). Preflight passed.
- **Commit pipeline** - Function-length fix: extracted _setup_heartbeat_and_callbacks in pre_commit_tools_run_helpers.py; Phase A passed (4942 tests, 91.64% coverage).
- **Commit pipeline** — Phase B/C: memory bank verified, 0 plans archived; proceeding to final gate and commit.
- **Phase: Investigate execute_pre_commit_checks MCP Tool Failure (2026-03-08)** - COMPLETE. Root cause: second long-running tool call timed out (330s). Fix: wait/max-hold 600s, clearer error message, doc updates, test for semaphore release on cancellation.

## 2026-03-07

- **Week containing 2026-03-07** - 1 entries summarized.

## 2026-03-06

- **Week containing 2026-03-06** - 1 entries summarized.

## 2026-03-05

- **Week containing 2026-03-05** - 1 entries summarized.

## 2026-03-04

- **Week containing 2026-03-04** - 1 entries summarized.

## 2026-03-03

- **Week containing 2026-03-03** - 1 entries summarized.

## 2026-03-02

- **Week containing 2026-03-02** - 1 entries summarized.

## 2026-03-01

- **Week containing 2026-03-01** - 1 entries summarized.

## 2026-02-28

- **Week containing 2026-02-28** - 1 entries summarized.

## 2026-02-27

- **Week containing 2026-02-27** - 1 entries summarized.

## 2026-02-26

- **Week containing 2026-02-26** - 1 entries summarized.

## 2026-02-24

- **Week containing 2026-02-24** - 1 entries summarized.

## 2026-02-23

- **Week containing 2026-02-23** - 1 entries summarized.

## 2026-02-22

- **Week containing 2026-02-22** - 1 entries summarized.

## 2026-02-20

- **Week containing 2026-02-20** - 1 entries summarized.

## 2026-02-19

- **Week containing 2026-02-19** - 1 entries summarized.

## 2026-02-18

- **Week containing 2026-02-18** - 1 entries summarized.

## 2026-02-17

- **Week containing 2026-02-17** - 1 entries summarized.

## 2026-02-16

- **Week containing 2026-02-16** - 1 entries summarized.

## 2026-02-13

- **Week containing 2026-02-13** - 1 entries summarized.

## 2026-02-12

- **Month containing 2026-02-12** - 1 entries summarized.

## 2026-02-11

- **Month containing 2026-02-11** - 1 entries summarized.

## 2026-02-10

- **Month containing 2026-02-10** - 1 entries summarized.

## 2026-02-09

- **Month containing 2026-02-09** - 1 entries summarized.

## 2026-02-07

- **Month containing 2026-02-07** - 1 entries summarized.

## 2026-02-05

- **Month containing 2026-02-05** - 1 entries summarized.

## What Works

Pre-commit pipeline (fix_errors, format, type_check, quality, tests); 3702 tests, 90.36% coverage; integration tests for projectBrief schema; Option C HTTP/SSE transport (Phase 1 and 2). Create-plan and memory-bank-updater mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption.

## What's Left

See roadmap.md.
