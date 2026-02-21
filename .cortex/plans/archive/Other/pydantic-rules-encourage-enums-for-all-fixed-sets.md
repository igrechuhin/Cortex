# Encourage enums for all fixed-set fields in Python Pydantic standards

**Status:** COMPLETE  
**Created:** 2026-02-20  
**Completed:** 2026-02-21

## Goal

Update `.cortex/synapse/rules/python/python-pydantic-standards.mdc` to encourage using enums (or existing project enums) for **all** fixed-set fields (e.g. status, priority, state, and any closed list of values), not only status. Align with the existing "Fixed Sets of Values: Prefer Enums" guidance in `python-coding-standards.mdc` and keep a single source of truth (DRY).

## Context

- The Pydantic standards currently have a section "Status Fields: Use Existing Enums or Literal" that prefers project enums for status and allows Literal for "one-off" fields like priority and state.
- User request: "encourage enums for all lists" — i.e. for any fixed set (priority, state, or other list-like sets), the rule should encourage enums (or existing project enums) rather than implying Literal is the default for non-status fields.
- `python-coding-standards.mdc` already states: prefer `class X(str, Enum)` for fixed sets; reserve Literal for one-off or external API constraints. The Pydantic rule should be consistent and explicitly extend that to all fixed-set fields in Pydantic models.

## Scope

**In scope:**

- `.cortex/synapse/rules/python/python-pydantic-standards.mdc` only (rules documentation).
- Generalize the "Status Fields" section to cover all fixed-set fields (status, priority, state, and any other closed list).
- State clearly: for any field that has a fixed set of allowed values, prefer an existing project enum; if none exists, define `class X(str, Enum)` (or use Literal only for one-off/single-field constraints).
- Keep examples consistent (e.g. show priority/state as enum when reused, or Literal when one-off).
- Add or update violations list to forbid `str` for any fixed-set field (not only status).

**Out of scope:**

- No codebase changes (no new enums in source code).
- No changes to `python-coding-standards.mdc` except optional cross-references if needed.

## Approach

1. Rename or reframe the section from "Status Fields: Use Existing Enums or Literal" to a broader title (e.g. "Fixed-set fields: Use enums or Literal (STRICT MANDATORY)").
2. Add explicit guidance: for **all** fields that represent a fixed list of values (status, priority, state, type, kind, etc.):
   - Prefer an existing project enum (e.g. `OperationStatus`, `PreCommitCheck`).
   - If no project enum exists, prefer defining `class X(str, Enum)` for that set (especially if reused or branched on).
   - Use `Literal` only for one-off or single-field constraints.
3. Update the example block to show priority/state as enums where appropriate (e.g. `Priority(str, Enum)` / `State(str, Enum)` for reused sets) or keep as Literal with a comment that they are acceptable when one-off.
4. In the Violations section, generalize "Using `str` for status/enum fields" to "Using `str` for any fixed-set field (status, priority, state, etc.)".
5. Cross-reference `python-coding-standards.mdc` (Fixed Sets of Values: Prefer Enums) so agents loading Pydantic rules also get the enum definition pattern from one place.

## Implementation Steps

1. **Update section title and intro**  
   - Change "Status Fields: Use Existing Enums or Literal" to "Fixed-set fields (status, priority, state, etc.): Use enums or Literal".  
   - First paragraph: state that this applies to **all** fixed-set fields, not only status.

2. **Add explicit "all lists" guidance**  
   - Add a bullet: "For any field that has a closed set of allowed values (status, priority, state, type, kind, etc.): prefer existing project enum; else prefer `class X(str, Enum)`; use Literal only for one-off/single-field constraints."  
   - Reference `python-coding-standards.mdc` for the enum definition pattern (DRY).

3. **Update example block**  
   - In the Pydantic example, either:  
     (a) Show `Priority(str, Enum)` and `State(str, Enum)` with a note that when such enums exist or are reused, use them; or  
     (b) Keep `Literal` for priority/state but add a comment that enums are encouraged when the set is reused elsewhere.  
   - Ensure the "PROHIBITED" example still shows `status: str` and optionally `priority: str` as blocked.

4. **Update Violations list**  
   - Replace "Using `str` for status/enum fields" with "Using `str` for any fixed-set field (status, priority, state, type, etc.)".

5. **Consistency pass**  
   - Search the file for "status" / "Literal" / "enum" and ensure no wording implies only status must use enum; all fixed-set fields should be covered.

## Dependencies

- None. Uses existing Synapse rules layout.

## Success Criteria

- The Pydantic standards rule clearly encourages enums (or project enums) for all fixed-set fields, not only status.
- Priority and state (and similar "lists") are explicitly in scope.
- Violations list forbids `str` for any fixed-set field.
- One source of truth: enum definition pattern lives in python-coding-standards; Pydantic rule references it and focuses on model fields.
- No code changes; only `.cortex/synapse/rules/python/python-pydantic-standards.mdc` is modified.

## Testing Strategy

- **Rule file**: Manual review and lint (markdown/format) if applicable.
- **Rule loading**: If the project has tests that load or validate Synapse rules (e.g. rule discovery, get_synapse_rules), run them to ensure no regression.
- **Coverage**: N/A (documentation-only change).

## Risks & Mitigation

- **Wording too strict**: If we require enum for every Literal, existing one-off Literals might be flagged. Mitigation: keep "Literal acceptable for one-off or single-field constraints" and "when no project enum exists" so existing patterns remain valid.

## Timeline

Single session (rules-only edit).
