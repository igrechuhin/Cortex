# Session Optimization 2026-02-23: Tools Optimization

## Source

End-of-session analysis: `.cortex/reviews/session-optimization-2026-02-23T22-22.md`

## Objective

Create or update a plan to optimize the tools set: deprecate, merge, or remove low-usage tools using usage data and existing baseline/mapping docs.

## Context

- **Low-usage tools** (usage ≤ 5 in 90-day window): check_task_available_lock, claim_task_lock, get_plan, get_session_tool_anomalies, list_active_tasks, list_plans, release_task_lock, remove_roadmap_entry, run_tool_optimization_workflow, session_deregister, session_register.
- **High-error tools** (24h anomalies): AsyncMock, _execute_transclusion_resolution.
- **References**: `docs/architecture/tool-optimization-mapping.md`, tool-optimization baseline.

## Steps

1. Review usage data and tool-optimization-mapping.md. — COMPLETED
2. Decide for each low-usage tool: deprecate, merge, or keep (e.g. task locking may be needed for specific flows). — COMPLETED (mapping + baseline updated; remove_roadmap_entry added as keep)
3. Add deprecation notices or consolidation per mapping; update docs. — COMPLETED (mapping and baseline docs updated)
4. Investigate high-error tools (transclusion resolution, test mocks) and fix or document. — COMPLETED (documented in mapping: AsyncMock and _execute_transclusion_resolution are not MCP tools; no action)
5. Register plan in roadmap and track completion. — COMPLETED

## Status

COMPLETE
