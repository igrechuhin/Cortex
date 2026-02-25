# Tool Optimization Mapping (Low-Usage Tools)

**Status**: Step 2 deliverable (plan: optimize-tools-from-usage)  
**Created**: 2026-02-23

## Purpose

Map each tool below the usage threshold (≤5 calls in 90 days) to an action: **keep**, **deprecate** (redirect to consolidated tool or resource), or **consolidate** (remove standalone; behavior only via consolidated entry point).

## Mapping Table

| Tool | Action | Target / Notes |
|------|--------|----------------|
| check_task_available_lock | **keep** | Phase 58 multi-agent task locking; required for task-claim flows. |
| claim_task_lock | **keep** | Phase 58; critical for multi-agent coordination. |
| release_task_lock | **keep** | Phase 58; critical for multi-agent coordination. |
| list_active_tasks | **keep** | Phase 58; discovery of locked tasks. |
| get_plan | **keep** | Plan discovery and content; used by create-plan and implement workflows (see docs/api/tools.md). |
| list_plans | **keep** | Plan discovery; used before create_plan and in implement (roadmap/plan steps). |
| session_register | **keep** | Session lifecycle; may be used by clients for registration. |
| session_deregister | **keep** | Session lifecycle; may be used by clients for deregistration. |
| remove_roadmap_entry | **keep** | Memory bank discipline; implement/commit use it for safe single-entry roadmap updates (see memory-bank-updater, AGENTS.md). |
| append_active_context_entry | **keep** | Memory bank discipline; implement and complete_plan use it for safe activeContext updates (memory-bank-updater, AGENTS.md). |
| get_session_tool_anomalies | **removed** (pruned) | Use `query_usage(query_type="anomalies", hours=24)`. No longer in MCP tool list. |
| run_tool_optimization_workflow | **removed** (pruned) | Use `query_usage(query_type="unused")` and `query_usage(query_type="recommendations")` and [tool-optimization-baseline](tool-optimization-baseline.md). No longer in MCP tool list. |
| quick_start, quality_check, safe_manage_file, suggest_workflow | **consolidated** (2026-02-25) | Use `agent_workflow(operation="quick_start" or "quality_check" or "safe_manage_file" or "suggest_workflow", ...)`. Saves 3 tool slots. |

## Summary

- **Keep**: 10 tools (task locking ×4, plan ×2, session ×2, roadmap ×1, activeContext ×1).
- **Removed (pruned)**: 2 tools (`get_session_tool_anomalies`, `run_tool_optimization_workflow`) — no longer registered; use `query_usage` alternatives above.
- **Consolidated**: 4 tools → 1 (`agent_workflow`) — quick_start, quality_check, safe_manage_file, suggest_workflow.

## Done

1. Both tools removed from MCP registration (pruning); tool count reduced by 2.
2. analyze.md and callers use `query_usage(query_type="anomalies", hours=24)`.

## High-error symbols (not MCP tools)

The anomaly report (`query_usage(query_type="anomalies", hours=24)`) may list **AsyncMock** or **_execute_transclusion_resolution** as high-error. These are not MCP tools:

- **AsyncMock**: Test mock (e.g. in `test_fix_markdown_lint.py`, `conftest.py`); usage events from test runs. No MCP action.
- **_execute_transclusion_resolution**: Internal transclusion path; may appear in usage events. No MCP action.

Optionally filter these from the anomaly report in a future change; documenting here avoids treating them as tools to deprecate.

## Resource vs tool audit (Step 7, 2026-02-24)

Tool consolidation plan Step 7 verified that all `*_resource` endpoints are registered only via `@mcp.resource()` (not also as `@mcp.tool()`). No double-registrations were found; resources do not consume tool slots. A regression test enforces this: `TestNoResourceDoubleRegisteredAsTool::test_no_function_has_both_mcp_tool_and_mcp_resource` in `tests/unit/test_mcp_stability_timeouts.py`.

## References

- [Tool optimization baseline](tool-optimization-baseline.md)
- Plan: `.cortex/plans/plan-optimize-tools-from-usage.md`
- Plan: `.cortex/plans/session-optimization-tools-set-optimization-from-usage-data.md` (tool consolidation 64→24)
