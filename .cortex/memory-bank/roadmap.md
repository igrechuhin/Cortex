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
- **Phase 57: Evaluation-Driven Tool Improvement** - IN PROGRESS - Remaining work: extend the evaluation task suite, add evaluation dashboards, and implement automated tool description optimization and A/B testing on top of the existing evaluation framework and error-pattern tooling. Plan: .cortex/plans/phase-57-evaluation-driven-tool-improvement.md.
- **Reference: Compound engineering alignment** - Plan: .cortex/plans/compound-engineering-alignment-cortex.md
- **Reference: Phase 58 multi-agent specialization** - Plan: .cortex/plans/phase-58-multi-agent-specialization-task-locking.md
- **Reference: Phase 9 excellence** - Plan: .cortex/plans/phase-9-excellence-98.md
- **Reference: Investigate execute_pre_commit_checks failure (2026-02-17)** - Plan: .cortex/plans/phase-investigate-execute_pre_commit_checks-failure-20260217-201854.md
- **Reference: Investigate fix_markdown_lint failure (2026-02-16)** - Plan: .cortex/plans/phase-investigate-fix_markdown_lint-failure-20260216-204350.md
- **Reference: Session Optimization load context and test typing** - Plan: .cortex/plans/session-optimization-load-context-and-test-typing.md
- **Session Optimization: Testing Standards and Code Quality Improvements (2026-02-19 Analysis)** - PENDING - Improve testing standards compliance and code quality workflow: add prompt reminders for private API testing prohibition and proactive helper extraction, add testing standards review step, review type checker configuration. Plan: .cortex/plans/session-optimization-testing-standards-and-code-quality-improvements-2026-02-19-analysis.md
- **Promote response_format Literal to Pydantic Enum** - PENDING - Replace Literal["concise", "detailed"] with ResponseFormat(str, Enum) across MCP tools for better type safety and consistency with project patterns. Plan: .cortex/plans/promote-response-format-to-pydantic-enum.md
- **Session Optimization: Analyze 2026-02-19 Follow-ups** - PENDING - Implement load_context budget examples, memory-bank MCP-only edit reminders, and roadmap sync guidance from end-of-session analysis. Plan: .cortex/plans/session-optimization-analyze-2026-02-19-follow-ups.md
- **Session Optimization: Step 12.7 MCP Connection Stability Enhancements** - PENDING - Enhance MCP connection stability for Step 12.7 (tests with coverage validation) in the commit pipeline to prevent commit blocks due to connection closure during long-running test execution. Plan: .cortex/plans/session-optimization-step-12-7-mcp-connection-stability-enhancements.md.
- **Promote load_context depth Literal to Pydantic Enum** - PENDING - Replace Literal["metadata_only", "summary", "full"] with ContextDepth(str, Enum) for load_context depth parameter; align with OperationStatus/ResponseFormat pattern. Plan: .cortex/plans/promote-load-context-depth-to-pydantic-enum.md.
- **Encourage enums for all fixed-set fields in Python Pydantic standards** - PENDING - Update python-pydantic-standards.mdc to encourage enums (or project enums) for all fixed-set fields (status, priority, state, etc.), not only status; align with python-coding-standards and DRY.
