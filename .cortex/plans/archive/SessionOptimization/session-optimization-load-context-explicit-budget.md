# Plan: load_context Explicit Budget for Implement/Refactor

## Status: PENDING

## Source

End-of-session analysis 2026-02-22 (session-optimization-2026-02-22T17-22.md).

## Problem

Context-effectiveness analysis shows load_context calls with token_budget=0 or files_selected=0 for non-trivial tasks (refactor, implement). Zero-budget/zero-files for these tasks is a configuration error and violates the documented workflow (agents run without memory-bank guidance).

## Recommendation

1. **Implement prompt**: At the "Load relevant context" step, require an explicit non-zero `token_budget` when calling load_context for roadmap steps (e.g. 10,000 for implement/update, 15,000 for fix/debug). Do not pass 0 or omit for non-trivial tasks.
2. **Documentation**: In implement.md and CLAUDE.md/AGENTS.md, state that zero-budget or zero-files load_context for implement/refactor/fix/debug is invalid and that the tool may return a validation error when token_budget=0 is passed for non-trivial tasks.
3. **Context-effectiveness**: Keep surfacing the zero-budget/zero-files warning in learned_patterns so agents and prompt updates correct usage.

## Acceptance criteria

- Implement prompt (and any refactor/fix flows) explicitly pass token_budget (e.g. 10000) at step start when calling load_context.
- No load_context calls with token_budget=0 for implement/refactor/fix/debug in normal flows.
- Documentation updated to reflect the requirement.
