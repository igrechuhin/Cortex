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

- **Claude-mem ideas for Cortex** - PENDING - Plan: .cortex/plans/claude-mem-ideas-for-cortex.md.
- **Claude-mem inspired improvements (usage search, observations, progressive disclosure)** - PENDING - Plan: .cortex/plans/claude-mem-inspired-improvements.md.
- **Conditional prompt registration** - PENDING - Only show setup prompts when project not fully configured. Plan: .cortex/plans/conditional-prompt-registration.md.
- **Make fix_markdown_lint report progress like tests tool** - PENDING - Progress reporting for markdown linting. Plan: .cortex/plans/fix-markdown-lint-progress-like-tests.md.
- **Phase 49: Introduce Anthropic advanced tool use** - IN PROGRESS - Plan: .cortex/plans/phase-49-introduce-anthropic-advanced-tool-use.md.
- **Phase 9: Excellence 98** - PENDING - Plan: .cortex/plans/phase-9-excellence-98.md.
- **Quality gate: commit pipeline spelling gap** - PENDING - Plan: .cortex/plans/quality-gate-commit-pipeline-spelling-gap.md.
- **Refactor setup prompts (simplify to 3)** - PENDING - Simplify from 4 to 3 prompts. Plan: .cortex/plans/refactor-setup-prompts.md.
- **Type cleanup inventory (Phase 53)** - PENDING - Inventory of dict[str, object], list[object], TypedDict, Any. Plan: .cortex/plans/type-cleanup-inventory.md.
- **Test Fixture Validation and Maintenance** - PENDING - Implement test fixture validation and maintenance mechanisms to prevent test failures caused by incomplete mock configurations. Addresses session optimization recommendations: fixture validation, documentation, and maintenance protocol.
- **Session Optimization: Commit Pipeline Improvements** - PENDING - Implement improvements to commit pipeline based on end-of-session analysis: async test validation, early markdown lint validation, markdown formatting guidelines, git SSL documentation, test maintenance checklist, push strategy improvements; plus (2026-02-07) integration test schema alignment, markdown lint scope clarification, memory-bank write quality. Plan: .cortex/plans/session-optimization-commit-pipeline-improvements-2026-02-07.md.
- **Compound engineering alignment (Cortex MCP)** - PENDING - Align Cortex with compound-engineering goal (each unit of work makes the next easier); adopt ideas from EveryInc compound-engineering-plugin; document Plan→Work→Review→Compound loop; add compound checklist to prompts; reduce recurring friction. Plan: .cortex/plans/compound-engineering-alignment-cortex.md.
- **MCP idempotent resource: project root path** - PENDING - Add an idempotent MCP resource that resolves and provides the project root path as a centralized entry point (e.g. cortex://project/root). Plan: .cortex/plans/mcp-idempotent-project-root-resource.md.
- **Load context when agent encounters problem / fix path** - PENDING - Require agents to load context (and rules) when fixing so they follow project rules and guidelines. Plan: .cortex/plans/session-optimization-load-context-on-problem-fix-path-2026-02-09.md.
- **Session optimization: roadmap section removal and roadmap_sync clarity** - PENDING - Safer roadmap section removal and roadmap_sync unlinked_plans clarity for archive.
- **Reconsider Memory Bank Structure and File Responsibilities** - PENDING - Define canonical memory bank file set and single-responsibility per file; one DRY spec; align schema, path_resolver, template, rules, and docs. Plan: .cortex/plans/reconsider-memory-bank-structure.md
