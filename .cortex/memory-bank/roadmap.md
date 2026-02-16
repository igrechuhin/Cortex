# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Session Optimization Plans (2026-02-03)

### Session Optimization Plans (2026-02-02)

### Session Optimization Plans (2026-02-01)

### Features & Enhancements

- **Phase 49: Introduce Anthropic advanced tool use** - IN PROGRESS - Plan: .cortex/plans/phase-49-introduce-anthropic-advanced-tool-use.md.
- **Phase 55: Lightweight Think Tool Enhancement** - PENDING - Add minimal think(thought) tool alongside sequentialthinking; add domain-specific thinking examples to commit, implement, and plan prompts for better reasoning. Plan: .cortex/plans/phase-55-lightweight-think-tool.md.
- **Phase 56: Session Compaction Workflow** - PENDING - Automatic compaction for activeContext/progress, structured JSON session handoff, progressive summarization (daily/weekly/monthly tiers), compact_session tool. Plan: .cortex/plans/phase-56-session-compaction-workflow.md.
- **Phase 57: Evaluation-Driven Tool Improvement** - PENDING - Build evaluation framework for tool effectiveness (success rates, token efficiency, error patterns); 20+ eval tasks for real workflows; automated tool description optimization using Claude; A/B testing for improvements. Plan: .cortex/plans/phase-57-evaluation-driven-tool-improvement.md.
- **Phase 58: Multi-Agent Specialization and Task Locking** - PENDING - Role-based context loading (quality/feature/test/docs agents), task locking for roadmap items to prevent duplicate work, concurrent session visibility, agent role profiles. Plan: .cortex/plans/phase-58-multi-agent-specialization-task-locking.md.
- **Session Optimization: Path Resolver and Context Loading (2026-02-11)** - PENDING - Path resolver rule for tests; include roadmap/activeContext for session/commit-pipeline tasks in load_context/implement guidance.
- **Session Optimization: Rules and Context Loading Follow-Ups (2026-02-12)** - PENDING - Follow-up session optimization plan to fix rules manager → optimization.rules.rules_folder integration, clarify Synapse Pydantic standards ownership, improve memory-bank schema extension guidance, and strengthen guardrails for zero-budget/zero-files load_context calls.
- **Session Optimization: Rules and Context Loading Follow-Ups (2026-02-12 Analysis)** - PENDING - Follow-up work from the 2026-02-12 end-of-session analysis to improve watcher testing rules, task-type context budgets, rules indexing, and zero-budget/zero-files load_context guardrails.
- **Session Optimization: Pydantic Rule Visibility and Rule Discovery (2026-02-12 Analysis)** - PENDING - Ensure Pydantic-for-params rule is visible when implementing/refactoring MCP tools; add implement prompt + AGENTS/CLAUDE bullet and rule-discovery fallback so agents apply it without user reminder.
- **Session Optimization: Quality gate skip documentation when environment unavailable** - PENDING - Document when quality gate can be skipped for doc-only sessions when execute_pre_commit_checks fails due to env (ruff/black not in path or type_check unavailable); implement prompt + optional troubleshooting/AGENTS.
- **Session Optimization: Testing Coverage Documentation and Planning (2026-02-16 Analysis)** - PENDING - Document coverage expectations for consolidated tools (90%+ acceptable, 95%+ ideal), add test planning checklist to implement prompt, document integration test pattern for handler dispatch tools.
- **Session Optimization: Test Coverage and Development Workflow Improvements** - PENDING - Improve coverage gap identification, proactive file size enforcement, test coverage guidance, and reduce test development friction based on 2026-02-16 session analysis
- **Session Optimization: Commit Pipeline Context Loading and Helper Module Pattern** - PENDING - Optimize commit pipeline context loading (reduce token usage 40-60%) and document helper module extraction pattern for code quality violations
