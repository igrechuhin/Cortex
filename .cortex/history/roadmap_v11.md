# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

#### Tool Failure Investigations (Archive Recommended)

The following 22 investigation plans document MCP tool registration issues resolved by Phase 45 annotations). **Recommend archiving to `.cortex/plans/archive/Investigations/20262-4/`**:

- phase-investigate-analyze_session_scripts-failure-20260204-80340- phase-investigate-analyze-failure-22620475106.md
- phase-investigate-configure-failure-202620475107d
- phase-investigate-execute_pre_commit_checks-failure-20260248256.md
- phase-investigate-fix_markdown_lint-failure-2026020436d
- phase-investigate-get_context_usage_statistics-failure-202602480331.md
- phase-investigate-get_dependency_graph-failure-2026024-75114.md
- phase-investigate-get_link_graph-failure-2026020480337.md
- phase-investigate-get_memory_bank_stats-failure-202620475116md
- phase-investigate-get_structure_info-failure-20260204-8737d
- phase-investigate-get_version_history-failure-202602475115.md
- phase-investigate-list_session_scripts-failure-22620480339md
- phase-investigate-load_context-failure-2026020408337d
- phase-investigate-parse_file_links-failure-2260204-8336md
- phase-investigate-promote_session_script-failure-226204080340md
- phase-investigate-read_cache_json-failure-2026020482030.md
- phase-investigate-resolve_transclusions-failure-2026020480337.md
- phase-investigate-rollback_file_version-failure-2026024075115d
- phase-investigate-rules-failure-202620475121d
- phase-investigate-suggest_tool_improvements-failure-202602480340 phase-investigate-validate-failure-20260204075123d
- phase-investigate-write_cache_json-failure-202620431## Session Optimization Plans (2026023 **Analyze prompt and memory bank responsibilities** - PENDING - Plan: .cortex/plans/session-optimization-analyze-prompt-memory-bank-responsibilities-2026-2-3.
- **Connection closed follow-ups** - PENDING - Plan: .cortex/plans/session-optimization-connection-closed-follow-ups-22603md.
- **Roadmap full-content enforcement** - PENDING - Plan: .cortex/plans/session-optimization-roadmap-full-content-enforcement.md.

### Session Optimization Plans (2026-2

- **Implement load_context at step start, rules fallback, and task-type token budget** - PENDING - Plan: .cortex/plans/session-optimization-implement-load-context-and-rules-fallback.md.
- **Implement prompt memory bank and function length** - PENDING - Plan: .cortex/plans/session-optimization-implement-prompt-memory-bank.md.
- **Plan Status MD036 side-effect imports** - PENDING - Plan: .cortex/plans/session-optimization-plan-status-and-side-effect-imports.md.

### Session Optimization Plans (20261)

- **Markdown corruption in progress and plans** - PENDING - Plan: .cortex/plans/session-optimization-markdown-corruption-progress-plans.md.
- **Public API, memory bank, rules** - PENDING - Plan: .cortex/plans/session-optimization-public-api-memory-bank-rules.md.
- **Sequential thinking in Cortex MCP** - PENDING - Sequential thinking tool with thought history, revisions, branches. Plan: .cortex/plans/sequential-thinking-cortex-mcp.md.

### Features & Enhancements

- **Claude-mem ideas for Cortex** - PENDING - Plan: .cortex/plans/claude-mem-ideas-for-cortex.md.
- **Claude-mem inspired improvements (usage search, observations, progressive disclosure)** - PENDING - Plan: .cortex/plans/claude-mem-inspired-improvements.md.
- **Conditional prompt registration** - PENDING - Only show setup prompts when project not fully configured. Plan: .cortex/plans/conditional-prompt-registration.md.
- **Make fix_markdown_lint report progress like tests tool** - PENDING - Progress reporting for markdown linting. Plan: .cortex/plans/fix-markdown-lint-progress-like-tests.md.
- **Phase 49: Introduce Anthropic advanced tool use** - IN PROGRESS - Plan: .cortex/plans/phase-49-introduce-anthropic-advanced-tool-use.md.
- **Phase9Excellence98** - PENDING - Plan: .cortex/plans/phase-9cellence-98.md.
- **Quality gate: commit pipeline spelling gap** - PENDING - Plan: .cortex/plans/quality-gate-commit-pipeline-spelling-gap.md.
- **Refactor setup prompts (simplify to3)** - PENDING - Simplify from4 to 3ompts. Plan: .cortex/plans/refactor-setup-prompts.md.
- **Type cleanup inventory (Phase53 - PENDING - Inventory of dict[str, object], list[object], TypedDict, Any. Plan: .cortex/plans/type-cleanup-inventory.md.
- **Test Fixture Validation and Maintenance** - PENDING - Implement test fixture validation and maintenance mechanisms to prevent test failures caused by incomplete mock configurations. Addresses session optimization recommendations: fixture validation, documentation, and maintenance protocol.
- **Session Optimization: Commit Pipeline Improvements** - PENDING - Implement improvements to commit pipeline based on end-of-session analysis: async test validation, early markdown lint validation, markdown formatting guidelines, git SSL documentation, test maintenance checklist, push strategy improvements; plus (2026-2ation test schema alignment, markdown lint scope clarification, memory-bank write quality. Plan: .cortex/plans/session-optimization-commit-pipeline-improvements-202602d.
- **Compound engineering alignment (Cortex MCP)** - PENDING - Align Cortex with compound-engineering goal (each unit of work makes the next easier); adopt ideas from EveryInc compound-engineering-plugin; document Plan→Work→Review→Compound loop; add compound checklist to prompts; reduce recurring friction. Plan: .cortex/plans/compound-engineering-alignment-cortex.md.
- **MCP idempotent resource: project root path** - PENDING - Add an idempotent MCP resource that resolves and provides the project root path as a centralized entry point (e.g. cortex://project/root). Plan: .cortex/plans/mcp-idempotent-project-root-resource.md.
