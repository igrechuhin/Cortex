# Plan: Tool Consolidation from Session Analysis

## Status: PARTIALLY COMPLETE (further reduction blocked)

## Created: 2026-02-25

## Motivation

End-of-session analysis (session-optimization-2026-02-25T13-10.md) identified tool budget violation: 100+ registered tools vs 40 target (80 hard limit).

## Actions

1. **Complete Phase 50 consolidation** – Remove old get_* endpoints (get_memory_bank_stats, get_version_history, get_link_graph, get_tool_usage_stats, get_unused_tools) in favor of query_memory_bank/query_usage.
   - **DONE**: Verified 2026-02-25. These functions are internal only (no @mcp.tool); query_memory_bank and query_usage dispatch to them. No removal needed.
2. **Deprecate dead tools** (&lt; 5 calls in 90 days): append_active_context_entry, cache_json, check_task_available_lock, claim_task_lock, get_plan, get_session_tool_anomalies, list_active_tasks, list_plans, release_task_lock, remove_roadmap_entry, run_tool_optimization_workflow, session_deregister, session_register, suggest_workflow, update_synapse.
   - **DONE for 2**: get_session_tool_anomalies and run_tool_optimization_workflow already pruned (no @mcp.tool; use query_usage instead).
   - **BLOCKED for 10**: tool-optimization-mapping.md marks append_active_context_entry, remove_roadmap_entry, check_task_available_lock, claim_task_lock, release_task_lock, list_active_tasks, get_plan, list_plans, session_register, session_deregister as **keep**.
3. **Consolidate composite tools** (2026-02-25): quick_start, quality_check, safe_manage_file, suggest_workflow → agent_workflow(operation=...).
   - **DONE**: 4 tools merged into 1; saves 3 slots. See docs/architecture/tool-optimization-mapping.md.
4. **Target**: Reduce to ≤40 @mcp.tool() registrations.
   - **Current**: 46 tools (within MAX_REGISTERED_TOOLS=51). Target 40 not yet reached.
   - **Path forward**: Further consolidation or revise mapping's KEEP guidance; run tool-consolidation-next-analysis.

## References

- .cortex/reviews/session-optimization-2026-02-25T13-10.md
- docs/architecture/tool-optimization-mapping.md
