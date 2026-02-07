# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next** step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- [Phase: Investigate execute_pre_commit_checks MCP Tool Failure](.cortex/plans/phase-investigate-execute_pre_commit_checks-failure-20260205-222815.md) - ASAP (PLANNING) - Investigate and fix MCP tool failure that occurred during commit procedure - Tool: `execute_pre_commit_checks`, Error: TypeError - Impact: Commit procedure blocked - Target completion: 2026-02-05

None - MCP annotations blocker resolved 2026-02-05

## Active Work (in progress)

## Future Enhancements

## Pending plans (from .cortex/plans)

### Critical Infrastructure (HIGH PRIORITY - Next)

- **Ensure proper logging for FastMCP** - PENDING - Comprehensive logging for MCP server and tool execution. Plan: .cortex/plans/ensure-proper-logging-fastmcp.md.

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

#### Tool Failure Investigations (Archive Recommended)

The following 22 investigation plans document MCP tool registration issues resolved by Phase 45 (MCP annotations). **Recommend archiving to `.cortex/plans/archive/Investigations/2026-02-04/`**:

- phase-investigate-analyze_session_scripts-failure-20260204-080340.md
- phase-investigate-analyze-failure-20260204-075106.md
- phase-investigate-configure-failure-20260204-075107.md
- phase-investigate-execute_pre_commit_checks-failure-20260204-082056.md
- phase-investigate-fix_markdown_lint-failure-20260204-082036.md
- phase-investigate-get_context_usage_statistics-failure-20260204-080331.md
- phase-investigate-get_dependency_graph-failure-20260204-075114.md
- phase-investigate-get_link_graph-failure-20260204-080337.md
- phase-investigate-get_memory_bank_stats-failure-20260204-075116.md
- phase-investigate-get_structure_info-failure-20260204-080737.md
- phase-investigate-get_version_history-failure-20260204-075115.md
- phase-investigate-list_session_scripts-failure-20260204-080339.md
- phase-investigate-load_context-failure-20260204-080337.md
- phase-investigate-parse_file_links-failure-20260204-080336.md
- phase-investigate-promote_session_script-failure-20260204-080340.md
- phase-investigate-read_cache_json-failure-20260204-082030.md
- phase-investigate-resolve_transclusions-failure-20260204-080337.md
- phase-investigate-rollback_file_version-failure-20260204-075115.md
- phase-investigate-rules-failure-20260204-075121.md
- phase-investigate-suggest_tool_improvements-failure-20260204-080340.md
- phase-investigate-validate-failure-20260204-075123.md
- phase-investigate-write_cache_json-failure-20260204-082031.md

### Session Optimization Plans (2026-02-03)

- **Analyze prompt and memory bank responsibilities** - PENDING - Plan: .cortex/plans/session-optimization-analyze-prompt-memory-bank-responsibilities-2026-02-03.md.
- **Connection closed follow-ups** - PENDING - Plan: .cortex/plans/session-optimization-connection-closed-follow-ups-2026-02-03.md.
- **Roadmap full-content enforcement** - PENDING - Plan: .cortex/plans/session-optimization-roadmap-full-content-enforcement.md.

### Session Optimization Plans (2026-02-02)

- **Implement load_context at step start, rules fallback, and task-type token budget** - PENDING - Plan: .cortex/plans/session-optimization-implement-load-context-and-rules-fallback.md.
- **Implement prompt memory bank and function length** - PENDING - Plan: .cortex/plans/session-optimization-implement-prompt-memory-bank.md.
- **Plan Status MD036 and side-effect imports** - PENDING - Plan: .cortex/plans/session-optimization-plan-status-and-side-effect-imports.md.

### Session Optimization Plans (2026-02-01)

- **Markdown corruption in progress and plans** - PENDING - Plan: .cortex/plans/session-optimization-markdown-corruption-progress-plans.md.
- **Public API, memory bank, rules** - PENDING - Plan: .cortex/plans/session-optimization-public-api-memory-bank-rules.md.
- **Sequential plan steps** - PENDING - Plan: .cortex/plans/session-optimization-sequential-plan-steps.md.

### Features & Enhancements

- **Claude-mem ideas for Cortex** - PENDING - Plan: .cortex/plans/claude-mem-ideas-for-cortex.md.
- **Claude-mem inspired improvements (usage search, observations, progressive disclosure)** - PENDING - Plan: .cortex/plans/claude-mem-inspired-improvements.md.
- **Conditional prompt registration** - PENDING - Only show setup prompts when project not fully configured. Plan: .cortex/plans/conditional-prompt-registration.md.
- **Make fix_markdown_lint report progress like tests tool** - PENDING - Progress reporting for markdown linting. Plan: .cortex/plans/fix-markdown-lint-progress-like-tests.md.
- **MCP transport HTTP/SSE analysis** - PENDING - Analyze HTTP/SSE transport options. Plan: .cortex/plans/mcp-transport-http-sse-analysis.md.
- **Phase 49: Introduce Anthropic advanced tool use** - IN PROGRESS - Plan: .cortex/plans/phase-49-introduce-anthropic-advanced-tool-use.md.
- **Phase 9: Excellence 98** - PENDING - Plan: .cortex/plans/phase-9-excellence-98.md.
- **Quality gate: commit pipeline spelling gap** - PENDING - Plan: .cortex/plans/quality-gate-commit-pipeline-spelling-gap.md.
- **Refactor setup prompts (simplify to 3)** - PENDING - Simplify from 4 to 3 prompts. Plan: .cortex/plans/refactor-setup-prompts.md.
- **Sequential thinking in Cortex MCP** - PENDING - Sequential thinking tool with thought history, revisions, branches. Plan: .cortex/plans/sequential-thinking-cortex-mcp.md.
- **Type cleanup inventory (Phase 53)** - PENDING - Inventory of dict[str, object], list[object], TypedDict, Any. Plan: .cortex/plans/type-cleanup-inventory.md.
- **Phase 18: Markdown Lint Fix Tool** - COMPLETED (archived) - Historical reference for the markdown lint fix tooling work. Plan: .cortex/plans/phase-18-markdown-lint-fix-tool.md.
- **Test Fixture Validation and Maintenance** - PENDING - Implement test fixture validation and maintenance mechanisms to prevent test failures caused by incomplete mock configurations. Addresses session optimization recommendations: fixture validation, documentation, and maintenance protocol.
