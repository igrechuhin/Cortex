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
- **Plans README** - Reference. Plan: .cortex/plans/README.md
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
- **Session Optimization: MCP Connection Stability and Fallback Script Improvements** - PENDING - Improve MCP connection stability during commit pipeline and fix fallback script compatibility issues
- **Session Optimization: Progress Entry Validation and Memory Bank Write Discipline** - PENDING - Reduce progress entry typos and enforce manage_file-only for memory-bank writes (from 2026-02-18 analysis).
- **Session Optimization: Analyze 2026-02-18 Follow-ups** - PENDING - Follow-ups from 2026-02-18 analysis: Step 12/MCP stability, load_context budgets, manage_file contract.
- **Session Optimization: Progress Entry Validation and Write Quality (2026-02-18 Analysis)** - PENDING - Progress entry format validation and write-quality guidance from 2026-02-18 analysis; reduce typos in complete_plan/append_progress_entry.
- **Promote OperationStatus to str Enum** - PENDING - Replace type OperationStatus = Literal["success", "error"] with class OperationStatus(str, Enum) in core/models.py; keep JSON output unchanged. Plan: .cortex/plans/operation-status-promote-to-enum.md
