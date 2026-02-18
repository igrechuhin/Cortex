# Add add_roadmap_entry MCP Tool for Minimal Roadmap Updates

**Status**: COMPLETE  
**Created**: 2026-02-02  
**Source**: Investigation report `.cortex/reviews/roadmap-update-workflow-investigation-2026-02-02T16-49.md` (Option A preferred fix)

## Goal

Add an MCP tool for minimal roadmap updates (e.g. `add_roadmap_entry(section, position, entry_text)`) that performs a server-side insert into `roadmap.md`. Plan creation (create-plan Step 6) will call this tool instead of sending the full roadmap in one `manage_file(write, ...)`. Small payload, no full-content serialization, much lower truncation risk and faster flow.

## Context

### Why This Is Needed

- **Current flow**: Create-plan Step 6 requires `manage_file(file_name="roadmap.md", operation="write", content=<complete resulting text>)` with the **full, unabridged** roadmap (~32 KB). StrReplace and direct Write on the roadmap are prohibited.
- **Truncation risk**: When the agent builds the write call, the model or tool layer may truncate the content (e.g. "Content truncated for length"), which corrupts the roadmap and forces recovery (restore from git, re-apply entry).
- **Recovery is slow**: Restoring and re-adding the entry is multi-step and error-prone.
- **No minimal-update API**: `manage_file` supports only read/write/metadata; there is no operation for "insert this bullet at section X."

### Desired State

- New MCP tool (e.g. `add_roadmap_entry`) accepts `section`, `position`, `entry_text` (and optional `change_description`). Server reads `roadmap.md`, finds the right section/line, inserts the bullet, writes the file. Client never sends full roadmap content.
- Create-plan Step 6 uses this tool for "add one plan entry"; full-content `manage_file(write)` remains as fallback when the new tool is unavailable or for non-append edits.

## Approach

1. **Design** the tool contract: parameters (`section`, `position`, `entry_text`), return shape, section identifiers matching roadmap structure (Blockers, Active Work, Future Enhancements, Pending plans).
2. **Implement** the tool in Cortex: resolve roadmap path via structure/memory-bank, read file, parse sections (e.g. by `##` headers), insert bullet at the right place, write file; reuse existing roadmap corruption checks if applicable.
3. **Update create-plan**: Step 6 instructs agents to use `add_roadmap_entry` for adding a new plan entry; keep `manage_file(roadmap.md, read)` for parsing structure and fallback to `manage_file(write, content=...)` if the new tool is unavailable.
4. **Update memory-bank-updater**: Document that when invoked from plan creation, prefer `add_roadmap_entry` for single-entry adds.
5. **Test**: Unit tests for insert logic (first/last, correct section); integration test that create-plan (or simulated add) adds an entry and roadmap stays valid.

## Implementation Steps

### Step 1: Define Tool Contract and Types

- **Target**: TypedDicts/protocols for request and response.
- **Parameters**: `section` (e.g. "blockers" | "active_work" | "future" | "pending"), `position` ("first" | "last" or after a given title), `entry_text` (single bullet string, one line), optional `change_description`.
- **Returns**: success, path or message, error message if failed.
- **Output**: Document in `docs/api/tools.md`; add TypedDicts in Cortex (e.g. in tool module or types).

### Step 2: Implement Roadmap Parse and Insert Helpers

- **Target**: Pure helpers (e.g. in `src/cortex/tools/roadmap_operations.py` or under memory-bank operations). No MCP handler yet.
- **Behavior**: Parse `roadmap.md` content by `##` headers to identify sections (Blockers (ASAP Priority), Current Status / Active Work, Future Enhancements, Pending plans). Given section and position, return updated content with new bullet inserted. Preserve exact formatting of existing lines.
- **Edge cases**: Unknown section → clear error; empty section → insert as first bullet; position "last" → append in section.
- **Tests**: Unit tests for parse (section boundaries), insert at first/last, insert after title; test that existing entries are unchanged (line count, content).

### Step 3: Implement add_roadmap_entry MCP Tool

- **Target**: New tool in Cortex (e.g. `src/cortex/tools/roadmap_operations.py` or file_operations extended). Resolve roadmap path via structure/memory-bank (memory_bank path + "roadmap.md").
- **Behavior**: Read roadmap via existing async file read (or manage_file internal path); call pure insert helper; write result via existing memory-bank write path (manage_file or equivalent) so versioning and conflict detection are preserved. Apply existing roadmap corruption fix if applicable (`fix_roadmap_content_if_needed`-style).
- **Handler**: Thin async handler with `@mcp.tool(annotations=...)`, `@ensure_usage_context`, `@mcp_tool_wrapper(timeout=...)`; delegate to pure helpers. Use `safe_write_annotations` and timeout constant (e.g. MCP_TOOL_TIMEOUT_MEDIUM).
- **Tests**: Unit tests for handler (success path, unknown section, read/write failure); integration test: call tool with test entry, then read roadmap and assert entry present and line count increased by one, rest unchanged.

### Step 4: Update Create-Plan Prompt (Step 6)

- **Target**: `.cortex/synapse/prompts/create-plan.md` Step 6 and related roadmap/error-handling text.
- **Change**: For "add one plan entry", instruct agents to call `add_roadmap_entry(section=..., position=..., entry_text=...)` when the tool is available. Require fallback: if tool is unavailable or returns error, use current flow (`manage_file(roadmap.md, read)` then `manage_file(roadmap.md, write, content=...)` with full content). Do not remove the full-content write rule for fallback; add explicit "prefer add_roadmap_entry for single-entry adds."
- **Verification**: Grep or integration test that create-plan prompt mentions add_roadmap_entry and fallback.

### Step 5: Update Memory-Bank-Updater Agent

- **Target**: `.cortex/synapse/agents/memory-bank-updater.md`.
- **Change**: In "Roadmap update (plan creation)" (or equivalent), document that when adding a single plan entry, prefer `add_roadmap_entry`; use full-content `manage_file(write)` only when updating multiple entries or when add_roadmap_entry is unavailable.

### Step 6: Integration and Documentation

- **Integration test**: Add or extend test in `tests/integration/` that (1) calls `add_roadmap_entry` with a known section and entry text, (2) reads roadmap via manage_file, (3) asserts the new bullet is present in the correct section and no other content was truncated. Use temp roadmap or restore after test if mutating real roadmap is undesirable in CI.
- **Docs**: `docs/api/tools.md` — add add_roadmap_entry (USE WHEN, EXAMPLES, RETURNS). CLAUDE.md / AGENTS.md if tool list is maintained there.

## Dependencies

- Existing structure/memory-bank path resolution (`get_structure_info`, memory_bank path).
- Existing roadmap write path and any corruption-fix logic (`fix_roadmap_content_if_needed` or equivalent).
- Create-plan prompt and memory-bank-updater agent (documentation only).

## Success Criteria

- `add_roadmap_entry` MCP tool exists and is registered; accepts section, position, entry_text; performs server-side insert.
- Create-plan Step 6 documents use of add_roadmap_entry for single-entry adds with fallback to full-content write.
- Unit tests for parse/insert helpers and for tool handler; integration test verifies entry appears in roadmap and rest unchanged.
- No regression: existing plan creation flow (fallback) still works when add_roadmap_entry is unavailable.

## Technical Design

- **Sections**: Map to roadmap headings: "blockers" → "## Blockers (ASAP Priority)"; "active_work" → "### Active Work" under Current Status; "future" → "## Future Enhancements"; "pending" → "## Pending plans (from .cortex/plans)". Parser must handle "Current Status" and "### Active Work" structure.
- **Position**: "first" = first bullet in section; "last" = last bullet in section. Optional: `after:<title>` for insert after a specific bullet (e.g. after "Phase 43").
- **Entry text**: Single line, stored as one list item (e.g. "- **Title** - PENDING - Description. Plan: .cortex/plans/slug.md."). No embedded newlines; agent responsible for format.
- **File I/O**: Use same async read/write and path validation as manage_file for memory-bank files; optionally call existing internal write path to preserve versioning and conflict checks.

## Testing Strategy (MANDATORY)

- **Coverage target**: Minimum 95% for new code (roadmap parse/insert helpers, tool handler).
- **Unit tests**:
  - Parse: roadmap content with all sections → correct section boundaries; malformed or missing section → error or safe default.
  - Insert: insert at first, last, after title; empty section; unknown section; idempotent format (existing lines unchanged).
  - Handler: success; invalid section; file read/write failure; timeout.
- **Integration test**: Call add_roadmap_entry(section="pending", position="last", entry_text="- **Test entry** - PENDING - Test."); read roadmap; assert entry present in Pending plans and line count increased by one; optionally restore roadmap for CI.
- **Regression**: Create-plan prompt still contains fallback to manage_file(write, full content); memory-bank-updater doc updated.
- **AAA pattern**: All tests Arrange-Act-Assert; no blanket skips.

## Risks & Mitigation

- **Section parsing brittle**: Roadmap format changes could break parser. Mitigation: strict contract (section headers), unit tests with real roadmap snippet; document supported format.
- **Concurrent writes**: Two agents adding at once. Mitigation: same as current flow (manage_file write path with conflict detection); add_roadmap_entry is a single read-modify-write.

## Timeline

- Steps 1–2: 1 session (design + helpers + unit tests).
- Step 3: 1 session (tool handler + integration test).
- Steps 4–6: 0.5 session (prompt/agent/docs).

## Notes

- Aligns with broader "Structured plan creation via Cortex MCP tools" (`.cortex/plans/structured-planning-cortex-mcp-tools.md`): add_roadmap_entry is the minimal first step; register_plan_in_roadmap in that plan can be this tool or a superset.
- Reference: `.cortex/reviews/roadmap-update-workflow-investigation-2026-02-02T16-49.md` for full analysis and other options (StrReplace with verification, section-based writes, hardening only).
