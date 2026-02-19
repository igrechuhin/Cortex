# Roadmap Sync Cleanup (Pre-existing Issues)

**Source**: End-of-session analysis 2026-02-09 (`session-optimization-2026-02-09T09-10.md`).

**Goal**: Resolve `validate(check_type="roadmap_sync")` failures so validation reports `valid: true`.

## Context

Roadmap sync validation currently reports:

- **missing_roadmap_entries**: 2 TODOs in code not tracked in roadmap (script_integrator.py, tool_converter.py).
- **invalid_references**: 22 investigation plan filenames listed in roadmap under "Tool Failure Investigations (Archive Recommended)" resolve to non-existent paths (plans may be in archive or path resolver expects different location).
- **unlinked_plans**: Multiple plans in `.cortex/plans/` with no corresponding roadmap entry.

## Steps

1. **Add missing roadmap entries** for the 2 TODOs (script_integrator.py L45, tool_converter.py L44) or document why they are out of scope.
2. **Fix investigation plan references**: Either update roadmap to point to archive paths (e.g. `.cortex/plans/archive/Investigations/2026-02-04/`) or remove/consolidate the list and archive the plan files.
3. **Link or archive unlinked plans**: For each plan in `.cortex/plans/` that is not in the roadmap, either add a roadmap entry (if still relevant) or move to archive.
4. **Re-run** `validate(check_type="roadmap_sync")` and confirm `valid: true`, empty `missing_roadmap_entries`, no invalid references, and no unlinked non-archived plans.

## Acceptance

- `validate(check_type="roadmap_sync")` returns `valid: true`.
- No new hardcoded paths; use `get_structure_info()` and MCP tools for paths.
