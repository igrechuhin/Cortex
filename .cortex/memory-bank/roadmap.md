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
- **Phase 57: Evaluation-Driven Tool Improvement** - IN PROGRESS - Remaining work: extend the evaluation task suite, add evaluation dashboards, and implement automated tool description optimization and A/B testing on top of the existing evaluation framework and error-pattern tooling.
- **Session Optimization: Phase 58 multi-agent follow-ups** - PENDING - Follow-ups for Phase 58 to log AgentRole in load_context session logs, extend context-effectiveness analysis with role-aware statistics, and update prompts/docs once role data is available.
- **Session Optimization: Refactoring Workflow Improvements (2026-02-17 Analysis)** - PENDING - Improve refactoring workflow to reduce fix iterations: add intermediate validation checkpoints, document type narrowing pattern, add duplicate detection step
- **Session Optimization: Rule Loading and Discovery (2026-02-18 Analysis)** - PENDING - Enforce rule loading in implement prompt, add rule discovery fallback when rules() empty, document fallback in AGENTS.md/prompt.
- **Session Optimization: load_context Budget and Test Type Narrowing** - PENDING - Document non-zero load_context budget for non-trivial tasks in implement/fix prompts; document JsonValue narrowing in tests (testing/type rules).
