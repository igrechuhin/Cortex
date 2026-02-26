# Tool Consolidation Phase 2 — Implementation

**Status:** COMPLETE
**Created:** 2026-02-25
**Source:** tool-consolidation-analysis-2026-02-25T21-47.md

## Goal

Reduce tool count from 51 to ≤40 by completing Phase 50 consolidation, deprecating low-usage tools, and merging duplicates.

## Context

- Current: ≤40 registered tools (MAX_REGISTERED_TOOLS)
- Target: ≤40 (achieved)
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

### Step 2: Deprecate low-usage plan tools (Est. 2 slots) — ✅ DONE 2026-02-26

1. ✅ create_plan supports operation=list and operation=get.
2. ✅ get_plan and list_plans have no @mcp.tool(); they are internal callables used by create_plan.
3. ✅ tool_categories contains create_plan only (no get_plan/list_plans).

### Step 3: Low-usage internalize/remove (Est. 2-3 slots) — ✅ DONE 2026-02-26

1. ✅ get_session_tool_anomalies — already internalized (no @mcp.tool(); use query_usage).
2. ✅ run_tool_optimization_workflow — already internalized (no @mcp.tool()).
3. ✅ suggest_workflow — already merged into agent_workflow(operation="suggest_workflow").

### Step 4: Verify cache consolidation — ✅ DONE 2026-02-26

1. ✅ read_cache_json and write_cache_json are in cortex.core.cache_json_access (internal); not MCP tools.
2. ✅ cache_json is the single MCP tool for cache JSON access.

### Step 5: Optional — load_context/load_progressive_context merge (Est. 1 slot) — ✅ DONE 2026-02-26

1. ✅ load_context supports strategy="progressive".
2. ✅ load_progressive_context merged into load_context; no separate @mcp.tool().

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
