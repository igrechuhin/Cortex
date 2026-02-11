# Session Optimization (2026-02-09): Load Context When Agent Encounters Problem / Fix Path

**Related**: See [Session Optimization: Commit Pipeline Orchestration Refactor](.cortex/plans/session-optimization-commit-pipeline-orchestration-refactor.md) for phase-based commit orchestration and helper commands; this plan focuses on requiring context/rules load when agents enter the fix path.

**Status**: PENDING  
**Created**: 2026-02-09  
**Source**: User request + `.cortex/reviews/session-optimization-2026-02-09T08-12.md`  
**Priority**: Medium

## Goal

Ensure that when an agent encounters a problem and has to fix something, it **must** load context (memory bank and rules) so it follows all project rules and guidelines. This prevents fix-path work from proceeding without project context and reduces mistake patterns (e.g. wrong mocks, usage-context assumptions) that could be avoided by loading rules and memory bank first.

## Context

- **User requirement**: "Once problem is encountered, and agent has to fix something, it must load context to ensure it follows all project rules and guidelines."
- **Review (2026-02-09)**: Session was workflow-only (commit command); no `load_context` calls were recorded. Mistake patterns identified: (1) rules manager `initialize()` not mocked as async; (2) manage_file metadata test reusing real managers from usage-context. Root cause notes: mocks must match call patterns (AsyncMock for awaited methods); tests that mock `get_managers` but invoke handlers through `ensure_usage_context` may need to patch `set_current_managers` / `set_current_project_root` so context is not stored. Loading context (and relevant rules) before fixing would surface coding standards (e.g. AsyncMock for awaited deps, usage-context isolation in tests) and reduce such mistakes.
- **Related**: `session-optimization-implement-load-context-and-rules-fallback.md` covers load_context at **implement** step start; this plan covers the **fix path** (problem encountered → agent must load context before fixing).

## Approach

Add explicit instructions to agent-facing prompts and/or guidelines (e.g. AGENTS.md, commit prompt, create-plan prompt) so that whenever the agent is in a "fix" or "problem encountered" situation, it must call `load_context(task_description="...", token_budget=...)` and, when applicable, `rules(operation="get_relevant", task_description="...")` (or fallback to reading rules from structure path) **before** making code or test changes. This keeps fix-path behavior aligned with project rules and test standards.

## Implementation Steps

### Step 1: Identify all prompts and guidelines that can trigger fix-path work

**Tasks**:

1. List prompts and docs where an agent might "encounter a problem and fix something": e.g. commit prompt (fix errors step), implement prompt (fixing failures), create-plan prompt (if it ever suggests fixing), general agent guidelines (AGENTS.md, CLAUDE.md).
2. For each, note whether it already instructs loading context when fixing; if not, it is in scope for Step 2.

**Acceptance**: A short inventory of fix-path entry points and current context-loading instructions (if any).

### Step 2: Add "load context when fixing" requirement to commit prompt

**Target**: Commit prompt (e.g. `.cortex/synapse/prompts/commit.md` or equivalent).

**Tasks**:

1. In the step where the agent is instructed to fix errors (e.g. "Fix Errors" or "Fix quality issues"), add an explicit requirement: **before** attempting fixes, the agent must load context so it follows project rules and guidelines.
2. Specify the mechanism: call `load_context(task_description="Fixing errors and quality issues for commit", token_budget=15000)` (or use task-type budget per context-effectiveness recommendations), and if rules are enabled, call `rules(operation="get_relevant", task_description="...")`; if rules return disabled, load key coding standards from the rules path (per existing rules-fallback guidance).
3. Keep wording consistent with `session-optimization-implement-load-context-and-rules-fallback.md` (rules fallback, task-type budgets).

**Acceptance**: Commit prompt clearly requires loading context (and rules when applicable) before fixing; agents running commit will have project context when fixing.

### Step 3: Add "load context when fixing" requirement to implement prompt

**Target**: Implement-next-roadmap-step prompt.

**Tasks**:

1. In the section that covers handling failures or fixing issues during implementation (e.g. "when a step fails" or "fix test failures"), add: before applying fixes, the agent must load context (and rules if applicable) so it follows project rules and guidelines.
2. Reference or reuse the same mechanism as Step 1 of `session-optimization-implement-load-context-and-rules-fallback.md` (load_context with task description and token budget); for fix/debug task type use 15k budget per context-effectiveness.
3. Ensure no conflict with "load context at step start"—step start loads context for the planned step; "when fixing" loads context specifically when the agent switches to fix mode.

**Acceptance**: Implement prompt requires loading context when the agent is fixing failures; wording is consistent with load-context-at-step-start and rules fallback.

### Step 4: Add "load context when fixing" to agent guidelines (AGENTS.md / CLAUDE.md)

**Target**: AGENTS.md and/or CLAUDE.md (or equivalent workspace rules).

**Tasks**:

1. Add a clear guideline: when the agent encounters a problem and has to fix something (errors, test failures, quality issues), it **must** load context before making changes—e.g. call `load_context(task_description="...", token_budget=...)` and, when applicable, get relevant rules—so it follows all project rules and guidelines.
2. Optionally reference the commit and implement prompts for concrete placement; keep the guideline general enough to apply to any fix-path scenario (e.g. create-plan flow if it ever suggests fixes).

**Acceptance**: Agent guidelines explicitly require loading context on the fix path; discoverable by agents and humans.

### Step 5: Document and verify

**Tasks**:

1. Update any session optimization or prompt docs that list "when to load context" to include the fix-path requirement.
2. Run a quick sanity check: read commit and implement prompts and confirm the new instructions are present and unambiguous.

**Acceptance**: Documentation reflects the fix-path requirement; prompts contain the new instructions.

## Dependencies

- Existing `load_context` and `rules` MCP tools (no new tooling).
- Optional: `session-optimization-implement-load-context-and-rules-fallback.md` (task-type token budgets and rules fallback) for consistent wording and budgets.

## Success Criteria

- Commit prompt requires loading context (and rules when applicable) before fixing.
- Implement prompt requires loading context when the agent is fixing failures.
- Agent guidelines (AGENTS.md/CLAUDE.md) state that on problem/fix path, the agent must load context to follow project rules and guidelines.
- End-of-session analyze can record `load_context` calls on fix-path sessions (commit, implement fix steps).

## Technical Design

- **No code changes to Cortex server**: only prompt and guideline text changes.
- **Token budget**: Use 15,000 for fix/debug path per context-effectiveness recommendations (or as defined in load-context-and-rules-fallback plan).
- **Rules**: Same fallback as implement prompt—if `rules(operation="get_relevant")` returns disabled, load key standards from rules path via `get_structure_info()` + Read.

## Testing Strategy

- **Coverage target**: N/A for prompt/docs-only changes; no new production code.
- **Validation**: (1) Manual review of updated prompt and guideline text. (2) Optional: add a small integration or checklist test that verifies commit/implement prompts contain the required phrases (e.g. "load context" and "before fixing" or "when fixing"). (3) Regression: ensure existing commit and implement flows still pass (run commit pipeline and implement-next-step flow once).
- **Acceptance**: All updated prompts and guidelines reviewed; no regressions in commit or implement behavior.

## Risks & Mitigation

- **Agent ignores instruction**: Mitigation: place requirement prominently (e.g. in pre-action or first step of fix); reinforce in AGENTS.md so it is in always-applied rules.
- **Duplicate or conflicting load_context calls**: Mitigation: wording should clarify "before fixing" (one call when switching to fix mode); step-start load_context remains for planned step; fix-path load_context is additional when agent actually fixes.

## Timeline

- Step 1: 0.5 day (inventory).
- Steps 2–4: 1 day (prompt and guideline edits).
- Step 5: 0.5 day (docs and verification).

**Total**: ~2 days.

## Notes

- Review 2026-02-09 recommended folding test-fixture and mock checklist into "Test Fixture Validation and Maintenance" or "Session Optimization: Commit Pipeline Improvements"; this plan does not duplicate those but ensures the **behavioral** requirement (load context when fixing) is explicit so future sessions are more likely to load context on the fix path.
- If create-plan or other prompts ever instruct the agent to "fix" something, they should be added to the inventory in Step 1 and updated similarly in a follow-up.
