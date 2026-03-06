# Phase 90: Agent Session Verbosity and "ok, proceed" Pattern

**Status**: COMPLETED
**Priority**: Medium
**Complexity**: Medium
**Category**: Fix / UX

## Goal

Reduce unnecessary agent pauses that require the user to say "ok, proceed" to continue. Agents should execute the full pipeline autonomously unless genuine clarification is needed.

## Context

- Across the analyzed chat sessions, the user had to type "ok, proceed" **at least 12 times** to push agents past informational pauses.
- Common pattern: agent loads context → prints a summary → stops → user says "ok, proceed" → agent continues.
- This is not a clarification question — the agent has all the information it needs but pauses out of excessive caution.
- The CLAUDE.md and AGENTS.md instructions already say to continue execution, but agents don't always follow through.

## Approach

1. Update agent prompts to explicitly forbid informational pauses.
2. Add "auto-continue" directive to implement and commit prompts.
3. Define clear "valid stopping points" vs "informational checkpoints."

## Implementation Steps

### Step 1: Audit current pause points in prompts

- Read implement, commit, fix_tests, and fix_quality prompts.
- Identify where agents are instructed to "report" or "summarize" mid-flow.
- Determine if any of these are intended as user approval gates.

### Step 2: Add auto-continue directives

- In implement prompt: "After loading context and rules, continue directly to implementation. Do not pause for user confirmation."
- In commit prompt: "After Phase A passes, continue directly to Phase B and Step 12. Only stop if a check fails."
- In fix_tests prompt: "After identifying failures, proceed directly to fixing them."

### Step 3: Define valid stopping conditions

- Add to AGENTS.md a clear list:
  - **Valid stops**: Clarification needed, unrecoverable error, task complete, multiple viable approaches requiring user choice.
  - **Invalid stops**: Informational summaries, phase transitions, context loading complete.

### Step 4: Update "Execution Continuity" section

- Strengthen existing CLAUDE.md execution continuity rules.
- Add specific anti-patterns: "Do not stop after loading context. Do not stop after Phase A passes."

## Verification Checklist

| What to search for | Scope | Expected result |
|---|---|---|
| "proceed" as valid stop | Synapse prompts | Zero instances of informational pauses |
| Auto-continue directive | Implement/commit prompts | Present |

## Dependencies

- None.

## Success Criteria

- A full `/cortex/implement` cycle completes without requiring user "ok, proceed."
- A full `/cortex/commit` cycle completes without requiring user "ok, proceed."
- Agents only stop for genuine clarification or unrecoverable errors.

## Testing Strategy

- **Coverage Target**: N/A (prompt/documentation changes).
- **Manual verification**: Run `/cortex/implement` and `/cortex/commit` and verify no unnecessary pauses.

## Risks & Mitigation

- **Risk**: Removing pauses means agents make wrong decisions without user input. **Mitigation**: Keep genuine decision points (multiple approaches, ambiguous requirements) as valid stops.

## Timeline

- Estimated: 2–3 hours.
