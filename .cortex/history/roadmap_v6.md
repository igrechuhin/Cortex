# Roadmap: MCP Memory Bank

**This file records future/upcoming work only.** Completed work is recorded in [activeContext.md](../memory-bank/activeContext.md). Do not duplicate entries between the two files.

**Implementation sequence**: The implement command picks the **next step as the **first PENDING item** when reading the roadmap in this order: (1) Blockers (ASAP Priority), (2) Active Work, (3) Future Enhancements, (4) Implementation queue (Pending plans). Order within each section is top-to-bottom. New plans are added by create-plan in the correct place so this order defines execution.

## Blockers (ASAP Priority)

- **Blocker: Fix MCP Plan Tool Argument Wiring/Bridging and Audit Similar Gaps** - IN_PROGRESS (partial: guardrail test + quality fixes) - Plan: `plans/fix-mcp-plan-tool-argument-bridging.md` — Ensure MCP-orchestrated flows call `plan`, `manage_file`, `rules`, and `execute_pre_commit_checks` with full JSON payloads, hardening `plan(operation="create"|"register"|"complete")` and auditing similar gaps.
- **Blocker: Implement-Select Must Respect Explicit Plan Targets** - IN_PROGRESS (PARTIAL) - Plan: `plans/blocker-implement-select-explicit-plan.md` — Explicit-plan-first selection behavior is now encoded in the implement pipeline prompts and prompt-level tests; deeper runtime wiring and eligibility logic still need to be implemented.
- **Blocker: Make Pre-Commit Job Status Observable and Bounded** - PENDING - Plan: `plans/blocker-pre-commit-job-status.md` — Ensure `start_pre_commit_job`/`get_pre_commit_job_status` always reach a clear terminal state (completed/failed/timeout) within bounded time and surface quality-gate results instead of hanging in `running`.
- **Blocker: Keep Finalize and Verify Memory-Bank State in Sync** - PENDING - Plan: `plans/blocker-finalize-verify-memory-bank-sync.md` — Fix implement-finalize and implement-verify so that roadmap/progress/activeContext updates are consistent and verification never fails due to finalize reporting changes that aren't visible to verify.

## Active Work (in progress)

- **[MED-8] Reduce Prompt-Alignment Test Fragility** ":" IN_PROGRESS (PARTIAL). Implemented semantic relaxation for implement-prompt guidance tests in `tests/integration/test_commit_workflow_prompt_alignment.py` using lowercased content and synonym lists; remaining fragile substring assertions in other prompt-alignment tests will be refactored in later subtasks.

## Future Enhancements

## Pending plans (from .cortex/plans)

### Fixes

### Documentation Cleanup (DRY)

### Refactoring

- **[MED-8] Reduce Prompt-Alignment Test Fragility** — Refactor substring assertions to semantic checks. MUST complete before HI-1. Plan: `plans/reduce-prompt-alignment-test-fragility.md` | Priority: Medium | Order: 20
- **[HI-4] Consolidate Roadmap Sync Models** — Remove legacy duplicates in `src/cortex/validation/roadmap_models.py`. Plan: `plans/consolidate-roadmap-sync-models.md` | Priority: High | Order: 9
- **[HI-7] Reduce Redundant Pipeline Checks** — Dirty-state tracking to skip clean checks in final validation. Depends: CRI-3, HI-1. Plan: `plans/reduce-redundant-pipeline-checks.md` | Priority: High | Order: 12
- **[MED-9] Reduce Oversized Modules** — Split top 5 files (>550 lines) to comply with 400-line limit. Plan: `plans/reduce-oversized-modules.md` | Priority: Medium | Order: 21

### Cleanup

### Investigation Plans (Archive / Reference)

Completed investigations are recorded in [activeContext.md](../memory-bank/activeContext.md). Plan files under `.cortex/plans/archive/` as needed.

### Features & Enhancements

- **[HI-2] Structured Quality Config** — Add structured quality config (JSON under `.cortex/config/`) replacing markdown-parsed thresholds. Plan: `plans/add-structured-quality-config.md` | Priority: High | Order: 7
