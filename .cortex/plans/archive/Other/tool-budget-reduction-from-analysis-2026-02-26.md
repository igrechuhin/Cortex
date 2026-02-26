# Tool Budget Reduction Plan

**Source**: End-of-session analysis 2026-02-26
**Report**: .cortex/reviews/session-optimization-2026-02-26T11-03.md
**Status**: COMPLETED 2026-02-26

## Current State (after implementation)

- **Tool budget**: 40 / 40 target (80 hard limit) — OK
- **Target**: ≤40 registered tools — achieved

## Dead Tools (< 5 calls in 90 days)

| Tool | Calls | Action |
|------|-------|--------|
| cache_json | 2 | Internalize or merge into existing cache tool |
| check_task_available_lock | 5 | Merge into task_locking dispatcher |
| claim_task_lock | 5 | Merge into task_locking dispatcher |
| get_plan | 2 | Internalize or consolidate |
| get_session_tool_anomalies | 3 | Internalize (query_usage covers) |
| get_synapse | 3 | Internalize or consolidate |
| list_active_tasks | 5 | Merge into task_locking dispatcher |
| list_available_tools | 3 | Internalize or merge |
| list_plans | 1 | Internalize (create_plan list) |
| release_task_lock | 5 | Merge into task_locking dispatcher |
| remove_roadmap_entry | 5 | Keep (implement workflow) |
| run_tool_optimization_workflow | 2 | Internalize |
| session_deregister | 5 | Internalize |
| session_register | 5 | Internalize |
| suggest_workflow | 5 | Internalize or deprecate |

## Consolidation Candidates

1. **Task locking** (4 tools → 1): claim_task_lock, release_task_lock, list_active_tasks, check_task_available_lock → single `task_locking(operation="claim"|"release"|"list"|"check")`
2. **Script capture**: Already grouped; consider single dispatcher with operation parameter
3. **Usage/analytics**: query_usage already consolidates; verify legacy get_* tools removed

## Implementation Steps

1. ✅ Audit tool_categories.py and main.py for exact @mcp.tool() count — 46 tools before reduction
2. ⏭️ Merge task-locking tools — skipped; claim_task_lock, release_task_lock, list_active_tasks, check_task_available_lock use @mcp_tool_wrapper only (no @mcp.tool); not registered
3. ✅ Internalize: cache_json, get_synapse, list_available_tools, skill_pack, provide_feedback, fix_roadmap_corruption (6 tools)
4. ✅ Phase 50 verified — legacy get_* tools already consolidated
5. ✅ MAX_REGISTERED_TOOLS set to 40; governance tests pass

## Expected Outcome

- Tool count: 51 → ≤40
- No duplicate/legacy tools registered
- All low-usage tools either internalized or merged

## References

- docs/architecture/tool-optimization-mapping.md
- docs/architecture/tool-optimization-baseline.md
- tool-consolidation-phase-2-implementation.md
