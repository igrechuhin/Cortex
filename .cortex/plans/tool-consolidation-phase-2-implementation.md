# Tool Consolidation Phase 2 — Implementation

**Status:** PENDING
**Created:** 2026-02-25
**Source:** tool-consolidation-analysis-2026-02-25T21-47.md

## Goal

Reduce tool count from 51 to ≤40 by completing Phase 50 consolidation, deprecating low-usage tools, and merging duplicates.

## Context

- Current: 51 registered tools (MAX_REGISTERED_TOOLS)
- Target: ≤40
- Hard limit: 80
- Analysis: .cortex/reviews/tool-consolidation-analysis-2026-02-25T21-47.md

## Implementation Steps

### Step 1: Complete Phase 50 — Remove old memory/usage tools (Est. 7 slots) — ✅ DONE 2026-02-26

1. ✅ Migrate all internal callers from get_memory_bank_stats, get_version_history, get_link_graph to query_memory_bank (tests/test_integration.py, tests/integration/test_mcp_tools_integration.py, tests/test_quick.py).
2. ✅ Migrate callers from get_tool_usage_stats, get_unused_tools, etc. — query_usage already dispatches; no external callers migrated (usage tools were never registered).
3. MCP resources — resources use internal callables; no change needed.
4. ✅ Old tools (get_memory_bank_stats, get_version_history, get_dependency_graph, get_link_graph, get_tool_usage_stats, get_unused_tools, get_tool_usage_report, get_optimization_recommendations) have no @mcp.tool() — already consolidated into query_memory_bank/query_usage.
5. ✅ Implementations kept as internal callables for query_memory_bank/query_usage dispatch.
6. ✅ Tests updated; docs/api/tools.md already documents Phase 50 consolidation.

### Step 2: Deprecate low-usage plan tools (Est. 2 slots)

1. Verify create_plan supports operation=list and operation=get.
2. Migrate any callers of get_plan and list_plans to create_plan.
3. Remove get_plan and list_plans @mcp.tool() registration.
4. Update tool_categories and TOOL_CATEGORIES.

### Step 3: Low-usage internalize/remove (Est. 2-3 slots)

1. get_session_tool_anomalies — internalize (use only from analyze or internal code).
2. run_tool_optimization_workflow — internalize or remove if unused.
3. suggest_workflow — evaluate merge into agent_workflow or remove.

### Step 4: Verify cache consolidation

1. Confirm read_cache_json and write_cache_json are no longer registered if cache_json exists.
2. If still registered, remove and ensure all callers use cache_json.

### Step 5: Optional — load_context/load_progressive_context merge (Est. 1 slot)

1. Add strategy parameter to load_context (e.g. strategy="progressive").
2. Migrate load_progressive_context callers to load_context(strategy="progressive").
3. Remove load_progressive_context @mcp.tool() registration.

## Success Criteria

- Tool count ≤40 (MAX_REGISTERED_TOOLS updated)
- All tests pass
- No regressions in implement, commit, analyze workflows
- docs/api/tools.md updated

## References

- tool-consolidation-analysis-2026-02-25T21-47.md
- docs/architecture/tool-optimization-mapping.md
- src/cortex/tools/tool_categories.py
- Phase 50 consolidation docs
