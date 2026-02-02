# Session Optimization: Require Script-Analysis When Commit Runs a Script (Blocker)

**Status**: COMPLETE (2026-02-02)  
**Priority**: FIX-ASAP (Blockers ASAP Priority)  
**Created**: 2026-02-01  
**Source**: `.cortex/reviews/session-optimization-2026-02-01T23-07.md` (Recommendation 1)

## Goal

Ensure that whenever the commit workflow (or any session) creates or executes a script (inline snippet or file), the agent MUST use the project's script-analysis tooling (`capture_session_script`, `analyze_session_scripts`, `suggest_tool_improvements`) so scripts are captured, analyzed, and aligned with Phase 27 script-generation-prevention and implement-next-roadmap-step guidance.

## Context

During a `/commit` run, the agent ran an inline Python script (subprocess calling `npx markdownlint-cli2` on three files) to work around markdown lint results instead of using `fix_markdown_lint` or feeding the script into script tooling. The project has MCP tools for script capture and analysis (`capture_session_script`, `list_session_scripts`, `analyze_session_scripts`, `suggest_tool_improvements`, `promote_session_script`), but none were used. Scripts are therefore not captured or analyzed, and there is no promotion path or consistency with script-generation-prevention (Phase 27) or implement-next-roadmap-step guidance.

Root cause (from review): The commit prompt and related agents focus on pre-commit checks, memory bank, and plan archiving. They do not state that when the agent creates or runs a script (inline or file), it must use `capture_session_script` and/or `analyze_session_scripts` / `suggest_tool_improvements`.

## Approach

1. **Commit prompt**: Add a mandatory step or bullet: "If during this run you created or executed any script (inline snippet or file), you MUST call `capture_session_script` and/or `analyze_session_scripts` or `suggest_tool_improvements` as appropriate. Do not run scripts without using script tooling."
2. **Optional**: Add the same rule in `.cortex/synapse/rules/general/agent-workflow.mdc` for all workflows.
3. **Commit prompt "Common errors" / tooling**: Add "Script run without analysis" as a visible, checkable item (e.g. in "COMMON ERRORS TO CATCH" or tooling section): "If you ran a script (e.g. Python/shell snippet) during the pipeline, you must use `capture_session_script` and/or `analyze_session_scripts` / `suggest_tool_improvements`. Not using script tooling is a process violation."

## Implementation Steps

1. **Edit commit prompt** (`.cortex/synapse/prompts/commit.md`):
   - Add a step or bullet (after "Steps without dedicated agents" or in a new "Script use" subsection): "If during this run you created or executed any script (inline snippet or file), you MUST call `capture_session_script` and/or `analyze_session_scripts` or `suggest_tool_improvements` as appropriate. Do not run scripts without using script tooling."
2. **Optional**: Edit `.cortex/synapse/rules/general/agent-workflow.mdc` (or equivalent): add rule that when an agent creates or executes a script, it must use script tooling as above.
3. **Edit commit prompt** ("COMMON ERRORS TO CATCH" or tooling section): Add bullet: "**Script run without analysis**: If you ran a script (e.g. Python/shell snippet) during the pipeline, you must use `capture_session_script` and/or `analyze_session_scripts` / `suggest_tool_improvements`. Not using script tooling is a process violation."

## Dependencies

- Phase 27 (script generation prevention) and existing script capture tools (`capture_session_script`, `analyze_session_scripts`, `suggest_tool_improvements`, `promote_session_script`) are in place.
- Implement-next-roadmap-step guidance references script tooling; this plan aligns commit prompt with that guidance.

## Success Criteria

- Commit prompt contains an explicit, mandatory requirement to use script tooling when a script was created or executed during the run.
- Commit prompt lists "Script run without analysis" as a common error / process violation.
- Optional: Agent-workflow rule states the same for all workflows.
- Every session that generates or executes a script is directed to use script tooling, improving capture and alignment with Phase 27.

## Testing Strategy

- **Coverage target**: Minimum 95% for any new code; this plan is prompt/rule-only, so no new production code is required.
- **Unit tests**: N/A for prompt/rule-only changes.
- **Integration tests**: Optional integration test that verifies commit prompt contains the script-analysis requirement and the "Script run without analysis" common error (e.g. grep for `capture_session_script` and "Script run without analysis" in commit prompt).
- **Verification**: Review that commit prompt and optional agent-workflow rule contain the new text; no removal of existing steps.
- **Regression**: Existing commit steps and script tooling behavior unchanged.

## Risks & Mitigation

- **Risk**: Agents might still run scripts without calling tooling. **Mitigation**: Make the requirement mandatory and list "Script run without analysis" as a process violation in common errors so it is visible during commit.
- **Risk**: Duplication with implement-next-roadmap-step. **Mitigation**: Keep commit prompt wording aligned with implement-next-roadmap-step; both reinforce the same rule.

## Timeline

- Estimate: ~1 hour (commit prompt edits + optional agent-workflow rule).

## Notes

- User feedback: "Session created a script. Has it been analyzed? We have tooling for that. But I don't see that it was used."
- Existing guidance: `implement-next-roadmap-step.md` (script generation prevention, suggest_tool_improvements, capture_session_script, analyze_session_scripts, promote_session_script); Phase 27 script capture tools.
- Commit prompt already says "Do NOT run scripts directly; use tools only" in a different context (pre-commit scripts); this plan adds script-analysis use when a script *was* run.
