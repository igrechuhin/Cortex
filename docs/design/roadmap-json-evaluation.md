# Evaluation: Structured JSON Roadmap

**Status**: Evaluation complete (2026-02-09). Documented as future enhancement.

**Context**: The roadmap is currently stored as Markdown (`roadmap.md`). Plan-registration and implement flows were updated to use safe, programmatic tools (`register_plan_in_roadmap`, `add_roadmap_entry`, `remove_roadmap_entry`) to avoid full-content writes and corruption. This evaluation assesses moving the roadmap to a structured format (e.g. JSON) with dedicated read/write APIs so all edits are programmatic by design.

## Current State

- **Format**: Markdown with sections (Blockers, Active Work, Future Enhancements, Pending plans) and bullet entries.
- **APIs**: `add_roadmap_entry`, `remove_roadmap_entry`, `register_plan_in_roadmap`, `complete_plan`; `manage_file` for read/full write (fallback).
- **Parsing**: Section boundaries and bullets are derived from headers and `-` lines in `roadmap_operations.py` and `plan_completion.py`; `fix_roadmap_corruption` repairs known text corruption before write.

## Option: Structured JSON with Dedicated APIs

**Idea**: Store roadmap as JSON (or YAML) with a defined schema; expose only read/write APIs that operate on the structure (no raw full-document string assembly by clients).

### Pros

- **Programmatic edits only**: Add/remove/update entry by section and position without ever building full document text; eliminates truncation and corruption from full-content writes.
- **Schema validation**: Entries and sections can be validated (required fields, section ids, ordering).
- **Tooling**: Easier to implement reorder, bulk move, or merge; optional Markdown export for human reading.
- **Consistency**: Single source of truth in structured form; round-trip to Markdown is deterministic.

### Cons

- **Migration**: One-time migration from current `roadmap.md` to JSON and update of all readers (MCP tools, prompts, validation).
- **Readability**: Editors who open the file may prefer Markdown; can be mitigated by generated `roadmap.md` from JSON or a read-only view.
- **Scope**: Touches roadmap_operations, plan_completion, validation_roadmap_sync, file_operations (manage_file for roadmap), and any prompt that references roadmap content.

### Recommendation

- **Short term**: Keep current Markdown roadmap. The blocker fix (mandating `register_plan_in_roadmap` / `add_roadmap_entry` for plan registration and `remove_roadmap_entry` for completed steps) already makes the main edit paths programmatic and avoids the main corruption risk.
- **Future work**: When prioritizing a structured roadmap:
  1. Define a JSON schema (e.g. sections with ordered entries; fields: section_id, title, description, plan_path, status).
  2. Introduce a canonical store (e.g. `roadmap.json` in memory-bank) and APIs: get_roadmap, add_entry, remove_entry, update_entry, reorder.
  3. Optionally generate `roadmap.md` from JSON for backward compatibility and human readability.
  4. Migrate existing tools and validation to the new APIs; deprecate full-content write for roadmap.

## References

- Investigation plan (archived): `.cortex/plans/archive/Investigations/2026-02-09/investigate-roadmap-corruption-plan-registration-blocker.md`
- Current tools: `src/cortex/tools/roadmap_operations.py`, `plan_completion.py`, `roadmap_corruption.py`, `validation_roadmap_sync.py`
