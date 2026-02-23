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
| get_session_tool_anomalies | **deprecate** (consolidated) | Redirects to `query_usage(query_type="anomalies", hours=24)`. Use that as primary; see docs/api/tools.md and analyze.md. |
| run_tool_optimization_workflow | **deprecate** | Low usage; document `query_usage(query_type="unused")` and `query_usage(query_type="recommendations")` and manual workflow as the primary path. Add deprecation notice and point to docs/tool-optimization-baseline. |

## Summary

- **Keep**: 8 tools (task locking ×4, plan ×2, session ×2).
- **Deprecate**: 2 tools (`get_session_tool_anomalies`, `run_tool_optimization_workflow`). One is a candidate for later consolidation into `query_usage`; the other is documented alternative only.

## Next Steps (Plan Step 5+)

1. `run_tool_optimization_workflow`: deprecation done (Step 3).
2. `get_session_tool_anomalies`: consolidated into `query_usage(query_type="anomalies")`; tool redirects and is deprecated (Step 5).
3. Update Synapse prompts (e.g. analyze.md) to use consolidated tools where applicable — done for anomalies (prefer query_usage).

## References

- [Tool optimization baseline](tool-optimization-baseline.md)
- Plan: `.cortex/plans/plan-optimize-tools-from-usage.md`
