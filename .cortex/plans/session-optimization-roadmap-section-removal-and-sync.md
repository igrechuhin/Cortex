# Session Optimization: Roadmap Section Removal and Roadmap Sync Clarity

**Status**: PENDING  
**Source**: `.cortex/reviews/session-optimization-2026-02-10T07-54.md` (actionable); `.cortex/reviews/session-optimization-2026-02-09T22-31.md`, `.cortex/reviews/session-optimization-2026-02-10T08-00.md` (context only)

## Goal

(1) Safer roadmap section removal: avoid or constrain full-content `manage_file(roadmap.md, write, ...)` when removing a section and its list. (2) Clarify or adjust `roadmap_sync` so `unlinked_plans` correctly treats plans under `.cortex/plans/archive/`.

## Context

When completing "Archive 22 tool failure investigation plans", the roadmap subsection was removed by calling `remove_roadmap_entry` for each bullet, then a full-content `manage_file(roadmap.md, write, ...)` to delete the orphan header and paragraph. That full write introduced typos (e.g. "2026-02-03" → "2026-2", "Phase 9" → "Phase9Excellence98"); they were fixed with targeted StrReplace. Separately, `validate(check_type="roadmap_sync")` reported `valid: false` due to one unlinked plan (`phase-18-markdown-lint-fix-tool.md`), which lives in archive. This plan consolidates the only actionable findings from three end-of-session reviews (2026-02-09, 2026-02-10); the other two reviews had no improvement recommendations.

## Approach

Prefer MCP or process changes over one-off docs where feasible: extend `remove_roadmap_entry` or add a section-removal helper to avoid full-file writes; adjust or document `roadmap_sync` unlinked_plans behavior for archive paths.

## Implementation Steps

### Step 1: Roadmap section removal (implement or document)

- **Option A**: Add MCP or helper that removes a section by heading (and optional intro paragraph) without full-file overwrite.
- **Option B**: Document in implement prompt / memory-bank-updater: after removing all bullets with `remove_roadmap_entry`, either leave the orphan header/paragraph or use a single minimal `manage_file(roadmap, write, ...)` that only deletes that block (no other edits).
- **Option C**: Add validation or lint that detects common corruption patterns after roadmap writes (e.g. malformed dates, broken plan links).

### Step 2: Roadmap sync and archive

- Review `roadmap_sync` validation logic for `unlinked_plans`: does it list files under `.cortex/plans/archive/`?
- If yes: either exclude archive paths from unlinked_plans, or document that archived plans may appear as unlinked and are acceptable.
- If no: fix path resolution so archive plans are not reported as unlinked when they are in archive.

### Step 3: Implement prompt / agent docs

- Add guidance: avoid full-content roadmap writes for section removal; use remove_roadmap_entry for bullets and minimal edits for section header/paragraph.
- Reference this plan from session optimization or commit-pipeline improvements where relevant.

## Dependencies

None.

## Success Criteria

- No full-content roadmap write is required for "remove a section and its list" workflow, or the risk of corruption is documented and mitigated.
- `validate(check_type="roadmap_sync")` either does not report archived plans as unlinked, or the behavior is documented and accepted.

## Testing Strategy

- **Roadmap section removal**: After implementing Step 1, run `remove_roadmap_entry` for a test list and verify either (a) no full-content write is needed for the orphan header/paragraph, or (b) minimal write is documented and safe (no unrelated edits).
- **Roadmap sync**: After Step 2, run `validate(check_type="roadmap_sync")` and confirm archived plans are either excluded from `unlinked_plans` or the behavior is documented.
- Any new MCP or code paths must have unit tests; doc-only changes require no new tests but should be validated manually per above.

## Risks & Mitigation

- **Risk**: Full-content roadmap writes remain the only way to remove a section → document strict pre-write check (e.g. length ≥ current roadmap) and single-block edit discipline to reduce typos.
- **Risk**: Changing unlinked_plans logic could hide real broken links → ensure only paths under `archive/` are excluded (or document that unlinked_plans includes archive by design).

## Timeline

Low priority; can be scheduled with other session-optimization or commit-pipeline improvements.

## Notes

- Primary review (actionable): `.cortex/reviews/session-optimization-2026-02-10T07-54.md`
- Additional context: `.cortex/reviews/session-optimization-2026-02-09T22-31.md`, `.cortex/reviews/session-optimization-2026-02-10T08-00.md`
