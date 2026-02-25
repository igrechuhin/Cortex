# Plan: Tool Consolidation from Session Analysis

## Status: PENDING

## Created: 2026-02-25

## Motivation

End-of-session analysis (session-optimization-2026-02-25T13-10.md) identified tool budget violation: 100+ registered tools vs 40 target (80 hard limit).

## Actions

1. **Complete Phase 50 consolidation** – Remove old get_* endpoints (get_memory_bank_stats, get_version_history, get_link_graph, get_tool_usage_stats, get_unused_tools) in favor of query_memory_bank/query_usage.
2. **Deprecate dead tools** (&lt; 5 calls in 90 days): append_active_context_entry, cache_json, check_task_available_lock, claim_task_lock, get_plan, get_session_tool_anomalies, list_active_tasks, list_plans, release_task_lock, remove_roadmap_entry, run_tool_optimization_workflow, session_deregister, session_register, suggest_workflow, update_synapse.
3. **Target**: Reduce to ≤40 @mcp.tool() registrations.

## References

- .cortex/reviews/session-optimization-2026-02-25T13-10.md
- docs/architecture/tool-optimization-mapping.md (if exists)
