# Improvements from Session Analysis 2026-02-26

**Status**: PENDING
**Source**: End-of-session analysis (session-optimization-2026-02-26T13-29.md)

## Summary

Analysis identified: (1) zero-budget load_context configuration error for planning tasks, (2) query_usage response_format schema/prompt mismatch, (3) tools optimization opportunities (dead tools, consolidation candidates).

## Recommendations

### 1. Zero-budget load_context fix

- **Target**: Implement/session-start prompts and load_context callers
- **Issue**: At least one load_context call used token_budget=0 for a planning task (Phase 9.1 rules compliance). Zero-budget for non-trivial tasks violates workflow.
- **Action**: Add guardrails that planning, implement, fix/debug, and testing tasks MUST use non-zero token_budget (10k–20k). Reject or override token_budget=0 for non-trivial tasks.
- **Files**: Synapse implement prompt, session_start tools, CLAUDE.md/AGENTS.md

### 2. query_usage response_format alignment

- **Target**: Analyze prompt and query_usage tool schema
- **Issue**: Analyze prompt references response_format="full", but the tool rejected it as invalid.
- **Action**: Either add "full" to query_usage schema or update analyze prompt to use a valid response_format value.
- **Files**: .cortex/synapse/prompts/analyze.md, query_usage tool schema

### 3. Tools consolidation (optional)

- **Tool budget**: 39/40 target — OK
- **Dead tools** (< 5 calls in 90 days): agent_workflow, cache_json, check_task_available_lock, claim_task_lock, get_plan, get_session_tool_anomalies, list_active_tasks, list_plans, release_task_lock, remove_roadmap_entry, run_tool_optimization_workflow, session_deregister, session_register, suggest_workflow, update_synapse
- **Consolidation candidates**: Task-locking tools (check_task_available_lock, claim_task_lock, release_task_lock, list_active_tasks, session_register, session_deregister) could be merged into a single dispatcher
- **Action**: Evaluate deprecation/consolidation per Tool Consolidation Phase 2 plan; low priority (budget OK)

## References

- Report: .cortex/reviews/session-optimization-2026-02-26T13-29.md
- Tool Consolidation: .cortex/plans/archive/Other/tool-consolidation-phase-2-implementation.md
