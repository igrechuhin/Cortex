# Session Optimization Analysis

## Summary

Analysis focused on a single, user-identified mistake pattern: **implementing plan steps in non-sequential order** (e.g. "Step 1 (partial) and Step 6 (partial)" in Phase 27). The roadmap already enforces sequential execution at the roadmap level (Blockers → Active Work → …); the same principle was missing for **steps within a plan**, making it hard to predict and plan what will be implemented in a session. Recommendations were to promote sequential execution to plan steps and to document it in both the implement and create-plan prompts. Those changes have been applied.

## Mistake Patterns Identified

### Pattern 1: Non-sequential plan step execution

- **Description**: When implementing a plan, the agent implemented a subset of steps out of order (e.g. Step 1 and Step 6 partial) instead of Step 1, then Step 2, then Step 3, etc.
- **Examples**: Phase 27 (Script generation prevention): "Step 1 (partial) and Step 6 (partial) implemented" — script_detection module (Step 1) and MCP tools capture_session_script / list_session_scripts (Step 6) were done in one run; Steps 2–5 were skipped for that session.
- **Frequency**: Observed in at least one implementation session (Phase 27); user reported it makes prediction and planning difficult.
- **Impact**: Medium–high. Unpredictable execution order makes it hard to plan sessions, estimate scope, and reason about dependencies (e.g. Step 6 may depend on outputs of Steps 2–5).

## Root Cause Analysis

### Cause 1: No sequential rule for plan steps

- **Description**: The implement prompt stated "implement the plan (or as much as possible in one session)" without specifying that plan steps have an order and must be executed in sequence.
- **Contributing factors**: Roadmap-level sequence is explicit (Blockers → Active Work → …); plan-level sequence was implicit. Agents reasonably interpreted "as much as possible" as "pick high-value or tractable steps" rather than "next N steps in order."
- **Prevention opportunity**: Make plan-step sequence explicit in the implement prompt (same principle as roadmap order) and in the create-plan prompt so that steps are written with a clear implementation order.

## Optimization Recommendations

### Recommendation 1: Enforce sequential plan steps in implement prompt (DONE)

- **Priority**: High
- **Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md`
- **Change**: Added a "Plan step sequence (MANDATORY when implementing a plan)" block: execute plan steps in order (Step 1, then Step 2, …); next step = first uncompleted step; do not skip or reorder; if the session cannot finish all steps, complete as many as possible in order and update the plan file.
- **Expected impact**: Prevents out-of-order implementations (e.g. "Step 1 + Step 6 partial"); makes each run predictable (next step only) and easier to plan.
- **Implementation**: Applied in this session (see diff to `implement-next-roadmap-step.md`).

### Recommendation 2: Document plan-step sequence in create-plan (DONE)

- **Priority**: Medium
- **Target**: `.cortex/synapse/prompts/create-plan.md`
- **Change**: Under "Implementation Steps", clarified that steps define an implementation sequence and that the implement command will execute them in order; instructed to number steps and list them in implementation order.
- **Expected impact**: New and enriched plans will be written with a clear step order, reinforcing sequential execution at implementation time.
- **Implementation**: Applied in this session (see diff to `create-plan.md`).

## Implementation Plan

1. ✅ Add "Plan step sequence" to implement-next-roadmap-step.md (Step 1, after plan file reference).
2. ✅ Add "implementation sequence" wording to create-plan.md (Implementation Steps in plan structure).

## Expected Impact

- **Predictability**: Each implement run on a plan will target the **next** uncompleted step (or the next N steps in order), not an arbitrary subset.
- **Planning**: Users and agents can predict "next run will do Step 2" (or "Steps 2–3") when Step 1 is done.
- **Dependencies**: Steps that depend on earlier steps (e.g. analysis before promotion) are less likely to be run before their prerequisites.

## Notes

- Roadmap order (Blockers → Active Work → Future Enhancements → Pending plans) was already correct and unchanged.
- Plan file update requirements (when work is incomplete in one session) were already in place; the new rule only constrains **which** steps are implemented (next in order), not whether the plan file is updated.
