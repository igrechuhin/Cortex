# Reconsider Memory Bank Structure and File Responsibilities

**Status**: PENDING

## Goal

Define a single, comprehensive, DRY specification for the memory bank: which files exist, each file’s dedicated goal, and how they relate. Align code, schema, templates, and documentation with that specification so the structure is consistent, complete, and non-overlapping.

## Context

The Cortex project has accumulated multiple sources of truth for memory bank structure and file roles:

- **Path resolver** (`src/cortex/core/path_resolver.py`): `_MEMORY_BANK_CORE_FILES` lists 7 files (projectBrief, productContext, activeContext, systemPatterns, techContext, progress, roadmap).
- **Schema validator** (`src/cortex/validation/schema_validator.py`): `DEFAULT_SCHEMAS` defines schemas for 6 memory bank files plus `memorybankinstructions.md`; **roadmap.md has no schema**.
- **Synapse rule** (`.cortex/synapse/rules/general/memory-bank-workflow.mdc`): States activeContext = completed work only, roadmap = future/upcoming only, no overlap.
- **CLAUDE.md / AGENTS.md**: List core files and brief responsibilities; activeContext/roadmap split is stated.
- **Memory bank instructions template** (`src/cortex/templates/memory_bank_instructions.py`): Describes 6 “Core Files” (no roadmap in the numbered list) and describes activeContext as “Current work focus, Recent changes, Next steps,” which **conflicts** with the enforced rule that activeContext = completed work only.
- **techContext.md** (in memory bank): “Core Files” list and short descriptions.
- **memory-bank-updater agent**: Detailed rules for activeContext, progress, roadmap and safe tools.

Experience from the project shows:

- Strict separation (activeContext = completed, roadmap = future) is essential to avoid duplication and corruption; single-entry tools (`register_plan_in_roadmap`, `append_progress_entry`, `append_active_context_entry`, `remove_roadmap_entry`) are required to avoid full-content write bugs.
- Responsibilities are scattered; no one document is the canonical “memory bank structure and file responsibilities.”
- Every file should have a **single dedicated goal** so there is no overlap and updates are unambiguous.

## Approach

1. **Audit** all current references to memory bank files and their described roles (code, schema, rules, prompts, agents, docs).
2. **Define** the canonical file set and a single-responsibility statement per file in one place (DRY).
3. **Document** the canonical specification (e.g. in a dedicated doc or Synapse rule) so it can be transcluded or linked from CLAUDE.md, AGENTS.md, and prompts.
4. **Align** schema (add roadmap if needed, align required/recommended sections with roles), path_resolver, memory_bank_instructions template, techContext, and memory-bank-updater with the canonical spec.
5. **Validate** that no file’s stated goal overlaps another (especially activeContext vs progress vs roadmap).

## Implementation Steps

1. **Inventory current definitions**
   - List every place that defines or describes memory bank files: path_resolver, schema_validator, memory_bank_instructions.py, memory-bank-workflow.mdc, CLAUDE.md, AGENTS.md, techContext.md, memory-bank-updater, create-plan/implement prompts.
   - For each file name, extract stated purpose/required sections and note conflicts (e.g. activeContext “current focus” vs “completed work only”).

2. **Define canonical file set and single goal per file**
   - Decide the exact list of core files (e.g. keep all 7 or justify add/remove).
   - For each file, write one sentence: “This file’s only job is X.” Ensure no overlap (e.g. “completed work” appears in exactly one file; “future work” in exactly one; “what works / what’s left” in one).
   - Explicitly define boundaries: activeContext vs progress vs roadmap (who records “done,” who records “next,” who records “future backlog”).

3. **Create single DRY specification document**
   - Add one authoritative document (e.g. under docs or Synapse rules) that contains: list of files, one dedicated goal per file, optional “required sections” summary, and flow (e.g. roadmap → complete → activeContext + progress).
   - Use transclusion or links from CLAUDE.md, AGENTS.md, and memory-bank-workflow so they reference this spec instead of duplicating structure.

4. **Align schema validator**
   - Add roadmap.md to DEFAULT_SCHEMAS if roadmap is a core file, with sections that match its dedicated goal (e.g. Blockers, Active Work, Future, Pending plans).
   - Adjust required/recommended sections for activeContext (and any others) to match the canonical spec (e.g. “Completed Work” not “Current Focus” for activeContext).

5. **Align path_resolver and initialization**
   - Ensure _MEMORY_BANK_CORE_FILES (or equivalent) matches the canonical file set; document in code that the list is sourced from the canonical spec.

6. **Align memory_bank_instructions template**
   - Update the “Core Files” list to include roadmap and to describe activeContext as “completed work only,” progress and roadmap as per canonical spec; remove conflicting “current work focus” from activeContext description.

7. **Align memory-bank-workflow and memory-bank-updater**
   - Ensure memory-bank-workflow.mdc references the canonical spec and keeps the no-overlap and flow rules.
   - Ensure memory-bank-updater agent’s file roles and safe-tool usage match the canonical spec.

8. **Update CLAUDE.md and AGENTS.md**
   - Replace inline memory bank structure lists with a pointer to the canonical spec and a short summary (file names + one-line goal each) that does not duplicate the full spec.

9. **Update techContext (and other memory bank files if they describe structure)**
   - techContext “Core Files” and “Memory Bank Location” should point to or reflect the canonical spec; avoid long duplicate lists.

10. **Validation and tests**
    - Add or update tests that assert: core file list in code equals canonical list; schema has an entry for every core file; no two files share the same “dedicated goal” wording in the spec.
    - Optionally: integration test that loads the canonical spec and checks that all referenced files exist in path_resolver and schema.

## Dependencies

- None. Optional: session-optimization and memory-bank-updater plans for consistency with safe-tool usage.

## Success Criteria

- One canonical specification exists (single document or rule) that defines: (1) the list of memory bank files, (2) exactly one dedicated goal per file, (3) boundaries between activeContext, progress, and roadmap.
- Schema validator, path_resolver, memory_bank_instructions template, memory-bank-workflow, memory-bank-updater, CLAUDE.md, AGENTS.md, and techContext are aligned with that spec (no conflicting descriptions).
- roadmap.md has a schema entry if it remains a core file.
- activeContext is described everywhere as “completed work only”; roadmap as “future/upcoming only”; progress as the designated place for “what works / what’s left” and date-based log.

## Technical Design

- **Canonical spec location**: Prefer a single markdown file under `.cortex/synapse/rules/general/` (e.g. extend memory-bank-workflow.mdc with a “Memory Bank Structure” section) or a dedicated `memory-bank-structure.mdc` that other rules and docs reference. Alternative: `docs/memory-bank-structure.md` with links from rules and CLAUDE/AGENTS.
- **Schema**: Add `roadmap.md` to `DEFAULT_SCHEMAS` with sections consistent with current roadmap format (e.g. Blockers, Active Work, Future Enhancements, Pending plans). Update activeContext required sections to include “Completed Work” and remove or reword “Current Focus” so it does not imply “in-progress” (e.g. “Current Focus” = “current area of completed work” or replace with “Completed Work (by date)”).
- **DRY**: No copy-paste of the full file list or responsibility paragraphs; one source, references elsewhere.

## Testing Strategy

- **Coverage target**: 95% for any new or modified code (e.g. schema changes, path_resolver constants).
- **Unit tests**: If a constant or helper returns “core file list,” add a test that it matches the canonical set (e.g. from a shared constant or a small parsed doc).
- **Schema tests**: Assert every core file in path_resolver has a schema in DEFAULT_SCHEMAS; assert roadmap.md schema exists and has expected section keys.
- **Integration**: Test that `is_memory_bank_fully_initialized` and schema validation work with the updated file set and sections.
- **Documentation tests**: Optional: test that memory_bank_instructions template (or key prompts) contain the correct activeContext/roadmap wording (e.g. “completed work only” for activeContext).
- **AAA pattern**: All tests follow Arrange-Act-Assert.
- **No blanket skips**: Any skip must be justified and linked to a ticket.

## Risks & Mitigation

- **Risk**: Changing schema required_sections breaks existing projects that don’t have “Completed Work” in activeContext.
  **Mitigation**: Make “Completed Work” recommended or add migration note; prefer adding sections over removing them in a minor release.

- **Risk**: Canonical spec becomes outdated if new files are added in code only.
  **Mitigation**: Tests that assert code list vs spec; single place to update when adding a file.

## Timeline

- Implementation steps 1–3: 1 session (audit, define spec, write DRY doc).
- Steps 4–9: 1–2 sessions (align schema, path_resolver, template, rules, agents, CLAUDE, AGENTS, techContext).
- Step 10: 1 session (tests and validation).

## Notes

- “Dedicated goal” means: one file, one primary purpose; no two files are the source of truth for the same kind of information (e.g. only roadmap holds “future work,” only activeContext holds “completed work summaries”).
- progress.md is the date-ordered log of achievements and status; activeContext is the durable summary of completed work; roadmap is the execution queue and future backlog. Keep that triangle clear in the spec.
