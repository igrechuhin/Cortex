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
- **Type cleanup inventory (Phase 53)** - PENDING - Inventory of dict[str, object], list[object], TypedDict, Any. Plan: .cortex/plans/type-cleanup-inventory.md.
- **Test Fixture Validation and Maintenance** - PENDING - Implement test fixture validation and maintenance mechanisms to prevent test failures caused by incomplete mock configurations. Addresses session optimization recommendations: fixture validation, documentation, and maintenance protocol.
- **Session Optimization: Commit Pipeline Improvements** - PENDING - Implement improvements to commit pipeline based on end-of-session analysis: async test validation, early markdown lint validation, markdown formatting guidelines, git SSL documentation, test maintenance checklist, push strategy improvements; plus (2026-02-07) integration test schema alignment, markdown lint scope clarification, memory-bank write quality. Plan: .cortex/plans/session-optimization-commit-pipeline-improvements-2026-02-07.md.
- **Compound engineering alignment (Cortex MCP)** - PENDING - Align Cortex with compound-engineering goal (each unit of work makes the next easier); adopt ideas from EveryInc compound-engineering-plugin; document PlanWorkReviewCompound loop; add compound checklist to prompts; reduce recurring friction. Plan: .cortex/plans/compound-engineering-alignment-cortex.md.
- **MCP idempotent resource: project root path** - PENDING - Add an idempotent MCP resource that resolves and provides the project root path as a centralized entry point (e.g. cortex://project/root). Plan: .cortex/plans/mcp-idempotent-project-root-resource.md.
- **Load context when agent encounters problem / fix path** - PENDING - Require agents to load context (and rules) when fixing so they follow project rules and guidelines. Plan: .cortex/plans/session-optimization-load-context-on-problem-fix-path-2026-02-09.md.
- **Reconsider Memory Bank Structure and File Responsibilities** - PENDING - Define canonical memory bank file set and single-responsibility per file; one DRY spec; align schema, path_resolver, template, rules, and docs. Plan: .cortex/plans/reconsider-memory-bank-structure.md
- **Session Optimization: Roadmap Completed-Section Cleanup** - PENDING - Clean up legacy completed sections in roadmap.md by migrating their content into activeContext.md/progress.md and removing the completed block using the documented single-block edit pattern, then validating with roadmap_sync and timestamps.
- **Session Optimization: Pydantic v2 Context & Rules Improvements** - PENDING - Session optimization follow-up to anchor Pydantic v2 guidance in memory bank and Synapse rules, and harden load_context usage/analytics for refactor tasks so Pydantic-specific refactors always have the right context.
- **Session Optimization: Context & Usage Analytics Improvements (2026-02-11)** - PENDING - Improve context defaults and usage-analytics/test-failure observability based on 2026-02-11 end-of-session analysis. Plan: .cortex/plans/session-optimization-context-usage-analytics-improvements-2026-02-11.md.
