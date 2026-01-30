# Phase 66: Plan Creation Workflow Compliance — Path Resolution and Roadmap Updates

## Status

- **Status**: Completed
- **Priority**: High
- **Created**: 2026-01-30
- **Completed**: 2026-01-30

## Goal

Ensure plan creation always (1) uses path resolution correctly from `get_structure_info()` and reports paths unambiguously, and (2) updates the roadmap only via `manage_file(file_name="roadmap.md", operation="write", content=<full content>)` — never via direct file edits (StrReplace, Write to file path) during plan creation.

## Context

### Issues Encountered (Input)

During a previous plan creation (Phase 65), two compliance issues were reported:

1. **Path resolution**: Summary stated "plans path is .cortex/plans (structure_info.root was .cortex; plans path from layout)." This is ambiguous: `get_structure_info()` returns `structure_info.paths.plans` as an absolute path (e.g. `/path/to/project/.cortex/plans`). The prompt says to use `structure_info.paths.plans` but does not explicitly forbid inferring a relative path from `structure_info.root` or reporting paths in a way that could be misinterpreted. Agents should use and report the absolute path from `structure_info.paths.plans` for plan file creation.

2. **Roadmap update**: The roadmap was updated with a direct file edit (StrReplace) instead of `manage_file(file_name="roadmap.md", operation="write", content=...)`. The create-plan prompt (Step 6) already requires using `manage_file` with the complete, unabridged roadmap text. Using StrReplace or any direct file write bypasses the memory-bank contract (versioning, conflict detection, etc.) and violates the prompt. Roadmap updates during plan creation MUST be done only via `manage_file(roadmap.md, write, full content)`.

### Current Prompt Rules

- `.cortex/synapse/prompts/create-plan.md` Step 1: Use `get_structure_info(project_root=None)`; plans directory path = `structure_info.paths.plans`.
- Step 6: Use `manage_file(file_name="roadmap.md", operation="write", content="[updated roadmap content]", change_description="Added new plan: [plan title]")`; content MUST be the complete, unabridged roadmap text; never truncate or shorten existing entries.

The issues indicate that agents may still (a) report or use paths in a way that conflates root and plans path, or (b) fall back to direct file edits for roadmap when the full content is large. The plan must make compliance explicit and unambiguous.

## Approach

1. **Path resolution**: Strengthen the create-plan prompt (and any plan-creator/memory-bank-updater agent guidance) so that: (a) the plans directory for creating/writing plan files is always taken from `structure_info.paths.plans` (absolute path returned by the tool); (b) agents must not hardcode `.cortex/plans` or infer paths from `structure_info.root` + layout; (c) in "Issues encountered" or summaries, report the actual path used (e.g. `structure_info.paths.plans`) so it is unambiguous.
2. **Roadmap update**: Strengthen the create-plan prompt so that: (a) roadmap updates during plan creation are PROHIBITED via direct file edit (StrReplace, Write tool to roadmap path, or any method that bypasses `manage_file`); (b) REQUIRED: use only `manage_file(file_name="roadmap.md", operation="write", content=<full roadmap text>, change_description="...")`; (c) if the full content is large, the agent must still pass the full content (read current roadmap, apply the single add/update, pass entire result); (d) add an explicit "VIOLATION" note that using StrReplace or direct Write for roadmap during plan creation is a critical violation.

## Implementation Steps

### Step 1: Clarify Path Resolution in Create-Plan Prompt

- In Step 1 (Get Project Structure and Paths), add explicit instructions:
  - Use the absolute path from `structure_info.paths.plans` for creating/updating plan files. Do not hardcode `.cortex/plans` or derive the path from `structure_info.root` plus a layout segment.
  - When reporting paths (e.g. in plan summary or "Issues encountered"), use the value from `structure_info.paths.plans` (e.g. `/path/to/project/.cortex/plans`) so it is unambiguous. Note that `structure_info.root` may be the Cortex directory (e.g. `.cortex`) or the project root depending on configuration; the canonical plans path is always `structure_info.paths.plans`.
- Optionally add a "Path resolution" subsection under ERROR HANDLING or IMPLEMENTATION GUIDELINES that states the above and that hardcoding or inferring paths is a violation.

### Step 2: Enforce Roadmap Update via manage_file Only

- In Step 6 (Update Roadmap), add explicit PROHIBITED / REQUIRED / VIOLATION language:
  - **PROHIBITED**: Updating roadmap during plan creation by any method other than `manage_file(file_name="roadmap.md", operation="write", content=..., change_description=...)`. This includes: using StrReplace (or any search_replace) on the roadmap file, using the Write tool to write directly to the roadmap file path, or any edit that bypasses the `manage_file` MCP tool.
  - **REQUIRED**: Read the current roadmap with `manage_file(file_name="roadmap.md", operation="read")`, apply only the intended change (add or update one plan entry), then call `manage_file(file_name="roadmap.md", operation="write", content=<complete resulting text>, change_description="Added new plan: [plan title]" or similar)`. The `content` parameter MUST be the full, unabridged roadmap text. If the content is large, the agent must still pass the full content in one call.
  - **VIOLATION**: Using StrReplace or direct Write for roadmap during plan creation is a critical violation of the plan creation workflow and must not be used.
- Optionally add a short "Roadmap update (plan creation)" note in the memory-bank-updater agent that roadmap updates triggered by plan creation must use `manage_file` with full content only.

### Step 3: Optional — Verification Step

- In Step 7 (Verify Completion), add or reinforce: after updating the roadmap, re-read it via `manage_file(file_name="roadmap.md", operation="read")` and confirm (1) the new or updated plan entry is present and correct, and (2) all existing roadmap entries are unchanged. If any entry was shortened or removed, the agent must restore the full content and repeat the update using `manage_file(write, ...)` with the complete content (not StrReplace).

### Step 4: Testing and Documentation

- Add or update tests that verify: (a) plan creation flow uses `get_structure_info()` and uses `structure_info.paths.plans` for plan file paths; (b) any automated or documented plan-creation flow does not use direct file writes for roadmap (e.g. integration test or prompt test that asserts roadmap updates go through manage_file). Document the compliance rules in the create-plan prompt so future agents have a single source of truth.

## Dependencies

- Cortex MCP tools: `get_structure_info`, `manage_file`.
- Existing create-plan prompt (`.cortex/synapse/prompts/create-plan.md`) and memory-bank-updater agent.

## Success Criteria

- Create-plan prompt explicitly requires using `structure_info.paths.plans` (absolute) for plan file paths and prohibits hardcoding or inferring from root + layout.
- Create-plan prompt explicitly prohibits roadmap updates via StrReplace or direct Write and requires all roadmap updates during plan creation to use `manage_file(roadmap.md, write, full content)`.
- Plan creation summaries or "Issues encountered" that mention paths use the canonical path from the tool (e.g. `structure_info.paths.plans`) so path resolution is unambiguous.
- No roadmap update during plan creation is performed via direct file edit.

## Testing Strategy

- **Coverage target**: N/A for production code; prompt/agent changes only. If any helper or validation is added in code, target 95% for new code.
- **Prompt/flow tests**: (1) Grep or integration check that create-plan prompt contains the new PROHIBITED/REQUIRED/VIOLATION language for roadmap and path resolution. (2) Optionally: test that a simulated plan-creation step (e.g. "add one roadmap entry") uses manage_file for roadmap and not direct write.
- **Documentation**: Create-plan prompt and memory-bank-updater agent (if updated) clearly state the rules.

## Risks and Mitigation

- **Large roadmap**: Passing full roadmap content in one MCP call may hit size limits. Mitigation: prompt already requires full content; if limits are hit, document as a known constraint and consider chunking or tool evolution in a future phase (out of scope for this plan).

## Timeline

- Steps 1–2: Prompt and agent updates (estimate: 1 session).
- Step 3–4: Verification and tests/docs (estimate: 0.5 session).

## Notes

- This plan addresses workflow compliance for the plan creation command (`/cortex/plan`), not general roadmap edits outside plan creation.
- Phase 63 (Harden create-plan roadmap writes) already enforces full-content-only and no truncation; Phase 66 adds explicit prohibition of direct file edits and clarifies path resolution.
