# Plan: Session Scope Lock — Single-Goal Session Pattern

**Slug**: session-scope-lock-pattern
**Component**: prompts
**Work type**: improvement
**Priority**: medium
**Status**: IN_PROGRESS
**Created**: 2026-03-26

---

## Goal

Reduce budget exhaustion and partial completions (6 partial, 2 not-achieved outcomes) by establishing a single-goal session discipline enforced via prompt structure.

## Context

Usage analytics show fully_achieved sessions almost always had a single clear goal, while multi-goal sessions (combining CI fixes + MCP debugging + Synapse work) had the worst outcomes with budget exceeded errors. Sessions average 9-minute user response times suggesting deep work context.

## Progress (2026-03-27)

- Done: `SessionBrief.session_scope` + `SESSION_SCOPE_PROMPT` on session start; tests in `tests/tools/test_session_start_tools.py`.
- Done: Added `## Session Discipline` in `CLAUDE.md` with single-goal session guidance and deferral rules for unrelated work.
- Done: Added `cortex://context` parity so successful context payloads include `session_scope`; tests in `tests/tools/test_phase4_optimization.py`.
- Done: Strengthened `SESSION_SCOPE_PROMPT` wording to explicitly defer unrelated issues to follow-up sessions; added assertions covering this wording in session-start and context-resource tests.
- Remaining: commit.md split-commit hint; analyze.md multi-goal flag.

## Implementation Steps

1. Add a "Session Scope" section to `session()` tool output or the `cortex://context` resource — **done** (session brief).
2. The scope section should prompt the user to confirm ONE primary goal for the session — **done**.
3. Add to commit.md prompt: if multiple unrelated fixes were made, suggest splitting into separate commits
4. Add to the `analyze.md` prompt: detect multi-goal sessions and flag them as scope risk
5. Document the pattern in CLAUDE.md under `## Session Discipline`

## Verification

- Session scope guidance is surfaced at session start
- commit.md references single-goal discipline

## Testing

- Verify session() output includes scope guidance
- Verify analyze.md references session scope
