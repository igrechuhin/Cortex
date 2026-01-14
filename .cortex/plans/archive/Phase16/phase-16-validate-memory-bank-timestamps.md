# Phase 16: Validate Memory Bank Timestamps Command

## Status

- **Status**: PLANNED
- **Priority**: ASAP (Blocker for commit workflow completeness)
- **Start Date**: 2026-01-14
- **Target Completion Date**: 2026-01-15

## Goal

Design, implement, and wire a dedicated `validate-memory-bank-timestamps` command so the commit workflow can always:

- Validate that all Memory Bank timestamps use the required `YY-MM-DD` format.
- Detect and report any malformed or missing timestamps.
- Run this validation step automatically as part of the pre‑commit procedure.

## Problem

The commit workflow currently expects a `validate-memory-bank-timestamps.md` command, but that command file does not exist. As a result:

- Step 9 (“Memory bank optimization”) in the commit procedure is silently skipped.
- Timestamp normalization and validation are not enforced before commits.
- Future regressions in timestamp formatting will not be caught by automation.

This is a **gap** relative to the documented workflow and Memory Bank rules.

## Scope

- **In scope**:
  - Define a single, authoritative workflow for timestamp validation.
  - Implement the command using existing Cortex MCP tools (no ad‑hoc shell scripts).
  - Ensure all core Memory Bank files (`projectBrief.md`, `productContext.md`, `activeContext.md`, `systemPatterns.md`, `techContext.md`, `progress.md`, `roadmap.md`) are covered.
  - Add tests that exercise the timestamp validator end‑to‑end.
- **Out of scope**:
  - Large‑scale content rewrites of Memory Bank documents (beyond timestamp fixes).
  - Changing the canonical timestamp format (must remain `YY-MM-DD` per rules).

## Tasks

1. **Design Timestamp Validation Rules**
   - [ ] Confirm canonical format: `YY-MM-DD` (no time component).
   - [ ] Enumerate all headings/sections where timestamps appear (e.g., “Current Status”, dated progress entries, milestone completion dates).
   - [ ] Define how to treat legacy or free‑form dates (e.g., log a warning vs. hard failure).

2. **Implement Timestamp Scanner & Validator**
   - [ ] Add a pure helper that:
     - Scans a given Markdown string for date‑like substrings.
     - Validates them against `YY-MM-DD`.
     - Returns a structured result (valid entries, violations, suggested fixes).
   - [ ] Reuse existing tokenization/parsing utilities where possible (no bespoke regex forests).

3. **Create `validate-memory-bank-timestamps` Command**
   - [ ] Implement a command/prompt (or thin MCP wrapper) that:
     - Iterates over all Memory Bank files via `manage_file()` / `get_memory_bank_stats()`.
     - Runs the timestamp validator for each file.
     - Aggregates results into a single JSON/Markdown report.
   - [ ] Ensure the command:
     - Fails the step if any **blocking** violations remain.
     - Provides clear, actionable messages (file, line/section, bad value, expected format).

4. **Wire into Commit Workflow**
   - [ ] Reference the new command explicitly from the commit procedure (Step 9).
   - [ ] Ensure the command name and path match what the commit workflow expects.
   - [ ] Update any related documentation (e.g., `AGENTS.md`, Memory Bank rules) to mention the new step.

5. **Testing & CI Integration**
   - [ ] Add unit tests for the timestamp validator helper (valid/invalid/mixed cases).
   - [ ] Add integration tests that:
     - Create temporary Memory Bank files with bad timestamps.
     - Run the new command and assert that violations are reported.
   - [ ] Ensure CI fails when the command reports blocking violations.

6. **Backfill & Cleanup**
   - [ ] Run the new command against the existing Memory Bank.
   - [ ] Fix any timestamp violations it reports.
   - [ ] Re‑run the command to confirm a clean state.

## Success Criteria

- ✅ `validate-memory-bank-timestamps` command exists and runs without manual intervention.
- ✅ All Memory Bank files use `YY-MM-DD` timestamps exclusively (no time components).
- ✅ Commit workflow’s Step 9 no longer needs to be skipped and blocks commits on violations.
- ✅ CI fails if timestamp validation fails.
- ✅ Documentation and roadmap clearly describe the new validation step.

