---
title: "Blocker: Keep Finalize and Verify Memory-Bank State in Sync"
component: "Cortex MCP implement pipeline - finalize/verify phases"
work_type: "bugfix"
status: "PENDING"
priority: "Blocker"
created: "2026-03-12"
execution_order: 3
depends_on: []
---

## Blocker: Keep Finalize and Verify Memory-Bank State in Sync

**Status**: PENDING  
**Priority**: Blocker  
**Complexity**: Medium  
**Category**: Implement pipeline / Memory-bank consistency  
**Component**: Cortex MCP implement pipeline - finalize/verify phases  
**Work Type**: bugfix  
**Execution Order**: 3

## Goal

Ensure that the implement-finalize phase’s updates to `roadmap.md`, `progress.md`, and `activeContext.md` are **actually reflected** in the memory bank, and that implement-verify’s checks see consistent state (no more finalize reporting successful updates while verify reports missing entries).

## Context

- In this session, implement-finalize reported that it:
  - Added a `2026-03-12` entry to `progress.md` for `[MED-8] Reduce Prompt-Alignment Test Fragility`.
  - Appended an entry to `activeContext.md` describing partial work.  
  - Marked `[MED-8]` as `IN_PROGRESS (PARTIAL)` in the roadmap.  
- However, implement-verify later reported that:
  - `progress.md` and `activeContext.md` **did not** contain the expected `[MED-8]` entries.  
  - Verification therefore failed due to inconsistent memory-bank state.  
- This indicates either:
  - The finalize phase’s writes did not apply, were rolled back, or targeted the wrong paths/sections, or  
  - Verify was reading different or outdated views of the memory bank.

We must eliminate this finalize/verify mismatch for roadmap items.

## Implementation Steps

### Step 1: Audit finalize and verify memory-bank access patterns

1. Using MCP tools (`manage_file`, `update_memory_bank`, etc.), inspect how implement-finalize:
   - Writes to `progress.md` and `activeContext.md` (sections, headings, formats).  
   - Updates `roadmap.md` (e.g., adding entries under `Active Work`, updating statuses in `Refactoring`, etc.).
2. Similarly, inspect how implement-verify:
   - Reads these same files and determines whether a roadmap item’s partial/complete work is present.  
   - Detects inconsistencies or missing entries.
3. Identify mismatches in:
   - Section headings/paths (e.g., `## Current Work` vs `## Completed Work/### 2026-03-12`).  
   - Date formats or entry prefixes.  
   - Assumptions about how partial work is labeled.

### Step 2: Define a single source of truth for roadmap item logging

1. Specify, for each roadmap item (e.g., `[MED-8] ...`):
   - How entries must appear in `progress.md` (date heading, bullet format, required tags like `PARTIAL` or `COMPLETE`).  
   - How entries must appear in `activeContext.md` (section, title, and minimum content).  
   - How entries must appear in `roadmap.md` (under `Blockers`, `Active Work`, or `Pending plans` with canonical status markers).
2. Document these conventions in the implement/commit docs and ensure both finalize and verify use the same specification.

### Step 3: Refactor finalize to use canonical helpers

1. Introduce or reuse dedicated helpers (via MCP tools) such as:
   - `log_progress_entry(plan_id, status, summary)` for `progress.md`.  
   - `append_active_context_entry(plan_id, status, details)` for `activeContext.md`.  
   - `update_roadmap_status(plan_id, new_status)` for `roadmap.md`.
2. Ensure these helpers:
   - Use consistent headings/sections and formatting.  
   - Are the only way implement-finalize writes memory-bank changes for roadmap items.

### Step 4: Refactor verify to validate against the same helpers/spec

1. Update implement-verify to:
   - Use the same identifiers/markers (`plan_id`, tags like `PARTIAL`, date headings) when checking whether work has been logged.  
   - Validate that all three files (`roadmap.md`, `progress.md`, `activeContext.md`) reflect a consistent status for the item.
2. If discrepancies are found, implement-verify should:
   - Report precise details (which file is missing what).  
   - Suggest whether to re-run finalize or manually repair entries.

### Step 5: Add regression tests for finalize/verify round-trip

1. Add tests (unit and/or integration) that simulate a partial and full completion of a roadmap item via implement-finalize and then run implement-verify to assert:
   - All expected entries exist and match the spec.  
   - No spurious failures are reported when state is consistent.
2. Include a test mirroring this session’s `[MED-8]` partial work scenario and assert that once finalize reports success, verify also passes for the same item.

## Verification Checklist

| What to search for | Search scope | Expected result |
|---|---|---|
| Shared helpers for logging roadmap item progress | Memory-bank helper modules | Finalize and verify both depend on the same helpers/spec |
| `[MED-8]`-style tests for finalize+verify | Tests for implement pipeline | Round-trip finalize→verify tests pass without inconsistency |

## Dependencies

- Existing memory-bank files (`roadmap.md`, `progress.md`, `activeContext.md`).  
- MCP tools for managing memory-bank entries (`manage_file`, `update_memory_bank`, or equivalent helpers).

## Success Criteria

- When implement-finalize reports that a roadmap item’s partial or full completion has been logged, implement-verify sees the same state and passes.  
- Memory-bank entries for roadmap items follow a single, documented specification used by both finalize and verify.  
- Regression tests prevent future drift between finalize and verify behavior.

## Testing Strategy

- **Coverage Target**: ≥95% for new/modified helper and verification code.  
- Round-trip tests of finalize+verify for both partial and complete roadmap items.  
- Manual spot-checks of memory-bank files for representative items after running implement pipelines.
