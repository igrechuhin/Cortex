# Session Improvements Plan (2026-02-27)

## Context

Based on end-of-session analysis after commit pipeline. Report: `.cortex/reviews/session-optimization-2026-02-27T23-04.md`

## Recommendations

### 1. Context effectiveness

- **Issue**: No `load_context` calls in analysis-only sessions; context-effectiveness returns `no_data`.
- **Action**: Ensure implement/fix/debug sessions call `load_context(task_description="...", token_budget=15000)` at task start.
- **Impact**: Future analyses can use context-effectiveness metrics.

### 2. Rules indexing

- **Issue**: `rules_manager_status.indexed_files = 0`.
- **Action**: Verify `optimization.json` and rules path; run `rules(operation="index", force=True)` if rules are enabled.
- **Impact**: Rule-aware context selection when indexed.

### 3. Tools optimization (low priority)

- **Budget**: 37/40 — OK.
- **Low-usage tools (≤5 in 30 days)**: 16 tools including Phase 58 (task locking), session, suggest_workflow, update_synapse, etc.
- **Consolidation candidate**: Phase 58 tools (check_task_available_lock, claim_task_lock, release_task_lock, list_active_tasks) could merge into single dispatcher (~4 slots saved).
- **Action**: Consider Phase 58 consolidation in future tool-optimization phase; monitor dead tools.

### 4. MCP connection health

- **Issue**: MCP disconnected during Step 12; fallbacks used.
- **Action**: Already in commit prompt — call `check_mcp_connection_health()` before Step 12. No change needed.

## Status

PENDING
