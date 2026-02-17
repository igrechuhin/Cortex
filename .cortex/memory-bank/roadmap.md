# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

- **Phase 56: Session Compaction Workflow** - IN PROGRESS (Step 1 complete) - Automatic compaction for activeContext/progress, structured JSON session handoff, progressive summarization (daily/weekly/monthly tiers), compact_session tool. Plan: .cortex/plans/archive/Phase56/phase-56-session-compaction-workflow.md.

## Pending plans (from .cortex/plans)

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Session Optimization Plans (2026-02-03)

### Session Optimization Plans (2026-02-02)

### Session Optimization Plans (2026-02-01)

### Features & Enhancements

- **Phase 49: Introduce Anthropic advanced tool use** - IN PROGRESS - Plan: .cortex/plans/phase-49-introduce-anthropic-advanced-tool-use.md.
- **Phase 57: Evaluation-Driven Tool Improvement** - PENDING - Build evaluation framework for tool effectiveness (success rates, token efficiency, error patterns); 20+ eval tasks for real workflows; automated tool description optimization using Claude; A/B testing for improvements. Plan: .cortex/plans/phase-57-evaluation-driven-tool-improvement.md.
- **Phase 58: Multi-Agent Specialization and Task Locking** - PENDING - Role-based context loading (quality/feature/test/docs agents), task locking for roadmap items to prevent duplicate work, concurrent session visibility, agent role profiles. Plan: .cortex/plans/phase-58-multi-agent-specialization-task-locking.md.
- **Session Optimization: Path Resolver and Context Loading (2026-02-11)** - PENDING - Path resolver rule for tests; include roadmap/activeContext for session/commit-pipeline tasks in load_context/implement guidance.
- **Session Optimization: Rules and Context Loading Follow-Ups (2026-02-12)** - PENDING - Follow-up session optimization plan to fix rules manager  optimization.rules.rules_folder integration, clarify Synapse Pydantic standards ownership, improve memory-bank schema extension guidance, and strengthen guardrails for zero-budget/zero-files load_context calls.
- **Session Optimization: Rules and Context Loading Follow-Ups (2026-02-12 Analysis)** - PENDING - Follow-up work from the 2026-02-12 end-of-session analysis to improve watcher testing rules, task-type context budgets, rules indexing, and zero-budget/zero-files load_context guardrails.
- **Session Optimization: Pydantic Rule Visibility and Rule Discovery (2026-02-12 Analysis)** - PENDING - Ensure Pydantic-for-params rule is visible when implementing/refactoring MCP tools; add implement prompt + AGENTS/CLAUDE bullet and rule-discovery fallback so agents apply it without user reminder.
- **Session Optimization: Quality gate skip documentation when environment unavailable** - PENDING - Document when quality gate can be skipped for doc-only sessions when execute_pre_commit_checks fails due to env (ruff/black not in path or type_check unavailable); implement prompt + optional troubleshooting/AGENTS.
- **Session Optimization: Testing Coverage Documentation and Planning (2026-02-16 Analysis)** - PENDING - Document coverage expectations for consolidated tools (90%+ acceptable, 95%+ ideal), add test planning checklist to implement prompt, document integration test pattern for handler dispatch tools.
- **Session Optimization: Test Coverage and Development Workflow Improvements** - PENDING - Improve coverage gap identification, proactive file size enforcement, test coverage guidance, and reduce test development friction based on 2026-02-16 session analysis
- **Session Optimization: Commit Pipeline Context Loading and Helper Module Pattern** - PENDING - Optimize commit pipeline context loading (reduce token usage 40-60%) and document helper module extraction pattern for code quality violations
- **Session Optimization: fix_markdown_lint Opaque Errors and Commit Fallback** - PENDING - Improve fix_markdown_lint error reporting when batch fails; document commit fallback when tool returns no rule codes. Plan: .cortex/plans/session-optimization-fix-markdown-lint-opaque-errors.md.
- **Fix Broken Progress Entry: Phase 54 Title Corruption** - PENDING - Fix corrupted entry in progress.md line 66 ("Phase 54lizer Pattern"  "Phase 54: Session Start Initializer Pattern") and extend corruption detection to catch truncation patterns. Plan: .cortex/plans/fix-progress-phase-54-corruption.md.
- **Session Optimization: pytest.ini and IDE test discovery documentation** - PENDING - Document pytest.ini design (no coverage in addopts for IDE discovery); optional implement/commit reminder for explicit --cov in full runs.
- **Plans README** - Reference. Plan: .cortex/plans/README.md
- **Add roadmap entry MCP tool** - PENDING - Reference. Plan: .cortex/plans/add-roadmap-entry-mcp-tool.md
- **Compound engineering alignment (Cortex)** - PENDING - Reference. Plan: .cortex/plans/compound-engineering-alignment-cortex.md
- **Enrich memory bank write tools with validations** - PENDING - Reference. Plan: .cortex/plans/enrich-memory-bank-write-tools-with-validations.md
- **Investigate FastMCP blocking before tool handlers** - PENDING - Reference. Plan: .cortex/plans/investigate-fastmcp-blocking-before-tool-handlers-2026-02-09.md
- **Phase 45: Add MCP annotations** - PENDING - Reference. Plan: .cortex/plans/phase-45-add-mcp-annotations.md
- **Phase 53: Investigate manage_file conflict index stale** - PENDING - Reference. Plan: .cortex/plans/phase-53-investigate-manage-file-conflict-index-stale.md
- **Phase 68: Investigate fix_quality_issues MCP connection closed** - PENDING - Reference. Plan: .cortex/plans/phase-68-investigate-fix-quality-issues-mcp-connection-closed.md
- **Phase 9: Excellence 9.8+** - PENDING - Reference. Plan: .cortex/plans/phase-9-excellence-98.md
- **Phase: Investigate commit pipeline quality gate miss** - PENDING - Reference. Plan: .cortex/plans/phase-investigate-commit-pipeline-quality-gate-miss-2026-02-07.md
- **Phase: Investigate execute_pre_commit_checks failure (20260205)** - PENDING - Reference. Plan: .cortex/plans/phase-investigate-execute_pre_commit_checks-failure-20260205-222815.md
- **Phase: Investigate execute_pre_commit_checks failure (20260209)** - PENDING - Reference. Plan: .cortex/plans/phase-investigate-execute_pre_commit_checks-failure-20260209-203054.md
- **Phase: Investigate promote_session_script failure** - PENDING - Reference. Plan: .cortex/plans/phase-investigate-promote_session_script-failure-20260211-184849.md
- **Phase: Investigate roadmap sync validator ghost references** - PENDING - Reference. Plan: .cortex/plans/phase-investigate-roadmap-sync-validator-ghost-references.md
- **Session Optimization: Commit pipeline context loading and helper module** - PENDING - Reference. Plan: .cortex/plans/session-optimization-commit-pipeline-context-loading-and-helper-module-pattern.md
- **Session Optimization: Context usage analytics followups (2026-02-11)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-context-usage-analytics-followups-2026-02-11.md
- **Session Optimization: Load context on problem fix path (2026-02-09)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-load-context-on-problem-fix-path-2026-02-09.md
- **Session Optimization: Path resolver and context loading (2026-02-11)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-path-resolver-context-loading-2026-02-11.md
- **Session Optimization: Pydantic rule visibility and rule discovery (2026-02-12 Analysis)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-pydantic-rule-visibility-and-rule-discovery-2026-02-12-analysis.md
- **Session Optimization: Quality gate skip documentation when environment unavailable** - PENDING - Reference. Plan: .cortex/plans/session-optimization-quality-gate-skip-documentation-when-environment-unavailable.md
- **Session Optimization: Roadmap completed section cleanup (2026-02-10)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-roadmap-completed-section-cleanup-2026-02-10.md
- **Session Optimization: Roadmap section removal and sync** - PENDING - Reference. Plan: .cortex/plans/session-optimization-roadmap-section-removal-and-sync.md
- **Session Optimization: Roadmap sync cleanup (2026-02-09)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-roadmap-sync-cleanup-2026-02-09.md
- **Session Optimization: Rules and context loading follow-ups (2026-02-12 Analysis)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-rules-and-context-loading-follow-ups-2026-02-12-analysis.md
- **Session Optimization: Rules context followups (2026-02-12)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-rules-context-followups-2026-02-12.md
- **Session Optimization: Sequential plan steps** - PENDING - Reference. Plan: .cortex/plans/session-optimization-sequential-plan-steps.md
- **Session Optimization: Test coverage and development workflow improvements** - PENDING - Reference. Plan: .cortex/plans/session-optimization-test-coverage-and-development-workflow-improvements.md
- **Session Optimization: Testing coverage documentation and planning (2026-02-16 Analysis)** - PENDING - Reference. Plan: .cortex/plans/session-optimization-testing-coverage-documentation-and-planning-2026-02-16-analysis.md
- **Structured planning Cortex MCP tools** - PENDING - Reference. Plan: .cortex/plans/structured-planning-cortex-mcp-tools.md
- **Test fixture validation and maintenance** - PENDING - Reference. Plan: .cortex/plans/test-fixture-validation-maintenance.md
- **Type cleanup inventory** - PENDING - Reference. Plan: .cortex/plans/type-cleanup-inventory.md
- **Session Optimization Follow-Ups: Roadmap Dedup and Plan Lifecycle** - PENDING - Follow-ups from 2026-02-17 analysis to propagate roadmap blocker deduplication and investigation-plan lifecycle alignment patterns to all roadmap writers and failure handlers. Plan: .cortex/plans/session-optimization-follow-ups-roadmap-dedup-and-plan-lifecycle.md.
- **Session Optimization Follow-Ups: Phase 57 Evaluation Framework and Context Budgets (2026-02-17)** - PENDING - Follow-ups from 2026-02-17 analysis to harden context-budget validation/zero-file safeguards, expand the Phase 57 evaluation task suite, add evaluation dashboards, and enable rules indexing for implement/analyze flows.
