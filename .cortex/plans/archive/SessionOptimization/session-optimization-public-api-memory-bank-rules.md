# Session Optimization (2026-01-31 12-19): Public API Naming, Memory Bank Sync, SDK Generics

**Status**: Pending  
**Source**: `.cortex/reviews/session-optimization-2026-01-31T12-19.md`  
**Created**: 2026-01-31

## Goal

Implement the three recommendations from the session optimization review (2026-01-31 12-19) to prevent recurrence of: (1) public APIs exposing private type names in signatures, (2) memory bank drift after user-requested follow-up fixes, and (3) incorrect generic type parameters when using SDK/third-party types.

## Context

The review analyzed a session that implemented Phase 1–2 of "Ensure proper logging (FastMCP context)" and a follow-up fix. Key issues:

- **Public API / private type names**: Public functions (`log_client`, `report_progress_safe`, `manage_file`) used type hints with leading-underscore names (`_MCPContext`, `_LogLevel`). In Python, a leading underscore denotes "internal"; using such names in public signatures breaks the convention that the public API surface uses only public names.
- **Memory bank not updated after follow-up fix**: When the user requested renaming private type names to public (`MCPContext`, `LogLevel`), code and tests were updated but `progress.md` was not, so it still referred to `ctx: _MCPContext`.
- **Generic type parameters**: Initial use of `Context[object, object]` for the MCP Context type failed the type checker; the fix was to use `Context[ServerSession, object]` to match the SDK's `get_context()` return type.

The project has strong rules on types (no Any, concrete types, etc.) but no explicit rule that public functions must not reference types whose names start with an underscore, and no explicit step to update memory bank after user-requested fixes that change API or naming.

## Approach

1. **Rules (Synapse)**: Add two rule subsections—(a) public API must not use private type names, (b) use SDK/third-party type parameters for generics—in the appropriate Synapse rule files (e.g. `python-coding-standards.mdc`, `python-mcp-development.mdc`).
2. **Prompts / agents**: Add explicit guidance in the implement prompt and in the memory-bank-updater agent to update memory bank after any user-requested fix that changes public API, type names, or documented behavior.
3. **One-time alignment**: As part of this work, ensure `progress.md` (and any other memory bank text) no longer references outdated type names (e.g. `_MCPContext` → `MCPContext`) if drift remains.

## Implementation Steps

### Step 1: Rule — Public API Must Not Use Private Type Names (High)

- **Target**: Synapse rules, e.g. `.cortex/synapse/rules/python/python-coding-standards.mdc` (under Naming or a new "API design" subsection), and optionally `.cortex/synapse/rules/python/python-mcp-development.mdc` for MCP handlers.
- **Change**: Add a rule: "Public functions, methods, and their parameter/return type hints must not reference types or type aliases whose names start with an underscore. Any type that appears in a public signature must have a public name. Export such types via `__all__` if they are part of the module's API."
- **Optional**: Add a short checklist item in the implement prompt (e.g. in verification steps) to confirm new public functions do not use `_`-prefixed types in signatures.

### Step 2: Prompt / Agent — Update Memory Bank After User-Requested Fixes (Medium)

- **Target**: `.cortex/synapse/prompts/implement-next-roadmap-step.md` (e.g. Memory Bank Updates or Step 5 / post-implementation section) and `.cortex/synapse/agents/memory-bank-updater.md`.
- **Change**: Add an explicit step or note: "After applying any user-requested fix that changes public API, type names, or documented behavior, update progress.md (and activeContext.md if the change affects current focus) so memory bank remains consistent with the codebase."
- **Placement**: One short paragraph in the implement prompt's memory-bank section; optionally a bullet in the memory-bank-updater "Key practices" or "When to update" section.

### Step 3: Rule — Use SDK/Third-Party Type Parameters for Generics (Low)

- **Target**: Synapse rules, e.g. `.cortex/synapse/rules/python/python-coding-standards.mdc` (Type Hints or External integrations) or `.cortex/synapse/rules/python/python-mcp-development.mdc`.
- **Change**: Add guidance: "When using generic types from third-party or SDK code (e.g. MCP `Context`), use the same type parameters as in the library's public API or documented examples (e.g. `Context[ServerSession, object]`). Do not substitute `object` or other types without verifying they satisfy the generic's type bounds."

### Step 4: One-Time Memory Bank Alignment (If Needed)

- **Action**: Read `progress.md` (and optionally `activeContext.md`) via `manage_file()`; if any text still refers to outdated type names (e.g. `_MCPContext`), update the content to use the current public names (e.g. `MCPContext`) and write back with `manage_file(operation="write", ...)` with an appropriate `change_description`.

## Dependencies

- **ensure-proper-logging-fastmcp**: Related (context_logging.py, manage_file refactor) but not blocking; this plan focuses on rules and prompts to prevent recurrence, not on the logging implementation itself.

## Success Criteria

- Rule text added and clearly visible in the designated Synapse rule file(s); implementer/agents can discover it.
- Implement prompt and memory-bank-updater agent contain explicit guidance to update memory bank after user-requested fixes that change API/naming/behavior.
- No remaining references in memory bank files to private type names (e.g. `_MCPContext`) where the codebase now uses public names (e.g. `MCPContext`).
- Future introductions of type aliases for public signatures use public names and `__all__` where appropriate; follow-up renames trigger memory bank updates per the new guidance.

## Testing Strategy

- **Coverage target**: This plan is primarily documentation and rule/prompt text; no new production code. Verification is by review and prompt/rule conformance.
- **Verification**: (1) Grep/read rule files to confirm new subsections exist and are correctly placed. (2) Grep/read implement prompt and memory-bank-updater to confirm the new step/bullet exists. (3) Read progress.md (and activeContext if relevant) via `manage_file(read)` and assert no outdated type names. (4) Optional: add a short integration or prompt test that checks for the presence of the new rule/prompt phrases (e.g. "public signature", "user-requested fix", "memory bank") in the Synapse assets.
- **Regression**: Ensure existing tests and pre-commit checks still pass; no change to existing tool behavior.

## Risks & Mitigation

- **Rule overlap**: Multiple rule files might both mention naming or types. Mitigation: add in one primary file (e.g. python-coding-standards) and a short cross-reference in python-mcp-development if needed.
- **Prompt length**: Adding paragraphs could lengthen the implement prompt. Mitigation: keep the new text to one short paragraph and one bullet where possible.

## Timeline

- Single session: Steps 1–4 can be done in one pass (rules, prompt, agent, one-time memory bank alignment).

## Notes

- The review file is `.cortex/reviews/session-optimization-2026-01-31T12-19.md`; a different review (session-optimization-2026-01-31T15-00) was already implemented and is marked COMPLETE in the roadmap (rules load, commit prompt, etc.). This plan addresses only the 12-19 recommendations.
- Synapse is a submodule; rule and prompt edits are in `.cortex/synapse/` (or the resolved Synapse directory from project structure).
