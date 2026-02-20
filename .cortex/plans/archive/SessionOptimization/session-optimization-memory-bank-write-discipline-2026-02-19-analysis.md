# Session Optimization: Memory bank write discipline (2026-02-19 analysis)

**Source**: End-of-session analysis 2026-02-19 (`session-optimization-2026-02-19T08-31.md`).

## Goal

Reinforce that all memory bank updates (including roadmap.md edits during roadmap-sync or link/archive tasks) must be performed via Cortex MCP tools only—never via Write/StrReplace/ApplyPatch on memory-bank paths.

## Context

During implementation of "Session Optimization: Roadmap sync cleanup (2026-02-09)", roadmap.md was edited using the StrReplace tool. Project rules (AGENTS.md, implement prompt, memory-bank-updater) require all updates to roadmap.md, progress.md, and activeContext.md to be performed with `manage_file()` or the dedicated tools (`remove_roadmap_entry`, `append_progress_entry`, `complete_plan`, etc.).

## Steps

1. **Implement prompt**: In the step that updates roadmap (e.g. when "Roadmap sync cleanup" or "Link or archive unlinked plans" is the task), add an explicit reminder: "All edits to roadmap.md must be performed via `manage_file(operation='write', ...)` after reading current content with `manage_file(operation='read')`; do not use Write/StrReplace/ApplyPatch on memory-bank paths."
2. **Analyze prompt (optional)**: When reporting mistake patterns that include memory-bank write discipline, reference memory-bank-workflow and the dedicated MCP tools to reinforce the correct pattern.
3. **Memory-bank-updater agent**: Ensure the agent file reiterates that roadmap edits (e.g. adding Plan links or reference entries) must use `manage_file()` or the dedicated roadmap tools.

## Acceptance

- Implement and analyze prompts (and memory-bank-updater agent if applicable) explicitly state that roadmap.md must not be edited via IDE file tools.
- No new hardcoded paths; use get_structure_info() and MCP tools for paths.
