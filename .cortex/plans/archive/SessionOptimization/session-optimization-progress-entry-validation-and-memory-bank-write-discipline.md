# Session Optimization: Progress Entry Validation and Memory Bank Write Discipline

**Status**: PENDING
**Created**: 2026-02-18
**Source**: End-of-session analysis 2026-02-18T20-32

## Goal

Reduce mistake patterns from progress entry typos and memory-bank write rule violations.

## Context

- **Progress entry typo**: A `complete_plan` call used a malformed `progress_entry` string ("20260209COMPLETE" instead of "20260209)** - COMPLETE"), which produced a corrupted progress bullet. Fix required a manual edit.
- **Memory bank write rule**: The correction was applied with StrReplace on progress.md; AGENTS.md requires all memory-bank updates via `manage_file()` only (read then write for single-line fixes).

## Requirements

1. **Progress entry validation**: When generating text for `progress_entry` or `append_progress_entry`, ensure phase/title segments are properly closed (e.g. ")** - COMPLETE") before calling the tool. Document in memory-bank-updater agent or implement prompt.
2. **Memory bank write discipline**: In implement and analyze prompts (and AGENTS.md), state explicitly that any edit to memory-bank files—including one-line fixes—must use `manage_file(operation='read')` then `manage_file(operation='write', content=...)`; do not use Write, StrReplace, or ApplyPatch on memory-bank paths.
3. **Optional**: Add a small validation in the MCP layer or in the memory-bank-updater agent to reject progress bullets that match common corruption patterns (e.g. missing ")** - " before "COMPLETE").

## Success Criteria

- Implement/analyze (and related) prompts and AGENTS.md clearly require manage_file for all memory-bank writes.
- Progress entry generation guidance or validation reduces malformed bullets.
- No new violations of "no file tools for memory-bank writes" in normal flows.

## Notes

- Roadmap sync pre-existing issues (invalid references, unlinked plans) can be handled in a separate cleanup plan.
