# Tool Optimization Baseline and Threshold Policy

**Status**: Baseline established (plan: optimize-tools-from-usage)  
**Created**: 2026-02-23

## Goal

Document the usage baseline and threshold policy for reducing the Cortex MCP tool set based on real usage data. Tools below a defined usage threshold are candidates for deprecation, consolidation, or removal.

## Baseline Report (2026-02-23)

### Summary

- **Period**: 2025-11-25 to 2026-02-23 (approx. 90 days)
- **Total events**: 49,955
- **Published tools**: 100+ (exact count from tool registry; report lists all tools with at least one call)
- **Tools below threshold (≤5 calls in 90 days)**: 10

### Tools Below Threshold (≤5 calls in 90 days)

As of the baseline run (`query_usage(query_type="unused", days=90, min_usage_count=5)`):

| Tool | Action (Step 2) |
|------|------------------|
| check_task_available_lock | TBD |
| claim_task_lock | TBD |
| get_plan | TBD |
| get_session_tool_anomalies | TBD |
| list_active_tasks | TBD |
| list_plans | TBD |
| release_task_lock | TBD |
| run_tool_optimization_workflow | TBD |
| session_deregister | TBD |
| session_register | TBD |

### How to Reproduce the Baseline

1. **Full report (all tools, with recommendations)**  
   `query_usage(query_type="report", include_recommendations=True, format="markdown")`

2. **Unused / low-usage list**  
   `query_usage(query_type="unused", days=90, min_usage_count=5)`  
   Returns JSON with `unused_tools` (tool names with total_calls ≤ 5 in the window).

3. **Optimization recommendations**  
   `query_usage(query_type="recommendations", days=90, min_usage_threshold=5)`  
   Returns JSON with `low_usage_tools` and a message.

4. **Per-tool stats**  
   `query_usage(query_type="stats", response_format="detailed")`  
   Returns JSON with a `tools` array (tool_name, total_calls, successful_calls, failed_calls, avg_duration_ms, first_used, last_used, etc.).

## Threshold Policy

### Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `days` | 90 | Lookback window (days). |
| `min_usage_count` | 0 (unused), 5 (low use) | Tools with total_calls ≤ this in the window are "unused" or "low use". |
| `min_usage_threshold` | 5 | Same as min_usage_count; used by recommendations and report. |

### Definitions

- **Unused**: Total calls in the window = 0. Use `query_usage(query_type="unused", days=90, min_usage_count=0)`.
- **Low use**: Total calls in the window ≤ 5 (default threshold). Use `query_usage(query_type="unused", days=90, min_usage_count=5)` or `query_usage(query_type="recommendations", min_usage_threshold=5, days=90)`.
- **Must optimize**: Tools that appear in the "unused" or "low use" list and are not on an "always keep" list. These are candidates for deprecation, consolidation into `query_usage` / `query_memory_bank` / resources, or removal with a migration path.

### Configuration (future)

- Threshold and window are currently **hardcoded** in tool defaults (`QueryUsageParams`: `days=90`, `min_usage_threshold=5`; `usage_analytics.get_tool_usage_report` uses `min_usage_count=5` for recommendations).
- Plan Step 6 will make the threshold configurable (e.g. `.cortex/config/usage_tracking.json` or a dedicated optimization config) so that "tools below usage threshold" can be tuned without code changes.

### Single Source of Truth

- **Current**: Defaults in `src/cortex/tools/query_usage_operations.py` (`QueryUsageParams`) and `src/cortex/tools/usage_analytics.py` (e.g. `get_optimization_recommendations(min_usage_threshold=5, days=90)`).
- **After Step 6**: Config file plus docs; code reads threshold from config.

## References

- [Tool Usage Tracking Architecture](tool-usage-tracking.md) — Phase 29 implementation.
- [ADR-005 Tool Consolidation](../adr/ADR-005-tool-consolidation.md) — Phase 50 consolidation.
- Plan: `.cortex/plans/plan-optimize-tools-from-usage.md`.
