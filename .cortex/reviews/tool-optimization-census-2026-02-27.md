# Tool Optimization Census 2026-02-27

**Plan**: optimize-tools-from-usage-statistics  
**Step**: 1 (Run usage census and baseline)

## Summary

| Metric | Value |
|--------|-------|
| Total registered tools | 40 |
| MAX_REGISTERED_TOOLS | 40 |
| TARGET_REGISTERED_TOOLS | 24 |
| Gap to target | 16 tools |
| Total usage events | 50,341 |
| Lookback (recommendations) | 30 days |

## Tool Budget Status

- **Budget**: 40 / 40 (at MAX)
- **Target**: ≤24
- **Reduction needed**: 16 tools to reach target

## Low-Usage Tools (≤5 calls in 30 days)

From `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)` (config uses 30-day window):

| Tool | Calls | Status | Notes |
|------|-------|--------|-------|
| check_task_available_lock | 4 | Internal/Phase 58 | Not in TOOL_CATEGORIES (dispatcher) |
| claim_task_lock | 4 | Internal/Phase 58 | Not in TOOL_CATEGORIES (dispatcher) |
| get_plan | 2 | Internal | Not in TOOL_CATEGORIES (dispatcher) |
| get_session_tool_anomalies | 3 | Pruned | Use query_usage(anomalies) |
| list_active_tasks | 4 | Internal/Phase 58 | Not in TOOL_CATEGORIES (dispatcher) |
| list_available_tools | 3 | Internalized | Use search_tools |
| list_plans | 1 | Internal | Not in TOOL_CATEGORIES (dispatcher) |
| release_task_lock | 4 | Internal/Phase 58 | Not in TOOL_CATEGORIES (dispatcher) |
| remove_roadmap_entry | 4 | **Registered** | keep (memory bank discipline) |
| run_tool_optimization_workflow | 2 | Pruned | Use query_usage(recommendations) |
| session_deregister | 4 | Internal | Not in TOOL_CATEGORIES (dispatcher) |
| session_register | 4 | Internal | Not in TOOL_CATEGORIES (dispatcher) |
| suggest_workflow | 5 | **Consolidated** | Via agent_workflow |

## Registered Tools (TOOL_CATEGORIES) – Low-Usage Subset

Of the 40 registered tools, those with ≤10 calls in the period:

| Tool | Category | Calls | Action (Step 2) |
|------|----------|-------|-----------------|
| add_roadmap_entry | always_loaded | 7 | keep |
| append_active_context_entry | always_loaded | 6 | keep |
| append_progress_entry | always_loaded | 9 | keep |
| remove_roadmap_entry | always_loaded | 4 | keep |
| create_plan | deferred_medium | 7 | keep |
| compact_session | deferred_medium | 8 | keep |
| update_synapse | deferred_low | 6 | keep (rare admin) |
| run_tool_evaluation | deferred_medium | 17 | keep |
| analyze_error_patterns | deferred_low | 18 | keep |
| session_start | always_loaded | 17 | keep |
| search_tools | always_loaded | 35 | keep |
| query_usage | deferred_low | 46 | keep |
| query_memory_bank | always_loaded | 76 | keep |

## High-Usage Tools (Top 15 by total_calls)

| Tool | Calls |
|------|-------|
| manage_file | 4,034 |
| rules | 1,813 |
| configure | 1,659 |
| resolve_transclusions | 1,589 |
| check_structure_health | 1,586 |
| summarize_content | 1,452 |
| load_context | 1,185 |
| fix_markdown_lint | 1,210 |
| get_version_history | 1,252 |
| validate | 1,295 |
| validate_links | 1,397 |
| get_link_graph | 1,340 |
| suggest_refactoring | 992 |
| analyze | 997 |
| execute_pre_commit_checks | 1,940 |

## Consolidation Opportunities (from plan Step 2)

1. **Already consolidated**: suggest_workflow → agent_workflow
2. **Pruned**: get_session_tool_anomalies, run_tool_optimization_workflow
3. **Internalized**: list_available_tools, cache_json, get_synapse, skill_pack, provide_feedback, fix_roadmap_corruption (per 2026-02-26)

## Next Steps (Step 2)

- Build optimization mapping for any remaining low-value tools
- Consider consolidating plan tools (get_plan, list_plans) into a single dispatcher
- Consider consolidating task locking tools into a single dispatcher
- Consider consolidating session tools (session_register, session_deregister) if exposed
