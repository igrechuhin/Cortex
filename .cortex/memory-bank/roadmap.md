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
- **Encourage enums for all fixed-set fields in Python Pydantic standards** - PENDING - Update python-pydantic-standards.mdc to encourage enums (or project enums) for all fixed-set fields (status, priority, state, etc.), not only status; align with python-coding-standards and DRY.
