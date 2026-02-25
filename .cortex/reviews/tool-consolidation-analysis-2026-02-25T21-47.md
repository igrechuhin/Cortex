# Tool Consolidation — Next Analysis

**Created:** 2026-02-25
**Plan:** .cortex/plans/tool-consolidation-next-analysis.md

## Summary

Tool census and usage analysis completed. Budget violation: 51 / 40 target (CRITICAL, over by 11). Fifteen low-usage tools, incomplete Phase 50 consolidation (old endpoints still used), and consolidation candidates identified. Recommended: deprecate low-usage tools, complete Phase 50 by migrating callers to `query_memory_bank` / `query_usage`, and evaluate load_context / load_progressive_context merge.

---

## 1. Tool Census

| Source | Count |
|--------|-------|
| tool_categories.py MAX_REGISTERED_TOOLS | 51 |
| TOOL_CATEGORIES entries | 41 |
| Target | ≤40 |
| Hard limit | 80 |

**Note:** The governance test enforces MAX_REGISTERED_TOOLS=51. The MCP server registers additional tools beyond TOOL_CATEGORIES (e.g. from phase modules, setup, resources). Usage report shows 100+ distinct tool/resource names; many are internal dispatchers or resources.

---

## 2. Tool Budget Status

**Tool budget:** 51 / 40 target (80 hard limit) — **CRITICAL: over by 11**

To reach target: remove or internalize at least 11 tools, or consolidate multiple tools into single dispatchers.

---

## 3. Low-Usage Tools (<5 calls in 90 days)

From `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)`:

| Tool | Action |
|------|--------|
| agent_workflow | Consider remove or internalize (5 calls) |
| append_active_context_entry | Keep (used by implement workflow Step 5) |
| check_task_available_lock | Keep (Phase 58 multi-agent coordination) |
| claim_task_lock | Keep (Phase 58) |
| get_plan | Deprecate → use create_plan(operation="get") |
| get_session_tool_anomalies | Consider internalize |
| list_active_tasks | Keep (Phase 58) |
| list_plans | Deprecate → use create_plan(operation="list") |
| release_task_lock | Keep (Phase 58) |
| remove_roadmap_entry | Keep (implement workflow) |
| run_tool_optimization_workflow | Consider internalize |
| session_deregister | Keep (session management) |
| session_register | Keep (session management) |
| suggest_workflow | Consider merge into agent_workflow |
| update_synapse | Keep (admin workflow) |

**Remove/internalize candidates:** get_plan (2 calls), list_plans (1 call), run_tool_optimization_workflow (2 calls), get_session_tool_anomalies (3 calls), suggest_workflow (5 calls). **Est. reduction:** 3–5 slots if merged/deprecate.

---

## 4. Incomplete Consolidations

Phase 50 consolidated `query_memory_bank` and `query_usage`, but old tools remain registered and have high usage:

| Old Tool | Calls | Replacement | Status |
|----------|-------|-------------|--------|
| get_memory_bank_stats | 695 | query_memory_bank(query_type="stats") | Old still used |
| get_version_history | 1,250 | query_memory_bank(query_type="version_history") | Old still used |
| get_link_graph | 1,343 | query_memory_bank(query_type="link_graph") | Old still used |
| get_tool_usage_stats | 265 | query_usage(query_type="stats") | Old still used |
| get_unused_tools | 264 | query_usage(query_type="recommendations") | Old still used |
| get_tool_usage_report | 263 | query_usage(query_type="report") | Old still used |
| get_optimization_recommendations | 265 | query_usage | Old still used |

**Action:** Migrate internal callers and MCP resources to use consolidated tools, then remove old `@mcp.tool()` registrations. **Est. reduction:** 7 slots.

---

## 5. Duplicates / Overlap

| Tool A | Calls | Tool B | Calls | Overlap | Action |
|--------|-------|--------|-------|---------|--------|
| load_context | 1,176 | load_progressive_context | 1,166 | Both load memory bank context | Evaluate merge: load_context(strategy="progressive") |
| read_cache_json | 662 | write_cache_json | 607 | Cache operations | Already consolidated as cache_json(operation=read/write) — verify old tools removed |
| configure | 1,659 | update_config | 248 | Config operations | Different operations; keep both |

**Note:** read_cache_json and write_cache_json appear in usage — if cache_json exists, old cache tools may still be registered. Verify and remove if duplicated.

---

## 6. Consolidation Candidates

| Group | Tools | Count | Consolidation | Est. Savings |
|-------|-------|-------|---------------|--------------|
| Script capture | capture_session_script, list_session_scripts, analyze_session_scripts, promote_session_script, suggest_tool_improvements | 5 | session_scripts (operation=...) | Already consolidated per tool_categories; verify registration |
| Phase 50 memory/usage | get_* (see §4) | 7 | query_memory_bank, query_usage | 7 slots |
| Plan operations | get_plan, list_plans | 2 | create_plan(operation=get/list) | 2 slots (create_plan already has list/get) |

---

## 7. Total Reduction Potential

| Category | Est. Slots |
|----------|------------|
| Incomplete Phase 50 (remove old get_* tools) | 7 |
| Low-usage deprecation (get_plan, list_plans, etc.) | 3–5 |
| load_context/load_progressive_context merge | 1 (if feasible) |
| **Total** | **11–13** |

Reducing by 11 would bring count to 40 (target). Reducing by 13 would provide buffer.

---

## 8. References

- `docs/architecture/tool-optimization-mapping.md`
- `src/cortex/tools/tool_categories.py`
- `.cortex/plans/archive/SessionOptimization/session-optimization-tools-set-optimization-from-usage-data.md`
- Analyze prompt Step 2.5 (Tools optimization)

---

## 9. Recommended Next Steps

1. **Create improvements plan** — Run Create Plan with this analysis as input for a concrete consolidation implementation plan.
2. **Phase 50 completion** — Migrate callers from get_memory_bank_stats, get_version_history, get_link_graph to query_memory_bank; remove old tool registrations.
3. **Usage consolidation** — Migrate get_tool_usage_stats, get_unused_tools, get_tool_usage_report, get_optimization_recommendations callers to query_usage; remove old registrations.
4. **Low-usage cleanup** — Deprecate or internalize get_plan, list_plans (if create_plan already supports these operations).
5. **Context loading** — Evaluate load_context(strategy="progressive") to replace load_progressive_context.
