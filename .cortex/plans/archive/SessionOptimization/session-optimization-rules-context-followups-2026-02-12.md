# Session Optimization: Rules and Context Loading Follow-Ups (2026-02-12)

**Status**: COMPLETE  
**Created**: 2026-02-12  
**Priority**: High (quality & guidance)  
**Source**: End-of-session analysis `session-optimization-2026-02-12T12-38.md`

## Goal

Tighten the integration between optimization config and rules manager, clarify ownership of Pydantic standards between Synapse and project-local docs, and reduce zero-budget/zero-files `load_context` calls for non-trivial tasks by improving guardrails and documentation.

## Context

Recent work improved Pydantic v2 usage patterns and context-effectiveness analytics, but surfaced several issues:

- `rules(operation="get_relevant", ...)` still reports `.cursorrules` as its rules_folder and returns 0 rules, even though optimization config points to `.cortex/rules`.
- Pydantic standards exist in Synapse (`python-pydantic-standards.mdc`), but a short-lived duplicate rule was added and removed, indicating unclear ownership.
- Attempts to extend techContext/systemPatterns triggered schema validation errors; the schema is strict but extension guidance is not easily discoverable.
- Context analysis shows some non-trivial tasks still calling `load_context` with `token_budget=0` and `files_selected=0`.

## Implementation Steps

### Step 1: Fix Rules Manager and Optimization Rules Folder Integration

- Locate the rules manager implementation and configuration mapping (e.g. where rules_folder is read/applied).
- Ensure the manager uses `optimization.rules.rules_folder` as the canonical source of truth for the rules directory.
- When the configured folder does not exist, fail loudly with a clear MCP error (ToolErrorResponse) instead of silently returning 0 rules.
- Add unit tests to cover:
  - Happy path: `.cortex/rules` exists and at least one rule is indexed.
  - Misconfigured path: folder missing, tool returns a clear error.

### Step 2: Clarify Pydantic Standards Ownership (Synapse vs Project-Local)

- Update `python-pydantic-standards.mdc` to explicitly state that Pydantic 2 standards are owned by Synapse for this repo.
- Add a short note in techContext/systemPatterns (or memory bank workflow) that points to the Synapse Pydantic rule instead of duplicating guidance.
- Ensure prompts (implement/commit/analyze) mention Synapse rules as the primary source for Pydantic v2 guidance.

### Step 3: Improve Memory-Bank Schema Extension Guidance

- Update the memory-bank workflow rule to include a "How to extend schema-constrained files" section, with concrete examples for techContext/systemPatterns:
  - Required headings per file.
  - Allowed heading levels and common pitfalls (heading-level skips).
  - Recommended pattern for adding new subsections.
- Optionally, add brief inline comments or a small note in techContext/systemPatterns explaining where new subsections should live and how to avoid schema violations.

### Step 4: Strengthen Guardrails for Zero-Budget/Zero-Files load_context Calls

- Expand the learned-pattern warning in context analysis to emphasize that refactor/fix/implement tasks must not run with `token_budget=0` and `files_selected=0`.
- Consider a lightweight helper in prompts or docs instructing agents to re-run `load_context` with a non-zero budget whenever they detect zero-budget/zero-files conditions for non-trivial tasks.
- Add or update tests to cover the new warnings and ensure they appear whenever such calls are present in session logs.

### Step 5: Maintain Analytics Helpers Within Function-Length Limits

- For context-analysis helpers (e.g. `_generate_learned_patterns`), extract new concerns into separate helper functions as soon as they are added, to keep each function under the 30-line limit.
- Add or update tests to cover any new helpers introduced by these extractions.

## Success Criteria

- `rules(operation="get_relevant", ...)` indexes from the configured `.cortex/rules` folder and fails loudly when misconfigured.
- Pydantic 2 standards are clearly owned by Synapse, with techContext/systemPatterns pointing to the canonical rule instead of duplicating content.
- Memory bank extension rules for techContext/systemPatterns are discoverable and prevent common schema errors.
- Context-analysis reports highlight zero-budget/zero-files patterns clearly, and prompts/docs give agents a simple fix-path.
- Analytics helpers remain within function-length limits with tests covering new helpers.
