# Session Optimization: Roadmap Completed-Section Cleanup

**Status**: PENDING  
**Source**: `.cortex/reviews/session-optimization-2026-02-10T10-44.md` (end-of-session analysis for roadmap section removal and roadmap_sync clarity)

## Goal

Remove legacy "completed" sections from `roadmap.md` that violate the future-only contract, while preserving history in `activeContext.md` and ensuring `roadmap_sync` passes without `completed_entries_in_roadmap` violations.

## Context

Previous work ("Session Optimization: Roadmap Section Removal and Roadmap Sync Clarity") addressed:

- Safe roadmap section removal patterns (use `remove_roadmap_entry` for bullets, then at most a single minimal block edit for the heading/intro paragraph).  
- Clarified how `roadmap_sync.unlinked_plans` should be interpreted for archived plans.

However, the current roadmap still includes a large historical "completed" summary section that:

- Contains bullets that look like completed work (e.g., "- ✅ ... - COMPLETE"), violating the rule that `roadmap.md` records future/upcoming work only.  
- Causes `validate(check_type="roadmap_sync")` to report `completed_entries_in_roadmap` violations.  
- Duplicates information that already lives (or should live) in `activeContext.md` and `progress.md`.

This plan defines a focused follow-up to clean up the legacy completed section(s) safely, using the documented block-edit pattern and existing validation tools.

## Approach

1. **Inventory and mapping**
   - Identify the legacy "completed" section(s) in `roadmap.md` that cause `completed_entries_in_roadmap` violations.  
   - Map each completed bullet to existing entries in `activeContext.md` and/or `progress.md`, noting any gaps where completed work is only documented in the roadmap.

2. **Migrate missing history to activeContext/progress**
   - For any completed roadmap bullet not already represented in `activeContext.md` (or represented only partially), add or enrich entries in:
     - `activeContext.md` → high-level completed-work summary (date, title, outcome).  
     - `progress.md` → more granular progress entries tied to the same date(s).

3. **Remove legacy completed section(s) from roadmap**
   - Once all history is safely captured in `activeContext.md` / `progress.md`, remove the legacy completed section(s) from `roadmap.md` using the single-block edit pattern:
     - Keep using `remove_roadmap_entry` for any remaining bullets where applicable.  
     - For the now-empty section header + intro paragraph, perform **one** minimal `manage_file(roadmap.md, write, ...)` edit that deletes just that contiguous block, leaving all other content untouched.

4. **Validate with roadmap_sync and timestamps**
   - Re-run `validate(check_type="roadmap_sync")` to confirm `completed_entries_in_roadmap` is empty and no new `unlinked_plans` or `invalid_references` were introduced.  
   - Run timestamp validation (`check_type="timestamps"`) to ensure any new dates added to `activeContext.md` / `progress.md` follow the `YYYY-MM-DD` convention.

5. **Document the migration**
   - Add a short note in `activeContext.md` (e.g., under a "Completed Work (2026-02-XX)" entry) summarizing that legacy completed bullets were migrated from `roadmap.md` and the completed section removed using the documented block-edit pattern.

## Implementation Steps

### Step 1: Analyze legacy completed sections in roadmap.md

1. Read `roadmap.md` via `manage_file(file_name="roadmap.md", operation="read")`.  
2. Use the `validate(check_type="roadmap_sync")` tooling to list `completed_entries_in_roadmap` and locate the exact lines corresponding to the legacy completed section(s).  
3. Confirm that these bullets are truly historical/completed (not future work mis-labeled) by cross-checking with `activeContext.md` and `progress.md`.

### Step 2: Build mapping from completed bullets to activeContext/progress

1. For each completed roadmap bullet:
   - Extract: title, phase/feature name, completion date (if present), and any linked plan or report.  
   - Search `activeContext.md` for a matching or related completed entry.  
   - Search `progress.md` for corresponding progress lines.
2. Produce a mapping table (in notes or comments) indicating, per bullet:
   - "Already represented" (both activeContext + progress adequately cover it), or  
   - "Partially represented" (needs enrichment), or  
   - "Missing" (needs new entries).

### Step 3: Migrate missing or partial history into activeContext.md and progress.md

1. For bullets marked "Missing" or "Partially represented":
   - Add or extend entries in `activeContext.md` under the appropriate date header, following the "Completed Work (YYYY-MM-DD)" pattern used today.  
   - Add one or more progress entries in `progress.md` under the same date(s), including short but specific descriptions of what was done.
2. Ensure new entries conform to:
   - Memory-bank rules (activeContext = completed work only; progress = progress log).  
   - Timestamp conventions (`YYYY-MM-DD`, no time component).  
   - Markdown formatting and code-style conventions (backticks for code identifiers, etc.).

### Step 4: Remove legacy completed section(s) from roadmap.md using block-edit pattern

1. After migration, re-confirm that every completed bullet from the legacy section is now represented in `activeContext.md` and `progress.md`.  
2. Remove any remaining bullets from the legacy completed section using `remove_roadmap_entry(entry_contains="<unique substring>")` where possible.  
3. When the section header and intro paragraph are empty of bullets:
   - Perform **one** minimal `manage_file(file_name="roadmap.md", operation="write", content=<full roadmap with that block removed>, change_description="Remove legacy completed section after migration to activeContext/progress")` call that deletes only the contiguous block (heading + optional intro paragraph + now-empty list).  
   - Ensure the rest of `roadmap.md` is preserved byte-for-byte to avoid accidental corruption (no re-wrapping, no date renaming, no structural changes elsewhere).

### Step 5: Re-run validations and confirm contracts

1. Call `validate(check_type="roadmap_sync")` and verify:
   - `valid` is `True` (or fails only on unrelated known issues), and  
   - `completed_entries_in_roadmap` is empty.  
2. Call `validate(check_type="timestamps")` (all files or at least `activeContext.md`, `progress.md`, `roadmap.md`) and verify:
   - All new timestamps conform to `YYYY-MM-DD` (no times/timezones).  
3. If any validation issues appear that are directly caused by this migration (e.g., broken plan links introduced while editing), fix them and re-run validation.

### Step 6: Document the cleanup in the memory bank

1. Add a new entry to `activeContext.md` under the current date summarizing:
   - That the legacy completed section in `roadmap.md` was cleaned up.  
   - That completed bullets were migrated into `activeContext.md` and `progress.md` as needed.  
   - That `roadmap_sync` now passes without `completed_entries_in_roadmap` violations (or explain any remaining, unrelated issues).
2. Add a corresponding bullet to `progress.md` under the same date describing the migration and validation.

## Dependencies

- Existing roadmap structure and historical completed section(s).  
- `validate(check_type="roadmap_sync")` and `validate(check_type="timestamps")` MCP tooling.  
- Existing memory bank files: `activeContext.md`, `progress.md`, `roadmap.md`.

## Success Criteria

- All legacy "completed" bullets are removed from `roadmap.md` after their content is fully represented in `activeContext.md` and `progress.md`.  
- `validate(check_type="roadmap_sync")` reports **no** `completed_entries_in_roadmap` violations for `roadmap.md`.  
- All new timestamps added during migration pass `validate(check_type="timestamps")` (date-only `YYYY-MM-DD`).  
- Memory bank clearly reflects the migration in both `activeContext.md` and `progress.md`.

## Testing Strategy (MANDATORY)

- **Coverage Target**: Achieve **≥95% test coverage** for any new code or tooling added to support this migration (e.g., helpers that read/transform roadmap content).

- **Unit Tests**:
  - Add or extend unit tests around `validate_roadmap_sync` to assert that `completed_entries_in_roadmap` is empty after the migration (using synthetic roadmap content that matches the new structure).  
  - If new helpers are introduced to parse/migrate roadmap sections, test them in isolation:
    - Mapping from legacy completed bullets to structured objects.  
    - Detection of whether a bullet is already represented in `activeContext.md` / `progress.md`.

- **Integration Tests**:
  - Add or extend integration tests that:
    - Build a small test memory-bank fixture (`roadmap.md`, `activeContext.md`, `progress.md`) with a legacy completed section.  
    - Run the migration logic (or simulate the end state).  
    - Assert that after migration, `validate(check_type="roadmap_sync")` returns `completed_entries_in_roadmap == []` and the roadmap no longer contains completed-style bullets.  
    - Assert that `activeContext.md` and `progress.md` contain appropriate migrated entries.

- **Edge Cases**:
  - Bullets where completion dates are missing or malformed; ensure migration still produces valid `YYYY-MM-DD` dates (or documents missing dates clearly).  
  - Bullets that reference archived plans or external reports; ensure links are preserved or updated, not dropped.  
  - Mixed sections where some bullets are still future work; ensure only the legacy completed block is removed and future/upcoming items remain.

- **Pydantic v2 for JSON Testing**:
  - When testing MCP responses from `validate(...)` wrappers (e.g., `validation_operations.validate`), use Pydantic v2 models and `model_validate_json()` / `model_validate()` on tool output instead of asserting on raw `dict` shapes, following existing patterns in `tests/tools/test_file_operations.py`.

- **AAA Pattern & No Blanket Skips**:
  - All tests must follow Arrange–Act–Assert.  
  - No blanket skips; any skip must include a justification and linked ticket.

## Risks & Mitigation

- **Risk**: Accidentally removing future/upcoming roadmap items while editing.
  - **Mitigation**: Strictly target only the legacy completed section(s) identified via `completed_entries_in_roadmap` and manual review; preserve all other roadmap content byte-for-byte when performing the minimal block edit.

- **Risk**: Losing historical information during migration.
  - **Mitigation**: Treat migration as two-step: (1) ensure all bullets are represented in `activeContext.md` / `progress.md`; (2) only then remove the legacy section from `roadmap.md`.

- **Risk**: Introducing new validation failures (broken links, bad timestamps).
  - **Mitigation**: Re-run `validate(check_type="roadmap_sync")` and `validate(check_type="timestamps")` after migration; fix any issues before considering the plan complete.

## Timeline

- **Day 1**: Inventory legacy completed sections; build mapping to activeContext/progress; identify gaps.  
- **Day 2**: Migrate missing/partial history into memory bank; remove legacy completed section(s) from roadmap using block-edit pattern.  
- **Day 3**: Final validation (roadmap_sync, timestamps), test additions, and documentation updates in memory bank.

## Notes

- This plan is a follow-up to **"Session Optimization: Roadmap Section Removal and Roadmap Sync Clarity"**, focused on cleaning up legacy completed content in `roadmap.md` while preserving all history in the memory bank.
