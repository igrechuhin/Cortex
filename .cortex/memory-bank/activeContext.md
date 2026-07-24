<!-- memory_type: preference -->
# Active Context: Cortex

**This file records completed work only.** For current status and upcoming work see [roadmap.md](roadmap.md).

## Completed Work (2026-07-23)

- ✅ **Support xcodebuild -skip-testing: via .cortex/config/swift_test.json** - COMPLETE (2026-07-23) - Added `SwiftTestConfig` (`src/cortex/config/swift_test_config.py`), mirroring the existing `swift_coverage.json` pattern, letting a Swift/xcodebuild project declare test identifiers to exclude from `run_quality_gate()`'s test-without-building run via `.cortex/config/swift_test.json` (`skip_testing` list). Wired into `SwiftXcodebuildMixin._xcodebuild_test_phase` so each configured identifier becomes an Xcode `-skip-testing:` flag ahead of the test-without-building action, fixing quality-gate failures on infra a project's own CLAUDE.md documents as intentionally excluded (e.g. a live-network integration suite). New tests: `tests/unit/test_swift_test_config.py`, `tests/unit/test_swift_xcodebuild_mixin.py`.

- ✅ **Fix analyze pipeline phase-allowlist and subagent tool-grant gaps** - COMPLETE (2026-07-23) - Extended the pipeline_handoff phase allowlist (src/cortex/tools/session/pipeline_handoff_validation.py) with context/session/tools so analyze-* phases no longer hit Unknown phase; granted ReadMcpResourceTool, Bash, and Write to the analyze-context/session/tools/compact subagents via the canonical Synapse source (propagated to generated .claude/agents and .cursor/agents copies); added accept/reject tests. run_quality_gate() passed: 7273 tests, 91.09% coverage.

- ✅ **Prompt-Cache Payload Stability for Cached MCP Resources** - COMPLETE (2026-07-23) - Audited load_context()/get_relevant_rules() call chains end-to-end and fixed genuine payload non-determinism: PYTHONHASHSEED-dependent set iteration order in ContextDetector (detected_languages/frameworks/categories_to_load) and equal-mtime glob-order ties in recent_artifacts_context.py/recent_ingested_sources_context.py, both now explicitly sorted. Added audit_cache_payload_stability()/check_cache_payload_stability() (new pre_commit_cache_payload_audit.py), wired into run_quality_gate()'s quality check so future volatile-content regressions (datetime.now, time.time, uuid1/4, getpid, raw ISO timestamps) in the two cache-hinted resource handler files fail the gate automatically. 13 new tests; 91.11% coverage; quality gate green twice consecutively (stable).

- ✅ **Tool-Invocation Telemetry Log (PARTIAL, reopened)** - COMPLETE (2026-07-23) - <!-- memory_type: status -->

- ✅ **Tool-Invocation Telemetry Log to Strengthen Skill-Crystallization Signal** - COMPLETE (2026-07-23) - Added a redacted, session-scoped, append-only tool-invocation telemetry log (ToolInvocationEntry model + WAL append path reusing wal_atomic_write_bytes) exposed via memory_wal(operation=\"tool_invocations\"), wired into the existing mcp_tool_wrapper dispatch interception point, and cited as an additional evidence source in analyze-tools.md (all three mirrors). Reopened after review found _run_tool_with_telemetry() mislabeled cancelled tool calls as successful; fixed by detecting the CANCELLED_RESPONSE_JSON sentinel and recording error/CancelledError instead, matching the sibling record_usage_finish path. Follow-up review found no further gaps.

- ✅ **Embedding-Based Relevance Scoring for Context Load/Compaction Gating** - COMPLETE (2026-07-23) - Added src/cortex/tools/context/relevance_ranking.py (rank_candidates_by_relevance/reorder_by_relevance, Pydantic RankedCandidate, cosine+BM25 blend mirroring hybrid_rank, fail-open) and wired it into l0_identity._truncate_to_budget and l2_on_demand._truncate_paragraphs behind CORTEX_RELEVANCE_RANKING_ENABLED (default disabled). 25 new tests (17 unit + 8 integration), 91.15% coverage, quality gate green.

- ✅ **Git-Backed Sandboxed Self-Modification Proposal Tool** - COMPLETE (2026-07-23) - Added propose_framework_optimization MCP tool: creates an isolated detached git worktree (git worktree add --detach), applies proposed .cortex/synapse/ or .cortex/rules/ changes with a lexical + resolved-path allowlist check (rejects traversal/absolute paths before any write), self-tests changed files (JSON structural validation, YAML-frontmatter validation, file-size limit), and on pass returns a difflib-generated unified diff + rationale to the caller. Guaranteed try/finally worktree teardown tested under a forced mid-run exception. No code path calls git push or gh pr create (grepped + dedicated test) — human approval remains a separate, explicit step. 44 new tests, 91.18% project coverage, quality gate green. Tool budget bumped 13->14 (categories.py, docs/api/tools.md, tool-inventory.json, README.md, AGENTS.md, governance test) per this repo's documented process for standalone-tool additions.

- ✅ **Task-Level Stuck-Loop Constraints Monitor Beyond MCP Circuit Breaker** - COMPLETE (2026-07-23) - Added a task-level no-progress detector (src/cortex/core/no_progress_monitor.py: AttemptRecord, detect_no_progress, build_report_message) distinct from the MCP-transport circuit breaker. Subagent prompts (fix-tests, fix-quality, implement-code across .claude/agents, .cursor/agents, .cortex/synapse/cursor-agents) now write attempt_history via pipeline_handoff and check the detector before retrying, pausing per the existing circuit-breaker report format when tripped. shared-conventions.md documents the distinction. 23 new tests, 100% coverage on new module, repo-wide 91.19%, no regressions.

- ✅ **Remove Cursor IDE support and duplications** - COMPLETE (2026-07-23) - Removed all Cursor IDE integration and .cursor/ duplication across source, tests, and docs; added automatic cleanup of leftover .cursor/ artifacts in any host project on server startup. Full suite green (7384 passed, 1 pre-existing unrelated failure).
Added a session-scoped, append-only tool-invocation telemetry log (src/cortex/memory/wal.py ToolInvocationLog, src/cortex/core/mcp_tool_telemetry.py) hooked into the existing mcp_tool_wrapper dispatch site, exposed via memory_wal(operation="tool_invocations"), and cited by analyze-tools.md as a new consolidation-candidate evidence source. Review gate reopened the plan: cancelled tool calls are currently mislabeled as success in the new log (src/cortex/core/mcp_stability.py:_run_tool_with_telemetry) -- fix tracked in the plan's Review Follow-Up Gaps section.

## Completed Work (2026-07-22)

- ✅ **Session Runtime Token-Spend Guard** - COMPLETE (2026-07-22) - Added a runtime token-spend guard to session() tracking actual tokens consumed by tool-call activity within the current session, distinct from the existing static token_budget_status. New SessionSpendStatus/SessionSpendSummary models mirror the TokenBudgetStatus pattern; SessionLog gained cumulative_spend_tokens + record_spend_tokens() (backward-compatible, corruption-tolerant); two call sites instrumented (manage_file read/write, session() brief token_count); calculate_health_summary() exposes the new spend field; add_spend_suggestions() warns via session_suggestions when spend crosses warning/over_budget thresholds. Warn-only, purely additive. 19 new tests (boundary values, accumulation, legacy/corrupted-log tolerance, suggestion text, single-increment-per-call, end-to-end integration); quality gate green at 91.09% coverage.

- ✅ **Session Optimization 2026-07-22T16-42 [analyses/analysis-session-optimization-2026-07-22t16-42-2026-07-22.md]** - COMPLETE (2026-07-22) - [Session Optimization 2026-07-22T16-42](analyses/analysis-session-optimization-2026-07-22t16-42-2026-07-22.md) — Session analysis for Session Optimization 2026-07-22T16-42 (2026-07-22); decisions and follow-ups recorded.

- ✅ **Pipeline Handoff op_init/op_clear Idempotency Fix** - COMPLETE (2026-07-22) - <!-- memory_type: milestone -->
Closed the remaining pipeline_handoff phase-state-loss investigation: `op_clear` (`pipeline_handoff_io.py`/`pipeline_handoff.py`) was wiping ALL phases instead of respecting the `phase` argument passed to it, compounding the earlier `op_init` non-idempotency bug fixed on 2026-07-21. Both call paths fixed; multi-root-cause investigation now fully resolved and archived at `.cortex/plans/archive/Investigations/investigate-pipeline-handoff-phase-state-loss-during-long-running-subagent-calls.md`.

## Completed Work (2026-07-21)

- **Summary (2026-07-21)** - 4 entries archived.

## Completed Work (2026-07-20)

- **Summary (2026-07-20)** - 9 entries archived.

## Completed Work (2026-07-19)

- **Summary (2026-07-19)** - 1 entries archived.

## Completed Work (2026-06-30)

- **Summary (2026-06-30)** - 1 entries archived.

## Completed Work (2026-06-25)

- **Summary (2026-06-25)** - 1 entries archived.

## Completed Work (2026-06-24)

- **Summary (2026-06-24)** - 1 entries archived.

## Completed Work (2026-06-23)

- **Summary (2026-06-23)** - 1 entries archived.

## Completed Work (2026-05-08)

- **Summary (2026-05-08)** - 1 entries archived.

## Completed Work (2026-05-04)

- **Summary (2026-05-04)** - 1 entries archived.

## Completed Work (2026-05-03)

- **Summary (2026-05-03)** - 1 entries archived.

## Completed Work (2026-04-29)

- **Summary (2026-04-29)** - 1 entries archived.

## Completed Work (2026-04-27)

- **Summary (2026-04-27)** - 1 entries archived.

## Completed Work (2026-04-26)

- **Summary (2026-04-26)** - 1 entries archived.

## Completed Work (2026-04-25)

- **Summary (2026-04-25)** - 1 entries archived.

## Completed Work (2026-04-24)

- **Summary (2026-04-24)** - 1 entries archived.

## Completed Work (2026-04-23)

- **Summary (2026-04-23)** - 1 entries archived.

## Completed Work (2026-04-22)

- **Summary (2026-04-22)** - 1 entries archived.

## Completed Work (2026-04-20)

- **Summary (2026-04-20)** - 1 entries archived.

## Completed Work (2026-04-21)

- **Summary (2026-04-21)** - 1 entries archived.

## Completed Work (2026-04-19)

- **Summary (2026-04-19)** - 1 entries archived.

## Completed Work (2026-04-18)

- **Summary (2026-04-18)** - 1 entries archived.

## Completed Work (2026-04-17)

- **Summary (2026-04-17)** - 1 entries archived.

## Completed Work (2026-04-16)

- **Summary (2026-04-16)** - 1 entries archived.

## Completed Work (2026-04-15)

- **Summary (2026-04-15)** - 1 entries archived.

## Completed Work (2026-04-14)

- **Summary (2026-04-14)** - 1 entries archived.

## Completed Work (2026-04-12)

- **Summary (2026-04-12)** - 1 entries archived.

## Completed Work (2026-04-13)

- **Summary (2026-04-13)** - 1 entries archived.

## Completed Work (2026-04-11)

- **Summary (2026-04-11)** - 1 entries archived.

## Completed Work (2026-04-10)

- **Summary (2026-04-10)** - 1 entries archived.

## Completed Work (2026-04-09)

- **Summary (2026-04-09)** - 1 entries archived.

## Completed Work (2026-04-08)

- **Summary (2026-04-08)** - 1 entries archived.

## Completed Work (2026-04-07)

- **Summary (2026-04-07)** - 1 entries archived.

## Completed Work (2026-04-06)

- **Summary (2026-04-06)** - 1 entries archived.

## Completed Work (2026-04-04)

- **Summary (2026-04-04)** - 1 entries archived.

## Completed Work (2026-04-03)

- **Summary (2026-04-03)** - 1 entries archived.

## Completed Work (2026-04-02)

- **Summary (2026-04-02)** - 1 entries archived.

## Completed Work (2026-04-01)

- **Summary (2026-04-01)** - 1 entries archived.

## Completed Work (2026-03-31)

- **Summary (2026-03-31)** - 1 entries archived.

## Completed Work (2026-03-30)

- **Summary (2026-03-30)** - 1 entries archived.

## Completed Work (2026-03-29)

- **Summary (2026-03-29)** - 1 entries archived.

## Completed Work (2026-03-28)

- **Summary (2026-03-28)** - 1 entries archived.

## Completed Work (2026-03-27)

- **Summary (2026-03-27)** - 1 entries archived.

## Completed Work (2026-03-26)

- **Summary (2026-03-26)** - 1 entries archived.

## Completed Work (2026-03-25)

- **Summary (2026-03-25)** - 1 entries archived.

## Completed Work (2026-03-24)

- **Summary (2026-03-24)** - 1 entries archived.

## Completed Work (2026-03-23)

- **Summary (2026-03-23)** - 1 entries archived.

## Completed Work (2026-03-22)

- **Summary (2026-03-22)** - 1 entries archived.

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

Next roadmap item: **[Fast-Forward vs. Step-by-Step Planning Modes](../plans/archive/Other/fast-forward-vs-step-by-step-modes.md)** (see [roadmap.md](roadmap.md) pending plans).

## Recent Changes

CodeGraph integration (2026-06-30): added `setup_codegraph` setup prompt with visibility gated on `memory_bank_initialized and not codegraph_configured`; `ProjectConfigStatus.codegraph_configured` checks `.cursor/mcp.json` and `.mcp.json`; `.codegraph/` added to `.gitignore`.

CI quality gate green (2026-06-23): synapse scripts fully typed (99 pyright errors resolved across 8 files); docs gate test uses concrete types instead of Any; test_phase3 and test_phase4 stale dates fixed.

Refactor in progress (2026-04-14): split `session/brief.py` and `optimization/handlers.py` into `brief_cap.py`, `brief_loaders.py`, `context_appenders.py`, and `context_loaders.py`; compatibility symbols in `handlers.py` were retained for existing tests while finishing structural debt cleanup.

Memory-bank guardrail (2026-04-01): when `roadmap_progress_consistency` fails, never create synthetic reconciliation/verification backlog entries. Only keep concrete, implementation-ready roadmap items tied to real deliverables.

Synapse sync timing (2026-03-28): submodule update runs when lazy prompts first register, after `resolve_project_root_async`, aligning sync with MCP roots (not only process CWD).

MCP startup Synapse sync (2026-03-29): dirty submodule worktrees are stashed around `git pull --ff-only origin main` inside `.cortex/synapse` (replacing superproject `git submodule update --init --recursive`); structured outcomes cover stash/push/pop edge cases; see AGENTS.md and `docs/guides/troubleshooting.md` MCP preflight.

Submodule hygiene for commits (2026-03-20): `pre_commit_submodule_guard` blocks Phase A when a submodule worktree is dirty or the gitlink is out of sync; covered by `test_pre_commit_submodule_guard.py` and pre-commit tool fixture patches.

Blocker (2026-02-09): Plan prompt and memory-bank-updater now mandate register_plan_in_roadmap for new plan entry to prevent roadmap corruption. Commit (2026-02-09): rules manager initialize mock, manage_file metadata test with usage-context patches; 3702 tests, 90.36% coverage.

## Next Steps

See [roadmap.md](roadmap.md).
