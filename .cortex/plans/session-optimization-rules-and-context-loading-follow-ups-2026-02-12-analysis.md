# Session Optimization: Rules and Context Loading Follow-Ups (2026-02-12 Analysis)

Status: PENDING

## Overview

This plan captures follow-up work from the 2026-02-12 end-of-session analysis focused on context effectiveness, watcher test reliability, rules indexing, and guardrails around zero-budget/zero-files `load_context` calls.

## Goals

- Codify testing guidance so file watcher lifecycle tests use mocks instead of real OS observers.
- Align task-type context budgets and documentation with analyzer-backed recommendations.
- Ensure `rules()` indexing is exercised so commit/analyze flows can load relevant rules.
- Strengthen guardrails and observability around zero-budget/zero-files `load_context` calls.

## Tasks

1. **Watcher tests: mock observers instead of real threads**
   - Update Python testing rules (Synapse) with a short subsection describing how to test file watchers and lifecycle behavior using mocks.
   - Add or adjust tests around `MemoryBankWatcher` to ensure all lifecycle tests use patched `Observer` instances and verify interactions instead of `pytest-timeout`-sensitive real observers.

2. **Context budgets: document and tune per task type**
   - Add a “Context Budget Defaults” table to `CLAUDE.md` and `AGENTS.md` derived from analyzer insights (10k for implement/add, fix/debug, testing; 7k–8k candidates for narrow review/documentation tasks; 15k for optimization).
   - Update the `implement-next-roadmap-step` prompt’s Pre-Action Checklist to reference these task-type defaults explicitly instead of generic ranges.

3. **Rules indexing: make `rules()` effective for commit/analyze**
   - Ensure there is a small initialization or setup step that runs `rules(operation="index")` when rules are enabled and the rules folder exists.
   - Add an integration test that asserts `rules(operation="get_relevant", task_description="Commit pipeline, test coverage")` returns at least one rule when rules are present.

4. **Zero-budget / zero-files guardrails**
   - Extend usage analytics warnings so zero-budget or zero-files `load_context` calls for task types `refactor`, `fix/debug`, `testing`, or `implement/add` are clearly flagged as configuration issues.
   - Add short reminders in the commit and analyze prompts clarifying that zero-budget/zero-files calls are only acceptable for trivial/no-op tasks.

## Success Criteria

- File watcher lifecycle tests are stable under pytest-timeout and rely on mocks, not real observers.
- Task-type context budget guidance is documented in CLAUDE/AGENTS and referenced by prompts, and analyzer stats remain healthy.
- `rules()` returns relevant rules for commit/analyze tasks because indexing is run as part of normal setup.
- Zero-budget and zero-files `load_context` patterns are rare, clearly visible in analytics, and discouraged for non-trivial work.
