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
- **Load context when agent encounters problem / fix path** - PENDING - Require agents to load context (and rules) when fixing so they follow project rules and guidelines. Plan: .cortex/plans/session-optimization-load-context-on-problem-fix-path-2026-02-09.md.
- **Reconsider Memory Bank Structure and File Responsibilities** - PENDING - Define canonical memory bank file set and single-responsibility per file; one DRY spec; align schema, path_resolver, template, rules, and docs. Plan: .cortex/plans/reconsider-memory-bank-structure.md
- **Session Optimization: Roadmap Completed-Section Cleanup** - PENDING - Clean up legacy completed sections in roadmap.md by migrating their content into activeContext.md/progress.md and removing the completed block using the documented single-block edit pattern, then validating with roadmap_sync and timestamps.
- **Session Optimization: Pydantic v2 Context & Rules Improvements** - PENDING - Session optimization follow-up to anchor Pydantic v2 guidance in memory bank and Synapse rules, and harden load_context usage/analytics for refactor tasks so Pydantic-specific refactors always have the right context.
- **Session Optimization: Context & Usage Analytics Improvements (2026-02-11)** - PENDING - Improve context defaults and usage-analytics/test-failure observability based on 2026-02-11 end-of-session analysis. Plan: .cortex/plans/session-optimization-context-usage-analytics-improvements-2026-02-11.md.
- **Phase 50: Tool Consolidation and Response Format Optimization** - PENDING - Reduce tool count from 53+ to ~30, add response_format (concise/detailed) parameter to verbose tools, merge overlapping tools following Anthropic's guidance. Plan: .cortex/plans/phase-50-tool-consolidation-response-format.md.
- **Phase 51: Just-in-Time Context with Section-Level Loading** - PENDING - Transform context loading to metadata-first with section-level drill-down; hybrid retrieval strategy (always-load essentials + on-demand sections); 90%+ token savings for context map. Plan: .cortex/plans/phase-51-just-in-time-context-section-loading.md.
- **Phase 52: Consistent Helpful Error Responses** - PENDING - Standardize all tool error responses with ToolErrorResponse schema: what went wrong, suggestion, example of correct usage, fuzzy matching for did-you-mean. Plan: .cortex/plans/phase-52-consistent-helpful-error-responses.md.
- **Phase 54: Session Start Initializer Pattern** - PENDING - Single session_start tool replacing 3-5 manual orientation calls; returns SessionBrief (current focus, next work item, health check, git status) in less than 1000 tokens. Plan: .cortex/plans/phase-54-session-start-initializer-pattern.md.
- **Phase 55: Lightweight Think Tool Enhancement** - PENDING - Add minimal think(thought) tool alongside sequentialthinking; add domain-specific thinking examples to commit, implement, and plan prompts for better reasoning. Plan: .cortex/plans/phase-55-lightweight-think-tool.md.
- **Phase 56: Session Compaction Workflow** - PENDING - Automatic compaction for activeContext/progress, structured JSON session handoff, progressive summarization (daily/weekly/monthly tiers), compact_session tool. Plan: .cortex/plans/phase-56-session-compaction-workflow.md.
- **Phase 57: Evaluation-Driven Tool Improvement** - PENDING - Build evaluation framework for tool effectiveness (success rates, token efficiency, error patterns); 20+ eval tasks for real workflows; automated tool description optimization using Claude; A/B testing for improvements. Plan: .cortex/plans/phase-57-evaluation-driven-tool-improvement.md.
- **Phase 58: Multi-Agent Specialization and Task Locking** - PENDING - Role-based context loading (quality/feature/test/docs agents), task locking for roadmap items to prevent duplicate work, concurrent session visibility, agent role profiles. Plan: .cortex/plans/phase-58-multi-agent-specialization-task-locking.md.
- **Session Optimization: Path Resolver and Context Loading (2026-02-11)** - PENDING - Path resolver rule for tests; include roadmap/activeContext for session/commit-pipeline tasks in load_context/implement guidance.
