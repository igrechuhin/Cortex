# Session Optimization (2026-02-02): Commit Rules Load and Step 12.6 Fallback

**Status**: COMPLETE (2026-02-02)  
**Source**: `.cortex/reviews/session-optimization-2026-02-02T10-04.md`  
**Priority**: Blocker (ASAP)

## Goal

Implement all three optimization recommendations from the session optimization analysis (2026-02-02) as blockers: (1) require explicit rule file read when the rules tool is disabled, (2) add an example fallback command for Step 12.6 markdown lint, and (3) document tool unavailability after connection closed so the commit pipeline and docs stay consistent and unambiguous.

## Context

The analysis reviewed a workflow-only `/cortex/commit` run. When `rules()` returned `disabled`, the run did not explicitly read rule files from the rules or Synapse rules directory, and the checklist item "Rules loaded" was satisfied only by CLAUDE/AGENTS context. When `fix_markdown_lint` MCP returned "Connection closed" and a retry failed with "tool not found", the agent correctly used the documented fallback but had to infer the exact shell command. The report recommends making rules loading explicit when the tool is disabled, adding an example fallback command for Step 12.6, and documenting that "tool not found" after disconnect should trigger fallback.

## Approach

1. Update the commit prompt (Pre-Step "Load Rules" and Pre-Action Checklist) so that when `rules()` returns `disabled`, agents explicitly read key rule files and record "Rules loaded: Yes (via file read)".
2. Add the example markdown lint fallback command to the commit prompt (Step 12.6 and "Connection Closed During Long Tool" fallback).
3. Add a short note in docs or commit prompt that after a connection closed error, a retry may fail with "tool not found" and the pipeline should proceed with the documented fallback.

All changes are prompt/docs only; no production code changes. Verification via existing commit-prompt alignment tests and manual review.

## Implementation Steps

### Step 1: Require Explicit Rule File Read When Rules Tool Is Disabled

- **Target**: `.cortex/synapse/prompts/commit.md` — Pre-Step "Load Rules (MANDATORY — BEFORE Step 0)" and Pre-Action Checklist.
- **Change**: Add an explicit step: "When `rules()` returns status `disabled`, resolve the rules or Synapse rules path via `get_structure_info()` (e.g. `structure_info.paths.rules` or Synapse rules directory), then use the Read tool to load at least the rule files relevant to the commit task (e.g. python-coding-standards.mdc, python-mcp-development.mdc, no-test-skipping.mdc from Synapse rules, or equivalent). Record 'Rules loaded: Yes (via file read)' so the checklist is satisfied."
- **Optional**: Add one sentence to the memory-bank-updater or agent-workflow rule about satisfying "Rules loaded" via file read when the tool is disabled.
- **Verification**: Re-read the commit prompt; confirm the new step and checklist wording are present. Optionally add an integration test that asserts the commit prompt contains the "When rules() returns status disabled" (or equivalent) instruction.

### Step 2: Add Example Fallback Command for Step 12.6 Markdown Lint

- **Target**: `.cortex/synapse/prompts/commit.md` — Step 12.6 and "Connection Closed During Long Tool (Retry Then Fallback)" / fallbacks for `fix_markdown_lint`.
- **Change**: After the sentence "Run markdown lint via shell with the same scope", add: "Example (match CI scope): `uv run rumdl check --fix .` with appropriate ignore patterns. Record 'MCP connection closed; fallback used' in the commit output."
- **Verification**: Re-read the commit prompt; confirm the example command appears in Step 12.6 and/or the Connection Closed fallback section.

### Step 3: Document Tool Unavailability After Connection Closed

- **Target**: `docs/mcp-tool-timeouts.md` and/or `.cortex/synapse/prompts/commit.md` — Failure Handling.
- **Change**: Add a short note: "After a connection closed error, a retry may fail with 'tool not found' or similar; in that case proceed with the documented fallback for that step (e.g. markdown lint via shell) and do not block the pipeline."
- **Verification**: Confirm the note appears in the chosen location(s); run markdown lint on modified files.

## Dependencies

- None. Synapse prompt and docs only.

## Success Criteria

- When `rules()` is disabled, the commit prompt explicitly requires reading rule files and recording "Rules loaded: Yes (via file read)".
- Step 12.6 and the Connection Closed fallback include the example markdown lint command so agents do not need to infer it.
- Docs and/or commit prompt state that "tool not found" after disconnect should trigger the documented fallback and not block the pipeline.
- All existing commit and markdown lint checks still pass.

## Testing Strategy

- **Coverage target**: Prompt/docs changes only; no new production code. Minimum 95% coverage for any new test code.
- **Integration tests**: Add or extend tests in `tests/integration/test_commit_workflow_prompt_alignment.py` (or equivalent) to assert:
  - The commit prompt contains instructions for the "rules disabled" path (e.g. "When rules() returns status disabled" or "Rules loaded: Yes (via file read)").
  - The commit prompt contains the example markdown lint fallback command (or a clear reference to it) in Step 12.6 / Connection Closed fallback.
- **Regression**: Run full test suite and commit pipeline once manually to ensure no regressions.
- **Docs**: Run markdown lint on `docs/mcp-tool-timeouts.md` and any modified prompt files; fix any new lint issues.

## Risks and Mitigation

- **Prompt length**: Adding text may lengthen the commit prompt; keep additions concise. Mitigation: Use bullet points and optional "Example" lines.
- **Synapse submodule**: If the commit prompt lives in Synapse, changes will be in the submodule; commit and push submodule then update parent reference per Step 11.

## Timeline

- Step 1: ~30 min (edit commit prompt, optional rule edit, verification).
- Step 2: ~15 min (edit commit prompt, verification).
- Step 3: ~15 min (edit docs and/or commit prompt, markdown lint).
- Testing and pipeline run: ~20 min.  
**Total**: ~1–1.5 hours.

## Notes

- Source review: `.cortex/reviews/session-optimization-2026-02-02T10-04.md`.
- All three recommendations are treated as blockers per user request ("all as blockers").
- Paths: Resolve via `get_structure_info()`; do not hardcode `.cortex/` or Synapse paths in the plan body when referencing them in implementation (agents should use MCP/structure for resolution).
