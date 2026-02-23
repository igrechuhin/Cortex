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
| get_session_tool_anomalies | **removed** (pruned) | Use `query_usage(query_type="anomalies", hours=24)`. No longer in MCP tool list. |
| run_tool_optimization_workflow | **removed** (pruned) | Use `query_usage(query_type="unused")` and `query_usage(query_type="recommendations")` and [tool-optimization-baseline](tool-optimization-baseline.md). No longer in MCP tool list. |

## Summary

- **Keep**: 8 tools (task locking ×4, plan ×2, session ×2).
- **Removed (pruned)**: 2 tools (`get_session_tool_anomalies`, `run_tool_optimization_workflow`) — no longer registered as MCP tools; use `query_usage` alternatives above.

## Done

1. Both tools removed from MCP registration (pruning); tool count reduced by 2.
2. analyze.md and callers use `query_usage(query_type="anomalies", hours=24)`.

## References

- [Tool optimization baseline](tool-optimization-baseline.md)
- Plan: `.cortex/plans/plan-optimize-tools-from-usage.md`
