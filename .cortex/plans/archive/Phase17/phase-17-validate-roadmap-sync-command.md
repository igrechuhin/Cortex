# Phase 17: Validate Roadmap Sync Command

## Status

- **Status**: PLANNED
- **Priority**: ASAP (Blocker for roadmap/codebase consistency)
- **Start Date**: 2026-01-14
- **Target Completion Date**: 2026-01-15

## Goal

Provide a robust `validate-roadmap-sync` command so the commit workflow can automatically verify that:

- All production TODOs / work items in the codebase are tracked in `roadmap.md`.
- All roadmap entries that reference files/lines remain valid.
- There are no orphaned roadmap items pointing at code that no longer exists.

## Problem

The commit workflow references a `validate-roadmap-sync.md` command, but that command file does not exist. Today:

- Step 10 (“Roadmap synchronization validation”) is always skipped.
- There is no automated guard that the roadmap stays in sync with sources.
- Violations of the “all TODOs must be tracked in roadmap.md” rule can slip through.

This is a **gap** that undermines the reliability of the Memory Bank as a source of truth.

## Scope

- **In scope**:
  - Define a single, canonical roadmap ↔ code synchronization check.
  - Implement a command that uses MCP tools and existing helpers (no ad‑hoc greps).
  - Validate both directions:
    - Code → Roadmap: production TODOs and markers must be represented in `roadmap.md`.
    - Roadmap → Code: referenced files/paths/line numbers must still exist.
  - Integrate with the commit workflow and CI.
- **Out of scope**:
  - Rewriting the entire roadmap structure.
  - Changing how TODO comments are formatted in the codebase (beyond what’s needed for discovery).

## Tasks

1. **Define Synchronization Rules**
   - [ ] Enumerate which TODO markers should be considered “production TODOs” (e.g., `# TODO:`, `// TODO:` without `test`/`example`).
   - [ ] Decide how roadmap entries encode references (file path only vs. file + line vs. section anchors).
   - [ ] Define what constitutes a **blocking** desync vs. a warning (e.g., missing roadmap entry vs. extra roadmap notes).

2. **Implement Codebase TODO Scanner**
   - [ ] Add or reuse a helper that:
     - Scans `src/` (and other production directories) for TODO markers.
     - Produces a structured list: `{file_path, line, snippet, category}`.
   - [ ] Ensure the scanner is language‑agnostic (works for multi‑language repositories).

3. **Implement Roadmap Reference Parser**
   - [ ] Parse `roadmap.md` into a structured form capturing:
     - Phase/milestone headings.
     - TODO entries and their associated file references (if any).
   - [ ] Normalize file paths to match repository layout (`src/`, `.cortex/memory-bank/`, etc.).

4. **Create `validate-roadmap-sync` Command**
   - [ ] Implement a command/prompt (or thin MCP wrapper) that:
     - Uses the TODO scanner (Code → Roadmap).
     - Uses the roadmap parser (Roadmap → Code).
     - Produces a diff‑like report of:
       - TODOs present in code but missing from roadmap.
       - Roadmap items pointing to missing/renamed files or invalid line ranges.
   - [ ] Ensure the command can:
     - Fail the step on blocking issues.
     - Optionally emit suggestions for new roadmap entries to add.

5. **Wire into Commit Workflow**
   - [ ] Create a `validate-roadmap-sync.md` command file (or equivalent) that the commit workflow can call directly.
   - [ ] Update the commit procedure documentation to:
     - Reference the new command.
     - Clarify that commits are blocked when roadmap sync fails.

6. **Testing & CI Integration**
   - [ ] Add unit tests for the TODO scanner and roadmap parser.
   - [ ] Add integration tests that:
     - Introduce unsynced TODOs and assert that the command fails with clear diagnostics.
     - Introduce stale roadmap references and assert they are detected.
   - [ ] Wire the command into CI so desynchronization fails the pipeline.

7. **Backfill & Cleanup**
   - [ ] Run the new command against the current codebase and roadmap.
   - [ ] Fix any discrepancies (missing roadmap entries or stale references).
   - [ ] Re‑run until the command reports a fully synchronized state.

## Success Criteria

- ✅ `validate-roadmap-sync` command exists and is callable from the commit workflow.
- ✅ All production TODOs are represented in `roadmap.md` with appropriate context.
- ✅ All roadmap references to source files are valid and up‑to‑date.
- ✅ Commit workflow’s Step 10 is enforced (commits blocked on desync).
- ✅ CI fails when roadmap synchronization fails.

