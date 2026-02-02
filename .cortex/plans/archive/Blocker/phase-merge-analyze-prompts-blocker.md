# Merge analyze* Prompts into Single End-of-Session Analyze (Blocker)

**Status**: COMPLETE (2026-02-02)  
**Priority**: Blocker (ASAP)  
**Goal**: Merge all `analyze*` Synapse prompts into a single `analyze` prompt used at end of sessions that runs all analyses ("check all").

## Context

- **Current state**: Several separate analyze prompts exist:
  - `analyze-context-effectiveness.md` – analyzes `load_context` effectiveness, structured feedback, usage statistics.
  - `analyze-session-optimization.md` – analyzes current session for mistakes, anti-patterns, Synapse optimization recommendations, saves review to `.cortex/reviews/`.
- **User need**: One unified `analyze` prompt to run at **end of sessions** that **checks all** (context effectiveness, session optimization, and any other analyses).
- **Why blocker**: End-of-session workflow is fragmented; a single entry point is required for consistent "check all" behavior.

## Approach

1. **Inventory** all analyze-related prompts and MCP tools.
2. **Design** a single `analyze` prompt that runs in a fixed order: pre-checklist → context effectiveness → session optimization → (optional: health/session-scripts if in scope) → unified report.
3. **Implement** one prompt file and registration; deprecate or remove the separate analyze* prompt files and update manifest/docs.
4. **Verify** that running the single `analyze` prompt at end of session executes all checks.

## Implementation Steps

1. **Inventory analyze* assets**
   - List Synapse prompts: `analyze-context-effectiveness.md`, `analyze-session-optimization.md`.
   - List MCP tools used by them: `analyze_context_effectiveness`, `get_context_usage_statistics`; session optimization uses memory bank, rules, and optionally `analyze_context_effectiveness(analyze_all_sessions=False)`.
   - Decide whether `analyze_health_check` and/or `analyze_session_scripts` are part of "check all" for end-of-session; if yes, add corresponding steps to the unified prompt; if no, document scope and leave for future.
   - Document in the plan or a short design note which tools the unified prompt will call and in what order.

2. **Design unified analyze prompt structure**
   - **Purpose**: End-of-session analysis; must "check all" (at minimum: context effectiveness + session optimization).
   - **Pre-Analysis Checklist**: Merge pre-checklists from both prompts (memory bank read, rules read if needed, session scope).
   - **Execution order**: (1) Context effectiveness – call `analyze_context_effectiveness(...)` and optionally `get_context_usage_statistics()`; handle `no_data` and manual fallback per existing analyze-context-effectiveness. (2) Session optimization – mistake patterns, root causes, Synapse recommendations, save report to reviews dir with canonical filename and path from `get_structure_info()`.
   - **Output**: Single report with clear sections (e.g. Context Effectiveness Analysis, Session Optimization Analysis); optional combined summary at top.
   - **Path resolution**: Use Cortex MCP tools only (`get_structure_info()`, `manage_file()`, `rules()`); no hardcoded `.cortex/` paths.
   - **Agent delegation**: If existing agents (context-effectiveness-analyzer, session-optimization-analyzer) are used, specify that the unified prompt orchestrates both; otherwise inline the steps into one prompt.

3. **Create unified prompt file**
   - Add `.cortex/synapse/prompts/analyze.md` (or project’s Synapse prompts path from structure) with:
     - Title and AI execution command for end-of-session "analyze" that checks all.
     - Pre-analysis checklist (merged).
     - Step 1: Context effectiveness (tool call + optional manual fallback).
     - Step 2: Session optimization (mistake patterns, root causes, recommendations, save report).
     - Step 3 (optional): Health / session-scripts if in scope.
     - Unified output format and success criteria.
     - Requirements: path resolution via MCP only; real timestamps for review filenames; MD024 duplicate-heading guidance when appending addenda.
   - Keep language-agnostic; no hardcoded commands or structure paths.

4. **Register unified prompt and update manifest**
   - In `prompts-manifest.json`: add one entry for `analyze.md` (e.g. name "Analyze", description for end-of-session check-all).
   - Remove or deprecate entries for `analyze-context-effectiveness.md` and `analyze-session-optimization.md` (remove from manifest so only `analyze` is exposed).
   - In `synapse_prompts.py`: add icon for `analyze` in `SYNAPSE_PROMPT_ICONS` if needed; ensure prompt name maps to `analyze` (e.g. "Analyze" → `analyze`).
   - Verify registration: `get_synapse_prompts` (or equivalent) returns one "analyze" prompt.

5. **Handle old prompt files**
   - Either remove `analyze-context-effectiveness.md` and `analyze-session-optimization.md` from the Synapse prompts directory, or move them to an `archive/` or `deprecated/` folder and add a one-line note at the top pointing to `analyze.md`. Prefer removal if no other references depend on them; otherwise deprecate with clear pointer.

6. **Update references**
   - Search codebase and docs for references to "analyze-context-effectiveness", "analyze-session-optimization", "Analyze Context Effectiveness", "Analyze Session Optimization".
   - Update README, docs/prompts, CLAUDE.md, and any commit/review prompts that mention running "analyze" or "session optimization" so they refer to the single `analyze` prompt.
   - Ensure review/implement prompts that suggest "run analyze at end of session" point to the unified prompt.

7. **Testing**
   - **Unit/registration**: Assert manifest contains exactly one analyze entry and that prompt content for `analyze` loads and contains required sections (context effectiveness, session optimization).
   - **Integration**: Add or extend test (e.g. in `tests/integration/`) that runs or simulates the analyze flow: prompt content includes pre-checklist, context-effectiveness step (tool + no_data handling), session-optimization step (report save with path from `get_structure_info`), and output format.
   - **Manual**: Run the unified `analyze` prompt at end of a session and confirm both context effectiveness and session optimization run and report is produced.

## Dependencies

- Cortex MCP tools: `get_structure_info`, `manage_file`, `rules`, `analyze_context_effectiveness`, `get_context_usage_statistics`.
- Synapse prompts directory and manifest; `synapse_prompts.py` registration.
- No dependency on other phases; can be done independently.

## Success Criteria

- One Synapse prompt named **Analyze** (file `analyze.md`) is the single entry point for end-of-session analysis.
- Running that prompt executes **all** intended checks: at least (1) context effectiveness, (2) session optimization; optional (3) health/session-scripts if scoped.
- Pre-analysis checklist, path resolution via MCP only, and unified output format are present and followed.
- Old analyze* prompts are removed from manifest (and optionally from disk or archived); no duplicate "analyze" prompts registered.
- Documentation and references updated; integration test(s) cover the unified analyze flow.

## Technical Design

- **Prompt file**: Single markdown file in Synapse prompts directory; language-agnostic; uses semantic names and Cortex MCP for paths.
- **Registration**: One entry in `prompts-manifest.json`; one icon entry in `SYNAPSE_PROMPT_ICONS` for `analyze`; prompt name derived from manifest "name" (e.g. "Analyze" → `analyze`).
- **Data flow**: Same as today – context effectiveness uses existing tool and optional manual fallback; session optimization uses memory bank, rules, and optional `analyze_context_effectiveness(analyze_all_sessions=False)`, then writes report to `structure_info.paths.reviews` with canonical filename.
- **Backward compatibility**: Callers that previously invoked "Analyze Context Effectiveness" or "Analyze Session Optimization" should use the single "Analyze" prompt; document this in release notes or docs.

## Testing Strategy

- **Coverage target**: Minimum 95% for any new code (e.g. registration path); prompt content itself is data, tested via integration tests.
- **Unit tests**: Manifest parsing and prompt registration – ensure only one analyze prompt is registered and content loads; optional unit test for icon/key presence.
- **Integration tests**: (1) Prompt file exists and contains required sections (pre-checklist, context effectiveness, session optimization, output format). (2) Required MCP tools and path resolution rules are mentioned (get_structure_info, manage_file, analyze_context_effectiveness). (3) No references to deprecated prompt filenames in manifest. Use AAA; Pydantic v2 for any structured assertion on manifest/prompt metadata if applicable.
- **Edge cases**: Manifest missing analyze entry; prompt file missing; empty sections – fail fast with clear errors.
- **Regression**: Existing integration tests that referenced analyze-context-effectiveness (e.g. `test_analyze_context_effectiveness_prompt`) should be updated to assert on the unified `analyze` prompt content/sections.

## Risks & Mitigation

- **Scope creep**: "Check all" might be interpreted as adding health check and session scripts. Mitigation: In Step 1, explicitly decide and document scope; implement minimum (context effectiveness + session optimization) first; add optional step 3 only if agreed.
- **Long prompt**: Merged content could be large. Mitigation: Keep sections concise; use DRY phrasing; consider transclusion or shared checklist file later if needed.
- **Broken references**: External docs or agents might reference old prompt names. Mitigation: Grep for old names in Step 6; update or add deprecation notes.

## Timeline

- Implementation: 1–2 sessions (inventory + design, implement prompt + manifest + registration, update refs + tests).
- Blocker resolution: Complete before treating "end-of-session analyze" as the single workflow.

## Notes

- User explicitly requested a **blocker** plan; this is placed in Blockers (ASAP Priority) in the roadmap.
- "Check all" is interpreted as: at least context effectiveness and session optimization; optional extensions (health, session scripts) to be confirmed in Step 1.
