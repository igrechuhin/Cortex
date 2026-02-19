# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- [Phase: Investigate tool_raising_json_error MCP Tool Failure](.cortex/plans/phase-investigate-tool_raising_json_error-failure-20260219-203414.md) - ASAP (PLANNING) - Investigate and fix MCP tool failure that occurred during commit procedure - Tool: `tool_raising_json_error`, Error: JSONDecodeError - Impact: Commit procedure blocked - Target completion: 2026-02-19

- [Phase: Investigate tool_raising_json_error MCP Tool Failure](.cortex/plans/phase-investigate-tool_raising_json_error-failure-20260219-202641.md) - ASAP (PLANNING) - Investigate and fix MCP tool failure that occurred during commit procedure - Tool: `tool_raising_json_error`, Error: JSONDecodeError - Impact: Commit procedure blocked - Target completion: 2026-02-19

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
- **Phase 57: Evaluation-Driven Tool Improvement** - IN PROGRESS - Remaining work: extend the evaluation task suite, add evaluation dashboards, and implement automated tool description optimization and A/B testing on top of the existing evaluation framework and error-pattern tooling. Plan: .cortex/plans/phase-57-evaluation-driven-tool-improvement.md.
- **Session Optimization: load_context Budget and Test Type Narrowing** - PENDING - Document non-zero load_context budget for non-trivial tasks in implement/fix prompts; document JsonValue narrowing in tests (testing/type rules).
- **Session Optimization: MCP Connection Stability and Fallback Script Improvements** - PENDING - Improve MCP connection stability during commit pipeline and fix fallback script compatibility issues. Plan: .cortex/plans/session-optimization-mcp-connection-stability-and-fallback-script-improvements.md.
- **Session Optimization: Progress Entry Validation and Memory Bank Write Discipline** - PENDING - Reduce progress entry typos and enforce manage_file-only for memory-bank writes (from 2026-02-18 analysis). Plan: .cortex/plans/session-optimization-progress-entry-validation-and-memory-bank-write-discipline.md.
- **Session Optimization: Analyze 2026-02-18 Follow-ups** - PENDING - Follow-ups from 2026-02-18 analysis: Step 12/MCP stability, load_context budgets, manage_file contract. Plan: .cortex/plans/session-optimization-analyze-2026-02-18-follow-ups.md.
- **Session Optimization: Progress Entry Validation and Write Quality (2026-02-18 Analysis)** - PENDING - Progress entry format validation and write-quality guidance from 2026-02-18 analysis; reduce typos in complete_plan/append_progress_entry. Plan: .cortex/plans/session-optimization-progress-entry-validation-2026-02-18-analysis.md.
- **Reference: Compound engineering alignment** - Plan: .cortex/plans/compound-engineering-alignment-cortex.md
- **Reference: Phase 58 multi-agent specialization** - Plan: .cortex/plans/phase-58-multi-agent-specialization-task-locking.md
- **Reference: Phase 9 excellence** - Plan: .cortex/plans/phase-9-excellence-98.md
- **Reference: Investigate execute_pre_commit_checks failure (2026-02-17)** - Plan: .cortex/plans/phase-investigate-execute_pre_commit_checks-failure-20260217-201854.md
- **Reference: Investigate fix_markdown_lint failure (2026-02-16)** - Plan: .cortex/plans/phase-investigate-fix_markdown_lint-failure-20260216-204350.md
- **Reference: Session Optimization load context and test typing** - Plan: .cortex/plans/session-optimization-load-context-and-test-typing.md
- **Session Optimization: Memory bank write discipline (2026-02-19 analysis)** - PENDING - Reinforce manage_file-only for roadmap edits in implement/analyze prompts and memory-bank-updater. Plan: .cortex/plans/session-optimization-memory-bank-write-discipline-2026-02-19-analysis.md
- **Session Optimization: Testing Standards and Code Quality Improvements (2026-02-19 Analysis)** - PENDING - Improve testing standards compliance and code quality workflow: add prompt reminders for private API testing prohibition and proactive helper extraction, add testing standards review step, review type checker configuration.
- **Promote response_format Literal to Pydantic Enum** - PENDING - Replace Literal["concise", "detailed"] with ResponseFormat(str, Enum) across MCP tools for better type safety and consistency with project patterns.
