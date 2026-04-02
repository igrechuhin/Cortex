# Tool Optimization Mapping (Low-Usage Tools)

**Status**: Step 2 deliverable (plan: optimize-tools-from-usage)  
**Created**: 2026-02-23  
**Updated**: 2026-02-27 (census 2026-02-27)

## Purpose

Map each tool below the usage threshold (≤5 calls in 90 days) to an action: **keep**, **deprecate** (redirect to consolidated tool or resource), or **consolidate** (remove standalone; behavior only via consolidated entry point).

## Mapping Table

| Tool | Action | Target / Notes |
|------|--------|----------------|
| check_task_available_lock | **keep** | Phase 58 multi-agent task locking; required for task-claim flows. |
| claim_task_lock | **keep** | Phase 58; critical for multi-agent coordination. |
| release_task_lock | **keep** | Phase 58; critical for multi-agent coordination. |
| list_active_tasks | **keep** | Phase 58; discovery of locked tasks. |
| get_plan | **keep** | Plan discovery and content; used by plan and do workflows (see docs/api/tools.md). |
| list_plans | **keep** | Plan discovery; used before create_plan and in implement (roadmap/plan steps). |
| session_register | **consolidated** (2026-02-27) | Use `session(operation="register", task_title=..., role=...)`. |
| session_deregister | **consolidated** (2026-02-27) | Use `session(operation="deregister")`. |
| session_start | **consolidated** (2026-02-27) | Use `session(operation="start")`. |
| compact_session | **consolidated** (2026-02-27) | Use `session(operation="compact", summary=...)`. |
| roadmap | **keep** | Consolidates add_roadmap_entry, remove_roadmap_entry, remove_roadmap_section (plan: consolidate-plan-and-roadmap-tools). |
| append_entry | **keep** | Consolidates append_progress_entry and append_active_context_entry. Memory bank discipline; implement and complete_plan use it (operation=progress or active_context). |
| get_session_tool_anomalies | **removed** (pruned) | Use `query_usage(query_type="anomalies", hours=24)`. No longer in MCP tool list. |
| run_tool_optimization_workflow | **removed** (pruned) | Use `query_usage(query_type="unused")` and `query_usage(query_type="recommendations")` and [tool-optimization-baseline](tool-optimization-baseline.md). No longer in MCP tool list. |
| quick_start, quality_check, safe_manage_file, suggest_workflow | **consolidated** (2026-02-25) | Use `run_composite_workflow(operation="quick_start" or "quality_check" or "safe_manage_file" or "suggest_workflow", ...)`. Saves 3 tool slots. |
| sync_synapse, update_synapse | **consolidated** (2026-02-27) | Use `synapse(operation="sync" or "update_rule" or "update_prompt", ...)`. Saves 1 tool slot. |
| benchmark_model | **removed (unpublished)** (2026-03-02) | Use `run_tool_evaluation(mode="full")` + manual store/compare. Handler kept for internal use. |

### Census 2026-02-27 Additions

| Tool | Action | Target / Notes |
|------|--------|----------------|
| plan | **keep** | Consolidates create_plan, complete_plan, list_plans, get_plan, register_plan_in_roadmap. Use `plan(operation="register", ...)` for roadmap registration. |
| register_plan_in_roadmap | **consolidated** (2026-02-27) | Use `plan(operation="register", plan_title=..., description=..., section=...)`. Saves 1 tool slot. |
| rollback_file_version | **consolidated** (2026-02-27) | Use `manage_file(operation="rollback", file_name="...", version=<int>)`. Saves 1 tool slot. |

## Summary

- **Keep**: 6 tools (task locking ×4, plan ×1, roadmap ×1, activeContext ×1).
- **Consolidated** (2026-02-27): session_start, session_register, session_deregister, compact_session → `session(operation=start|register|deregister|compact)`. Saves 4 tool slots.
- **Removed (pruned)**: 2 tools (`get_session_tool_anomalies`, `run_tool_optimization_workflow`) — no longer registered; use `query_usage` alternatives above.
- **Consolidated**: 4 tools → 1 (`run_composite_workflow`) — quick_start, quality_check, safe_manage_file, suggest_workflow.
- **Consolidated**: 2 tools → 1 (`synapse`) — sync_synapse, update_synapse.
- **Consolidated**: register_plan_in_roadmap → `plan` (operation="register").
- **Consolidated**: rollback_file_version → `manage_file` (operation="rollback").

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

- [Naming conventions](naming-conventions.md) — Tools, resources, prompts naming rubric
- [Naming inventory](naming-inventory-2026-02.md) — Current state and inconsistencies
- [Tool optimization baseline](tool-optimization-baseline.md)
- Plan: `.cortex/plans/plan-optimize-tools-from-usage.md`
- Plan: `.cortex/plans/session-optimization-tools-set-optimization-from-usage-data.md` (tool consolidation 64→24)
