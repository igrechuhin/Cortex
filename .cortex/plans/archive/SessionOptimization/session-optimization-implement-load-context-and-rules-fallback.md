# Session Optimization (2026-02-02): Implement Load Context at Step Start and Rules Fallback

**Status**: PENDING  
**Created**: 2026-02-02  
**Source**: `.cortex/reviews/session-optimization-2026-02-02T21-14.md`  
**Priority**: Low

## Goal

Implement two recommendations from the end-of-session analysis (2026-02-02T21-14): (1) ensure the implement prompt instructs agents to call `load_context()` at step start so the current session is recorded for end-of-session analyze; (2) add a short reminder in the implement prompt that when `rules(operation="get_relevant")` returns disabled, agents should still load key coding standards from the rules path (e.g. via `get_structure_info()` + Read) for implementation quality.

## Context

- **Context effectiveness**: Current session had no recorded `load_context` calls (`analyze_context_effectiveness` returned `status: no_data`). Aggregated stats (3 sessions, 4 calls) show ~23% token utilization and high value for activeContext/roadmap/progress.
- **Session optimization**: No critical mistake patterns; path resolution and memory bank access followed Cortex tools. Two low-priority improvements identified.

### New input (2026-02-03)

End-of-session analysis `session-optimization-2026-02-03T20-53.md`: global context stats (5 sessions, 6 calls) show avg 26.8% token utilization; budget recommendations by task type (fix/debug 15k, other 15k, implement/add 10k, update/modify 10k). Recommendation: use task-type-based token budgets in the implement prompt when calling `load_context()` to reduce over-provisioning. Added as Step 3 below.

## Implementation Steps

### Step 1: Implement prompt — load_context at step start

**Target**: Implement-next-roadmap-step prompt (Step 1 or Step 2).

**Tasks**:

1. Add an explicit instruction: at the beginning of execution (after reading the roadmap and picking the next step), call `load_context(task_description="[roadmap step description]", token_budget=...)` so the current session is recorded for end-of-session analyze.
2. Place this in Step 1 (Read Roadmap and Pick Next Step) or Step 2 (Load Context) so it is always executed at task start.

**Acceptance**: Implement prompt text includes the load_context-at-step-start instruction; agents running implement will record context for analyze.

### Step 2: Implement prompt — rules fallback when disabled

**Target**: Implement-next-roadmap-step prompt (e.g. Pre-Action Checklist or Step 3).

**Tasks**:

1. Add a short reminder: when `rules(operation="get_relevant", task_description="...")` returns `status: disabled`, agents should still load key coding standards (e.g. from the rules directory path via `get_structure_info()` → `structure_info.paths.rules` and Read) for implementation quality.
2. Commit prompt already has similar guidance; keep wording consistent.

**Acceptance**: Implement prompt includes the rules-disabled fallback reminder; no new tooling required.

### Step 3: Implement prompt — task-type token budget (from context effectiveness)

**Target**: Implement-next-roadmap-step prompt (Step 1/2 where `load_context` is called).

**Tasks**:

1. Use context-effectiveness budget recommendations when choosing `token_budget` for `load_context(task_description="...", token_budget=...)`: e.g. **10,000** for update/modify and implement/add, **15,000** for fix/debug and other (per `get_context_usage_statistics` insights). Optionally document the mapping in the prompt (task type → budget) so agents can select a budget that matches observed utilization and reduces waste.
2. Current default (e.g. 25k–50k) often yields &lt;30% utilization; lowering budget for update/modify and implement/add steps can reduce over-provisioning.

**Acceptance**: Implement prompt references or applies task-type-based token budgets when loading context; session analyze can still record calls.

## Success Criteria

- Step 1, Step 2, and Step 3 implemented in the implement prompt.
- End-of-session analyze runs in future implement sessions can receive context-effectiveness data when agents call load_context at step start.
- Token budgets aligned with context-effectiveness insights where applicable.
