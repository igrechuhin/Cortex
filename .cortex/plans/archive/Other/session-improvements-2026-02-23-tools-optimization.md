# Session Improvements Plan (2026-02-23)

## Status: COMPLETE

## Source

End-of-session analysis: `.cortex/reviews/session-optimization-2026-02-23T23-05.md`

## Items

1. **Tools set optimization** – Use usage data and existing docs (`docs/architecture/tool-optimization-baseline.md`, `docs/architecture/tool-optimization-mapping.md`) to create or update a plan to deprecate, merge, or remove low-usage tools. Low-usage list (30-day, threshold 5): append_active_context_entry, check_task_available_lock, claim_task_lock, compact_session, create_plan, get_plan, get_session_tool_anomalies, list_active_tasks, list_plans, release_task_lock, remove_roadmap_entry, run_tool_optimization_workflow, session_deregister, session_register.

## Done

- Reviewed `query_usage(query_type="recommendations", days=30, min_usage_threshold=5)` output and baseline/mapping docs.
- Updated `docs/architecture/tool-optimization-mapping.md`: added **append_active_context_entry** with action **keep** (memory bank discipline). Summary updated to Keep: 10 tools.
- No further deprecations recommended; two tools already pruned (get_session_tool_anomalies, run_tool_optimization_workflow). All other current low-usage tools are keep (Phase 58, plan discovery, session lifecycle, memory bank).
