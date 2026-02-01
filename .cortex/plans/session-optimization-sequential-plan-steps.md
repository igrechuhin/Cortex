# Session Optimization (2026-02-01 15-23): Sequential Plan Steps

**Status**: Pending  
**Source**: `.cortex/reviews/session-optimization-2026-02-01T15-23.md`  
**Created**: 2026-02-01

## Goal

Document and verify enforcement of **sequential plan-step execution** in the implement and create-plan prompts so that agents execute plan steps in order (Step 1, then Step 2, …) instead of picking an arbitrary subset (e.g. Step 1 and Step 6 partial). The review identified that roadmap-level sequence was already explicit; plan-level sequence was missing and has been addressed by prompt changes. This plan ensures those changes are present and optionally adds tests to guard them.

## Context

The session optimization review (2026-02-01 15-23) analyzed a single mistake pattern:

- **Pattern**: When implementing a plan, the agent implemented steps out of order (e.g. Phase 27: "Step 1 (partial) and Step 6 (partial)" — script_detection module and MCP tools done in one run; Steps 2–5 skipped). This makes prediction and planning difficult and can violate step dependencies.
- **Root cause**: The implement prompt did not state that plan steps have an order and must be executed in sequence; agents reasonably interpreted "as much as possible" as "pick high-value or tractable steps" rather than "next N steps in order."
- **Recommendations (applied in review session)**:
  1. Add "Plan step sequence (MANDATORY when implementing a plan)" to `.cortex/synapse/prompts/implement-next-roadmap-step.md`.
  2. Under "Implementation Steps" in `.cortex/synapse/prompts/create-plan.md`, clarify that steps define an implementation sequence and that the implement command will execute them in order; number steps and list them in implementation order.

## Approach

1. **Verify** that both prompts contain the required wording (they may already have been applied in the session that produced the review).
2. **If missing**: Add the "Plan step sequence" block to implement-next-roadmap-step.md and the "implementation sequence" wording to create-plan.md per the review.
3. **Optional**: Add an integration test that asserts the implement prompt file contains the Plan step sequence block and that create-plan contains implementation sequence in Implementation Steps, to prevent regressions.

## Implementation Steps

### Step 1: Verify implement-next-roadmap-step.md Contains Plan Step Sequence (High)

- **Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md`.
- **Check**: File must contain a "Plan step sequence (MANDATORY when implementing a plan)" block that states: execute plan steps in order (Step 1, then Step 2, …); next step = first uncompleted step; do not skip or reorder; if the session cannot finish all steps, complete as many as possible in order and update the plan file.
- **If missing**: Add the block (e.g. after plan file reference in Step 1). See review "Recommendation 1" for exact wording.
- **Expected impact**: Ensures implement runs target the next uncompleted step only, not an arbitrary subset.

### Step 2: Verify create-plan.md Documents Implementation Sequence (High)

- **Target**: `.cortex/synapse/prompts/create-plan.md`.
- **Check**: Under "Implementation Steps" (plan structure), text must state that steps define an implementation sequence and that the implement command will execute them in order; instruct to number steps and list them in implementation order.
- **If missing**: Add the wording under "Implementation Steps" per review "Recommendation 2."
- **Expected impact**: New and enriched plans are written with a clear step order, reinforcing sequential execution at implementation time.

### Step 3: Optional — Add Integration Test for Prompt Content (Medium)

- **Target**: `tests/integration/` (e.g. `test_implement_prompt_quality_gates.py` or a new `test_plan_step_sequence_prompts.py`).
- **Change**: Add a test that (1) reads the implement prompt file (path resolved via project structure or fixture), (2) asserts that the file content includes a string such as "Plan step sequence" and "MANDATORY when implementing a plan" (or equivalent). Optionally assert that create-plan.md content includes "implementation sequence" and "execute them in order" (or equivalent) in the Implementation Steps section.
- **Expected impact**: Prevents accidental removal or rephrasing that drops the sequential plan-step rule.
- **Note**: Synapse prompts may live in a submodule; test should resolve path via `get_structure_info()` or a test fixture that points at the repo’s Synapse prompts directory.

### Step 4: Update Roadmap and Memory Bank (High)

- **Target**: Roadmap and progress/activeContext as per project workflow.
- **Change**: After verification (and any edits), add or update the roadmap entry for this session optimization (e.g. "Session optimization (2026-02-01 15-23): Sequential plan steps — COMPLETE") and update progress/activeContext if needed.
- **Expected impact**: Clear traceability from review → plan → roadmap.

## Dependencies

- **Synapse**: Prompts live under `.cortex/synapse/prompts/` (or resolved Synapse directory); may be a git submodule.
- **Path resolution**: Use Cortex MCP `get_structure_info()` for plans/prompts paths; do not hardcode `.cortex/` paths.

## Success Criteria

- implement-next-roadmap-step.md contains an explicit "Plan step sequence (MANDATORY when implementing a plan)" block that enforces step order (next step only; no skip/reorder).
- create-plan.md Implementation Steps section states that steps define an implementation sequence and that the implement command will execute them in order; instructions to number and list steps in implementation order are present.
- Roadmap entry exists for this session optimization and reflects completion after verification.
- Optional: Integration test asserts prompt content contains the required wording; all tests pass.

## Testing Strategy

- **Verification (Steps 1–2)**: Manual or scripted read/grep of prompt files to confirm required strings/sections exist. No new production code if only verification is done.
- **Integration test (Step 3, optional)**:
  - **Coverage target**: If new test file or assertions are added, maintain project test coverage (e.g. 90%+); the test exercises prompt file content, not production Python.
  - **Unit/Integration**: Single test (or two) that read(s) implement-next-roadmap-step.md and create-plan.md and assert content includes "Plan step sequence", "implementation sequence", and "in order" (or equivalent). Use path from `get_structure_info()` or conftest fixture for Synapse prompts path.
  - **AAA pattern**: Arrange (resolve path, read file), Act (parse content), Assert (required substrings/sections present).
  - **No blanket skips**: If test is skipped (e.g. Synapse not present), justify and link ticket.
- **Regression**: Existing test suite and pre-commit checks must pass.

## Risks & Mitigation

- **Submodule location**: Synapse may be a submodule; path might differ in CI vs local. Mitigation: Resolve path via `get_structure_info()` or documented fixture; skip test with reason if prompts directory is missing.
- **Wording drift**: Exact strings may be rephrased later. Mitigation: Assert on semantic content (e.g. "Plan step sequence" and "in order" / "next" step) rather than a single literal block.

## Timeline

- Step 1–2: Single session (verify and optionally add missing wording).
- Step 3: Single session if optional test is implemented.
- Step 4: Same session (roadmap/memory bank update).

## Notes

- Review file: `.cortex/reviews/session-optimization-2026-02-01T15-23.md`. Recommendations 1 and 2 were marked DONE in the review; implementation may already be present in the repo.
- Roadmap order (Blockers → Active Work → Future Enhancements → Pending plans) was unchanged; only plan-step sequence within a plan was added.
- Expected impact: Each implement run on a plan will target the **next** uncompleted step (or next N in order), improving predictability and respecting step dependencies.
