# Session Optimization Follow-Ups: Roadmap Dedup and Plan Lifecycle

**Status**: PENDING
**Source**: End-of-session analysis 2026-02-17 (session-optimization-2026-02-17T14-28.md)

## Goal

Propagate roadmap blocker deduplication and investigation-plan lifecycle alignment patterns to any additional roadmap writers and failure handlers, ensuring consistent, idempotent behavior across the system.

## Context

The 2026-02-17 analysis and implementation work improved:

- Submodule handling documentation in the commit prompt (non-blocking submodule push failures when commits succeed).
- Roadmap blocker deduplication for MCP tool failures via `MCPToolFailureHandler._insert_plan_entry`.
- Plan-archiver guidance to require marking investigation plans `Status: COMPLETE` before or during archiving.

Remaining follow-up work is to ensure similar patterns are applied wherever roadmap entries and investigation plans are manipulated automatically.

## Implementation Steps

1. **Inventory roadmap writers and failure handlers**
   - Identify all code paths that add entries to the `Blockers (ASAP Priority)` section or other roadmap sections automatically (e.g. additional failure handlers, helper utilities).
   - Confirm which ones reference plan paths (e.g. `.cortex/plans/phase-...` or `session-optimization-...`).

2. **Extend deduplication behavior where needed**
   - For each additional roadmap writer that adds blocker entries based on a plan path, add plan-path-based deduplication logic similar to `MCPToolFailureHandler._insert_plan_entry` so repeated failures do not create duplicate blockers for the same plan.
   - Add focused unit tests to verify: (a) first insertion succeeds, (b) second insertion referencing the same plan path is a no-op.

3. **Align plan lifecycle handling**
   - Review plan-related agents and helpers (e.g. plan-archiver, memory-bank-updater) to confirm they consistently expect investigation plans to have `Status: COMPLETE` when corresponding work in `activeContext.md`/`progress.md` is complete.
   - If any agents rely on different signals, update their documentation and behavior to prefer explicit `Status` fields for detection.

4. **Validate roadmap and plan consistency**
   - Run the roadmap sync validation (`validate(check_type="roadmap_sync")` or equivalent helper) to confirm there are no duplicate blockers for the same plan path and no completed investigation plans left in the plans root.
   - Fix any remaining inconsistencies and add regression tests where appropriate.

## Success Criteria

- All automated roadmap writers that add blocker entries based on a plan path behave idempotently for the same plan.
- Investigation plans that are complete are reliably detected via `Status: COMPLETE` and archived promptly.
- Roadmap sync validation reports no duplicate blockers or stale completed plans in the plans root.

## Notes

- Primary analysis reference: `.cortex/reviews/session-optimization-2026-02-17T14-28.md`.
- Coordinate changes with existing MCP failure-handling and commit-pipeline prompts to keep guidance aligned.
