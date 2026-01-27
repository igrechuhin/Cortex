# Phase 56: Commit Workflow Parallelization (Steps 9–11)

**Status:** PLANNING  
**Owner:** Cortex MCP / Synapse commit workflow  
**Last Updated:** 2026-01-27

## Goal

Safely parallelize the commit procedure’s validation and submodule steps (Steps 9–11) to reduce end-to-end commit time while preserving strict ordering for stateful steps and avoiding any “fighting” between subagents.

## Context

- The current commit workflow in `commit.md` is intentionally **fully sequential** to avoid conflicts between agents that read/write shared state (especially memory bank and plans).
- The `commit-parallelization-analysis.md` review concluded that:
  - Steps **0–8** and **12–14** must remain sequential due to strong data and ordering dependencies.
  - Steps **9 (timestamp-validator)** and **10 (roadmap-sync-validator)** are **read-only validators** and operate on different logical aspects of the memory bank/roadmap.
  - Step **11 (submodule handling)** operates on the `.cortex/synapse` submodule and is independent of memory bank state.
  - Therefore, Steps **9, 10, and 11** can safely run in parallel **after** Steps 7–8 complete, as long as we still wait for all three to finish before Step 12 (Final Validation Gate).
- The fear is that if subagents are allowed to run in parallel without strict scoping, they may:
  - Compete for the same files (read/write races on memory bank or plans).
  - Re-run overlapping checks with different assumptions.
  - Introduce non-deterministic behavior in the commit pipeline.

This plan implements a **constrained parallelization** where only read-only validation and submodule handling steps are run concurrently, keeping all write-heavy steps strictly ordered.

## High-Level Approach

1. **Preserve the existing sequential ordering** for all write-heavy and stateful steps:
   - Steps 0–4: error-fixer, quality preflight, formatting, markdown lint, type check, quality checks, tests.
   - Steps 5–8: memory-bank updates, plan archiving, archive validation.
   - Steps 12–14: final validation gate, commit creation, push.
2. **Introduce a small orchestration layer** that:
   - Runs Steps 9, 10, and 11 together in a structured concurrency group (e.g., `asyncio.TaskGroup`).
   - Collects and normalizes their results into the existing commit summary structure.
   - Ensures Step 12 only runs after all three complete successfully.
3. **Explicitly codify read/write boundaries**:
   - Document which agents are allowed to run in parallel (read-only + submodule).
   - Keep all memory bank writers (`memory-bank-updater`, `plan-archiver`) strictly serialized.
4. **Harden tests and prompts**:
   - Add tests that assert ordering and concurrency invariants.
   - Update `commit.md` to clearly call out which steps may run in parallel and why.

## Detailed Implementation Steps

### 1. Model Parallelizable vs Sequential Steps

- Extend the internal representation of the commit pipeline to include:
  - **Step metadata**: `id`, `name`, `can_run_in_parallel`, `group_id`.
  - A grouping that marks:
    - Steps 9, 10, 11 as `group_id="validation_parallel_block_9_11"`, `can_run_in_parallel=True`.
    - All other steps as `can_run_in_parallel=False`.
- Ensure this metadata is **data-only** (no behavior) so it is easy to test and reason about.

### 2. Implement Parallel Orchestration Block for Steps 9–11

- In the commit orchestration code:
  - After Step 8 completes successfully, create a **TaskGroup** to run:
    - `run_step_9_timestamp_validator()`
    - `run_step_10_roadmap_sync_validator()`
    - `run_step_11_submodule_handling()`
  - Collect results and errors for each task:
    - Normalize into the same shape currently used in the commit summary.
    - If **any** of the three steps fails or reports blocking issues:
      - Treat the entire parallel block as failed.
      - Stop the pipeline and surface a clear, per-step error summary.
- Ensure:
  - Order of side-effect-free output **does not matter**.
  - All three tasks **must finish** (no “fire-and-forget”).

### 3. Keep Memory-Bank and Plan Writers Strictly Sequential

- Explicitly enforce sequential execution for:
  - Steps 5–6: `memory-bank-updater`:
    - Updates `activeContext.md`, `progress.md`, `roadmap.md`.
  - Steps 7–8: `plan-archiver`:
    - Archives completed plans and updates memory bank links.
- Guardrails:
  - Do **not** run any memory-bank reading validators (Steps 9–10) in parallel with these writers.
  - Consider adding lightweight logging/metrics when memory bank files are written to make future conflicts easier to diagnose.

### 4. Update Commit Prompt (`commit.md`) to Reflect Parallelization

- In `commit.md`:
  - Update **Command Execution Order** section to annotate:
    - Steps 9–11 as a **parallel validation/submodule block**.
  - Add a short **“Concurrency Rules”** subsection:
    - Which steps **must remain sequential** (0–8, 12–14).
    - Which steps **may run in parallel** (9–11) and that they are logically independent and read-only/submodule.
    - A clear warning that no other new steps should be added to the parallel group without explicit dependency analysis.
- Call out in the docs that:
  - Parallelization is deliberately constrained to avoid agents “fighting”.
  - Memory-bank and plan operations remain serialized.

### 5. Add Tests for Orchestration and Safety

Design tests (unit + integration) that assert:

- **Ordering invariants**:
  - Steps 0–8 and 12–14 still run in the exact documented order.
  - Steps 9–11 all start **after** Step 8 and complete **before** Step 12.
- **Parallel execution behavior**:
  - In a test harness, Steps 9–11 can be instrumented (e.g., via mocks) to confirm they are started within a TaskGroup.
  - If one of Steps 9–11 fails:
    - The overall block is reported as failed.
    - Errors are correctly surfaced in the commit summary.
    - Step 12 is **not** executed.
- **No data races**:
  - There are **no writes** to memory bank or plans from Steps 9–11.
  - Submodule handling (Step 11) only touches `.cortex/synapse` and submodule metadata.
- **Idempotency / determinism**:
  - Running the commit procedure multiple times with the same code state yields the same logical results, regardless of scheduling of Steps 9–11.

### 6. Update Memory Bank and Docs

- After implementation:
  - Update `.cortex/memory-bank/progress.md` with a short log entry describing:
    - Parallelization of Steps 9–11.
    - Observed impact on commit run time (if measured).
  - Update `.cortex/memory-bank/activeContext.md` to reflect that work on commit workflow parallelization is in progress or completed.
  - Ensure `roadmap.md` includes this plan (see below).

## Dependencies

- Existing commit pipeline and Synapse architecture:
  - `commit.md` prompt.
  - Agents:
    - `timestamp-validator`
    - `roadmap-sync-validator`
    - Submodule handling logic in the commit orchestration.
- No new external services or MCP tools are required; this is purely:
  - Orchestration-level logic.
  - Documentation and memory bank updates.

## Risks & Mitigations

- **Risk:** Hidden write operations in validators (e.g., future changes to timestamp/roadmap validators).
  - **Mitigation:** Document and enforce that Steps 9–10 **must remain read-only**; add comments and tests that assert this behavior.
- **Risk:** More complex error handling when multiple parallel steps fail.
  - **Mitigation:** Centralize error aggregation and ensure the commit summary clearly lists per-step failures.
- **Risk:** Future contributors might incorrectly add new steps into the parallel group.
  - **Mitigation:** Document explicit rules in `commit.md` and, if possible, encode allowed parallel groups in a small data structure that is easy to review.

## Testing Strategy (MANDATORY, ≥95% Coverage for New Code)

- **Unit Tests:**
  - Orchestration helper that runs steps 9–11 in a TaskGroup:
    - All-success case.
    - Single-step failure.
    - Multiple-step failure.
  - Mapping from step metadata to execution order and grouping.
- **Integration Tests:**
  - End-to-end commit pipeline test that:
    - Uses mocks/spies for Steps 9–11 to assert concurrent execution and correct summary output.
    - Confirms that earlier and later steps still execute in strict order.
- **Negative/Edge Cases:**
  - One of the parallel steps timing out or raising an unexpected exception.
  - Submodule handling skipped (no changes in `.cortex/synapse`) while validators still run.
- **Coverage Target:**
  - ≥95% coverage for:
    - New orchestration helpers.
    - Any new data structures for step metadata.
  - Ensure existing overall project coverage stays ≥90%.

## Success Criteria

- Commit pipeline:
  - Still enforces all existing quality gates with **no regressions**.
  - Successfully runs Steps 9–11 in parallel and Step 12 only after they complete.
- Agents:
  - No reports of conflicting writes between agents.
  - Validators (Steps 9–10) remain read-only.
- Observability:
  - Commit summary clearly indicates parallel execution of Steps 9–11.
  - Errors in any of these steps are clearly surfaced and block commit as before.
- Documentation:
  - `commit.md` updated to reflect the parallel block and concurrency rules.
  - Memory bank (roadmap, progress, activeContext) updated to record this work.

