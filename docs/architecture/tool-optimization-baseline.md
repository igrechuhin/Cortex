# Tool Optimization Baseline and Threshold Policy

**Status**: Baseline established (plan: optimize-tools-from-usage)  
**Created**: 2026-02-23

## Goal

Document the usage baseline and threshold policy for reducing the Cortex MCP tool set based on real usage data. Tools below a defined usage threshold are candidates for deprecation, consolidation, or removal.

## Baseline Report (2026-02-23)

### Summary

- **Period**: 2025-11-25 to 2026-02-23 (approx. 30 days)
- **Total events**: 49,955
- **Published tools**: 100+ (exact count from tool registry; report lists all tools with at least one call)
- **Tools below threshold (≤5 calls in 30 days)**: 10

### Tools Below Threshold (≤5 calls in 30 days)

As of the baseline run (`query_usage(query_type="unused", days=30, min_usage_count=5)`):

| Tool | Action (Step 2) |
|------|------------------|
| check_task_available_lock | keep (Phase 58 task locking) |
| claim_task_lock | keep (Phase 58 task locking) |
| get_plan | keep (plan discovery; implement/create-plan) |
| get_session_tool_anomalies | removed (pruned); use query_usage(anomalies) |
| list_active_tasks | keep (Phase 58 task locking) |
| list_plans | keep (plan discovery) |
| release_task_lock | keep (Phase 58) |
| remove_roadmap_entry | keep (memory bank discipline) |
| run_tool_optimization_workflow | removed (pruned); use query_usage(unused/recommendations) |
| session_deregister | keep (session lifecycle) |
| session_register | keep (session lifecycle) |

### How to Reproduce the Baseline (and Run Unused / Recommendations)

Threshold and window are read from **`.cortex/config/usage_tracking.json`** under the `tool_optimization` key (see [Configuration](#configuration)). The following calls use those config values by default.

1. **Full report (all tools, with recommendations)**  
   `query_usage(query_type="report", include_recommendations=True, format="markdown")`

2. **Unused / low-usage list**  
   `query_usage(query_type="unused")`  
   Uses config `tool_optimization.days` and `tool_optimization.min_usage_count`. Returns JSON with `unused_tools` (tool names with total_calls ≤ min_usage_count in the window).

3. **Optimization recommendations**  
   `query_usage(query_type="recommendations")`  
   Uses config `tool_optimization.days` and `tool_optimization.min_usage_threshold`. Returns JSON with `low_usage_tools` and a message.

4. **Per-tool stats**  
   `query_usage(query_type="stats", response_format="detailed")`  
   Returns JSON with a `tools` array (tool_name, total_calls, successful_calls, failed_calls, avg_duration_ms, first_used, last_used, etc.).

## Threshold Policy

### Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `days` | 30 | Lookback window (days). |
| `min_usage_count` | 0 (unused), 5 (low use) | Tools with total_calls ≤ this in the window are "unused" or "low use". |
| `min_usage_threshold` | 5 | Same as min_usage_count; used by recommendations and report. |

### Definitions

- **Unused**: Total calls in the window = 0. Use `query_usage(query_type="unused", days=30, min_usage_count=0)`.
- **Low use**: Total calls in the window ≤ 5 (default threshold). Use `query_usage(query_type="unused", days=30, min_usage_count=5)` or `query_usage(query_type="recommendations", min_usage_threshold=5, days=30)`.
- **Must optimize**: Tools that appear in the "unused" or "low use" list and are not on an "always keep" list. These are candidates for deprecation, consolidation into `query_usage` / `query_memory_bank` / resources, or removal with a migration path.

### Configuration

The threshold and lookback window are configurable so that "tools below usage threshold" can be tuned without code changes.

- **File**: `.cortex/config/usage_tracking.json`
- **Section**: `tool_optimization`

Example:

```json
{
  "tool_optimization": {
    "days": 30,
    "min_usage_count": 0,
    "min_usage_threshold": 5
  }
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `days` | 30 | Lookback window (days) for unused and recommendations. |
| `min_usage_count` | 0 | Used by `query_usage(query_type="unused")`: tools with total_calls ≤ this are "unused". |
| `min_usage_threshold` | 5 | Used by `query_usage(query_type="recommendations")`: tools with total_calls ≤ this are low-use candidates. |

`query_usage(query_type="unused")` and `query_usage(query_type="recommendations")` read these values at runtime; the resources `cortex://usage/unused` and `cortex://usage/optimization-recommendations` use the same config. To change which tools appear in the below-threshold list, edit this file and re-run the queries.

### Single Source of Truth

- **Config**: `.cortex/config/usage_tracking.json` → `tool_optimization` (days, min_usage_count, min_usage_threshold).
- **Code**: `get_tool_optimization_config(project_root)` in `cortex.managers.usage_tracker`; used by `query_usage_operations` and usage analytics resources.

## References

- [Tool Usage Tracking Architecture](tool-usage-tracking.md) — Phase 29 implementation.
- [ADR-005 Tool Consolidation](../adr/ADR-005-tool-consolidation.md) — Phase 50 consolidation.
- Plan: `.cortex/plans/plan-optimize-tools-from-usage.md`.
